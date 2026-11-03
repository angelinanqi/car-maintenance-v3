"""Bounded HTTP/CONNECT egress proxy; connect only to the checked IP addresses.

The browser keeps its own HTTPS/TLS stack through CONNECT tunnels. The proxy
never handles application credentials or forwards browser proxy-auth headers.
"""
from contextlib import contextmanager
import select
import socket
import socketserver
import threading
import time
from urllib.parse import urlsplit, urlunsplit

from shared.public_web import public_url, resolve_public


class CaptureProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, deadline, max_bytes):
        super().__init__(('127.0.0.1', 0), ProxyHandler)
        self.deadline = deadline
        self.remaining_bytes = max_bytes
        self.budget_lock = threading.Lock()
        self.stopped = threading.Event()
        self.blocked = 0
        self.connections = threading.BoundedSemaphore(32)

    def process_request(self, request, client_address):
        if not self.connections.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.connections.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.connections.release()

    def debit(self, size):
        with self.budget_lock:
            self.remaining_bytes -= size
            return self.remaining_bytes >= 0


class ProxyHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.request.settimeout(10)
        upstream = None
        try:
            if self.server.remaining_bytes <= 0 or time.monotonic() >= self.server.deadline:
                raise ValueError('Capture budget exhausted')
            line = self.rfile.readline(8193)
            if len(line) > 8192:
                raise ValueError('Request line too long')
            method, target, version = line.decode('ascii').strip().split(' ', 2)
            headers, total = [], 0
            while True:
                line = self.rfile.readline(8193)
                total += len(line)
                if not line or total > 32768 or len(line) > 8192:
                    raise ValueError('Invalid headers')
                if line == b'\r\n':
                    break
                headers.append(line)
            url = public_url(('https://' + target + '/') if method == 'CONNECT' else target)
            parts = urlsplit(url)
            port = parts.port or (443 if parts.scheme == 'https' else 80)
            if method != 'CONNECT' and (method not in {'GET', 'HEAD', 'POST', 'OPTIONS'} or parts.scheme != 'http'):
                raise ValueError('Unsupported request')
            last_error = None
            for family, kind, proto, _, address in resolve_public(parts.hostname, port):
                candidate = socket.socket(family, kind, proto)
                try:
                    candidate.settimeout(max(.1, min(8, self.server.deadline - time.monotonic())))
                    candidate.connect(address)
                    upstream = candidate
                    break
                except OSError as error:
                    candidate.close()
                    last_error = error
            if upstream is None:
                raise last_error or OSError('No reachable address')
            if method == 'CONNECT':
                self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
            else:
                path = urlunsplit(('', '', parts.path or '/', parts.query, ''))
                request = f'{method} {path} HTTP/1.1\r\n'.encode()
                # Close plain HTTP after one request. Chromium reconnects through
                # validation instead of reusing this tunnel for another host.
                for header in headers:
                    if header.split(b':', 1)[0].lower() not in {b'connection', b'proxy-connection', b'proxy-authorization'}:
                        request += header
                upstream.sendall(request + b'Connection: close\r\n\r\n')
            sockets = [self.request, upstream]
            # rfile is unbuffered (see setup); POST bytes remain on the socket.
            while time.monotonic() < self.server.deadline and not self.server.stopped.is_set():
                ready, _, _ = select.select(sockets, [], [], .2)
                for source in ready:
                    data = source.recv(65536)
                    if not data or not self.server.debit(len(data)):
                        return
                    destination = upstream if source is self.request else self.request
                    destination.sendall(data)
        except (OSError, ValueError, UnicodeError):
            self.server.blocked += 1
            try:
                self.request.sendall(b'HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            except OSError:
                pass
        finally:
            if upstream is not None:
                upstream.close()

    def setup(self):
        self.rbufsize = 0
        super().setup()


@contextmanager
def capture_proxy(deadline, max_bytes):
    server = CaptureProxy(deadline, max_bytes)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .1}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.stopped.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)

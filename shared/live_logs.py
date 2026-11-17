"""Follow existing local logs and optional Android debug output. No log server."""
import argparse
from collections import OrderedDict
from datetime import datetime
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

from shared.configuration import load_configuration, PROJECT_ROOT
from shared.observability import log_directory, safe_path

OPAQUE_ID = re.compile(r'[a-fA-F0-9-]{32,36}')
SESSION = re.compile(r'(?:guest|auth)-[a-f0-9]{16}')
MOBILE = re.compile(r'\[([^\]]+)\] \[MOBILE\] \[HTTP\] ([A-Z]+) (\S+) (\d{3}|—) \| (\d+)ms \| (SUCCESS|ERROR)(.*)')
PROCESSING = {'document_upload', 'document_received', 'document_queued', 'document_job', 'document_queue_attempt',
              'document_preparation', 'document_index', 'extraction_handoff', 'extraction_packaging',
              'ocr_extraction', 'remote_ocr', 'mineru_task', 'mineru_connection', 'mineru_health_check',
              'mineru_submission', 'mineru_wait', 'mineru_result_download', 'mineru_result_unpack'}
_notices = set()


def notice(message):
    if message not in _notices:
        _notices.add(message)
        print(message, file=sys.stderr)


def text(value, limit=120):
    return ''.join(c for c in str(value) if c.isprintable())[:limit]


def mobile_event(line):
    match = MOBILE.search(line)
    if not match:
        return None
    stamp, method, path, status, duration, outcome, tail = match.groups()
    try:
        when = datetime.fromisoformat(stamp).timestamp()
    except ValueError:
        return None
    fields = dict(re.findall(r'\| ([a-z]+)=([A-Za-z0-9_-]+)', tail))
    return dict(timestamp=stamp, time=when, service='mobile', stage='http_response',
                client_source='MOBILE', method=method, route=safe_path(path),
                status_code=int(status) if status.isdigit() else None, duration_ms=int(duration),
                outcome=outcome, client_session=fields.get('session'), request_id=fields.get('id'),
                destination=fields.get('via'), application_outcome=fields.get('app'),
                error_type=fields.get('error'))


class Tail:
    """Keep old descriptors through rotation; incomplete lines wait for a newline."""
    def __init__(self):
        self.handles = {}

    @staticmethod
    def lines(handle):
        result = []
        while True:
            offset = handle.tell()
            line = handle.readline()
            if not line:
                break
            if not line.endswith(b'\n'):
                handle.seek(offset)
                break
            if len(line) <= 65536:
                result.append(line.decode('utf-8', errors='replace'))
        return result

    def read(self, path, *, initial=False):
        old = self.handles.get(path)
        result = []
        try:
            stat = path.stat()
            if old and old[0] != stat.st_ino:
                result += self.lines(old[1])
                old[1].close()
                old = None
            if old is None:
                handle = path.open('rb')
                offset = max(0, stat.st_size - 256 * 1024) if initial else 0
                if offset:
                    handle.seek(offset - 1)
                    if handle.read(1) != b'\n':
                        handle.readline()
                old = (stat.st_ino, handle)
                self.handles[path] = old
            handle = old[1]
            if handle.tell() > stat.st_size:
                handle.seek(0)
            result += self.lines(handle)
        except OSError:
            if old:
                try:
                    result += self.lines(old[1])
                except OSError:
                    pass
        return result

    def close(self):
        for _, handle in self.handles.values():
            handle.close()


class Viewer:
    def __init__(self, args):
        self.args = args
        self.seen = OrderedDict()
        self.hops = OrderedDict()
        self.states = {}

    def accept(self, event):
        stage = event.get('stage', '')
        level = event.get('level', 'INFO')
        service = event.get('service', '')
        if not all(isinstance(v, str) for v in (stage, level, service)):
            return None
        if stage == 'http_response':
            client = event.get('client_source', 'UNKNOWN')
            client = client if isinstance(client, str) else 'UNKNOWN'
            source = client if client in {'WEB', 'MOBILE'} else 'API'
            status = event.get('status_code')
            status = status if isinstance(status, int) and 100 <= status <= 599 else None
            app_error = event.get('application_outcome') == 'ERROR' or status is None or status >= 400
            level = 'ERROR' if status is None or status >= 500 or app_error and status < 400 else 'WARN' if status >= 400 else 'INFO'
            hop = 'DEVICE' if service == 'mobile' else 'PROXY' if service == 'web' else 'RAG' if service == 'rag' else 'API'
            event = {**event, 'source': source, 'kind': 'HTTP', 'status_code': status,
                     'route': safe_path(event.get('route', '/')), 'level': level, 'hop': hop,
                     'application_outcome': 'ERROR' if app_error else 'SUCCESS',
                     'outcome': 'SUCCESS' if status is not None and status < 400 else 'ERROR'}
        elif stage == 'service':
            key = (service, event.get('pid'))
            state = event.get('state')
            if self.states.get(key) == state:
                return None
            self.states[key] = state
            event = {**event, 'source': 'API', 'kind': 'INFO'}
        elif stage in PROCESSING or stage in {'answer_generation', 'rag_service_call', 'youtube_sync'} or level in {'WARNING', 'ERROR', 'CRITICAL'}:
            event = {**event, 'source': 'OCR' if stage in PROCESSING or '.ocr' in event.get('module', '') else 'API', 'kind': level.replace('WARNING', 'WARN')}
        else:
            return None
        if not self.matches(event):
            return None
        # A file may reappear as a rotation backup. Never replay the same event.
        fingerprint = tuple(str(event.get(k, '')) for k in ('time', 'service', 'pid', 'stage', 'state', 'request_id', 'method', 'route', 'status_code'))
        if fingerprint in self.seen:
            return None
        self.seen[fingerprint] = True
        if len(self.seen) > 10000:
            self.seen.popitem(last=False)
        identity = event.get('request_id', '')
        identity = identity if isinstance(identity, str) else ''
        if stage == 'http_response' and OPAQUE_ID.fullmatch(identity or ''):
            key = (event['source'], identity, event.get('method'), event['route'], event['status_code'], event['application_outcome'])
            old = self.hops.get(key)
            now = time.monotonic()
            if old and now - old[0] < 60 and event['hop'] not in old[1]:
                old[1].add(event['hop'])
                return None
            self.hops[key] = (now, {event['hop']})
            if len(self.hops) > 5000:
                self.hops.popitem(last=False)
        return event

    def matches(self, event):
        selected = {s for s in ('WEB', 'MOBILE', 'API', 'OCR') if getattr(self.args, s.lower())}
        if selected and event['source'] not in selected and not ('API' in selected and event.get('hop') in {'API', 'RAG'}):
            return False
        if self.args.http and event['kind'] != 'HTTP':
            return False
        if self.args.errors and event.get('level') not in {'WARNING', 'WARN', 'ERROR', 'CRITICAL'}:
            return False
        return True

    def render(self, event):
        try:
            stamp = datetime.fromisoformat(event['timestamp']).astimezone().strftime('%H:%M:%S')
        except (KeyError, ValueError, TypeError):
            stamp = '--:--:--'
        prefix = f"[{stamp}] [{event['source']:<6}] [{event['kind']:<5}] "
        if event['kind'] == 'HTTP':
            method = event.get('method')
            method = method if isinstance(method, str) and method in {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'} else 'UNKNOWN'
            duration = event.get('duration_ms')
            duration = round(duration) if isinstance(duration, (int, float)) and math.isfinite(duration) and 0 <= duration < 1e9 else '?'
            detail = f"{method} {event['route']} {event['status_code'] or '—'} | {duration}ms | {event['outcome']} | observed={event['hop']}"
            if event.get('client_source') in {'INTERNAL', 'UNKNOWN'}:
                detail += ' | client=' + event['client_source']
            destination = event.get('destination')
            if destination in {'API', 'SUPABASE', 'EXTERNAL'}:
                detail += ' | via=' + destination
            if event.get('backend_response') == 'NOT_OBSERVED':
                detail += ' | backend=NO_RESPONSE_OBSERVED'
            if event.get('application_outcome') == 'ERROR' and event['outcome'] == 'SUCCESS':
                detail += ' | application=ERROR'
            error = event.get('error_type', '')
            if isinstance(error, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,60}', error):
                detail += ' | error=' + error
            if event['source'] == 'WEB':
                names = {'documents': 'Documents', 'guides': 'Learning guides', 'knowledge': 'Knowledge base',
                         'chat': 'Chat', 'accounts': 'Account', 'emergency': 'Emergency content'}
                name = next((names[p] for p in event['route'].split('/') if p in names), 'API')
                detail += ' | ' + name + (' loaded' if method == 'GET' and event['outcome'] == 'SUCCESS'
                                         else ' request completed' if event['outcome'] == 'SUCCESS' else ' request failed')
            session = event.get('client_session', '')
            if isinstance(session, str) and SESSION.fullmatch(session):
                detail += ' | session=' + session
        else:
            stage = re.sub(r'[^a-zA-Z0-9_]', '', str(event.get('stage', 'event')))[:60]
            state = re.sub(r'[^a-zA-Z0-9_]', '', str(event.get('state', '')))[:30]
            detail = stage.replace('_', ' ') + ': ' + state
            module = event.get('module', '')
            location = event.get('source', '')
            if stage == 'diagnostic' and isinstance(module, str) and re.fullmatch(r'[A-Za-z0-9_.]{1,100}', module):
                detail += ' | ' + module
            if isinstance(location, str) and re.fullmatch(r'[A-Za-z0-9_.-]+:\d+', location):
                detail += ' | ' + location
            error = event.get('error_type')
            if isinstance(error, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,60}', error):
                detail += ' | ' + error
            # Diagnostic code locations only; never original exception messages.
            frames = event.get('frames')
            if isinstance(frames, list) and frames and isinstance(frames[-1], str) and re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:py|m?js|dart):\d+(?::[A-Za-z0-9_<>.]+)?', frames[-1]):
                detail += ' | ' + frames[-1]
        identity = event.get('request_id', '')
        if isinstance(identity, str) and OPAQUE_ID.fullmatch(identity):
            detail += ' | id=' + identity
        job = event.get('job_id', '')
        if isinstance(job, str) and OPAQUE_ID.fullmatch(job):
            detail += ' | job=' + job
        value = prefix + detail
        colour = self.args.colour == 'always' or self.args.colour == 'auto' and sys.stdout.isatty() and 'NO_COLOR' not in os.environ
        if colour:
            code = '31' if event.get('level') in {'ERROR', 'CRITICAL'} else '33' if event.get('level') in {'WARN', 'WARNING'} else '32' if event.get('state') == 'completed' else '36' if event['kind'] != 'HTTP' else '0'
            value = f'\033[{code}m{value}\033[0m'
        return value


def android_bridge(args, output, stop):
    adb = shutil.which(args.adb)
    if not adb:
        notice('Device-only mobile logs: adb unavailable. Backend-observed MOBILE traffic is still shown.')
        return
    process = None
    try:
        devices = subprocess.run([adb, 'devices'], capture_output=True, text=True, timeout=5, check=True)
        available = [line.split()[0] for line in devices.stdout.splitlines()[1:] if len(line.split()) == 2 and line.split()[1] == 'device']
        device = args.device or (available[0] if len(available) == 1 else None)
        if not device or device not in available:
            notice('Device-only mobile logs: connect/authorise one Android device, or select it with --device. Backend logs remain available.')
            return
        if stop.is_set():
            return
        process = subprocess.Popen([adb, '-s', device, 'logcat', '-v', 'raw', '-T', '50', '-s', 'flutter:I'],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        def read():
            try:
                for line in process.stdout:
                    event = mobile_event(line)
                    if event:
                        try:
                            output.put_nowait(event)
                        except queue.Full:
                            pass
            except (OSError, ValueError):
                pass
        threading.Thread(target=read, daemon=True).start()
        while not stop.wait(.25) and process.poll() is None:
            pass
    except (OSError, subprocess.SubprocessError):
        notice('Device log bridge unavailable; local/backend logs remain available.')
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            process.stdout.close()


def bridge_loop(args, output, stop):
    while not stop.is_set():
        android_bridge(args, output, stop)
        stop.wait(5)


def main():
    load_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('web', 'mobile', 'api', 'ocr', 'http', 'errors'):
        parser.add_argument('--' + flag, action='store_true')
    parser.add_argument('--lines', type=int, default=30, help='Recent matching entries (0–200)')
    parser.add_argument('--once', action='store_true', help='Print recent entries and exit')
    parser.add_argument('--colour', '--color', choices=('auto', 'always', 'never'), default='auto')
    parser.add_argument('--device', help='Optional adb device serial; otherwise use one authorised device')
    parser.add_argument('--adb', default='adb', help='adb executable or full path')
    parser.add_argument('--no-device', action='store_true', help='Do not read Android debug output')
    parser.add_argument('--log-dir', type=Path, default=PROJECT_ROOT / 'output/logs')
    parser.add_argument('--monitor-dir', type=Path, default=log_directory())
    args = parser.parse_args()
    if not 0 <= args.lines <= 200:
        parser.error('--lines must be between 0 and 200')
    def interrupt(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, interrupt)
    reader, viewer = Tail(), Viewer(args)
    messages = queue.Queue(maxsize=1000)
    stop = threading.Event()
    bridge = None
    if not args.once and not args.no_device and (args.mobile or not any((args.web, args.api, args.ocr))):
        bridge = threading.Thread(target=bridge_loop, args=(args, messages, stop), daemon=True)
        bridge.start()
    initial = True
    try:
        while True:
            # Backups provide startup history only. The open current descriptor
            # already drains rotations; rediscovering backups would replay them.
            paths = list(args.monitor_dir.glob('*.jsonl*' if initial else '*.jsonl'))
            paths += list(args.log_dir.glob('web-live.jsonl*' if initial else 'web-live.jsonl'))
            paths += [args.log_dir / 'mobile.log']
            events = []
            for path in sorted(set(paths)):
                for line in reader.read(path, initial=initial):
                    try:
                        event = mobile_event(line) if path.name == 'mobile.log' else json.loads(line)
                        if isinstance(event, dict):
                            events.append(event)
                    except (ValueError, TypeError):
                        pass
            while not messages.empty():
                try:
                    events.append(messages.get_nowait())
                except queue.Empty:
                    break
            events.sort(key=lambda e: e.get('time') if isinstance(e.get('time'), (int, float)) else 0)
            accepted = [value for event in events if (value := viewer.accept(event)) is not None]
            for event in accepted[-args.lines:] if initial and args.lines else [] if initial else accepted:
                print(viewer.render(event), flush=True)
            if args.once:
                return
            if initial:
                print('Following logs. Ctrl+C stops only this viewer. Missing sources are picked up when available.', file=sys.stderr)
            initial = False
            stop.wait(.25)
    except (KeyboardInterrupt, BrokenPipeError):
        pass
    finally:
        stop.set()
        if bridge:
            bridge.join(timeout=3)
        reader.close()


if __name__ == '__main__':
    main()

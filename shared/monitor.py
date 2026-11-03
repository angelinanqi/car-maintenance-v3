"""Read local telemetry and probe MinerU. Run: python -m shared.monitor."""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from shared.configuration import load_configuration
from shared.observability import log_directory


class Monitor:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.positions = {}
        self.processes = {}
        self.recent = deque(maxlen=100)
        self.finished = deque(maxlen=50)
        self.dependencies = {}
        self.remote = {'state': 'unknown', 'detail': 'not configured'}

    def poll(self):
        for path in self.directory.glob('*.jsonl'):
            try:
                stat = path.stat()
                if stat.st_mtime < time.time() - 86400:
                    continue
                old_inode, offset = self.positions.get(path, (None, 0))
                if old_inode != stat.st_ino or offset > stat.st_size:
                    offset = max(0, stat.st_size - 256 * 1024)
                with path.open('rb') as handle:
                    handle.seek(offset)
                    if offset and path not in self.positions:
                        handle.readline()  # Initial tail may begin in a partial record.
                    while line := handle.readline():
                        if not line.endswith(b'\n'):
                            handle.seek(-len(line), 1)
                            break
                        try:
                            self.accept(json.loads(line))
                        except (ValueError, KeyError, TypeError):
                            pass
                    self.positions[path] = (stat.st_ino, handle.tell())
            except OSError:
                continue

    def accept(self, event):
        key = (event['service'], event['machine'], event['pid'])
        process = self.processes.setdefault(key, {'operations': {}, 'seen': 0, 'state': 'unknown'})
        if event['stage'] == 'service':
            process['seen'] = event['time']
            process['state'] = event['state']
            if event['state'] in {'starting', 'stopped'}:
                process['operations'].clear()
            if 'operations' in event:
                process['operations'] = {op['span_id']: op for op in event['operations']}
        identity = event.get('span_id')
        if event['state'] == 'started' and identity:
            process['operations'][identity] = dict(event, started=event['time'])
        elif event['state'] in {'completed', 'failed', 'cancelled', 'deferred'} and identity and 'duration_ms' in event:
            process['operations'].pop(identity, None)
            if 'duration_ms' in event:
                self.finished.append(event)
        if event['stage'].startswith(('database_', 'vector_')) and event['state'] in {'completed', 'failed'}:
            self.dependencies[event['stage'].split('_')[0]] = event
        if event['stage'] != 'service':
            self.recent.append(event)

    def probe_remote(self, url):
        if not url:
            return
        host = urlsplit(url).hostname
        started = time.monotonic()
        try:
            with urlopen(url.rstrip('/') + '/health', timeout=2) as response:
                data = json.loads(response.read(65536))
            compatible = data.get('version') == '3.4.5' and data.get('protocol_version') == 2
            self.remote = dict(state='available' if compatible else 'failed', host=host,
                               detail='task protocol ready' if compatible else 'incompatible health response',
                               latency_ms=round((time.monotonic() - started) * 1000), checked=time.time())
        except Exception as error:
            self.remote = dict(state='disconnected', host=host, detail=type(error).__name__, checked=time.time())

    def snapshot(self):
        now = time.time()
        services, active = [], []
        for (service, machine, pid), process in self.processes.items():
            age = now - process['seen']
            state = process['state']
            if state != 'stopped':
                state = 'unknown' if not process['seen'] else 'disconnected' if age > 16 else 'starting' if state == 'starting' else 'busy' if process['operations'] else 'running'
            services.append(dict(service=service, machine=machine, pid=pid, state=state, age_s=round(age, 1)))
            if state in {'running', 'busy', 'starting'}:
                for op in process['operations'].values():
                    active.append(dict(op, service=service, elapsed_s=round(now - op['started'], 1)))
        dependencies = {name: dict(state='unknown' if now - event['time'] > 60 else 'failed' if event['state'] == 'failed' else 'last operation succeeded',
                                   age_s=round(now - event['time'], 1)) for name, event in self.dependencies.items()}
        remote = dict(self.remote)
        if remote['state'] == 'available' and any(op['stage'] == 'remote_ocr' for op in active):
            remote['state'] = 'busy'
        return dict(services=services, remote_ocr=remote, dependencies=dependencies,
                    active=active, finished=list(self.finished)[-12:], recent=list(self.recent)[-15:])


def safe(value):
    # Strip control sequences before rendering hostnames, IDs or messages in a terminal.
    return ''.join(c for c in str(value) if c.isprintable())[:180]


def render(snapshot):
    lines = ['BACKEND MONITOR  |  Ctrl+C to exit', 'Service states use 5s heartbeats; stale after 16s.', '']
    for service in snapshot['services']:
        lines.append(f"{safe(service['service']):18} {safe(service['state']):13} {safe(service['machine'])} pid={service['pid']}")
    if not snapshot['services']:
        lines.append('Local services: UNKNOWN — no telemetry yet; start the application.')
    remote = snapshot['remote_ocr']
    lines.append(f"MinerU OCR         {safe(remote['state']):13} {safe(remote.get('host', ''))} {safe(remote.get('detail', ''))}")
    for name in ('database', 'vector'):
        evidence = snapshot['dependencies'].get(name, {'state': 'unknown', 'age_s': '-'})
        lines.append(f"{name:18} {evidence['state']} (observation age {evidence['age_s']}s)")
    lines += ['', 'ACTIVE STAGES (nested stages share a request or document ID)']
    for op in sorted(snapshot['active'], key=lambda row: row['started'])[-20:]:
        identity = op.get('job_id') or op.get('request_id') or op['span_id']
        lines.append(f"{safe(identity)[:36]} | {safe(op['stage']):28} {op['elapsed_s']:7.1f}s")
    lines += ['', 'RECENT STAGE RESULTS']
    for event in snapshot['finished'][-8:]:
        lines.append(f"{safe(event['stage']):28} {event['state']:10} {event.get('duration_ms', 0):9.1f}ms {safe(event.get('error_type', ''))}")
    lines += ['', 'RECENT EVENTS']
    for event in snapshot['recent']:
        identity = event.get('job_id') or event.get('request_id') or ''
        lines.append(f"{event['timestamp'][11:19]}Z {safe(event['level']):7} {safe(event['service']):12} {safe(event['message'])} {safe(event.get('worker_host', ''))} {safe(event.get('worker_task_id', ''))} {safe(identity)} {safe(event.get('error_type', ''))}")
    return '\n'.join(lines)


def main():
    load_configuration()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Print one snapshot and exit')
    parser.add_argument('--json', action='store_true', help='Emit JSON snapshots (also useful with --once)')
    parser.add_argument('--interval', type=float, default=2)
    args = parser.parse_args()
    if not 0.2 <= args.interval <= 60:
        parser.error('--interval must be between 0.2 and 60 seconds')
    monitor = Monitor(log_directory())
    url = os.getenv('MINERU_API_URL', '').strip()
    if os.getenv('MONITOR_ENABLED', '1').lower() in {'0', 'false', 'off'}:
        print('Monitoring is disabled (MONITOR_ENABLED=0); existing files are historical.', file=sys.stderr)
        return
    stop = threading.Event()
    def probe():
        while not stop.is_set():
            monitor.probe_remote(url)
            stop.wait(5)
    if args.once:
        monitor.probe_remote(url)
    else:
        threading.Thread(target=probe, daemon=True).start()
    try:
        while True:
            monitor.poll()
            snapshot = monitor.snapshot()
            if sys.stdout.isatty() and not args.json:
                print('\033[2J\033[H', end='')
            print(json.dumps(snapshot) if args.json else render(snapshot), flush=True)
            if args.once:
                break
            stop.wait(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()


if __name__ == '__main__':
    main()

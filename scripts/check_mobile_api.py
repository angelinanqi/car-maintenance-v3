"""Read-only public mobile API check and fixture capture for Flutter model tests."""
import argparse
import json
from pathlib import Path
from time import monotonic

import httpx


def capture(base_url, output):
    fixture = {}
    with httpx.Client(base_url=base_url.rstrip('/'), timeout=30) as client:
        for path in ('/health', '/config', '/mobile/chat-starters', '/mobile/vehicle-catalogue',
                     '/mobile/maintenance-items', '/guides', '/categories', '/manuals',
                     '/emergency/contacts', '/emergency/playbooks'):
            started = monotonic()
            paginated = path not in {'/health', '/config', '/mobile/chat-starters'}
            rows, ids = [], set()
            while True:
                response = client.get(path, params={'offset': len(rows), 'limit': 100} if paginated else None)
                response.raise_for_status()
                data = response.json()
                if not paginated:
                    if not isinstance(data, dict):
                        raise ValueError(f'{path}: expected an object')
                    fixture[path] = data
                    break
                if not isinstance(data, list):
                    raise ValueError(f'{path}: expected a list')
                for row in data:
                    if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] in ids:
                        raise ValueError(f'{path}: invalid or repeating record')
                    ids.add(row['id'])
                rows.extend(data)
                if len(data) < 100:
                    fixture[path] = rows
                    break
                if monotonic() - started > 60:
                    raise TimeoutError(f'{path}: pagination did not complete')
            count = len(fixture[path]) if paginated else 'object'
            print(f'{path}: 200, {count}, {monotonic() - started:.2f}s')
        fixture['manuals_by_scope'] = {}
        for scope in fixture['/config']['vehicle_scopes']:
            response = client.get('/manuals', params={'car_model': scope['value'], 'limit': 1000})
            response.raise_for_status()
            fixture['manuals_by_scope'][scope['value']] = response.json()
        print('Vehicle-specific manual listings: '
              + ', '.join(f'{key}={len(rows)}' for key, rows in fixture['manuals_by_scope'].items()))
        for path in ('/mobile/me', '/accounts/me'):
            response = client.get(path)
            if response.status_code != 401:
                raise ValueError(f'{path}: expected guest access to be denied, got {response.status_code}')
            print(f'{path}: 401 as expected')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Public response fixture: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', type=Path, default=Path('output/mobile-audit/live-api.json'))
    args = parser.parse_args()
    capture(args.base_url, args.output)

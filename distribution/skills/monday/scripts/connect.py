"""Local credential form and identity/destination checks. Setup never uploads clips."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from delivery_ledger import atomic_json
from monday_client import CFG, MondayClient
from frameio_client import FrameClient
from deliver import verify_route, token

FIELDS = ('MONDAY_TOKEN', 'FRAME_CLIENT_ID', 'FRAME_CLIENT_SECRET')
FILES = ('monday.json', 'frameio/credentials.json', 'frameio/token.json', 'routes.json')


def save_credentials(root, values):
    if not isinstance(values, dict) or set(values) - set(FIELDS):
        raise ValueError('Unexpected credential field')
    if any(not isinstance(v, str) or len(v) > 4096 or any(c.isspace() for c in v.strip()) for v in values.values()):
        raise ValueError('Paste only the requested values')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    frame = root / 'frameio'; frame.mkdir(exist_ok=True, mode=0o700)
    if frame.is_symlink() or any((root / name).is_symlink() for name in FILES):
        raise ValueError('Linked credential files preserved')
    fd = os.open(root / 'credentials.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        monday_file, frame_file = root / 'monday.json', frame / 'credentials.json'
        monday = json.loads(monday_file.read_text()) if monday_file.exists() else {}
        adobe = json.loads(frame_file.read_text()) if frame_file.exists() else {}
        if not isinstance(monday, dict) or not isinstance(adobe, dict):
            raise ValueError('Existing configuration needs repair')
        updated = dict(adobe)
        if values.get('MONDAY_TOKEN', '').strip(): monday['token'] = values['MONDAY_TOKEN'].strip()
        if values.get('FRAME_CLIENT_ID', '').strip(): updated['client_id'] = values['FRAME_CLIENT_ID'].strip()
        if values.get('FRAME_CLIENT_SECRET', '').strip(): updated['client_secret'] = values['FRAME_CLIENT_SECRET'].strip()
        if not all(isinstance(v, str) and v.strip() for v in (monday.get('token'), updated.get('client_id'), updated.get('client_secret'))):
            raise ValueError('Monday token and Adobe app credentials are required')
        if updated.get('client_id') != adobe.get('client_id') and not values.get('FRAME_CLIENT_SECRET', '').strip():
            raise ValueError('A different Adobe client ID requires its client secret')
        if updated != adobe and (frame / 'token.json').exists():
            # Preserve the previous login, but require login to the newly selected app.
            (frame / 'token.json').rename(frame / ('token.previous-' + str(time.time_ns()) + '.json'))
        atomic_json(monday_file, monday)
        atomic_json(frame_file, updated)


def configuration_hash(root):
    digest = hashlib.sha256()
    for name in FILES:
        digest.update(name.encode()); digest.update((root / name).read_bytes())
    return digest.hexdigest()


def readiness(root=CFG):
    missing = [name for name in FILES if not (root / name).is_file()]
    result = {'ready': False, 'status': 'delivery-pending', 'missing': missing,
              'next': 'Follow the monday onboarding guide: connect accounts, choose destinations, then run acq-edit onboard delivery.'}
    if missing: return result
    try:
        receipt = json.loads((root / 'connection-check.json').read_text())
        if (receipt.get('ready') and receipt.get('configurationSha256') == configuration_hash(root)
                and 0 <= time.time() - receipt['checkedAt'] < 86400):
            return {**result, 'ready': True, 'status': 'delivery-read-verified', 'next': None,
                    'routes': receipt['routes'], 'qualification': receipt['qualification']}
    except (OSError, ValueError, KeyError, TypeError): pass
    return result


def check(root=CFG, frame_factory=FrameClient, monday_factory=MondayClient):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = {'ready': False, 'status': 'delivery-pending', 'checkedAt': time.time(), 'routes': [],
              'qualification': 'Identity and destination reads only; upload permission and successful delivery are not proven.'}
    step = 'credentials'
    try:
        stable_files = ('monday.json', 'frameio/credentials.json', 'routes.json')
        before = {name: (root/name).read_bytes() if (root/name).is_file() else None for name in stable_files}
        fc, mc = frame_factory(), monday_factory()
        step = 'Frame sign-in'; fc.get('/v4/me')['data']
        step = 'Monday connection'; mc.gql('{me {id name account {id name}}}')['me']
        step = 'saved destinations'
        config = json.loads((root / 'routes.json').read_text())
        token(config['editor'])
        if not isinstance(config.get('brands'), dict) or not config['brands']:
            raise ValueError('No brand routes')
        route_hash = hashlib.sha256((root / 'routes.json').read_bytes()).hexdigest()
        for brand, profile in config['brands'].items():
            token(brand); token(profile['code'])
            if not isinstance(profile.get('routes'), dict) or not profile['routes']:
                raise ValueError('No destination for a selected brand')
            for format_name, route in profile['routes'].items():
                token(format_name); token(route['content_code'])
                verify_route(fc, mc, route)
                result['routes'].append({'brand': brand, 'format': format_name,
                                        'frameFolder': route['frame']['folder_name'], 'mondayBoard': route['monday']['board_name']})
        if route_hash != hashlib.sha256((root / 'routes.json').read_bytes()).hexdigest():
            raise ValueError('Destinations changed during verification')
        if any(before[name] != (root/name).read_bytes() for name in stable_files):
            raise ValueError('Account or destinations changed during verification')
        result.update(ready=True, status='delivery-read-verified', configurationSha256=configuration_hash(root))
    except Exception:
        # Provider bodies, token values and raw exception strings are never logged.
        result.update(failedStep=step, repair='Reconnect or repair this step using the monday onboarding guide, then rerun acq-edit onboard delivery.')
    atomic_json(root / 'connection-check.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['credentials', 'check', 'status'])
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    if args.action == 'credentials':
        sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
        from credentials import form_page, run_browser
        page = form_page('Connect clip delivery', 'Get the shared Adobe client ID and secret from Maddex; no new Adobe app is needed. Use your own Monday token. After saving, sign into your own Adobe / Frame account. These values stay on this Mac.', [
            ('MONDAY_TOKEN', 'Monday personal API token', 'In Monday: profile → Developers → API token.', 'https://developer.monday.com/api-reference/docs/authentication'),
            ('FRAME_CLIENT_ID', 'Frame / Adobe client ID', 'Get this from Maddex. Do not create an Adobe app.', None),
            ('FRAME_CLIENT_SECRET', 'Frame / Adobe client secret', 'Get this from Maddex with the client ID. You will sign into your own Adobe account next.', None),
        ])
        run_browser(CFG, page, save_credentials, args.no_open)
        print('Delivery credentials saved. Next: acq-edit delivery login, choose destinations, then acq-edit onboard delivery.')
    else:
        result = readiness() if args.action == 'status' else check()
        print(json.dumps(result, indent=2))
        if not result['ready']: sys.exit(2)


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyboardInterrupt):
        print('Delivery setup needs attention. Reopen the local form or follow the monday onboarding guide; credential values were not printed.', file=sys.stderr)
        sys.exit(1)

"""Project-local provenance around the existing read-only editorial brain owner."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from common import SKILLS, inside, read, require, save, sha


def owner():
    folder = SKILLS / 'find-precedents/scripts'
    require((folder / 'editorial_context.py').is_file(), 'Install the packaged find-precedents runtime first')
    sys.path.insert(0, str(folder))
    spec = importlib.util.spec_from_file_location('_acq_editorial_context_owner', folder / 'editorial_context.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def versions(context):
    return {
        'playbooks': [{key: row[key] for key in ['format', 'version', 'body_sha256']} for row in context['playbooks']],
        'requiredReading': [{key: row[key] for key in ['policy_id', 'format', 'version']} |
                            {'documents': [{key: doc[key] for key in ['source_id', 'source_sha256']} for doc in row['documents']]}
                            for row in context['required_reading']['policies']],
        'cards': [{key: row[key] for key in ['card_id', 'revision', 'status', 'evidence_class']} for row in context['cards']],
        'scopedPolicies': [{key: row[key] for key in ['policy_id', 'version', 'brand', 'production_type', 'stage', 'source_sha256']}
                           for row in context.get('scoped_policy', {}).get('policies', [])],
        'scopedStatus': context.get('scoped_policy', {}).get('status', 'not-requested'),
    }


def verify_saved(path):
    """Offline integrity: never refresh a saved design or claim the agent read it."""
    context = read(path)
    require(context.get('schema') == 'editorial-brain.context/v1', 'A real editorial brain context receipt is required')
    receipt = context.get('client_receipt', {})
    require(receipt.get('schema') == 'editorial-brain.fetch-receipt/v1', 'Brain retrieval receipt is missing')
    require(response_hash({k: v for k, v in context.items() if k != 'client_receipt'}) == receipt.get('response_sha256'), 'Saved brain response hash differs')
    require(datetime.fromisoformat(receipt['fetched_at']).tzinfo is not None, 'Brain fetch timestamp must include its timezone')
    require(isinstance(context.get('project_ref'), str) and context['project_ref'], 'Brain project identity is missing')
    query = context['query']; reader = owner()
    require(query['format'] in reader.FORMATS and query.get('includeRequiredReading') is True, 'New editorial design requires complete format-specific reading')
    books = context['playbooks']
    require(len(books) == 2 and {b['format'] for b in books} == {'universal', query['format']}, 'Required playbooks missing')
    for row in books:
        require(type(row['version']) is int and row['version'] > 0, 'Invalid playbook version')
        require(hashlib.sha256(row['body'].encode()).hexdigest() == row['body_sha256'], 'Playbook content hash differs')
    reader.validate_required_reading(context, query['format'], query.get('readingOverlays', []))
    reader.validate_cards(context['cards'], query['format'], query.get('includeDevelopment', False),
                          [x for x in [query.get('currentProjectPrefix'), *query.get('heldOutSourcePrefixes', [])] if x])
    # The owner deliberately treats unavailable scoped guidance as additive; preserve that boundary.
    scoped = context.get('scoped_policy')
    if scoped and scoped.get('status') != 'unavailable':
        reader.validate_scoped_policies(scoped, {'brand': query.get('brand'), 'production_type': query.get('productionType'), 'stage': query.get('stage')})
    return {'receiptPath': str(Path(path).resolve()), 'sha256': sha(path), 'fetchedAt': receipt['fetched_at'],
            'responseSha256': receipt['response_sha256'], 'versions': versions(context),
            'qualification': 'retrieved content integrity; not reading, application or human approval'}


@contextmanager
def configured_reader(config):
    require(config.get('brainConfig'), 'Configure the teammate editorial-brain directory explicitly; no global fallback')
    folder = Path(config['brainConfig']).expanduser().resolve()
    stored = read(folder / 'context.json')
    require(stored.get('function_url') and stored.get('project_ref'), 'Editorial-brain URL/project configuration missing')
    values = {'EDITORIAL_BRAIN_CONFIG_DIR': str(folder), 'EDITORIAL_BRAIN_FUNCTION_URL': stored['function_url'],
              'EDITORIAL_BRAIN_PROJECT_REF': stored['project_ref']}
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value


def check_configuration(config):
    """Local-only readiness. Never fetch guidance or return credential values."""
    try:
        with configured_reader(config):
            endpoint, key, project = owner().configuration()
            from urllib.parse import urlsplit
            url = urlsplit(endpoint)
            require(key.strip() and project.strip(), 'missing')
            require(url.scheme == 'https' and url.hostname and
                    url.hostname == project + '.supabase.co' and
                    url.path in {'/functions/v1/editorial-search', '/functions/v1/vibe-editorial-read'} and url.port in {None,443} and
                    not url.username and not url.password and not url.query and not url.fragment, 'invalid')
    except Exception:
        # Parse/filesystem exceptions can contain private configuration contents.
        return {'ready': False, 'remoteAccess': 'not-checked',
                'repair': 'Configure brainConfig with context.json for the matching editorial-search endpoint/project and a restricted read token. Check token ownership and mode 0600; no global fallback is used.'}
    return {'ready': True, 'remoteAccess': 'not-checked',
            'qualification': 'Local configuration only; token validity, restricted scope and live guidance retrieval are not verified.'}


def fetch(project, config, request):
    allowed = {'format', 'problem', 'output', 'projectPrefix', 'heldOut', 'readingOverlays', 'brand', 'productionType', 'stage'}
    require(set(request) <= allowed, 'Unknown brain request field; this command only retrieves guidance')
    require(isinstance(request.get('format'), str) and isinstance(request.get('problem'), str), 'Specify the content-unit format and editorial problem')
    target = inside(Path(project['root']) / '10_WORK', request['output'])
    require(target != (Path(project['root']) / '10_WORK').resolve(), 'Use a new guidance directory')
    require(not target.exists(), 'Guidance destination exists; preserve it and use a new request directory')
    reader = owner()
    # Validate configuration before making a reservation; credentials never enter artifacts.
    with configured_reader(config):
        target.mkdir(parents=True, mode=0o700)
        save(target / 'request.json', {'projectId': project['id'], 'request': request})
        try:
            result = reader.fetch_context(problem=request['problem'], fmt=request['format'],
                                          project_prefix=request.get('projectPrefix'), held_out=request.get('heldOut', []),
                                          required_reading=True, reading_overlays=request.get('readingOverlays', []),
                                          brand=request.get('brand'), production_type=request.get('productionType'), stage=request.get('stage'))
            context_path = target / 'context.json'
            reader.save_context(result, context_path)
            summary = verify_saved(context_path)
            save(target / 'versions.json', {'schema': 'acq-edit/brain-versions-v1', 'projectId': project['id'], **summary})
            for path in target.iterdir():
                if path.is_file(): path.chmod(0o400)
            return {**summary, 'versionsPath': str(target / 'versions.json'), 'versionsSha256': sha(target / 'versions.json')}
        except Exception as error:
            save(target / 'failure.json', {'status': 'unavailable', 'errorType': type(error).__name__,
                                          'action': 'Preserve this attempt. New design has no cached-guidance fallback.'})
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--project'); parser.add_argument('--config', required=True); parser.add_argument('--request')
    parser.add_argument('--check-config', action='store_true')
    args = parser.parse_args()
    if args.check_config:
        try: checked = check_configuration(read(args.config))
        except Exception: checked = {'ready': False, 'remoteAccess': 'not-checked', 'repair': 'Run setup with a readable toolkit configuration.'}
        print(json.dumps(checked)); sys.exit(0)
    if not args.project or not args.request: parser.error('--project and --request are required for retrieval')
    try:
        project = read(args.project); request = read(inside(project['root'], args.request))
        print(json.dumps(fetch(project, read(args.config), request), indent=2))
    except Exception as error:
        print(json.dumps({'status': 'brain-unavailable', 'error': str(error)}), file=sys.stderr)
        sys.exit(1)

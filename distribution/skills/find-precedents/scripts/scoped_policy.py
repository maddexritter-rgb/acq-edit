"""Brand policy selection and integrity checks, independent of editorial quality."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

STAGES = ('orchestration', 'assembly', 'reframe', 'audio', 'captions', 'delivery', 'publishing')
_SLUG = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')


def validate_scope(brand=None, production_type=None, stage=None):
    if brand is None and production_type is None and stage is None:
        return None
    if not all(isinstance(v, str) and _SLUG.fullmatch(v) for v in (brand, production_type)):
        raise ValueError('brand and production_type must be provided together as lowercase slugs')
    if stage is not None and stage not in STAGES:
        raise ValueError('unsupported policy stage')
    return {'brand': brand, 'production_type': production_type, 'stage': stage}


def validate_scoped_policies(value, scope):
    policies = value.get('policies') if isinstance(value, dict) else None
    if not isinstance(policies, list) or len(policies) > len(STAGES):
        raise ValueError('invalid scoped policy list')
    seen = set()
    total = 0
    for row in policies:
        if not isinstance(row, dict) or row.get('brand') != scope['brand'] or \
                row.get('production_type') != scope['production_type'] or \
                row.get('stage') not in STAGES or row['stage'] in seen or \
                (scope['stage'] is not None and row['stage'] != scope['stage']):
            raise ValueError('policy scope mismatch or duplicate stage')
        seen.add(row['stage'])
        for field in ('policy_id', 'source_id', 'original_source_id', 'source_title',
                      'source_body', 'source_sha256', 'priority_note', 'evidence_class', 'verification_note'):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError('scoped policy is missing identity or provenance')
        if type(row.get('version')) is not int or row['version'] < 1 or not isinstance(row.get('settings'), dict):
            raise ValueError('invalid policy version or settings')
        body = row['source_body'].encode('utf-8')
        total += len(body)
        if total > 128_000 or hashlib.sha256(body).hexdigest() != row['source_sha256']:
            raise ValueError('scoped policy body hash or size mismatch')
    return policies


def load_brand_profile(brand, *, root=None):
    """A brand-folder pointer is discovery data, never an offline brain substitute."""
    if not isinstance(brand, str) or not _SLUG.fullmatch(brand):
        raise ValueError('invalid brand slug')
    base = Path(root or os.environ.get('ACQ_EDIT_PROJECTS_ROOT', str(Path.home() / 'Movies' / 'ACQ Edit')))
    path = base / brand / '_brand' / 'editorial_profile.json'
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema') != 'edit.brand-editorial-profile/v1' or data.get('brand') != brand:
        raise ValueError('brand profile identity mismatch')
    return data


def select_stage(context, *, brand, production_type, stage):
    """Read a stage from the same validated run receipt without a second fetch."""
    scope = validate_scope(brand, production_type, None)
    policies = validate_scoped_policies(context.get('scoped_policy'), scope)
    if stage not in STAGES:
        raise ValueError('unsupported policy stage')
    return next((p for p in policies if p['stage'] == stage), None)


def camera_exclusion_matches(exclusions, *, session_id, camera_id, media, source_ticks):
    """Find source-scoped overlap; does not delete media or choose a replacement."""
    a, z = map(int, source_ticks)
    if a >= z:
        raise ValueError('source interval must be nonempty and half-open')
    resolved_media = str(Path(media).resolve())
    matches = []
    for entry in exclusions:
        if entry.get('session_id') != session_id or entry.get('camera_id') != camera_id:
            continue
        if str(Path(entry['media']).resolve()) != resolved_media:
            continue
        bounds = entry.get('source_ticks')
        if bounds is None or max(a, int(bounds[0])) < min(z, int(bounds[1])):
            if not entry.get('reason'):
                raise ValueError('exclusions need the actual review reason')
            matches.append(entry)
    return matches

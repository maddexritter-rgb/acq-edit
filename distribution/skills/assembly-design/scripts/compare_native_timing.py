#!/usr/bin/env python3
"""Compare native track snapshots, allowing only whole-group timeline translation.

Inputs contain tracks: [[{id, media_path, start, end, inPoint, outPoint,
links, speed, nested, offline}, ...], ...]. Tick values must be integer strings
or integers. An optional map contains groups: [{id, items: [{track, before,
after}, ...]}]. Mapped groups can be protected clips after a batch reorder.
This is geometry/link evidence, not listening or an editorial judgment.
"""
import argparse
import hashlib
import json
from pathlib import Path


def audit_picture(snapshot, frame_ticks, groups):
    """Check final picture coverage and linked-source clocks, not just plan equality.

    groups is an explicit complete partition of video node IDs, one per content
    unit. Gaps between units are intentional review spacing. Source in/out may use
    a different clock from the sequence; only picture timeline edges use its grid.
    This does not assess sound, motion, lip sync perceptually, or source handles.
    """
    frame_ticks = tick(frame_ticks)
    if frame_ticks <= 0:
        raise ValueError('positive exact sequence frame ticks required')
    videos, audios = snapshot['tracks']
    by_video = {c['id']: c for c in videos}
    by_audio = {c['id']: c for c in audios}
    if len(by_video) != len(videos) or len(by_audio) != len(audios):
        raise ValueError('duplicate native identities')
    seen, issues, audio_warnings = set(), [], []
    for group in groups:
        ids = group['video_ids']
        if not ids or any(i in seen or i not in by_video for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('groups must partition actual video identities')
        seen.update(ids)
        clips = [by_video[i] for i in ids]
        if clips != sorted(clips, key=lambda c: tick(c['start'])):
            raise ValueError('group must be in current playback order')
        for c in clips:
            def issue(code, **extra):
                issues.append({'group': group['id'], 'node_id': c['id'], 'code': code, **extra})
            if c.get('speed') != 1 or c.get('nested') or c.get('offline'):
                issue('UNSUPPORTED_PICTURE_STATE')
            for field in ('start', 'end'):
                if tick(c[field]) % frame_ticks:
                    issue('PICTURE_OFF_SEQUENCE_GRID', field=field, ticks=c[field])
            if tick(c['end']) <= tick(c['start']):
                issue('NONPOSITIVE_PICTURE_DURATION')
            if tick(c['end']) - tick(c['start']) != tick(c['outPoint']) - tick(c['inPoint']):
                issue('PICTURE_SOURCE_DURATION_MISMATCH')
            partners = [by_audio[i] for i in c.get('links', []) if i in by_audio]
            if len(partners) != 1:
                issue('AMBIGUOUS_AUDIO_PARTNER')
                continue
            a = partners[0]
            if c['id'] not in a.get('links', []) or c['media_path'] != a['media_path'] or a.get('speed') != 1:
                issue('UNSUPPORTED_LINKED_SOURCE')
                continue
            # A J/L cut changes edges, not the source-to-timeline translation.
            # Some reviewed native items expose an audio outPoint inconsistent
            # with timeline duration. Do not silently rewrite that audio. Report
            # it separately; this picture-only check uses the played head clock.
            if tick(a['end']) - tick(a['start']) != tick(a['outPoint']) - tick(a['inPoint']):
                audio_warnings.append({'node_id': a['id'], 'code': 'AUDIO_TAIL_CLOCK_CONFLICT',
                                       'requires': 'Separate native PCM review; never infer acoustic approval'})
            for timeline, source in [('start', 'inPoint')]:
                delta = (tick(c[timeline]) - tick(c[source])) - (tick(a[timeline]) - tick(a[source]))
                if delta:
                    issue('AV_SOURCE_CLOCK_OFFSET', edge=timeline, delta_ticks=str(delta))
        for left, right in zip(clips, clips[1:]):
            delta = tick(right['start']) - tick(left['end'])
            if delta:
                issues.append({'group': group['id'], 'left': left['id'], 'right': right['id'],
                               'code': 'PICTURE_GAP' if delta > 0 else 'PICTURE_OVERLAP',
                               'delta_ticks': str(delta)})
    if seen != set(by_video):
        raise ValueError('unaudited picture items remain; no protected-clip exemption')
    return {'schema': 'edit.picture-continuity-audit/v1', 'status': 'FAIL' if issues else 'PASS',
            'frame_ticks': str(frame_ticks), 'picture_items': len(videos), 'groups': len(groups),
            'issues': issues, 'audio_warnings': audio_warnings,
            'scope': 'Exact timeline grid, picture coverage and linked audio head clocks; audio tail conflicts reported separately; no acoustic approval'}


def tick(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('ticks must be exact integer strings or integers')
    return int(value)


def compare(before, after, mapping=None):
    if mapping is None:
        if list(map(len, before['tracks'])) != list(map(len, after['tracks'])):
            raise ValueError('track counts differ; supply an explicit item map')
        mapping = {'groups': [{'id': 'sequence', 'items': [
            {'track': t, 'before': i, 'after': i}
            for t, items in enumerate(before['tracks']) for i in range(len(items))]}]}
    seen_before, seen_after = set(), set()
    reports = []
    for group in mapping['groups']:
        bound = []
        for entry in group['items']:
            t, a, b = (entry[k] for k in ('track', 'before', 'after'))
            if any(type(x) is not int or x < 0 for x in (t, a, b)):
                raise ValueError('item indices must be nonnegative integers')
            if (t, a) in seen_before or (t, b) in seen_after:
                raise ValueError('duplicate mapped item')
            seen_before.add((t, a)); seen_after.add((t, b))
            old, new = before['tracks'][t][a], after['tracks'][t][b]
            bound.append((entry, old, new))
        if not bound:
            raise ValueError('empty group')
        shifts = [tick(new['start']) - tick(old['start']) for _, old, new in bound]
        shift = shifts[0]
        old_ids = {old['id']: str(i) for i, (_, old, _) in enumerate(bound)}
        new_ids = {new['id']: str(i) for i, (_, _, new) in enumerate(bound)}
        if len(old_ids) != len(bound) or len(new_ids) != len(bound):
            raise ValueError('duplicate native item identity in group')
        differences = []
        for entry, old, new in bound:
            changes = {}
            for key in ('inPoint', 'outPoint'):
                if tick(old[key]) != tick(new[key]):
                    changes[key] = {'before': str(old[key]), 'after': str(new[key]),
                                    'delta_ticks': tick(new[key]) - tick(old[key])}
            for key in ('start', 'end'):
                delta = tick(new[key]) - tick(old[key])
                if delta != shift:
                    changes[key] = {'expected_translation_ticks': shift,
                                    'actual_translation_ticks': delta}
            for key in ('media_path', 'speed', 'nested', 'offline'):
                if key not in old or key not in new:
                    raise ValueError(f'missing required native field {key}')
                if old[key] != new[key]:
                    changes[key] = {'before': old[key], 'after': new[key]}
            if 'links' not in old or 'links' not in new:
                raise ValueError('native link readback is required')
            # Self references are present in some Premiere readbacks. Compare the
            # group topology rather than opaque IDs, which can change on import.
            old_links = sorted({old_ids[x] if x in old_ids else 'external:' + x
                                for x in old['links'] if x != old['id']})
            new_links = sorted({new_ids[x] if x in new_ids else 'external:' + x
                                for x in new['links'] if x != new['id']})
            if old_links != new_links:
                changes['links'] = {'before': old_links, 'after': new_links}
            if changes:
                differences.append({**entry, 'before_id': old['id'], 'after_id': new['id'],
                                    'changes': changes})
        reports.append({'id': group['id'], 'item_count': len(bound),
                        'translation_ticks': shift, 'unchanged_except_translation': not differences,
                        'differences': differences})
    if not reports:
        raise ValueError('no mapped groups')
    return {'schema': 'edit.native-timing-comparison/v1',
            'status': 'MATCH' if all(r['unchanged_except_translation'] for r in reports) else 'CHANGED',
            'scope': 'Only mapped items; exact ticks, media, speed, availability and link topology. No acoustic judgment.',
            'groups': reports}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path, nargs='?')
    p.add_argument('--map', type=Path)
    p.add_argument('--audit-picture', type=Path, help='JSON groups: [{id, video_ids}] covering every picture item')
    p.add_argument('--frame-ticks', help='Exact sequence ticks per video frame for picture audit')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error('output exists; use a new revision path')
    if a.audit_picture:
        if a.after or a.map or not a.frame_ticks:
            p.error('picture audit takes one snapshot, --audit-picture and --frame-ticks')
        try:
            result = audit_picture(json.loads(a.before.read_text()), a.frame_ticks,
                                   json.loads(a.audit_picture.read_text()))
        except (ValueError, KeyError, IndexError, TypeError) as e:
            p.error(str(e))
        result['snapshot_sha256'] = hashlib.sha256(a.before.read_bytes()).hexdigest()
        result['groups_sha256'] = hashlib.sha256(a.audit_picture.read_bytes()).hexdigest()
        a.out.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'status': result['status'], 'issues': len(result['issues']), 'out': str(a.out)}))
        return 0 if result['status'] == 'PASS' else 2
    if not a.after:
        p.error('comparison requires before and after snapshots')
    try:
        result = compare(json.loads(a.before.read_text()), json.loads(a.after.read_text()),
                         json.loads(a.map.read_text()) if a.map else None)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        p.error(str(e))
    result['inputs'] = {k: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                        for k, path in [('before', a.before), ('after', a.after), ('map', a.map)] if path}
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'groups': len(result['groups']),
                      'changed_items': sum(len(g['differences']) for g in result['groups']),
                      'out': str(a.out)}))
    return 0 if result['status'] == 'MATCH' else 2


if __name__ == '__main__':
    raise SystemExit(main())

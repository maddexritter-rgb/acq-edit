#!/usr/bin/env python3
"""Read-only native Premiere timing, media, geometry and track-state audit.

Only the observed flat project graph is supported. Unknown graphs fail closed.
Clip enable states are checked from exported XML through Resolve, not inferred
from undocumented native clip flag fields.
"""
import argparse
import gzip
import json
import pathlib
import xml.etree.ElementTree as E
from fractions import Fraction
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prepare import boolean, sha, validate_manifest

TICKS = 254016000000
AUDIT_SCHEMA = 'premiere-to-resolve/native-audit-v2'


def audit(project, manifest):
    validate_manifest(manifest)
    data = pathlib.Path(project).read_bytes()
    root = E.fromstring(gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data)
    ids = {x.get('ObjectID'): x for x in root if x.get('ObjectID')}
    uids = {x.get('ObjectUID'): x for x in root if x.get('ObjectUID')}
    native_sequences = [x for x in root if x.tag == 'Sequence' and x.get('ObjectUID')]
    names = [x.findtext('Name') for x in native_sequences]
    if len(names) != len(set(names)):
        raise ValueError('Ambiguous native sequence names')
    seqs = dict(zip(names, native_sequences))
    report = {'schema': AUDIT_SCHEMA, 'project_sha256': sha(project), 'passed': False,
              'errors': [], 'sequences': [], 'track_settings': {},
              'native_sequences_not_in_export': sorted(set(names) - {s['name'] for s in manifest['sequences']}),
              'limits': ['Native clip enabled flags are not decoded; XML-to-Resolve clip state is separately verified']}
    for ex in manifest['sequences']:
        s = seqs[ex['name']]
        q = Fraction(TICKS) / Fraction(ex['rate'])
        count = 0
        seen_kinds = set()
        report['track_settings'][ex['name']] = {'video': [], 'audio': []}
        for tr in s.findall('TrackGroups/TrackGroup/Second'):
            group = ids[tr.get('ObjectRef')]
            if group.tag not in ('VideoTrackGroup', 'AudioTrackGroup'):
                continue
            kind = 'video' if group.tag == 'VideoTrackGroup' else 'audio'
            if kind in seen_kinds:
                raise ValueError('Duplicate native track group')
            seen_kinds.add(kind)
            if kind == 'video':
                rect = list(map(int, group.findtext('FrameRect').split(',')))
                if [rect[2] - rect[0], rect[3] - rect[1]] != [ex['width'], ex['height']]:
                    report['errors'].append({'sequence': ex['name'], 'field': 'resolution'})
                if Fraction(group.findtext('TrackGroup/FrameRate')) != q:
                    report['errors'].append({'sequence': ex['name'], 'field': 'frame_rate'})
            tracks = group.findall('TrackGroup/Tracks/Track')
            if len(tracks) != len(ex['tracks'][kind]):
                raise ValueError(ex['name'] + ': native ' + kind + ' track inventory differs')
            for j, t in enumerate(tracks):
                track = uids[t.get('ObjectURef')]
                enabled = not boolean(track.findtext('ClipTrack/Track/IsMuted'), default=False)
                name = track.findtext('ClipTrack/Track/Node/Properties/MZ.TrackName') or None
                meta = ex['track_settings'][kind][j]
                if meta['enabled'] != enabled:
                    report['errors'].append({'sequence': ex['name'], 'track': kind + str(j + 1),
                                             'field': 'track_enabled', 'native': enabled, 'xml': meta['enabled']})
                if meta['name'] and meta['name'] != name:
                    report['errors'].append({'sequence': ex['name'], 'track': kind + str(j + 1), 'field': 'track_name'})
                # Premiere XML can omit custom names. Carry the native name in the bound audit.
                report['track_settings'][ex['name']][kind].append({'enabled': enabled, 'name': name})
                items = track.findall('ClipTrack/ClipItems/TrackItems/TrackItem')
                expected = ex['tracks'][kind][j]
                if len(items) != len(expected):
                    raise ValueError(ex['name'] + ': native item inventory differs')
                for n, (ref, e) in enumerate(zip(items, expected)):
                    item = ids[ref.get('ObjectRef')]
                    ct = item.find('ClipTrackItem')
                    ti = ct.find('TrackItem')
                    sub = ids[ct.find('SubClip').get('ObjectRef')]
                    clip = ids[sub.find('Clip').get('ObjectRef')].find('Clip')
                    fields = {'start': int(ti.findtext('Start', '0')), 'end': int(ti.findtext('End')),
                              'in': int(clip.findtext('InPoint', '0')), 'out': int(clip.findtext('OutPoint'))}
                    for key, ticks in fields.items():
                        if ticks != e[key] * q:
                            report['errors'].append({'sequence': ex['name'], 'track': kind + str(j + 1),
                                'item': n, 'field': key, 'native_ticks': str(ticks), 'xml_ticks': str(e[key] * q),
                                'delta_samples_48k': float((Fraction(ticks) - e[key] * q) * 48000 / TICKS)})
                    if sub.findtext('Name') != e['name']:
                        report['errors'].append({'sequence': ex['name'], 'item': n, 'field': 'name'})
                    source = ids[clip.find('Source').get('ObjectRef')]
                    media_ref = source.find('MediaSource/Media')
                    if media_ref is None:
                        raise ValueError('Nested/generated/non-file native source requires a separate plan')
                    media = uids[media_ref.get('ObjectURef')]
                    paths = {v for v in (media.findtext('ActualMediaFilePath'), media.findtext('FilePath')) if v}
                    if len(paths) != 1:
                        raise ValueError('Native media path missing or ambiguous')
                    native_path = str(pathlib.Path(paths.pop()).resolve())
                    wanted = manifest['media'][e['path']]
                    allowed = {str(pathlib.Path(wanted['original_path']).resolve()), str(pathlib.Path(e['path']).resolve())}
                    if native_path not in allowed:
                        report['errors'].append({'sequence': ex['name'], 'track': kind + str(j + 1),
                                                 'item': n, 'field': 'media_path', 'native': native_path, 'xml': e['path']})
                    count += 1
        if any(ex['tracks'][k] and k not in seen_kinds for k in ('video', 'audio')):
            raise ValueError('Native track group missing')
        report['sequences'].append({'name': ex['name'], 'items_checked': count})
    report['passed'] = not report['errors']
    return report


def write_audit(project, manifest_path, output):
    """Write a fresh receipt on both supported success and schema/timing failure."""
    output = pathlib.Path(output)
    if output.exists():
        raise FileExistsError(output)
    try:
        result = audit(project, json.loads(pathlib.Path(manifest_path).read_text()))
    except (ValueError, KeyError, TypeError, AttributeError, E.ParseError) as exc:
        result = {'schema': AUDIT_SCHEMA, 'passed': False, 'errors': [{'unsupported_or_invalid': str(exc)}],
                  'sequences': [], 'project_sha256': sha(project)}
    result.update(project_path=str(pathlib.Path(project).resolve()), manifest_sha256=sha(manifest_path),
                  auditor_sha256=sha(__file__))
    output.write_text(json.dumps(result, indent=2))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('project'); p.add_argument('manifest'); p.add_argument('output')
    a = p.parse_args()
    result = write_audit(a.project, a.manifest, a.output)
    print(json.dumps({'passed': result['passed'], 'errors': len(result['errors']),
                      'items': sum(x['items_checked'] for x in result['sequences'])}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

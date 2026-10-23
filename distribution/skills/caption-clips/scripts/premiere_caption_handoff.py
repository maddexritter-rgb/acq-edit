#!/usr/bin/env python3
"""Prepared native Graphics preflight and post-import identity mapping.

Uses the existing caption builder/verifier; sends no Premiere commands. Native
text is opaque in CEP on the tested host. Saved-file verification and rendered
review remain required; XML ObjectIDs are never used as native timeline IDs.
"""
from pathlib import Path
from fractions import Fraction
import argparse
import hashlib
import json
import sys


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact(value):
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or str(int(value)) != value or int(value) > 9223372036854775807:
        raise ValueError('Noncanonical exact tick count')
    return int(value)


def synthetic_aliases(root):
    """Reject inconsistent cached descriptors for one generated-media identity.

    A live imported fixture reverted to the larger descriptor after save. This
    consistency check detects that input risk; it does not claim a proven fix.
    """
    ids = {node.get('ObjectID'): node for node in root if node.get('ObjectID')}
    groups = {}
    for media in root.findall('Media'):
        if media.findtext('Infinite') != 'true' or media.findtext('Title') != 'Graphic':
            continue
        key = (media.findtext('ImplementationID'), media.findtext('FilePath'))
        if not all(key):
            raise ValueError('Generated Graphics media identity unavailable')
        rows = groups.setdefault(key, [])
        for ref in media.findall('VideoStream'):
            stream = ids.get(ref.get('ObjectRef'))
            if stream is None or stream.findtext('FrameRect') is None:
                raise ValueError('Generated Graphics stream unavailable')
            rows.append({'media_uid': media.get('ObjectUID'), 'frame_rect': stream.findtext('FrameRect')})
    for key, rows in groups.items():
        if not rows or len({row['frame_rect'] for row in rows}) != 1:
            raise ValueError('Conflicting generated Graphics canvas descriptors: ' + repr(key))
    return [{'implementation_id': key[0], 'media_path': key[1], 'descriptors': rows} for key, rows in groups.items()]


def normalize_aliases(root, targets, canvas):
    """Explicit experimental retarget option, on the caller's output copy only."""
    if not targets or any(not all(key) or len(key) != 2 for key in targets):
        raise ValueError('Exact generated media identities required')
    if len(canvas) != 2 or any(type(v) is not int or v <= 0 for v in canvas):
        raise ValueError('Positive integral canvas required')
    ids = {node.get('ObjectID'): node for node in root if node.get('ObjectID')}
    changes = []; matched = set(); pending = []
    for media in root.findall('Media'):
        key = (media.findtext('ImplementationID'), media.findtext('FilePath'))
        if key not in targets:
            continue
        if media.findtext('Infinite') != 'true' or media.findtext('Title') != 'Graphic':
            raise ValueError('Alias is not generated Graphics')
        matched.add(key)
        refs = media.findall('VideoStream')
        if not refs:
            raise ValueError('Generated media has no stream')
        for ref in refs:
            stream = ids.get(ref.get('ObjectRef'))
            if stream is None or stream.find('FrameRect') is None:
                raise ValueError('Generated stream descriptor missing')
            rect = stream.find('FrameRect'); desired = f'0,0,{canvas[0]},{canvas[1]}'
            if rect.text != desired:
                pending.append((rect, desired))
                changes.append({'media_uid':media.get('ObjectUID'),'stream_id':stream.get('ObjectID'),'before':rect.text,'after':desired})
    if matched != set(targets):
        raise ValueError('Generated donor identity not found')
    # Resolve every descriptor before changing the in-memory output copy.
    for rect, desired in pending:
        rect.text = desired
    return changes


def bind_segments(receipt, manifest):
    rate = manifest['frame_rate']
    fps = Fraction(rate['numerator'], rate['denominator'])
    if fps <= 0:
        raise ValueError('Positive rational frame rate required')
    segments = manifest['render_segments']
    cards = receipt['cards']
    if not cards or len(cards) != len(segments) or len(cards) > 10000:
        raise ValueError('Card/segment count mismatch')
    seen = set()
    result = []
    prior_end = 0
    for card, segment in zip(cards, segments):
        sid = segment['id']; semantic = segment['semantic_card_id']
        if not isinstance(sid, str) or not sid or sid in seen or sid != card['id'] or not isinstance(semantic, str) or not semantic:
            raise ValueError('Unique segment and semantic identities required')
        seen.add(sid)
        timing = card['timing']
        for frame, tick in [('start_frame', 'start_ticks'), ('end_frame', 'end_ticks'), ('animation_elapsed_frames', 'animation_elapsed_ticks')]:
            if type(segment[frame]) is not int or segment[frame] < 0:
                raise ValueError('Integer nonnegative frame index required')
            expected = Fraction(segment[frame] * 254016000000, 1) / fps
            if expected.denominator != 1 or exact(timing[tick]) != expected.numerator:
                raise ValueError('Manifest/receipt exact frame mismatch')
        start, end = exact(timing['start_ticks']), exact(timing['end_ticks'])
        sin, sout = exact(timing['source_in_ticks']), exact(timing['source_out_ticks'])
        if end <= start or start < prior_end or sout - sin != end - start:
            raise ValueError('Overlapping or inconsistent card/source duration')
        prior_end = end
        if card['text'] != segment['text'] or ''.join(run['text'] for run in card['expected_runs']) != card['text']:
            raise ValueError('Manifest/decoded text mismatch')
        result.append({'segment_id': sid, 'semantic_card_id': semantic,
                       'prepared_object_id': card['item_id'], 'timing': timing, 'expected_text': card['text']})
    return result


def prepare(project, receipt_path, manifest_path, native):
    paths = [Path(project).resolve(), Path(receipt_path).resolve(), Path(manifest_path).resolve()]
    hashes = [sha(p) for p in paths]
    receipt, manifest = (json.loads(p.read_text()) for p in paths[1:])
    if not any(row['path'] == str(paths[2]) and row['sha256'] == hashes[2] for row in receipt['inputs']):
        raise ValueError('Manifest is not bound by original builder receipt')
    for row in receipt['inputs']:
        if sha(row['path']) != row['sha256']:
            raise ValueError('Original builder input changed')
    checked = native.verify(paths[0], paths[1])
    aliases = synthetic_aliases(native.load(paths[0]))
    segments = bind_segments(receipt, manifest)
    from native_caption_revision import transfer_precondition
    revision_precondition = transfer_precondition(receipt, manifest)
    if hashes != [sha(p) for p in paths]:
        raise ValueError('Prepared artifacts changed during preflight')
    return {'schema': 'edit.prepared-caption-handoff/v1', 'scope': 'Graphics transfer preflight; no native acceptance',
            'artifacts': [{'path': str(p), 'sha256': h} for p, h in zip(paths, hashes)],
            'sequence_id': receipt['sequence_uid'], 'sequence_name': receipt['sequence_name'],
            'track_index': receipt['track_index'], 'canvas': receipt['canvas'],
            'segments': segments, 'synthetic_media': aliases, 'offline_readback': checked,
            'revision_precondition': revision_precondition,
            'execution': 'not_run', 'persistence': 'not_run', 'rendered': 'not_run', 'text_editability': 'not_proven'}


def map_import(prepared, before, after):
    """Bounded one-sequence fixture mapping; rejects dependencies and any drift."""
    def index(state):
        if not isinstance(state, dict) or not isinstance(state.get('sequences'), list):
            raise ValueError('Structured project snapshot required')
        rows = {s['sequence_id']: s for s in state['sequences']}
        if len(rows) != len(state['sequences']):
            raise ValueError('Ambiguous sequence identity')
        if any(s['snapshot']['projectPath'] != state['project_path'] or s['snapshot']['sequenceId'] != sid for sid, s in rows.items()):
            raise ValueError('Inconsistent native sequence identity')
        return rows
    old, new = index(before), index(after)
    if before['project_path'] != after['project_path']:
        raise ValueError('Destination project changed')
    if any(new.get(k) != v for k, v in old.items()):
        raise ValueError('Protected existing sequence changed')
    added = set(new) - set(old)
    if added != {prepared['sequence_id']}:
        raise ValueError('Unexpected imported sequence/dependency set')
    seq = new[prepared['sequence_id']]
    if seq['name'] != prepared['sequence_name']:
        raise ValueError('Imported sequence name mismatch')
    snapshot = seq['snapshot']; settings = snapshot['settings']
    if [settings['videoFrameWidth'], settings['videoFrameHeight']] != prepared['canvas']:
        raise ValueError('Imported canvas mismatch')
    lanes = [t for t in snapshot['tracks'] if t['kind'] == 0 and t['index'] == prepared['track_index']]
    if len(lanes) != 1 or len(lanes[0]['clips']) != len(prepared['segments']):
        raise ValueError('Caption lane/count mismatch')
    mappings = []; seen = set()
    for item, segment in zip(lanes[0]['clips'], prepared['segments']):
        if not isinstance(item.get('id'), str) or not item['id'] or item['id'] in seen or 'sourceId' not in item or not (item['sourceId'] is None or isinstance(item['sourceId'], str) and item['sourceId']):
            raise ValueError('Native Graphics identity ambiguous')
        seen.add(item['id'])
        for native_key, receipt_key in [('start','start_ticks'),('end','end_ticks'),('inPoint','source_in_ticks'),('outPoint','source_out_ticks')]:
            if exact(item[native_key]) != exact(segment['timing'][receipt_key]):
                raise ValueError('Native card/source clock mismatch')
        if item['disabled'] or item['speed'] != 1 or len([c for c in item['components'] if c['matchName'] == 'AE.ADBE Text']) != 1:
            raise ValueError('Unexpected Graphics component or playback state')
        mappings.append({**segment, 'native_item_id': item['id'], 'native_source_id': item['sourceId']})
    return {'schema':'edit.native-caption-map/v1','project_path':after['project_path'],
            'sequence_id':prepared['sequence_id'],'track_index':prepared['track_index'],
            'items':mappings,'protected_sequences_unchanged':True,
            'native_readback':'item identities, exact clocks and Text component only',
            'native_project_item':'may be unavailable for generated Graphics; native item ID and exact sequence/track required',
            'native_text':'opaque; saved-file verifier required','persistence':'not_run','rendered':'not_run',
            'full_imported_picture_audio_structure':'not_verified','text_editability':'not_proven'}


def main():
    ap = argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--receipt',required=True);ap.add_argument('--manifest',required=True);ap.add_argument('--output',required=True)
    a = ap.parse_args()
    # The deployed sibling module owns caption construction and saved-file verification.
    sys.path.insert(0, str(Path("__ACQ_SKILLS__/caption-clips/scripts")))
    import premiere_native_cards as native
    result = prepare(a.project,a.receipt,a.manifest,native)
    with Path(a.output).open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'status':'OFFLINE_PREFLIGHT_ONLY','output':a.output}))


if __name__ == '__main__':main()

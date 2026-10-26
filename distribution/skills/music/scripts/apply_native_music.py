#!/usr/bin/env python3
"""Apply a selected music envelope to an explicitly owned native audio item.

No selection, placement range or EQ is inferred here. Explicit placement plans
prepare an audio source and add one owned item before the envelope stage.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
import struct
from pathlib import Path
import sys
import uuid
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
from premiere_bridge import BridgeError, PremiereBridge, Profile, execute_operation
from premiere_stage_handoff import write_handoff

TPS = 254016000000
PARAMETER_FIELDS = ('component_index', 'component_match_name', 'parameter_index', 'display_name')
ITEM_FIELDS = ('node_id', 'source_id', 'media_path', 'start_ticks', 'end_ticks', 'source_in_ticks', 'source_out_ticks', 'source_offset_ticks')


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def exact(value):
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or str(int(value)) != value or int(value) > 9223372036854775807:
        raise BridgeError('Expected canonical nonnegative int64 tick string')
    return int(value)


def file_source_range(item):
    """Resolve file-relative audition times from explicitly evidenced local marks."""
    if item.get('source_clock_evidence') != 'project_metadata_audio_in_out_offsets' or item.get('source_clock_unavailable'):
        raise BridgeError('Native source clock lacks offset evidence')
    offset = exact(item.get('source_offset_ticks'))
    values = tuple(str(offset + exact(item[field])) for field in ('source_in_ticks', 'source_out_ticks'))
    for value in values:
        exact(value)
    return values


def seconds_ticks(value):
    ticks = Fraction(str(value)) * TPS
    if ticks.denominator != 1 or ticks < 0:
        raise BridgeError('Selected source start cannot be represented exactly in ticks')
    return str(ticks.numerator)


def artifact(path, expected_hash=None):
    path = Path(path)
    if not path.is_absolute() or not path.is_file():
        raise BridgeError('Evidence/media path must be an existing absolute file')
    current = sha(path)
    if expected_hash is not None and current != expected_hash:
        raise BridgeError('Evidence/media hash changed')
    return {'path': str(path), 'sha256': current}


def pcm_rms(path):
    # Calibration uses constant-level PCM fixtures; compressed or float WAV is
    # deliberately unsupported. This measures amplitude, not perceived loudness.
    with wave.open(str(path), 'rb') as audio:
        channels, width, rate, frames = audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()
        if width not in (2, 3, 4) or not 1 <= channels <= 8 or frames < rate or frames > rate * 60:
            raise BridgeError('Calibration requires 1–60 seconds of signed PCM WAV')
        raw = audio.readframes(frames)
    if len(raw) != frames * channels * width:
        raise BridgeError('Truncated calibration audio')
    scale = 2 ** (8 * width - 1)
    # Measure each channel, so a stereo channel loss cannot look like a gain change.
    sums = [0.0] * channels
    for frame in range(frames):
        for ch in range(channels):
            at = (frame * channels + ch) * width
            sample = int.from_bytes(raw[at:at + width], 'little', signed=True) / scale
            if abs(sample) >= 0.999:
                raise BridgeError('Clipped calibration fixture')
            sums[ch] += sample * sample
    return (channels, rate, frames), [math.sqrt(total / frames) for total in sums]


def native_level_keys_match(requested, returned):
    """Premiere Level uses binary32; ES3 JSON rounds at 14 decimal places.

    Keep key ticks exact and allow only observed native storage/serialization,
    rather than treating a generic gain tolerance as calibration evidence.
    """
    if len(requested) != len(returned):
        return False
    for want, got in zip(requested, returned):
        if got.get('ticks') != want.get('ticks'):
            return False
        value = got.get('value')
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return False
        expected = struct.unpack('!f', struct.pack('!f', want['value']))[0]
        if value != want['value'] and abs(value - expected) > 1e-14:
            return False
    return True


def calibrated_values(calibration_path, descriptor, requested_db):
    calibration = read(calibration_path)
    if (calibration.get('schema'), calibration.get('host_version'), calibration.get('backend')) != ('edit.music-level-calibration/v1', '26.3.0', 'CEP/ExtendScript') or calibration.get('parameter') != descriptor:
        raise BridgeError('Missing matching host/parameter calibration')
    found, evidence = {}, [artifact(calibration_path)]
    for sample in calibration.get('samples', []):
        db, native = sample['db'], sample['native_value']
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (db, native)) or not 0 <= native <= 1 or db in found:
            raise BridgeError('Invalid or duplicate calibration sample')
        if db not in requested_db:
            continue
        src = artifact(sample['source_wav']['path'], sample['source_wav']['sha256'])
        rendered = artifact(sample['rendered_wav']['path'], sample['rendered_wav']['sha256'])
        receipt = artifact(sample['native_receipt']['path'], sample['native_receipt']['sha256'])
        export_receipt = artifact(sample['export_receipt']['path'], sample['export_receipt']['sha256'])
        native_record = read(receipt['path'])
        operation = native_record.get('operation', {})
        outcome = native_record.get('result', {}).get('operation', {})
        keys = operation.get('arguments', {}).get('keys', [])
        returned = outcome.get('result', {}).get('data', {}).get('keys', [])
        if operation.get('tool') != 'lab_apply_music_envelope' or operation.get('arguments', {}).get('parameter') != descriptor or len(keys) < 2 or any(k['value'] != native for k in keys) or outcome.get('status') != 'committed_unverified' or outcome.get('result', {}).get('success') is not True or not native_level_keys_match(keys, returned):
            raise BridgeError('Calibration lacks matching constant-envelope native readback')
        export_record = read(export_receipt['path'])
        export_op = export_record.get('operation', {})
        export_outcome = export_record.get('result', {}).get('operation', {})
        native_target, export_target = operation.get('target', {}), export_op.get('target', {})
        if operation['arguments'].get('media_path') != src['path'] or export_op.get('tool') != 'export_sequence' or export_op.get('arguments', {}).get('output_path') != rendered['path'] or any(native_target.get(f) is None or native_target[f] != export_target.get(f) for f in ('project_path', 'sequence_id')) or export_outcome.get('status') != 'committed_unverified' or export_outcome.get('result', {}).get('success') is not True or export_outcome.get('result', {}).get('data', {}).get('outputPath') != rendered['path']:
            raise BridgeError('Calibration source or native export provenance differs')
        aformat, source_rms = pcm_rms(src['path'])
        bformat, output_rms = pcm_rms(rendered['path'])
        if aformat != bformat:
            raise BridgeError('Calibration source/render audio formats differ')
        for a, b in zip(source_rms, output_rms):
            if a < 0.01 or b <= 0 or abs(20 * math.log10(b / a) - db) > 0.15:
                raise BridgeError('Rendered calibration amplitude disagrees with requested dB')
        found[db] = native
        evidence.extend([src, rendered, receipt, export_receipt])
    if set(found) != set(requested_db):
        raise BridgeError('Every requested dB value requires a measured native/render sample; no guessed conversion')
    return found, evidence


def selected_candidate(selection, duration_seconds):
    if selection.get('schema') != 'edit.music-selection.v2':
        raise BridgeError('Expected the existing music-selection.v2 receipt with audition decision')
    winner = selection.get('winner')
    winner_id = winner.get('id') if isinstance(winner, dict) else winner
    matches = [p for p in selection.get('picks', []) if p.get('id') == winner_id]
    if len(matches) != 1:
        raise BridgeError('Winner must identify exactly one existing candidate')
    candidate = matches[0]
    if isinstance(winner, dict) and any(winner.get(k, candidate[k]) != candidate[k] for k in ('id', 'path', 'start')):
        raise BridgeError('Winner differs from its auditioned candidate')
    # Reuse the canonical filter implementation; do not build another selector.
    spec = importlib.util.spec_from_file_location('music_eligibility', Path(__file__).with_name('pick_music.py'))
    picker = importlib.util.module_from_spec(spec); spec.loader.exec_module(picker)
    inputs = selection.get('eligibility_inputs', {})
    index_path = Path(inputs.get('index', picker.ROOT / '_music_index.json')).expanduser()
    review_path = Path(inputs.get('review_decisions', picker.DEFAULT_REVIEW)).expanduser()
    blacklist_path = Path(inputs.get('blacklist', picker.ROOT / 'MUSIC_BLACKLIST.txt')).expanduser()
    used = selection.get('recent_track_exclusions')
    if not isinstance(used, list) or any(not isinstance(v, str) or not v.strip() for v in used):
        raise BridgeError('Selection receipt must retain recent-track exclusions')
    evidence = [artifact(p.resolve()) for p in (index_path, review_path, blacklist_path)]
    eligible = picker.rank(read(index_path), review=read(review_path), banned=picker.load_rules(blacklist_path),
                           used=[v.strip().lower() for v in used], duration=duration_seconds,
                           brief=selection['brief'])
    if not any(p['path'] == candidate['path'] and p['id'] == candidate['id'] for p in eligible):
        raise BridgeError('Selected music no longer passes the existing eligibility filters')
    return project_source_candidate(selection, candidate, evidence)


def project_source_candidate(selection, candidate, evidence):
    """Bind the eligible catalog recording to an unchanged project-owned source.

    Full decoded PCM equality permits container/codec normalization, never edits,
    offsets, gain, fades or replacement recordings. Approval stays on the catalog.
    """
    import subprocess
    binding = selection.get('project_source')
    if binding is None:
        return candidate, evidence
    if not isinstance(binding, dict) or binding.get('schema') != 'edit.music-project-source/v1':
        raise BridgeError('Invalid project music source binding')
    target = selection.get('target', {})
    project = Path(target.get('project_path', ''))
    media = Path(binding.get('path', ''))
    if not project.is_absolute() or project.parent.name != '10_WORK' or not media.is_absolute():
        raise BridgeError('Music binding requires the project storage convention')
    source_root = (project.parent.parent / '00_SOURCE').resolve()
    if not media.resolve().is_relative_to(source_root):
        raise BridgeError('Music must be a project-owned source')
    if any(not isinstance(binding.get(k), str) or len(binding[k]) != 64 or
           any(c not in '0123456789abcdef' for c in binding[k])
           for k in ('catalog_sha256', 'sha256', 'decoded_pcm_sha256')):
        raise BridgeError('Music binding requires exact SHA256 pins')
    catalog = artifact(candidate['path'], binding['catalog_sha256'])
    owned = artifact(media, binding['sha256'])
    for path in (candidate['path'], str(media)):
        result = subprocess.run(['ffmpeg', '-v', 'error', '-i', path,
                                 '-map', '0:a:0', '-vn', '-ar', '48000', '-ac', '2',
                                 '-c:a', 'pcm_s24le', '-f', 'hash', '-hash', 'sha256', '-'],
                                capture_output=True, text=True, timeout=120, check=True)
        if result.stdout.strip() != 'SHA256=' + binding['decoded_pcm_sha256']:
            raise BridgeError('Project music differs from the complete catalog recording')
    return {**candidate, 'path': str(media)}, evidence + [catalog, owned]


def make_plan(selection_path, envelope_path, calibration_path, inspection, node_id):
    selection, envelope = read(selection_path), read(envelope_path)
    if envelope.get('schema') != 'edit.music-envelope/v1':
        raise BridgeError('Expected an explicit music envelope plan')
    target = {'project_path': inspection['project_path'], 'sequence_id': inspection['sequence_id']}
    if selection.get('target') != target or envelope.get('target') != target:
        raise BridgeError('Selection/envelope target differs from current native target')
    located = [(t, c) for t in inspection['audio_tracks'] for c in t['clips'] if c['node_id'] == node_id]
    if len(located) != 1:
        raise BridgeError('Owned music item is missing or ambiguous')
    track, item = located[0]
    if track['locked'] is not False or item['speed'] != 1 or item.get('speed_reversed') is not False:
        raise BridgeError('Music target is locked or forward playback is unverified')
    duration = exact(item['end_ticks']) - exact(item['start_ticks'])
    if duration <= 0 or duration != exact(item['source_out_ticks']) - exact(item['source_in_ticks']):
        raise BridgeError('Music placement must preserve forward unit-speed ranges')
    file_in, file_out = file_source_range(item)
    candidate, evidence = selected_candidate(selection, duration / TPS)
    audition = selection.get('audition', {})
    if candidate['path'] != item['media_path'] or seconds_ticks(candidate['start']) != file_in or audition.get('winner_id') != candidate['id'] or audition.get('source_start_ticks') != file_in or audition.get('duration_ticks') != str(duration) or not audition.get('listening_notes'):
        raise BridgeError('Placed music differs from the recorded audition decision')
    evidence += [artifact(selection_path), artifact(envelope_path), artifact(item['media_path']), artifact(audition['clip_path'], audition['clip_sha256'])]
    level = item.get('level')
    if not level or level.get('keyframes_supported') is not True:
        raise BridgeError('Native Volume/Level automation unavailable')
    descriptor = {f: level[f] for f in PARAMETER_FIELDS}
    points = envelope.get('points', [])
    if len(points) < 2 or len(points) > 1000 or envelope.get('interpolation') != 'linear_native':
        raise BridgeError('Envelope must specify 2–1000 points and linear_native interpolation')
    last = -1
    for point in points:
        time = exact(point['offset_ticks']); db = point['db']
        if time <= last or time > duration or not isinstance(db, (int, float)) or isinstance(db, bool) or not math.isfinite(db):
            raise BridgeError('Invalid envelope time or dB value')
        last = time
    if points[0]['offset_ticks'] != '0' or points[-1]['offset_ticks'] != str(duration):
        raise BridgeError('Envelope must explicitly cover both music boundaries')
    values, calibration_evidence = calibrated_values(calibration_path, descriptor, {p['db'] for p in points})
    evidence += calibration_evidence
    args = {**{f: item[f] for f in ITEM_FIELDS}, 'parameter': descriptor,
            'keys': [{'ticks': str(exact(item['source_in_ticks']) + exact(p['offset_ticks'])), 'value': values[p['db']]} for p in points]}
    return {'schema': 'edit.music-native-plan/v1', 'operation': {
        'schema': 'edit.native-operation/v1', 'stage': 'music', 'operation_id': 'music-envelope-' + uuid.uuid4().hex,
        'tool': 'lab_apply_music_envelope', 'arguments': args,
        'target': {**target, 'expected_revision': inspection['revision']},
        'intended_changes': ['owned music item Volume/Level envelope only'],
        'protected_state': ['dialogue, picture, graphics, Motion and all other bounded snapshot fields']},
        'baseline': copy.deepcopy(inspection['snapshot']), 'evidence': evidence,
        'planning_inputs': {'selection': str(selection_path), 'envelope': str(envelope_path), 'calibration': str(calibration_path), 'node_id': node_id},
        'inspection': copy.deepcopy(inspection),
        'selection': {'winner_id': candidate['id'], 'audition': 'recorded_not_independently_listened'},
        'limitations': ['existing placement required', 'native interpolation readback unavailable', 'persistence/rendered full-mix/listening not run']}


def verify(plan, inspection):
    op = plan['operation']; args = op['arguments']
    if (inspection['project_path'], inspection['sequence_id']) != (op['target']['project_path'], op['target']['sequence_id']):
        raise BridgeError('Music verification target changed')
    rows = [c for t in inspection['audio_tracks'] for c in t['clips'] if c['node_id'] == args['node_id']]
    if len(rows) != 1 or any(rows[0][f] != args[f] for f in ITEM_FIELDS) or rows[0]['speed'] != 1 or rows[0].get('speed_reversed') is not False:
        raise BridgeError('Music source/timing/playback changed')
    level = rows[0]['level']
    def keys_equal(keys):
        return len(keys) == len(args['keys']) and all(a['ticks'] == b['ticks'] and isinstance(a['value'], (int, float)) and math.isfinite(a['value']) and abs(a['value'] - b['value']) <= 1e-7 for a, b in zip(keys, args['keys']))
    if not level or {f: level[f] for f in PARAMETER_FIELDS} != args['parameter'] or level['time_varying'] is not True or not keys_equal(level['keys']):
        raise BridgeError('Music envelope readback failed')
    before, after = copy.deepcopy(plan['baseline']), copy.deepcopy(inspection['snapshot'])
    def prop(state):
        clips = [c for t in state['tracks'] if t['kind'] == 1 for c in t['clips'] if c['id'] == args['node_id']]
        if len(clips) != 1:
            raise BridgeError('Ambiguous music snapshot')
        component = clips[0]['components'][args['parameter']['component_index']]
        p = component['properties'][args['parameter']['parameter_index']]
        if component['matchName'] != args['parameter']['component_match_name'] or p['name'] != args['parameter']['display_name'] or p.get('valueUnavailable') or p.get('keyframesUnavailable'):
            raise BridgeError('Music snapshot descriptor unavailable')
        return p
    old, observed = prop(before), prop(after)
    if not keys_equal(observed.get('keys', [])):
        raise BridgeError('Music snapshot envelope differs from direct readback')
    if 'keys' in old:
        observed['keys'] = old['keys']
    else:
        observed.pop('keys')
    observed['value'] = old['value']
    if before != after:
        raise BridgeError('Protected timeline state changed during music application')
    return {'revision': inspection['revision'], 'verification': 'exact_raw_envelope_and_bounded_protected_state',
            'interpolation': 'not_read_back', 'persistence': 'reopen_not_run', 'rendered': 'not_run', 'listening': 'not_run'}


def inspect(client):
    result = client.inspect('inspect_music_state', {})
    if result.get('success') is not True:
        raise BridgeError('Music inspection failed')
    return result['data']


def apply(client, plan_path, timeout=120):
    plan = read(plan_path)
    if plan.get('schema') != 'edit.music-native-plan/v1':
        raise BridgeError('Expected a prepared native music plan')
    for evidence in plan['evidence']:
        artifact(evidence['path'], evidence['sha256'])
    inputs = plan['planning_inputs']
    rebuilt = make_plan(Path(inputs['selection']), Path(inputs['envelope']), Path(inputs['calibration']), plan['inspection'], inputs['node_id'])
    rebuilt['operation']['operation_id'] = plan['operation']['operation_id']
    if rebuilt != plan:
        raise BridgeError('Prepared music plan differs from its selection, envelope or measured calibration')
    result = execute_operation(client, plan['operation'], plan_path.with_suffix('.bridge-operation.json'), timeout)
    verified = verify(plan, inspect(client))
    save = {'schema': 'edit.native-operation/v1', 'stage': 'music', 'operation_id': plan['operation']['operation_id'] + '-save',
            'tool': 'save_project', 'arguments': {}, 'target': {**plan['operation']['target'], 'expected_revision': verified['revision']},
            'intended_changes': ['save verified native music envelope'], 'protected_state': ['all timeline state']}
    execute_operation(client, save, plan_path.with_suffix('.bridge-save.json'), timeout)
    final_inspection = inspect(client)
    after = verify(plan, final_inspection)
    if after['revision'] != verified['revision']:
        raise BridgeError('Protected state changed across music save')
    handoff_path = plan_path.with_suffix('.stage-handoff.json')
    write_handoff(handoff_path, stage='music', before=plan['baseline'], after=final_inspection['snapshot'],
                  before_revision=plan['operation']['target']['expected_revision'], after_revision=after['revision'],
                  receipts=[plan_path.with_suffix('.bridge-operation.json'), plan_path.with_suffix('.bridge-save.json')])
    return {'execution': result, 'readback': after, 'handoff': str(handoff_path), 'persistence': 'reopen_not_run', 'rendered': 'not_run', 'listening': 'not_run'}


def make_placement_plan(selection_path, placement_path, inspection):
    selection, placement = read(selection_path), read(placement_path)
    target = {'project_path': inspection['project_path'], 'sequence_id': inspection['sequence_id']}
    if placement.get('schema') != 'edit.music-placement/v1' or placement.get('target') != target or selection.get('target') != target:
        raise BridgeError('Music placement/selection must identify the current project and sequence')
    if type(placement.get('track_index')) is not int or not 0 <= placement['track_index'] <= 255 or not isinstance(placement.get('track_id'), str) or not 1 <= len(placement['track_id']) <= 512:
        raise BridgeError('Music placement needs an exact track index and native track identity')
    start, end = exact(placement['start_ticks']), exact(placement['end_ticks'])
    if end <= start:
        raise BridgeError('Music placement must have positive duration')
    extent = max((exact(c['end']) for t in inspection['snapshot']['tracks'] for c in t['clips']), default=0)
    if end > extent:
        raise BridgeError('Music placement beyond existing timeline extent is not accepted; prepare the picture/dialogue sequence first')
    track = [t for t in inspection['audio_tracks'] if t['index'] == placement['track_index'] and t.get('track_id') == placement['track_id']]
    if len(track) != 1 or track[0]['locked'] is not False or track[0].get('muted') is not False or track[0].get('transition_count') != 0:
        raise BridgeError('Music requires an identified unlocked/unmuted track without transitions')
    if any(exact(c['end_ticks']) > start and exact(c['start_ticks']) < end for c in track[0]['clips']):
        raise BridgeError('Music placement overlaps an existing audio item')
    candidate, evidence = selected_candidate(selection, (end - start) / TPS)
    source_in = seconds_ticks(candidate['start']); source_out = str(exact(source_in) + end - start)
    audition = selection.get('audition', {})
    if audition.get('winner_id') != candidate['id'] or audition.get('source_start_ticks') != source_in or audition.get('duration_ticks') != str(end - start) or not audition.get('listening_notes'):
        raise BridgeError('Placement differs from the recorded music audition')
    evidence += [artifact(selection_path), artifact(placement_path), artifact(candidate['path']), artifact(audition['clip_path'], audition['clip_sha256'])]
    request = {'media_path': candidate['path'], 'media_sha256': sha(candidate['path']), 'source_in_ticks': source_in, 'source_out_ticks': source_out}
    if placement.get('source_item_id'):
        request['source_item_id'] = placement['source_item_id']
    operation_id = 'music-place-' + uuid.uuid4().hex
    return {'schema': 'edit.music-placement-plan/v1', 'operation_id': operation_id,
            'source_operation': {'schema': 'edit.native-operation/v1', 'stage': 'music', 'operation_id': operation_id + '-source',
                                 'tool': 'lab_prepare_music_source', 'arguments': request,
                                 'target': {**target, 'expected_revision': inspection['revision']},
                                 'intended_changes': ['import selected source if absent; create an owned exact-range audio subclip'],
                                 'protected_state': ['shared source marks, existing bounded project tree and active timeline']},
            'placement': {**{f: placement[f] for f in ('track_index', 'track_id', 'start_ticks', 'end_ticks')},
                          **{f: request[f] for f in ('media_path', 'media_sha256', 'source_in_ticks', 'source_out_ticks')}},
            'inspection': copy.deepcopy(inspection), 'evidence': evidence,
            'planning_inputs': {'selection': str(selection_path), 'placement': str(placement_path)},
            'limits': ['gain/envelope not applied by placement', 'source clocks, channel routing and source effects require host proof', 'save/reopen and rendered/listening not run']}


def verify_placement(plan, inspection, placed):
    target, expected = plan['source_operation']['target'], plan['placement']
    if (inspection['project_path'], inspection['sequence_id']) != (target['project_path'], target['sequence_id']):
        raise BridgeError('Music placement target changed')
    tracks = [t for t in inspection['audio_tracks'] if t['index'] == expected['track_index'] and t.get('track_id') == expected['track_id']]
    if len(tracks) != 1 or tracks[0]['locked'] is not False or tracks[0].get('muted') is not False or tracks[0].get('transition_count') != 0:
        raise BridgeError('Music destination changed during placement')
    rows = [c for c in tracks[0]['clips'] if c['node_id'] == placed['node_id']]
    if len(rows) != 1 or rows[0]['source_id'] != placed['source_id'] or any(rows[0][f] != expected[f] for f in ('media_path', 'start_ticks', 'end_ticks')) or rows[0]['speed'] != 1 or rows[0].get('speed_reversed') is not False:
        raise BridgeError('Placed music identity/source/range differs from the audition plan')
    if file_source_range(rows[0]) != (expected['source_in_ticks'], expected['source_out_ticks']):
        raise BridgeError('Placed music file-relative source clock differs from audition')
    before, after = plan['inspection']['snapshot'], copy.deepcopy(inspection['snapshot'])
    if any(c['id'] == placed['node_id'] for t in before['tracks'] for c in t['clips']):
        raise BridgeError('Placement reused a pre-existing timeline identity')
    removed = 0
    for track in after['tracks']:
        if track['kind'] != 1 or track['index'] != expected['track_index']:
            continue
        for i in range(len(track['clips']) - 1, -1, -1):
            c = track['clips'][i]
            if c['id'] != placed['node_id']:
                continue
            if c['sourceId'] != placed['source_id'] or c['start'] != expected['start_ticks'] or c['end'] != expected['end_ticks'] or c['inPoint'] != rows[0]['source_in_ticks'] or c['outPoint'] != rows[0]['source_out_ticks'] or c['speed'] != 1 or c['disabled'] is not False:
                raise BridgeError('Placement snapshot disagrees with exact native readback')
            track['clips'].pop(i); removed += 1
    if removed != 1 or before != after:
        raise BridgeError('Protected dialogue/picture/timeline changed during music placement')
    return {'revision': inspection['revision'], 'node_id': placed['node_id'], 'source_id': placed['source_id'],
            'verification': 'exact_placement_and_bounded_protected_state', 'channels_and_routing': 'not_inspected',
            'persistence': 'reopen_not_run', 'rendered': 'not_run', 'listening': 'not_run', 'envelope': 'not_applied'}


def apply_placement(client, plan_path, timeout=120):
    plan = read(plan_path)
    if plan.get('schema') != 'edit.music-placement-plan/v1':
        raise BridgeError('Expected prepared music placement plan')
    for suffix in ('.source-operation.json', '.placement-operation.json', '.placement-save.json', '.ownership.json'):
        if plan_path.with_suffix(suffix).exists():
            raise BridgeError('Placement attempt already exists; reconcile its original operation IDs')
    for evidence in plan['evidence']:
        artifact(evidence['path'], evidence['sha256'])
    inputs = plan['planning_inputs']
    rebuilt = make_placement_plan(Path(inputs['selection']), Path(inputs['placement']), plan['inspection'])
    rebuilt['operation_id'] = plan['operation_id']; rebuilt['source_operation']['operation_id'] = plan['source_operation']['operation_id']
    if rebuilt != plan or plan['source_operation']['operation_id'] != plan['operation_id'] + '-source':
        raise BridgeError('Music placement plan differs from its selection/audition inputs')
    source = execute_operation(client, plan['source_operation'], plan_path.with_suffix('.source-operation.json'), timeout)
    target, expected = plan['source_operation']['target'], plan['placement']
    if source.get('project_path') != target['project_path'] or source.get('sequence_id') != target['sequence_id'] or not source.get('source_item_id') or source['source_item_id'] == source.get('parent_source_id') or any(source.get(f) != expected[f] for f in ('media_path', 'source_in_ticks', 'source_out_ticks')):
        raise BridgeError('Prepared source identity/range was not verified; stop before placement')
    if source.get('native_source_in_ticks') != '0' or source.get('native_source_out_ticks') != str(exact(expected['source_out_ticks']) - exact(expected['source_in_ticks'])) or source.get('source_offset_ticks') != expected['source_in_ticks'] or source.get('clock_evidence') != 'project_metadata_audio_in_out_offsets':
        raise BridgeError('Prepared source clock was not verified; stop before placement')
    after_source = inspect(client)
    if after_source['snapshot'] != plan['inspection']['snapshot'] or after_source['revision'] != target['expected_revision'] or (after_source['project_path'], after_source['sequence_id']) != (target['project_path'], target['sequence_id']):
        raise BridgeError('Timeline changed during source preparation; stop before placement')
    placement_op = {'schema': 'edit.native-operation/v1', 'stage': 'music', 'operation_id': plan['operation_id'] + '-item',
                    'tool': 'lab_place_music_item', 'target': target,
                    'arguments': {**expected, 'source_item_id': source['source_item_id']},
                    'intended_changes': ['place one owned audio-only item into the specified empty range'],
                    'protected_state': ['all pre-existing bounded timeline fields and project source marks']}
    placed = execute_operation(client, placement_op, plan_path.with_suffix('.placement-operation.json'), timeout)
    if not placed.get('node_id') or placed.get('source_id') != source['source_item_id']:
        raise BridgeError('Placement did not return the prepared source identity')
    verified = verify_placement(plan, inspect(client), placed)
    ownership = {'schema': 'edit.music-ownership/v1', 'project_path': target['project_path'], 'sequence_id': target['sequence_id'],
                 'node_id': placed['node_id'], 'source_id': placed['source_id'], 'placement_plan': artifact(plan_path),
                 'source_operation_id': plan['source_operation']['operation_id'], 'placement_operation_id': placement_op['operation_id'],
                 'verification': verified}
    with plan_path.with_suffix('.ownership.json').open('x') as stream:
        json.dump(ownership, stream, indent=2)
    save = {'schema': 'edit.native-operation/v1', 'stage': 'music', 'operation_id': plan['operation_id'] + '-save', 'tool': 'save_project', 'arguments': {},
            'target': {**target, 'expected_revision': verified['revision']}, 'intended_changes': ['save verified music placement'], 'protected_state': ['all timeline state']}
    execute_operation(client, save, plan_path.with_suffix('.placement-save.json'), timeout)
    final_inspection = inspect(client)
    after_save = verify_placement(plan, final_inspection, placed)
    if after_save['revision'] != verified['revision']:
        raise BridgeError('Timeline changed across music-placement save')
    handoff_path = plan_path.with_suffix('.placement-handoff.json')
    write_handoff(handoff_path, stage='music', before=plan['inspection']['snapshot'], after=final_inspection['snapshot'],
                  before_revision=target['expected_revision'], after_revision=after_save['revision'],
                  receipts=[plan_path.with_suffix(suffix) for suffix in ('.source-operation.json', '.placement-operation.json', '.placement-save.json')])
    return {'source': source, 'placed': placed, 'readback': after_save, 'handoff': str(handoff_path), 'ownership_receipt': str(plan_path.with_suffix('.ownership.json')),
            'status': 'PLACED_ENVELOPE_STILL_REQUIRED', 'persistence': 'reopen_not_run', 'rendered': 'not_run', 'listening': 'not_run'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge-profile', type=Path, default=None, help='Uses the configured Premiere Agent default')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--inspect', action='store_true')
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--apply-plan', type=Path)
    mode.add_argument('--prepare-placement', action='store_true')
    mode.add_argument('--apply-placement', type=Path)
    parser.add_argument('--placement', type=Path)
    parser.add_argument('--selection', type=Path); parser.add_argument('--envelope', type=Path)
    parser.add_argument('--calibration', type=Path); parser.add_argument('--item-id'); parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.prepare and not all((args.selection, args.envelope, args.calibration, args.item_id, args.out)):
        parser.error('--prepare requires --selection, --envelope, --calibration, --item-id and --out')
    if args.prepare_placement and not all((args.selection, args.placement, args.out)):
        parser.error('--prepare-placement requires --selection, --placement and --out')
    client = PremiereBridge(Profile.load(args.bridge_profile))
    try:
        if args.inspect:
            result = inspect(client)
        elif args.prepare_placement:
            result = make_placement_plan(args.selection.resolve(), args.placement.resolve(), inspect(client))
            with args.out.open('x') as stream:
                json.dump(result, stream, indent=2)
        elif args.apply_placement:
            result = apply_placement(client, args.apply_placement.resolve())
        elif args.prepare:
            result = make_plan(args.selection.resolve(), args.envelope.resolve(), args.calibration.resolve(), inspect(client), args.item_id)
            with args.out.open('x') as stream:
                json.dump(result, stream, indent=2)
        else:
            result = apply(client, args.apply_plan.resolve())
        print(json.dumps(result, indent=2))
    finally:
        if not client.unsettled and not client.transport.pending:
            client.close()


if __name__ == '__main__':
    main()

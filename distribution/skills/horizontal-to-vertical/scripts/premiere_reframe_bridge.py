"""Typed bridge binding for the existing native reframe planner; no tracking logic."""
from __future__ import annotations
import copy
import json
import math
import struct
from fractions import Fraction
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
from premiere_bridge import PremiereBridge, Profile, BridgeError, execute_operation
from premiere_stage_handoff import write_handoff


def native_scale(value):
    """26.3 Motion Scale stores IEEE binary32; keep exact ticks independent.

    Native fixture: 177.77777777777777 read back as 177.777770996094.
    Quantize the intended write, not an arbitrary readback tolerance.
    """
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise BridgeError('Invalid native Scale')
    try:stored=struct.unpack('!f',struct.pack('!f',value))[0]
    except (OverflowError,struct.error):raise BridgeError('Scale is outside native float32 storage')
    if not math.isfinite(stored) or stored<=0:raise BridgeError('Scale is outside native float32 storage')
    return stored


def inspect_active(client):
    data = client.inspect('inspect_reframe_state', {})
    if data.get('success') is not True:
        raise BridgeError('Reframe inspection failed')
    result = copy.deepcopy(data['data']['inspection'])
    result['bridge_baseline'] = {
        'revision': data['data']['revision'],
        'snapshot': copy.deepcopy(data['data']['snapshot']),
        'items': [copy.deepcopy(c) for t in result['video_tracks'] for c in t['clips']],
    }
    return result


def repair_operation(plan, operation_id):
    if plan.get('schema') != 'premiere-native-x-seam-repair/v1':
        raise BridgeError('Expected the existing X-only seam plan')
    baseline = plan.get('bridge_baseline')
    if not baseline or not plan.get('records'):
        raise BridgeError('Build a new Lab inspection/repair plan before applying through this profile')
    lookup = {}
    for row in baseline['items']:
        loc = (row['track_index'], row['item_index'])
        if loc in lookup:
            raise BridgeError('Ambiguous baseline locator')
        lookup[loc] = row
    items, seen = [], set()
    for record in plan['records']:
        row = lookup.get((record['track_index'], record['item_index']))
        if not row or row['node_id'] in seen:
            raise BridgeError('Missing or duplicate repair target')
        seen.add(row['node_id'])
        for field in ('media_path', 'start', 'end', 'source_in', 'source_out', 'speed'):
            if record[field] != row[field]:
                raise BridgeError('Repair record differs from its inspected source/timing baseline')
        if record['baseline_motion'] != row['motion']:
            raise BridgeError('Repair record differs from its inspected Motion baseline')
        before, after = row['motion']['anchor_keys'], record['new_anchor_keys']
        if not before or len(before) != len(after):
            raise BridgeError('Repair must preserve existing key count')
        keys = []
        for old, new in zip(before, after):
            if old['ticks'] != new['ticks'] or old['value'][1] != new['value'][1]:
                raise BridgeError('Repair must preserve exact key time and Y')
            keys.append({'ticks': old['ticks'], 'before': old['value'], 'after': new['value']})
        items.append({'node_id': row['node_id'], 'keys': keys})
    return {'schema': 'edit.native-operation/v1', 'stage': 'reframe',
            'operation_id': operation_id, 'tool': 'lab_repair_anchor_x_keys',
            'arguments': {'items': items},
            'target': {'project_path': plan['project_path'], 'sequence_id': plan['sequence_id'],
                       'expected_revision': baseline['revision']},
            'intended_changes': ['X values of the listed existing item-local Anchor Point keys'],
            'protected_state': ['key times and Y; all other fields in the bounded Lab snapshot']}


def fresh_operation(plan, operation_id):
    if plan.get('schema') != 'premiere-native-reframe/v1' or plan.get('sequence_dimensions') != [1080, 1920]:
        raise BridgeError('Expected the existing native vertical Motion plan')
    baseline = plan.get('bridge_baseline')
    if not baseline or not baseline.get('snapshot') or not plan.get('records'):
        raise BridgeError('Build a fresh Lab plan with protected-state snapshot')
    lookup = {}
    for row in baseline['items']:
        locator = (row['track_index'], row['item_index'])
        if locator in lookup:
            raise BridgeError('Ambiguous inspected item locator')
        lookup[locator] = row
    items, seen = [], set()
    for record in plan['records']:
        row = lookup.get((record['track_index'], record['item_index']))
        if not row or row['node_id'] in seen:
            raise BridgeError('Missing or duplicate Motion target')
        seen.add(row['node_id'])
        for field in ('media_path', 'start', 'end', 'source_in', 'source_out', 'speed'):
            if record[field] != row[field]:
                raise BridgeError('Motion plan differs from inspected source/timing baseline')
        motion = row['motion']
        if record['baseline_motion'] != motion or any(motion[f'{p}_time_varying'] for p in ('anchor', 'position', 'scale')):
            raise BridgeError('Fresh application requires unchanged static Motion')
        if row['speed'] != 1 or row.get('speed_reversed') is not False:
            raise BridgeError('Fresh Lab reframe currently requires forward unit speed')
        keys = []
        for relative, x, y in record['anchor_keys']:
            # Keep the source offset as an integer. Round only the rational,
            # nonnegative relative sample to the nearest native tick, ties up.
            offset = Fraction(str(relative)) * 254016000000
            if offset < 0:
                raise BridgeError('Negative relative key time')
            rounded = (2 * offset.numerator + offset.denominator) // (2 * offset.denominator)
            ticks = int(row['source_in_ticks']) + rounded
            if ticks > int(row['source_out_ticks']):
                raise BridgeError('Key outside the inspected source range')
            key = {'ticks': str(ticks), 'value': [x, y]}
            if keys and ticks <= int(keys[-1]['ticks']):
                if key == keys[-1]:
                    continue  # Original single-frame planner repeats the same key.
                raise BridgeError('Conflicting or unordered keys after exact-time conversion')
            keys.append(key)
        if not keys:
            raise BridgeError('Fresh Motion plan has no keys')
        items.append({**{k: row[k] for k in ('node_id', 'source_id', 'media_path', 'start_ticks', 'end_ticks', 'source_in_ticks', 'source_out_ticks')},
                      'baseline': {p: copy.deepcopy(motion[p]) for p in ('anchor', 'position', 'scale')},
                      'position': record['position'], 'scale': native_scale(record['scale_percent']), 'keys': keys})
    return {'schema': 'edit.native-operation/v1', 'stage': 'reframe', 'operation_id': operation_id,
            'tool': 'lab_apply_reframe_motion', 'arguments': {'items': items},
            'target': {'project_path': plan['project_path'], 'sequence_id': plan['sequence_id'], 'expected_revision': baseline['revision']},
            'intended_changes': ['item-local static Position/Scale and fresh media-time Anchor Point keys'],
            'protected_state': ['source linkage and ranges, all other bounded Lab snapshot fields']}


def verify_fresh(plan, inspection, *, after_reopen=False):
    operation = fresh_operation(plan, 'readback-only')
    if (inspection['project_path'], inspection['sequence_id'], inspection['width'], inspection['height']) != (plan['project_path'], plan['sequence_id'], 1080, 1920):
        raise BridgeError('Reframe verification target or canvas changed')
    before = copy.deepcopy(plan['bridge_baseline']['snapshot'])
    after = copy.deepcopy(inspection['bridge_baseline']['snapshot'])
    rows = {}
    for track in inspection['video_tracks']:
        for row in track['clips']:
            if row['node_id'] in rows:
                raise BridgeError('Ambiguous readback item identity')
            rows[row['node_id']] = row

    def close(actual, expected):
        if isinstance(expected, list):
            return isinstance(actual, list) and len(actual) == len(expected) and all(close(a, b) for a, b in zip(actual, expected))
        return isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual) and abs(actual - expected) <= 1e-7

    def prop(state, item_id, name):
        found = [p for t in state['tracks'] if t['kind'] == 0 for c in t['clips'] if c['id'] == item_id
                 for fx in c['components'] if fx['name'] == 'Motion' for p in fx['properties'] if p['name'] == name]
        if len(found) != 1:
            raise BridgeError('Missing or ambiguous snapshot Motion property')
        return found[0]

    def keys_match(actual, expected):
        return len(actual) == len(expected) and all(a['ticks'] == e['ticks'] and close(a['value'], e['value']) for a, e in zip(actual, expected))

    for item in operation['arguments']['items']:
        row = rows.get(item['node_id'])
        if not row or any(row[k] != item[k] for k in ('source_id', 'media_path', 'start_ticks', 'end_ticks', 'source_in_ticks', 'source_out_ticks')):
            raise BridgeError('Source or exact timing changed during reframe')
        if row['speed'] != 1 or row.get('speed_reversed') is not False:
            raise BridgeError('Forward playback changed or unavailable at readback')
        motion = row['motion']
        if not motion['anchor_time_varying'] or motion['position_time_varying'] or motion['scale_time_varying'] or not keys_match(motion['anchor_keys'], item['keys']) or not close(motion['position'], item['position']) or not close(motion['scale'], item['scale']):
            raise BridgeError('Native Motion/key readback differs from the plan')
        for name in ('Anchor Point', 'Position', 'Scale'):
            old, observed = prop(before, item['node_id'], name), prop(after, item['node_id'], name)
            if any(p.get(flag) for p in (old, observed) for flag in ('valueUnavailable', 'keyframesUnavailable')):
                raise BridgeError('Native Motion snapshot unavailable')
            if name == 'Anchor Point':
                if not keys_match(observed.get('keys', []), item['keys']):
                    raise BridgeError('Snapshot keys differ from the plan')
                observed.pop('keys')
            elif not close(observed['value'], item['position'] if name == 'Position' else item['scale']):
                raise BridgeError('Snapshot Motion differs from the plan')
            observed['value'] = old['value']
    preview_normalized = False
    if after_reopen:
        # Premiere 26.3 normalizes preview raster on reopen after canvas resize.
        # Only this exact pair is eligible; cuts/components/settings remain strict.
        expected_preview = (before.get('settings', {}).get('previewFrameWidth'), before.get('settings', {}).get('previewFrameHeight'))
        actual_preview = (after.get('settings', {}).get('previewFrameWidth'), after.get('settings', {}).get('previewFrameHeight'))
        if expected_preview != actual_preview and actual_preview == (1080, 1920):
            preview_normalized = True
            for field in ('previewFrameWidth', 'previewFrameHeight'):
                after['settings'][field] = before['settings'][field]
    if before != after:
        raise BridgeError('Protected timeline state differs from the reframe baseline')
    return {'project_path': plan['project_path'], 'sequence_id': plan['sequence_id'],
            'width': 1080, 'height': 1920, 'bad_records': [], 'keyed_items': len(operation['arguments']['items']),
            'total_keys': sum(len(i['keys']) for i in operation['arguments']['items']),
            'revision': inspection['bridge_baseline']['revision'], 'preview_normalized_on_reopen': preview_normalized, 'verification': 'exact_keys_and_bounded_protected_state',
            'interpolation': 'not_read_back', 'persistence': 'reopen_not_run', 'rendered': 'not_run'}


class ReframeSession:
    def __init__(self, profile_path, client=None):
        self.client = client if client is not None else PremiereBridge(Profile.load(profile_path))

    def inspect_active(self):
        return inspect_active(self.client)

    def duplicate(self, source, sequence_name, work_dir, timeout=120):
        if not source.get('bridge_baseline'):
            raise BridgeError('A fresh Lab inspection is required before duplication')
        operation = {'schema': 'edit.native-operation/v1', 'stage': 'reframe',
                     'operation_id': 'reframe-clone-' + uuid.uuid4().hex,
                     'tool': 'lab_duplicate_vertical_sequence',
                     'arguments': {'source_sequence_id': source['sequence_id'], 'sequence_name': sequence_name},
                     'target': {'project_path': source['project_path'], 'sequence_id': source['sequence_id'],
                                'expected_revision': source['bridge_baseline']['revision']},
                     'intended_changes': ['create and activate a 1080x1920 duplicate in the same project'],
                     'protected_state': ['source sequence; cloned source ranges, audio and bounded snapshot fields except new IDs/canvas']}
        receipt = work_dir / 'duplicate.bridge-operation.json'
        result = self._execute(operation, receipt, timeout)
        if (result.get('project_path') != source['project_path'] or
                result.get('source_sequence_id') != source['sequence_id'] or
                result.get('sequence_name') != sequence_name or
                not result.get('sequence_id') or result['sequence_id'] == source['sequence_id']):
            raise BridgeError('Duplicate identity readback failed; inspect the original receipt')
        return result

    def _execute(self, operation, receipt_path, timeout):
        return execute_operation(self.client, operation, receipt_path, timeout)

    def picture_operation(self, tool, arguments, receipt_path, timeout=180):
        """Bounded native picture operations with a fresh revision and durable receipt."""
        allowed = {'lab_update_static_panel_geometry', 'lab_repair_anchor_x_keys', 'lab_split_reframe_shots', 'lab_reframe_embedded_panels',
                   'lab_export_reframe_frames', 'save_project', 'set_active_sequence'}
        if tool not in allowed:
            raise BridgeError('Unsupported picture preparation operation')
        if Path(receipt_path).exists():
            raise BridgeError('Existing attempt must be reconciled, never replayed')
        current = self.inspect_active()
        operation = {'schema': 'edit.native-operation/v1', 'stage': 'reframe',
                     'operation_id': 'reframe-picture-' + uuid.uuid4().hex,
                     'tool': tool, 'arguments': arguments,
                     'target': {'project_path': current['project_path'],
                                'sequence_id': current['sequence_id'],
                                'expected_revision': current['bridge_baseline']['revision']},
                     'intended_changes': [tool],
                     'protected_state': ['dialogue, source clock, unrelated timeline state']}
        return self._execute(operation, Path(receipt_path), timeout)

    def verify(self, plan):
        return verify_fresh(plan, self.inspect_active())

    def apply(self, plan_path, plan, timeout=120):
        receipt = plan_path.with_suffix('.bridge-operation.json')
        if receipt.exists():
            raise BridgeError(f'An attempt exists; reconcile its operation ID in {receipt}')
        operation = fresh_operation(plan, 'reframe-motion-' + uuid.uuid4().hex)
        applied = self._execute(operation, receipt, timeout)
        verified = self.verify(plan)
        save = {'schema': 'edit.native-operation/v1', 'stage': 'reframe',
                'operation_id': operation['operation_id'] + '-save', 'tool': 'save_project', 'arguments': {},
                'target': {'project_path': plan['project_path'], 'sequence_id': plan['sequence_id'], 'expected_revision': verified['revision']},
                'intended_changes': ['save the verified in-memory Motion application'], 'protected_state': ['all timeline state']}
        self._execute(save, plan_path.with_suffix('.bridge-save.json'), timeout)
        final_inspection = self.inspect_active()
        after_save = verify_fresh(plan, final_inspection)
        if after_save['revision'] != verified['revision']:
            raise BridgeError('Protected state changed across Motion save; inspect the original receipts')
        handoff_path = plan_path.with_suffix('.stage-handoff.json')
        write_handoff(handoff_path, stage='reframe', before=plan['bridge_baseline']['snapshot'],
                      after=final_inspection['bridge_baseline']['snapshot'],
                      before_revision=operation['target']['expected_revision'], after_revision=after_save['revision'],
                      receipts=[receipt, plan_path.with_suffix('.bridge-save.json')])
        return {**applied, 'verification': after_save, 'receipt': str(receipt), 'handoff': str(handoff_path),
                'status': 'HOST_REPORTED_MOTION_AND_SAVE', 'persistence': 'reopen_not_run', 'rendered': 'not_run'}

    def repair(self, plan_path, plan, timeout=120):
        receipt = plan_path.with_suffix('.bridge-operation.json')
        if receipt.exists():
            raise BridgeError(f'An attempt exists; reconcile its operation ID in {receipt}')
        operation = repair_operation(plan, 'reframe-x-' + uuid.uuid4().hex)
        applied = self._execute(operation, receipt, timeout)
        fresh = self.client.inspect('lab_snapshot', {})
        if fresh['projectPath'] != plan['project_path'] or fresh['sequenceId'] != plan['sequence_id']:
            raise BridgeError('Target changed after repair; do not save another project')
        save = {'schema': 'edit.native-operation/v1', 'stage': 'reframe',
                'operation_id': operation['operation_id'] + '-save', 'tool': 'save_project', 'arguments': {},
                'target': {'project_path': fresh['projectPath'], 'sequence_id': fresh['sequenceId'], 'expected_revision': fresh['revision']},
                'intended_changes': ['save the verified in-memory repair'],
                'protected_state': ['all timeline state']}
        self._execute(save, plan_path.with_suffix('.bridge-save.json'), timeout)
        after_save = self.client.inspect('lab_snapshot', {})
        if (after_save['projectPath'], after_save['sequenceId'], after_save['revision']) != (fresh['projectPath'], fresh['sequenceId'], fresh['revision']):
            raise BridgeError('Protected timeline state changed across save; inspect the original receipts')
        return {**applied, 'bad_keys': [], 'status': 'HOST_REPORTED_REPAIR_AND_SAVE',
                'receipt': str(receipt), 'persistence': 'reopen_not_run', 'rendered': 'not_run'}

    def close(self):
        self.client.close()

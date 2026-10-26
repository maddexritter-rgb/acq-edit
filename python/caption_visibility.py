"""Native visibility transport for caption-clips-owned text and shadow layers."""
import copy
from common import require, fingerprint, inside, sha, plan, read


def ranges(spec):
    if 'captionVisibility' not in spec:
        return []
    value = spec['captionVisibility']
    require(spec['backend'] in ['filmcraft','resolve'], 'Native caption visibility requires FilmCraft or Resolve; no backend switch or burned overlay fallback')
    require(spec.get('captionContract'), 'Caption visibility requires the caption-clips native ownership contract')
    require(isinstance(value, dict) and set(value) == {'schema', 'owner', 'hiddenRanges', 'reason', 'evidence'}
            and value['schema'] == 'acq-edit/caption-visibility-v1' and value['owner'] == 'caption-clips', 'Explicit caption-clips visibility handoff required')
    require(all(isinstance(value[k], str) and value[k].strip() for k in ['reason', 'evidence']), 'Caption visibility needs a reason and observed geometry evidence')
    duration = sum(c['frames'] for c in spec['cuts'])
    rows = value['hiddenRanges']
    require(isinstance(rows, list) and rows, 'Nonempty hidden caption ranges required; remove the handoff to restore visibility')
    previous = 0
    for row in rows:
        require(isinstance(row, dict) and set(row) == {'startFrame', 'endFrame'}, 'Exact hidden caption frame range required')
        start, end = row['startFrame'], row['endFrame']
        require(type(start) == int and type(end) == int and previous <= start < end <= duration, 'Hidden caption ranges must be ordered, nonoverlapping and inside the clip')
        previous = end
    return rows


def masked_opacity(original, card, hidden, frame_ticks):
    """Keep the owning arrival curve; gate only explicitly hidden integer ticks."""
    start, end = card['start_frame'], card['end_frame']
    windows = [(max(start, r['startFrame'])-start, min(end, r['endFrame'])-start) for r in hidden
               if r['startFrame'] < end and r['endFrame'] > start]
    if not windows:
        return copy.deepcopy(original)
    windows = [(a*frame_ticks, b*frame_ticks) for a,b in windows]
    keys = original.get('keyframes', [])
    require(all(k['interp'] == 'Linear' and set(k['value']) == {'Float'} for k in keys), 'Unsupported owning caption opacity curve')
    def sample(tick):
        if not keys: return original['value']['Float']
        if tick <= keys[0]['time']: return keys[0]['value']['Float']
        for left, right in zip(keys, keys[1:]):
            if tick <= right['time']:
                weight = (tick-left['time'])/(right['time']-left['time'])
                return left['value']['Float'] + weight*(right['value']['Float']-left['value']['Float'])
        return keys[-1]['value']['Float']
    def hidden_at(tick): return any(a <= tick < b for a,b in windows)
    times = {0, *(k['time'] for k in keys)}
    for a,b in windows:
        times.update([a,b])
        if a: times.add(a-1)  # last visible integer tick; do not fade into a hidden range
    return {'value': {'Float': 0. if hidden_at(0) else original['value']['Float']},
            'keyframes': [{'time': t, 'value': {'Float': 0. if hidden_at(t) else sample(t)},
                           'interp': 'Hold' if hidden_at(t) else 'Linear'} for t in sorted(times)]}


def prepare(project, packet):
    previous_path = inside(project['root'], packet['previousPlan'])
    require(sha(previous_path) == packet['previousPlanSha256'], 'Previous caption plan changed')
    previous, current = plan(project, {'plan': str(previous_path)}), plan(project, packet)
    require(previous['backend'] == current['backend'] == project['backend'] and project['backend'] in ['filmcraft','resolve'], 'Caption visibility requires the fixed native backend')
    require(previous.get('captionContract') and current.get('captionContract'), 'Owned native captions required')
    require(not previous.get('hookContract') and not current.get('hookContract'), 'Legacy headline projects require their pinned toolkit version; preserve existing work')
    require({k:v for k,v in previous.items() if k != 'captionVisibility'} == {k:v for k,v in current.items() if k != 'captionVisibility'},
            'Caption visibility cannot change cuts, text, style, framing, audio or other plan fields')
    require(previous.get('captionVisibility') != current.get('captionVisibility'), 'Caption visibility request makes no change')
    ranges(previous); ranges(current)
    return previous, current


def targets(data, previous, current, prepared, frame_ticks):
    from caption_plan import opacity_for
    seq = data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    result = []
    for track_index in range(1,4):
        track = seq['video_tracks'][track_index]
        for index, card in enumerate(prepared['cards']):
            old, new = (opacity_for(spec, prepared, card, frame_ticks) for spec in [previous,current])
            if old == new: continue
            require(not track['locked'], 'Caption visibility target track is locked; preserve manual state')
            item = track['items'][index]
            original = next(e['params']['opacity'] for e in item['effects'] if e['effect'] == 'opacity')
            result.append({'track':track_index,'index':index,'clip':item['id'],'start':item['start'], 'old':original,'new':new})
    require(result, 'Hidden ranges do not affect any owned captions')
    return result


def apply(client, changes):
    from caption_plan import write_parameter
    for change in changes:
        args = {'clip':change['clip'],'effect':'opacity','param':'opacity'}
        # Reset Parameter preserves animation in FilmCraft. Delete the exact old
        # keys first, then write the owner-derived replacement through its API.
        for key in change['old'].get('keyframes', []):
            client.run('effects.deleteKeyframe', {**args,'mediaTime':key['time']})
        write_parameter(client, change['clip'], 'opacity', 'opacity', change['new'], change['start'])


def verify_protected(before, after, changes, destination):
    require(before['view']['active_sequence'] == after['view']['active_sequence'], 'Caption visibility changed active sequence')
    expected, actual = copy.deepcopy(before['project']), copy.deepcopy(after['project'])
    key = str(before['view']['active_sequence'])
    old_seq, new_seq = (p['items'][key]['kind']['Sequence'] for p in [expected,actual])
    for change in changes:
        old_item = old_seq['video_tracks'][change['track']]['items'][change['index']]
        new_item = new_seq['video_tracks'][change['track']]['items'][change['index']]
        require(old_item['id'] == new_item['id'] == change['clip'], 'Caption visibility target identity changed')
        # Exact new opacity is checked by the native caption verifier first.
        for effect in old_item['effects']:
            if effect['effect'] == 'opacity':
                effect['params']['opacity'] = copy.deepcopy(next(e['params']['opacity'] for e in new_item['effects'] if e['effect'] == 'opacity'))
    expected['name'] = expected['root']['name'] = destination
    require(fingerprint(expected) == fingerprint(actual), 'Caption visibility changed protected native state')

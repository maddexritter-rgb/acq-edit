"""Replace a selected music source without moving cuts or existing automation.

Selection and auditioning remain owned by music. This bounded operation keeps
the source offset fixed; a different section needs a separately qualified edit.
"""
import copy
import json
import subprocess
from fractions import Fraction
from pathlib import Path
from common import inside, require, sha, plan, fingerprint

TICKS = 254016000000


def compare_plans(previous, current, targets):
    require(isinstance(targets, list) and targets and all(type(i) == int for i in targets)
            and len(set(targets)) == len(targets), 'Select unique music indices')
    require({k: v for k, v in previous.items() if k not in ['sources', 'audio']} ==
            {k: v for k, v in current.items() if k not in ['sources', 'audio']},
            'Music replacement preserves every other plan field')
    old_audio, new_audio = previous.get('audio', {}), current.get('audio', {})
    require({k: v for k, v in old_audio.items() if k != 'music'} ==
            {k: v for k, v in new_audio.items() if k != 'music'}, 'Dialogue treatment changed')
    old, new = old_audio.get('music', []), new_audio.get('music', [])
    require(len(old) == len(new) and all(0 <= i < len(old) for i in targets),
            'Music order/count and target coverage must remain fixed')
    old_sources, new_sources = previous['sources'], current['sources']
    require(new_sources[:len(old_sources)] == old_sources, 'Existing source records must remain intact')
    ids = [s['id'] for s in new_sources]
    require(len(ids) == len(set(ids)), 'Source IDs must be unique')
    added = new_sources[len(old_sources):]
    require(len(added) == len(targets) and {s['id'] for s in added} == {new[i]['sourceId'] for i in targets},
            'Append exactly one new source per selected music bed')
    require(len({s['path'] for s in new_sources}) == len(new_sources), 'Replacement source paths must be distinct')
    changed_fields = ['sourceId', 'receiptPath', 'receiptSha256']
    for i, (a, b) in enumerate(zip(old, new)):
        if i not in targets:
            require(a == b, 'Unselected music changed')
            continue
        require({k: v for k, v in a.items() if k not in changed_fields} ==
                {k: v for k, v in b.items() if k not in changed_fields},
                'Music replacement preserves source offset, placement, duration, gain and fades')
        require(all(a[k] != b[k] for k in changed_fields), 'Use a new source and a new selection/audition receipt')
        old_source = next(s for s in old_sources if s['id'] == a['sourceId'])
        new_source = next(s for s in added if s['id'] == b['sourceId'])
        require(old_source['sha256'] != new_source['sha256'], 'Replacement music content is unchanged')
    return targets


def probe_source(source):
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', source['path']]))
    streams = info.get('streams', [])
    require(len(streams) == 1 and streams[0].get('codec_type') == 'audio',
            'Music replacement requires an audio-only source with exactly one stream')
    return streams[0]


def validate_sources(previous, current, targets):
    """Prepared PCM gives an exact source extent before any native mutation."""
    for index in targets:
        a, b = previous['audio']['music'][index], current['audio']['music'][index]
        old = probe_source(next(s for s in previous['sources'] if s['id'] == a['sourceId']))
        source = next(s for s in current['sources'] if s['id'] == b['sourceId'])
        new = probe_source(source)
        require(new.get('codec_name', '').startswith('pcm_'), 'Prepare replacement music as PCM before native replacement')
        require(int(new['sample_rate']) == int(old['sample_rate']) == current['sampleRate'],
                'Replacement and original music must use the project sample rate')
        require(new.get('channels') == old.get('channels') and new.get('channels') in [1, 2],
                'Replacement music must preserve mono/stereo channel count')
        require(new.get('duration_ts') is not None and new.get('time_base'), 'Replacement source extent is unknown')
        extent = Fraction(new['duration_ts']) * Fraction(new['time_base']) * current['sampleRate']
        require(extent >= b['sourceInSample'] + b['samples'], 'Replacement music is too short for the preserved source range')
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', source['path'], '-f', 'null', '-'],
                       check=True, capture_output=True)
        require(sha(source['path']) == source['sha256'], 'Replacement source changed during preflight')


def prepare(project, packet):
    previous = inside(project['root'], packet['previousPlan'])
    require(sha(previous) == packet['previousPlanSha256'], 'Previous published plan changed')
    old, new = plan(project, {'plan': str(previous)}), plan(project, packet)
    indices = compare_plans(old, new, packet['musicIndices'])
    validate_sources(old, new, indices)
    return old, new, indices


def filmcraft_items(data, spec, targets=()):
    seq = data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    require(len(seq['audio_tracks']) >= 2, 'Native music track missing')
    track = seq['audio_tracks'][1]
    clips, beds = track['items'], spec.get('audio', {}).get('music', [])
    require(len(clips) == len(beds), 'Native music coverage changed')
    ft = TICKS * spec['fps']['denominator'] // spec['fps']['numerator']
    st = TICKS // spec['sampleRate']
    for index, (clip, bed) in enumerate(zip(clips, beds)):
        source = next(s for s in spec['sources'] if s['id'] == bed['sourceId'])
        media = data['project']['items'][str(clip['item'])]['kind'].get('Media', {})
        require(Path(media.get('media', {}).get('File', {}).get('path', '')).resolve() == Path(source['path']).resolve(),
                'Native music source differs from pinned plan')
        require((clip['start'], clip['duration'], clip['source_in']) ==
                (bed['startFrame'] * ft, bed['samples'] * st, bed['sourceInSample'] * st), 'Native music timing changed')
        if index in targets:
            require(not track.get('locked') and clip.get('link') is None and clip.get('group') is None,
                    'Music target is locked, linked or grouped')
            require(clip.get('speed') == 1 and not clip.get('reverse') and clip.get('frame_hold') is None
                    and clip.get('multicam') is None, 'Retimed music replacement is unsupported')
            remap = next((e for e in clip['effects'] if e['effect'] == 'time_remap'), None)
            require(remap is None or remap['params']['speed'] == {'value': {'Float': 100.0}}, 'Animated music retiming is unsupported')
            require(not clip.get('source_channels'), 'Custom music channel routing requires separate reconciliation')
    return clips


def verify_filmcraft_replacement(before, after, previous, current, indices, destination):
    old_clips = filmcraft_items(before, previous, indices)
    new_clips = filmcraft_items(after, current)
    expected, actual = copy.deepcopy(before['project']), copy.deepcopy(after['project'])
    expected['name'] = expected['root']['name'] = destination
    added = set(actual['items']) - set(expected['items'])
    require(len(added) == len(indices) and set(expected['items']) <= set(actual['items']),
            'Replacement must import exactly one native item per music target')
    require(actual['next_id'] == expected['next_id'] + len(added)
            and added == {str(i) for i in range(expected['next_id'], actual['next_id'])}, 'Unexpected native ID allocation')
    selected = expected['items'][str(before['view']['active_sequence'])]['kind']['Sequence']['audio_tracks'][1]['items']
    imported = []
    for index in indices:
        old, new = old_clips[index], new_clips[index]
        key = str(new['item'])
        require(key in added and key not in imported, 'Replacement did not bind a unique new media item')
        imported.append(key)
        media = actual['items'][key]
        require(media['kind'].get('Media') and media['id'] == new['item'] and media['label'] == old['label'],
                'Replacement native media identity or label differs')
        selected[index]['item'] = new['item']
        expected['items'][key] = copy.deepcopy(media)
    expected['root']['children'] += [{'Item': int(i)} for i in imported]
    expected['next_id'] = actual['next_id']
    require(before['view']['active_sequence'] == after['view']['active_sequence'] and fingerprint(expected) == fingerprint(actual),
            'Music replacement changed protected native state, routing or automation')

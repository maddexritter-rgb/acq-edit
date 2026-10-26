"""Validate reviewed subject composition, separately from source-safe crop math.

The framing owner supplies footage-specific complete-head observations and a
profile. Detection confidence is not a silhouette measurement or visual approval.
"""
import hashlib
import json
import math


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def validate(spec, review, profiles):
    require(review.get('schema') == 'acq-edit/composition-review-v1', 'Composition review schema required')
    require(review.get('owner') == 'horizontal-to-vertical', 'Framing owner review required')
    require(review.get('shotsSha256') == digest(spec['framing']['shots']), 'Composition observations belong to different crops')
    expected = {}
    for cut in spec['cuts']:
        shot = spec['framing']['shots'][cut['id']]
        if shot['mode'] == 'panel-layout':
            for panel in shot['panels']:
                expected[(cut['id'], panel['id'])] = (cut, panel['crop'], panel['sourceRange'], 'panel')
        else:
            source = next(s for s in spec['sources'] if s['id'] == cut['sourceId'])
            binding = {'sourceId': source['id'], 'sha256': source['sha256'], 'inFrame': cut['sourceInFrame'], 'frames': cut['frames']}
            expected[(cut['id'], None)] = (cut, shot, binding, 'full')
    actual = {(e['cutId'], e.get('panelId')): e for e in review['entries']}
    require(len(actual) == len(review['entries']) and set(actual) == set(expected), 'Review every visible cut and panel exactly once')
    metrics, panel_sizes = [], {}
    fps = spec['fps']['numerator'] / spec['fps']['denominator']
    for key, (cut, crop, binding, layout) in expected.items():
        entry = actual[key]
        require(entry['sourceRange'] == binding, 'Stale source-clock composition evidence')
        require(entry.get('headBoundsMethod') in ('manual-silhouette', 'visually-calibrated-envelope'), 'Complete head including hat/hair must be inspected')
        require(entry.get('visualInspection') == 'source-frames-reviewed', 'Inspect source frames; detector success is not composition approval')
        policy = profiles[layout]
        samples = entry['samples']; frames = [s['frame'] for s in samples]
        require(frames == sorted(set(frames)) and frames and frames[0] == 0 and frames[-1] == cut['frames']-1 and cut['frames']//2 in frames, 'Review first, middle, last and movement samples')
        require(all(type(f) == int and 0 <= f < cut['frames'] for f in frames), 'Invalid observation clock')
        require(max([b-a for a,b in zip(frames, frames[1:])] or [0]) <= max(1, math.floor(fps * profiles['maxSampleGapSeconds'])), 'Composition sampling is too sparse')
        sizes = []
        for sample in samples:
            bounds = sample['head']; require(len(bounds) == 4 and all(type(v) in (int,float) and math.isfinite(v) for v in bounds), 'Finite complete-head bounds required')
            left, top, right, bottom = bounds
            require(0 <= left < right <= crop['sourceWidth'] and 0 <= top < bottom <= crop['sourceHeight'], 'Invalid source head bounds')
            x = crop['xByFrame'][sample['frame']] if crop['mode'] == 'tracked-crop' else crop['x']
            room = (top-crop['y'])/crop['height']; size = (bottom-top)/crop['height']
            side = min((left-x)/crop['width'], (x+crop['width']-right)/crop['width'])
            require(policy['headroom'][0] <= room <= policy['headroom'][1], f'{key} frame {sample["frame"]}: headroom outside reviewed profile')
            require(policy['headHeight'][0] <= size <= policy['headHeight'][1], f'{key}: subject size outside reviewed profile')
            require(side >= policy['minSideClearance'] and bottom <= crop['y']+crop['height'], f'{key}: complete head intersects crop safety margin')
            require(sample.get('evidence', {}).get('path') and sample['evidence'].get('sha256'), 'Source-frame evidence required')
            sizes.append(size)
            metrics.append({'cutId':key[0], 'panelId':key[1], 'frame':sample['frame'], 'headroom':room, 'headHeight':size, 'sideClearance':side})
        if layout == 'panel': panel_sizes.setdefault(key[0], []).append(sum(sizes)/len(sizes))
    for key, sizes in panel_sizes.items():
        require(max(sizes)/min(sizes) <= profiles['maxPanelHeadRatio'], f'{key}: split participants have mismatched apparent size')
    return {'status': 'composition-measurements-pass-awaiting-native-visual-review', 'samples':metrics, 'humanApproved':False}

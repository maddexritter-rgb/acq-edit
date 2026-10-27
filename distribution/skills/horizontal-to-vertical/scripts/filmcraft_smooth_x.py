"""Plan/apply fixed crops or deliberate dense Anchor-X tracking with locked Y.

Consumes exact per-frame tracking; does not choose shots or detect a new subject.
Requires numpy/scipy and the sibling edit skill's Filmcraft client.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import savgol_filter

TICKS = 254016000000


def smooth_x(values, sigma_frames=10):
    """Filter one source-continuous run; callers split camera/layout/source cuts."""
    raw = np.asarray(values, dtype=float)
    if raw.ndim != 1 or not len(raw) or not np.isfinite(raw).all() or not np.isfinite(sigma_frames) or sigma_frames <= 0:
        raise ValueError('Finite dense X observations and positive smoothing required')
    window = min(7, len(raw) if len(raw) % 2 else len(raw)-1)
    clean = savgol_filter(raw, window, 2, mode='interp') if window >= 3 else raw
    return gaussian_filter1d(clean, sigma=sigma_frames, mode='nearest')


def dense_subject_x(view, count, max_gap=6, fallbacks=()):
    """Preserve raw detections; label every interpolated or authored frame."""
    faces = view.get('denseFaces', [])
    if len(faces) != count or view.get('denseFrameIndices') != list(range(count)):
        raise ValueError('Every displayed source frame needs detector evidence')
    xs = np.full(count, np.nan); origins = ['missing'] * count
    for i, face in enumerate(faces):
        if face is None:
            continue
        if len(face) != 5 or not all(type(v) in (int,float) and np.isfinite(v) for v in face) or not 0 < face[4] <= 1 or face[2] <= 0 or face[3] <= 0:
            raise ValueError('Invalid detection; manual positions must remain separate fallbacks')
        xs[i] = face[0]; origins[i] = 'detected'
    for fallback in fallbacks:
        start, end, x = fallback['startFrame'], fallback['endFrame'], fallback['x']
        if type(start) != int or type(end) != int or not 0 <= start < end <= count or type(x) not in (int,float) or not np.isfinite(x):
            raise ValueError('Invalid explicit tracking fallback')
        evidence = fallback.get('evidence', [])
        if not fallback.get('reason') or not evidence or any(digest(e['path']) != e['sha256'] for e in evidence):
            raise ValueError('Tracking fallback needs pinned inspected source evidence and reason')
        for i in range(start,end):
            if origins[i] != 'missing':
                raise ValueError('Fallback may replace only missing detections')
            xs[i] = x; origins[i] = 'manual-fallback'
    i = 0
    while i < count:
        if origins[i] != 'missing':
            i += 1; continue
        start = i
        while i < count and origins[i] == 'missing':i += 1
        if start == 0 or i == count or i-start > max_gap or origins[start-1] != 'detected' or origins[i] != 'detected':
            raise ValueError(f'Unresolved detector gap [{start},{i}); inspect coverage or supply explicit fallback')
        xs[start:i] = np.linspace(xs[start-1], xs[i], i-start+2)[1:-1]
        origins[start:i] = ['interpolated'] * (i-start)
    return xs, origins


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_inspection(value):
    value = copy.deepcopy(value)
    for key in ('playhead', 'selection', 'gapSelection', 'transitionSelection'):
        value.pop(key, None)
    return value


def protected(value):
    value = stable_inspection(value)
    for track in value['video']:
        for item in track['items']:
            for effect in item['effects']:
                if effect['effect'] == 'motion':
                    for key in ('anchor', 'scale'):
                        effect['params'].pop(key, None)
    return value


def make_plan(project, inspection, tracking, anchor_y, scale, sigma_frames, single_run=False,
              motion_mode='track'):
    assert motion_mode in ('fixed', 'track'), 'Choose fixed crops or explicit tracking'
    assert sigma_frames > 0 and scale > 0
    s = inspection['settings']
    assert s['par'] == [1, 1], 'Only square-pixel full-frame sequences are supported'
    ft = Fraction(TICKS * s['frame_rate']['den'], s['frame_rate']['num'])
    assert ft.denominator == 1, 'Unsupported fractional tick grid'
    ft = int(ft)
    assert abs(tracking['fps'] - TICKS / ft) < .001
    width, height = tracking['width'], tracking['height']
    hx, hy = s['width'] / (2 * scale / 100), s['height'] / (2 * scale / 100)
    assert hx <= width / 2 and hy <= height / 2, 'Scale cannot fill the frame'
    assert hy <= anchor_y <= height - hy, 'Locked Y would reveal a source edge'
    assert all(not t['items'] for t in inspection['video'][1:]), 'Resolve panels/coverage first'
    items, tracks = inspection['video'][0]['items'], tracking['items']
    assert len(items) == len(tracks) and items, 'Incomplete tracking coverage'
    runs, current, last_run = [], [], None
    for i in range(len(items)):
        c, d = items[i], tracks[i]
        for key in ('clip', 'startFrame', 'endFrame', 'sourceIn', 'sourceOut'):
            assert c[key] == d[key], f'Stale tracking: item {i}, {key}'
        n = c['durationFrames']
        assert c['speed'] == 1 and not c['reverse']
        assert c['end'] - c['start'] == c['sourceOut'] - c['sourceIn'] == n * ft
        assert d['samples'] == n == len(d['face'])
        assert all(len(p) == 2 and all(np.isfinite(p)) and 0 <= p[0] <= 1 for p in d['face'])
        m = next(e['params'] for e in c['effects'] if e['effect'] == 'motion')
        assert m['position']['keyframes'] == m['scale']['keyframes'] == 0
        # The pinned renderer defaults absent rotation to zero and absent uniform
        # scale to true; sparse native projects omit these unmodified parameters.
        assert m.get('rotation', {'value': 'Float(0.0)'})['value'] == 'Float(0.0)'
        assert m.get('uniform_scale', {'value': 'Bool(true)'})['value'] == 'Bool(true)'
        assert m['position']['value'] == f"Vec2(Vec2 {{ x: {s['width']/2}, y: {s['height']/2} }})", 'Requires centered static Position'
        run = ('fixed-source-continuous' if motion_mode == 'fixed' else
               'reviewed-single-camera' if single_run else d.get('run'))
        assert run is not None, 'Assign reviewed camera/framing run IDs or --single-camera-run'
        # Timeline adjacency is not source continuity. A Gaussian across a removed
        # source passage invents a pan toward the next take before the hard cut.
        source_cut = bool(current and (
            items[i-1]['item'] != c['item'] or items[i-1]['sourceOut'] != c['sourceIn']))
        if current and (source_cut or
                        run != last_run or items[i-1]['end'] != c['start']):
            runs.append(current)
            current = []
        current.append(i)
        last_run = run
    runs.append(current)
    planned = [None] * len(items)
    for run in runs:
        if motion_mode == 'fixed':
            # A source-continuous subdivision is not a new shot calibration.
            x = np.clip(np.median([p[0] for i in run for p in tracks[i]['face']]) * width,
                        hx, width - hx)
            for i in run:
                planned[i] = {'clip': items[i]['clip'],
                              'anchor': [round(float(x), 3), anchor_y], 'keys': []}
            continue
        raw = np.array([p[0] for i in run for p in tracks[i]['face']])
        smooth = smooth_x(raw, sigma_frames) * width
        smooth = np.clip(smooth, hx, width - hx)
        cursor = 0
        for i in run:
            c, d = items[i], tracks[i]
            xs = smooth[cursor:cursor+d['samples']]
            planned[i] = {'clip': c['clip'], 'anchor': [round(float(xs[0]), 3), anchor_y], 'keys': [
                {'tick': c['start'] + j*ft, 'source_tick': c['sourceIn'] + j*ft,
                 'value': [round(float(x), 3), anchor_y]} for j, x in enumerate(xs)]}
            cursor += d['samples']
        assert cursor == len(smooth)
    return {'schema': 'horizontal-to-vertical.filmcraft-framing/v3',
            'project': str(Path(project).resolve()), 'project_sha256': digest(project),
            'inspection': inspection, 'anchor_y': anchor_y, 'scale_percent': scale,
            'motion_mode': motion_mode, 'sigma_frames': sigma_frames, 'runs': runs, 'items': planned,
            'key_count': sum(len(p['keys']) for p in planned)}


def apply_plan(plan, binary, session, output):
    assert plan.get('schema') == 'horizontal-to-vertical.filmcraft-framing/v3', 'Replan older framing recipes with continuous-run crop calibration'
    output = Path(output).resolve()
    assert not output.exists(), 'Never overwrite a reviewed project'
    assert digest(plan['project']) == plan['project_sha256'], 'Project changed after planning'
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'edit' / 'scripts'))
    from filmcraft_client import Filmcraft
    fc = Filmcraft(binary, session, plan['project'])
    try:
        before = fc.tool('sequence_inspect')
        assert stable_inspection(before) == stable_inspection(plan['inspection']), 'Native baseline changed'
        for i, p in enumerate(plan['items']):
            c = before['video'][0]['items'][i]
            m = next(e['params'] for e in c['effects'] if e['effect'] == 'motion')
            if m['anchor']['keyframes']:
                fc.run('effects.toggleAnimation', {'clip': p['clip'], 'effect': 'motion', 'param': 'anchor'})
            fc.run('effects.setParam', {'clip': p['clip'], 'effect': 'motion', 'param': 'anchor',
                                      'value': p['anchor']})
            fc.run('effects.setParam', {'clip': p['clip'], 'effect': 'motion', 'param': 'scale',
                                      'value': plan['scale_percent']})
            for key in p['keys']:
                fc.run('effects.setParam', {'clip': p['clip'], 'effect': 'motion', 'param': 'anchor',
                                          'value': key['value'], 'time': key['tick'], 'keyframe': True})
        assert digest(plan['project']) == plan['project_sha256'], 'Input changed during execution'
        fc.run('file.saveAs', {'path': str(output)})
        after = fc.tool('sequence_inspect')
        assert protected(before) == protected(after), 'Protected edit/effect state changed'
        saved = json.loads(output.read_text())
        seq = saved['project']['items'][str(before['id'])]['kind']['Sequence']
        clips = seq['video_tracks'][0]['items']
        assert len(clips) == len(plan['items'])
        for i, p in enumerate(plan['items']):
            m = next(e['params'] for e in clips[i]['effects'] if e['effect'] == 'motion')
            keys = m['anchor'].get('keyframes', [])
            assert m['anchor']['value']['Vec2'] == dict(zip(('x', 'y'), p['anchor']))
            assert len(keys) == len(p['keys'])
            for j, expected in enumerate(p['keys']):
                k = keys[j]
                assert k['time'] == expected['source_tick'] and k['interp'] == 'Linear'
                assert [k['value']['Vec2']['x'], k['value']['Vec2']['y']] == expected['value']
        return after
    finally:
        fc.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'inspection', 'tracking', 'plan'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--anchor-y', required=True, type=float, help='Measured locked source-space Y pixels')
    p.add_argument('--scale', required=True, type=float, help='Native Motion Scale percent')
    p.add_argument('--sigma-frames', default=10.0, type=float)
    p.add_argument('--motion-mode', choices=('fixed', 'track'), default='track',
                   help='Dense native tracking by default; fixed requires a reviewed exception')
    p.add_argument('--single-camera-run', action='store_true',
                   help='Confirm compatible camera/framing; source-time cuts still reset tracking')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--binary', type=Path)
    p.add_argument('--session', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    assert not a.plan.exists(), 'Use a new plan path'
    plan = make_plan(a.project, json.loads(a.inspection.read_text()), json.loads(a.tracking.read_text()),
                     a.anchor_y, a.scale, a.sigma_frames, a.single_camera_run, a.motion_mode)
    a.plan.write_text(json.dumps(plan, indent=2))
    if a.apply:
        assert a.binary and a.session and a.output
        result = apply_plan(plan, a.binary, a.session, a.output)
        a.plan.with_suffix('.readback.json').write_text(json.dumps(result, indent=2))
    print(json.dumps({'keys': plan['key_count'], 'runs': len(plan['runs']), 'plan': str(a.plan), 'applied': a.apply}))


if __name__ == '__main__':
    main()

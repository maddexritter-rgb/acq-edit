"""Validate Assembly Design's camera/layout decisions; never choose cameras here."""
import json
import subprocess
from fractions import Fraction
from common import inside, require, read, sha, fingerprint


def panel_spec(spec, cut, panel):
    source = panel['sourceRange']
    return {**spec, 'width': panel['rect']['width'], 'height': panel['rect']['height'],
            'cuts': [{**cut, 'id': panel['id'], 'sourceId': source['sourceId'],
                      'sourceInFrame': source['inFrame'], 'recordFrame': 0}],
            'framing': {**spec['framing'], 'shots': {panel['id']: panel['crop']}}}


def validate(project, spec, cut, layout, probes=None):
    probes = probes if probes is not None else {}
    require(spec['backend'] == 'filmcraft',
            'Native panel-layout execution is currently FilmCraft only; implement the selected backend, never convert or switch')
    require(set(layout) == {'mode', 'panels', 'cameraReceiptPath', 'cameraReceiptSha256'}, 'Incomplete panel layout')
    panels = layout['panels']
    require(isinstance(panels, list) and 2 <= len(panels) <= 4, 'Panel layouts require two to four explicit cameras')
    ids = [p.get('id') for p in panels]
    require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), 'Unique panel IDs required')
    receipt = inside(project['root'], layout['cameraReceiptPath'])
    require(sha(receipt) == layout['cameraReceiptSha256'], 'Assembly camera receipt changed')
    decision = read(receipt)
    expected = {'schema': 'acq-edit/camera-layout-v1', 'owner': 'assembly-design',
                'cutsSha256': fingerprint(spec['cuts']), 'width': spec['width'], 'height': spec['height'],
                'fps': spec['fps']}
    require(all(decision.get(k) == v for k, v in expected.items()), 'Camera decision is not bound to current assembly and output')
    selection = [{'id': p['id'], 'sourceRange': p.get('sourceRange'), 'rect': p.get('rect')} for p in panels]
    require(decision.get('layouts', {}).get(cut['id']) == selection, 'Panel cameras, sync or layout differ from Assembly Design')
    area = 0
    for index, panel in enumerate(panels):
        require(set(panel) == {'id', 'sourceRange', 'rect', 'crop'}, 'Unknown or incomplete panel operation')
        rect = panel['rect']
        require(isinstance(rect, dict) and set(rect) == {'x', 'y', 'width', 'height'}, 'Panel rectangle required')
        require(all(type(v) is int for v in rect.values()), 'Panel bounds require integer output pixels')
        x, y, w, h = (rect[k] for k in ['x', 'y', 'width', 'height'])
        require(x >= 0 and y >= 0 and w > 0 and h > 0 and x+w <= spec['width'] and y+h <= spec['height'], 'Panel outside output')
        area += w*h
        for other in panels[:index]:
            r = other['rect']
            require(x+w <= r['x'] or r['x']+r['width'] <= x or y+h <= r['y'] or r['y']+r['height'] <= y, 'Panel rectangles overlap')
        span = panel['sourceRange']
        require(isinstance(span, dict) and set(span) == {'sourceId', 'sha256', 'inFrame', 'frames'}, 'Exact panel source range required')
        source = next((s for s in spec['sources'] if s['id'] == span['sourceId']), None)
        require(source and source['sha256'] == span['sha256'], 'Panel source is absent or changed')
        require(type(span['inFrame']) is int and span['inFrame'] >= 0 and type(span['frames']) is int and span['frames'] == cut['frames'], 'Panel duration/sync differs from assembly')
        key = ('panel-coverage', source['id'])
        if key not in probes:
            # Read the indexed frame count when available. Decode/count once per
            # source only when its container does not supply one, never per shot.
            command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-of', 'json', source['path']]
            info = json.loads(subprocess.check_output(command))['streams']
            if info and not str(info[0].get('nb_frames', '')).isdigit():
                info = json.loads(subprocess.check_output(command[:1]+['-count_frames']+command[1:]))['streams']
            probes[key] = info
        info = probes[key]
        require(len(info) == 1, 'Panel source must have picture')
        video = info[0]
        rate = Fraction(spec['fps']['numerator'], spec['fps']['denominator'])
        require(all(video.get(k) and video[k] != '0/0' and Fraction(video[k]) == rate for k in ['r_frame_rate', 'avg_frame_rate']), 'Panel source/timeline rates differ; reconform explicitly')
        require(int(video.get('nb_read_frames', video.get('nb_frames', 0))) >= span['inFrame']+span['frames'], 'Panel exceeds source frame coverage')
        require(panel['crop'].get('mode') in ['fixed-crop', 'tracked-crop'], 'Nested panel layouts are unsupported')
        from framing_plan import validate_framing
        validate_framing(project, panel_spec(spec, cut, panel), probes)
    require(area == spec['width']*spec['height'], 'Panel rectangles must cover the complete output without gaps')


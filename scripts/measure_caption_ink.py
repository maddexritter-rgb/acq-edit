#!/usr/bin/env python3
"""Measure reviewed caption-clips cards in one native calibration session.

Repeated typography shares an isolated render within this run. No cross-run font
cache, caption generation, regrouping, or claim of visual approval is made here.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.local/skills/edit/scripts'),
                str(ROOT / '.local/skills/caption-clips/scripts')]


def measure(handoff, plan, binary, output):
    sys.path.insert(0,str(ROOT/'python'))
    from caption_plan import validate_native_fonts
    from filmcraft_client import Filmcraft
    from filmcraft_caption_contract import prepare_cards, foreground_ink_bounds, centered_text_position, apply_character_styles
    output.mkdir(parents=True, exist_ok=False)
    h = copy.deepcopy(handoff)
    profile_path = Path(h['profile']['path'])
    if hashlib.sha256(profile_path.read_bytes()).hexdigest() != h['profile']['sha256']:
        raise ValueError('Caption profile changed')
    profile = json.loads(profile_path.read_text())
    fps = plan['fps']['numerator'] / plan['fps']['denominator']
    ticks = round(254016000000 / fps)
    cards = prepare_cards(h['cards'], profile, fps, sum(c['frames'] for c in plan['cuts']),
                          picture_cuts=[c['recordFrame'] for c in plan['cuts'][1:]])
    client = Filmcraft(binary, output / 'session')
    results, cache = [], {}
    try:
        validate_native_fonts(client,cards)
        client.run('file.newSequence', {'name': 'Caption ink calibration', 'width': plan['width'],
                   'height': plan['height'], 'fps': fps, 'sampleRate': plan['sampleRate'], 'video': 1, 'audio': 0})
        for i, card in enumerate(cards):
            style = card['style']
            key = json.dumps({'text': card['text'], 'italic': card['italic'],
                'style': {k: v for k, v in style.items() if k not in ('position', 'color')}}, sort_keys=True)
            if key not in cache:
                center = [plan['width']/2, plan['height']/2]
                g = client.run('graphics.newText', {'newClip': True, 'text': card['text'], 'position': center,
                    'font': style['font'], 'fontStyle': style['italicStyle'] if card['italic'] and not style.get('syntheticQuoteItalic') else style['fontStyle'],
                    'size': style['size'], 'time': i*3*ticks, 'seconds': 3/fps, 'track': 0})
                client.run('graphics.set', {'clip': g['clip'], 'layer': g['layer'], 'props': {
                    'align': 'center', 'fill_color': '#ffffff', 'shadow': False, 'stroke': False,
                    'background': False, 'fauxBold': False,
                    'fauxItalic': bool(card['italic'] and style.get('syntheticQuoteItalic'))}})
                apply_character_styles(client, g['clip'], g['layer'], card)
                image = output / f'ink-{i:03d}.png'
                client.run('file.exportFrame', {'path': str(image), 'format': 'png', 'target': 'program', 'time': i*3*ticks})
                box = foreground_ink_bounds(image.read_bytes())
                local = [box[0]-center[0], box[1]-center[1], box[2]-center[0], box[3]-center[1]]
                position = centered_text_position(local, target=tuple(center))
                cache[key] = {'bounds': box, 'position': position, 'evidence': str(image),
                              'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
            result = cache[key]
            h['cards'][i]['style']['position'] = result['position']
            results.append({'id': card['id'], 'text': card['text'], **result})
        client.run('file.saveAs', {'path': str(output / 'calibration.fcproj')})
    finally:
        client.close()
    (output / 'measurements.json').write_text(json.dumps(results, indent=2))
    (output / 'handoff.json').write_text(json.dumps(h, indent=2))
    print(json.dumps({'cards': len(results), 'uniqueRenders': len(cache),
                      'widestInk': max(r['bounds'][2]-r['bounds'][0] for r in results),
                      'status': 'measured-awaiting-composed-visual-review'}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('handoff', 'plan', 'binary', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    measure(json.loads(a.handoff.read_text()), json.loads(a.plan.read_text()), a.binary, a.output.resolve())

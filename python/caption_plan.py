"""Transport caption-clips decisions; the owning skill supplies cards and placement."""
import copy
import math
import re
import sys
from common import SKILLS, inside, read, require, save, sha, fingerprint

sys.path.insert(0, str(SKILLS / 'caption-clips/scripts'))
from filmcraft_caption_contract import prepare_cards, profile_caption_motion, verify_native_layers, character_styles, apply_character_styles
from filmcraft_shadow import shadow_layer_props, LAYER_ORDER, PROFILE_ID

HELPERS = ('filmcraft_caption_contract.py', 'filmcraft_shadow.py', 'caption_profiles.py', 'caption_lint.py', 'resolve_cards.py', 'oliver_format.py')


def derive(project, spec, reference):
    from caption_visibility import ranges
    ranges(spec)
    require(spec['backend'] in ['filmcraft', 'resolve'], 'This caption contract needs FilmCraft or Resolve; Premiere must use its owning native Graphics route')
    file = inside(project['root'], reference['path'])
    require(sha(file) == reference['sha256'], 'Caption handoff changed')
    handoff = read(file)
    require(handoff.get('schema') == 'acq-edit/caption-handoff-v1' and handoff.get('owner') == 'caption-clips', 'Caption-clips handoff required')
    require(set(handoff) <= {'schema', 'owner', 'projectId', 'clipId', 'cutsFingerprint', 'profile', 'cards', 'omissions'}, 'Unsupported caption handoff field; do not silently drop requested behavior')
    require(handoff.get('projectId') == project['id'] and handoff.get('clipId') == spec['clipId'], 'Caption handoff identity differs')
    require(handoff.get('cutsFingerprint') == fingerprint(spec['cuts']), 'Caption handoff uses stale cut clocks')
    profile_ref = handoff['profile']
    profile_file = inside(project['root'], profile_ref['path'])
    require(sha(profile_file) == profile_ref['sha256'], 'Caption profile changed')
    profile = read(profile_file)
    if spec['backend'] == 'resolve':
        require(profile.get('resolve_caption_motion') in ['none', 'measured_fast_settle'], 'Explicit supported Resolve caption arrival required')
        # Reuse the pure caption-owner timing/curve helper, with an explicitly
        # selected Resolve preset. No FilmCraft binary or project is involved.
        profile = {**profile, 'filmcraft_caption_motion': profile['resolve_caption_motion']}
        shadows = profile.get('resolve_caption_shadows')
        require(isinstance(shadows, dict) and set(shadows) == {'id', 'wide', 'tight'} and isinstance(shadows['id'], str) and shadows['id'], 'Explicit Resolve shadow profile required')
        for role in ['wide', 'tight']:
            shadow = shadows[role]
            require(isinstance(shadow, dict) and set(shadow) == {'offset', 'softness', 'opacity'}, 'Resolve shadows require offset, softness and opacity')
            for key in ['offset', 'softness']:
                values = shadow[key]
                require(isinstance(values, list) and len(values) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in values), 'Invalid Resolve shadow coordinates')
            require(all(0 <= v <= 100 for v in shadow['softness']) and all(-1 <= v <= 1 for v in shadow['offset']), 'Resolve shadow values outside supported range; softness uses native Text+ units')
            require(type(shadow['opacity']) in (int, float) and 0 <= shadow['opacity'] <= 1, 'Invalid Resolve shadow opacity')
    for key in ['allow_quote_italics', 'guest_turn_italics']:
        require(type(profile.get(key)) == bool, 'Explicit caption profile setting required: ' + key)
    for key in ['caption_hold_through_seconds', 'caption_trailing_hold_seconds']:
        require(type(profile.get(key)) in (int, float) and math.isfinite(profile[key]) and profile[key] >= 0, 'Explicit finite caption hold required')
    require(profile.get('filmcraft_caption_motion') in ['none', 'measured_fast_settle'], 'Unsupported caption arrival; do not substitute a different animation')
    duration = sum(c['frames'] for c in spec['cuts'])
    fps = spec['fps']['numerator'] / spec['fps']['denominator']
    cards = handoff['cards']
    require(isinstance(cards, list) and cards, 'Reviewed caption cards required')
    prior = -1
    ids = set()
    for card in cards:
        require(set(card) <= {'id', 'text', 'start_frame', 'speech_end', 'quote', 'style', 'elapsed_frames', 'role', 'speaker_role', 'remove_question_exclamation'}, 'Unsupported caption card behavior')
        require(isinstance(card.get('text'), str) and card['text'].strip(), 'Nonempty caption text required')
        require(isinstance(card.get('id'), str) and card['id'] and card['id'] not in ids, 'Unique semantic card ID required')
        ids.add(card['id'])
        start = card['start_frame']
        require(type(start) == int and prior < start < duration, 'Caption onsets must be ordered inside the timeline')
        require(type(card.get('speech_end')) in (int, float) and math.isfinite(card['speech_end']) and start / fps < card['speech_end'] <= duration / fps, 'Mapped speech release outside timeline')
        require(type(card.get('elapsed_frames', 0)) == int and card.get('elapsed_frames', 0) >= 0, 'Invalid caption continuation clock')
        style = card['style']
        allowed = {'font', 'fontStyle', 'italicStyle', 'syntheticQuoteItalic', 'size', 'renderedFontPx', 'position', 'color', 'emphasis', 'fontPostscript', 'italicPostscript'} if spec['backend'] == 'filmcraft' else {'font', 'fontStyle', 'italicStyle', 'fusionSize', 'center', 'color'}
        require(set(style) <= allowed, 'Unsupported caption style; preserve the owner request instead of dropping properties')
        for key in ['font', 'fontStyle', 'color']:
            require(isinstance(style.get(key), str) and style[key].strip(), 'Explicit caption style required: ' + key)
        require(re.fullmatch(r'#[0-9a-fA-F]{6}', style['color']), 'Caption foreground color must use #RRGGBB')
        for key in (['size', 'renderedFontPx'] if spec['backend'] == 'filmcraft' else ['fusionSize']):
            require(type(style.get(key)) in (int, float) and math.isfinite(style[key]) and style[key] > 0, 'Positive measured caption size required')
        position = style.get('position' if spec['backend'] == 'filmcraft' else 'center')
        require(isinstance(position, list) and len(position) == 2 and all(type(v) in (int, float) and math.isfinite(v) for v in position), 'Measured native caption position required')
        require(type(style.get('syntheticQuoteItalic', False)) == bool, 'Explicit synthetic italic policy required')
        prior = start
    for previous, following in zip(cards, cards[1:]):
        require(previous['speech_end'] <= following['start_frame'] / fps, 'Overlapping spoken cards need an explicit supported multivoice layout')
    for omission in handoff.get('omissions', []):
        require(type(omission.get('start')) in (int, float) and type(omission.get('end')) in (int, float)
                and 0 <= omission['start'] < omission['end'] <= duration / fps, 'Invalid caption omission clock')
    prepared = prepare_cards(cards, profile, fps, duration,
                             picture_cuts=[c['recordFrame'] for c in spec['cuts'][1:]],
                             omissions=handoff.get('omissions', []))
    from caption_lint import validate_card_layout
    from resolve_cards import width_measurer
    budget = spec['width'] * profile.get('max_text_width_pct', 76.3889) / 100 * 0.95
    face = profile.get('body_font_postscript')
    if spec.get('editorial', {}).get('reviewed'):
        require(face, 'Measured body-caption profile font is required')
    measure, _ = width_measurer({'max_text_width_px': budget}) if face and spec['backend']=='filmcraft' else (None, None)
    captions = []
    for card in prepared:
        runs = character_styles(card)
        require(not runs or profile.get('allow_weight_variation') is True, 'Profile does not permit semantic weight variation')
        require(not runs or not card['style'].get('syntheticQuoteItalic'), 'Emphasis requires real italic faces')
        if measure:
            card_face = card['style'].get('italicPostscript' if card['italic'] else 'fontPostscript') or (profile.get('italic_font_postscript') if card['italic'] else face)
            # Conservatively measure the full line in every requested face, then
            # require native isolated-ink measurement for final placement.
            faces = {card_face} | {r['italicPostscript' if card['italic'] else 'fontPostscript'] for r in card['style'].get('emphasis', [])}
            for measured_face in faces:
                validate_card_layout(card['text'], profile, measure=measure, face=measured_face,
                    size_px=card['style']['renderedFontPx'], width_px=budget)
        style = copy.deepcopy(card['style'])
        if card['italic']:
            if style.get('syntheticQuoteItalic'):
                require(card['quote'], 'Synthetic italic permission applies only to classified quotes')
            else:
                require(isinstance(style.get('italicStyle'), str) and style['italicStyle'], 'Real italic face required for this caption')
        captions.append({'startFrame': card['start_frame'], 'endFrame': card['end_frame'], 'text': card['text'], 'style': style})
    return {'cards': prepared, 'captions': captions, 'profile': profile,
            'helperHashes': {name: sha(SKILLS / 'caption-clips/scripts' / name) for name in HELPERS},
            'shadowProfile': PROFILE_ID if spec['backend'] == 'filmcraft' else profile['resolve_caption_shadows']['id']}


def validate(project, spec):
    reference = spec.get('captionContract')
    if not reference:
        return None
    derived = derive(project, spec, reference)
    require(spec['captions'] == derived['captions'], 'Native captions differ from the pinned owning-skill handoff; prepare them again')
    require(reference.get('helperHashes') == derived['helperHashes'], 'Caption helpers changed; preserve the old plan and reconcile before rebuilding')
    return derived


def prepare_plan(project, packet):
    from common import plan
    spec = plan(project, {'plan': packet['plan']})
    require(not spec.get('captions') and not spec.get('captionContract'), 'Prepare captions from a separate plan with empty caption layers')
    reference = {'path': str(inside(project['root'], packet['handoff'])), 'sha256': packet['handoffSha256']}
    result = derive(project, spec, reference)
    spec['captions'] = result['captions']
    spec['captionContract'] = {**reference, 'helperHashes': result['helperHashes']}
    target = inside(project['root'], packet['output'])
    save(target, spec)
    return {'plan': str(target), 'sha256': sha(target), 'cards': len(spec['captions']),
            'shadowProfile': result['shadowProfile'], 'status': 'prepared-awaiting-native-construction'}


def opacity_for(spec, prepared, card, frame_ticks):
    from caption_visibility import ranges, masked_opacity
    _, original = profile_caption_motion(prepared['profile'], frame_ticks,
        card['end_frame'] - card['start_frame'], elapsed_frames=card.get('elapsed_frames', 0),
        center=(spec['width'] / 2, spec['height'] / 2), canvas_height=spec['height'])
    return masked_opacity(original, card, ranges(spec), frame_ticks)


def write_parameter(client, clip, effect, parameter, value, start_ticks):
    def unpack(v):
        return [v['Vec2']['x'], v['Vec2']['y']] if 'Vec2' in v else v['Float']
    client.run('effects.setParam', {'clip': clip, 'effect': effect, 'param': parameter, 'value': unpack(value['value'])})
    for key in value.get('keyframes', []):
        client.run('effects.setParam', {'clip': clip, 'effect': effect, 'param': parameter,
            'value': unpack(key['value']), 'time': start_ticks + key['time'], 'keyframe': True})
        client.run('effects.setInterpolation', {'clip': clip, 'effect': effect, 'param': parameter,
            'mediaTime': key['time'], 'interpolation': {'Linear':'linear','Hold':'hold'}[key['interp']]})


def build_native(client, spec, prepared, frame_ticks):
    fonts = {entry['family']: set(entry['styles']) for entry in client.run('fonts.list')}
    for card in prepared['cards']:
        style = card['style']
        face = style['italicStyle'] if card['italic'] and not style.get('syntheticQuoteItalic') else style['fontStyle']
        require(face in fonts.get(style['font'], set()), 'Exact caption font face missing: ' + style['font'] + ' / ' + face)
        for run in character_styles(card):
            require(run['fontStyle'] in fonts.get(style['font'], set()), 'Exact emphasis face missing: ' + run['fontStyle'])
    for role_index, role in enumerate(LAYER_ORDER):
        for card in prepared['cards']:
            style = card['style']
            face = style['italicStyle'] if card['italic'] and not style.get('syntheticQuoteItalic') else style['fontStyle']
            graphic = client.run('graphics.newText', {'newClip': True, 'text': card['text'], 'position': style['position'],
                'font': style['font'], 'fontStyle': face, 'size': style['size'], 'time': card['start_frame'] * frame_ticks,
                'seconds': (card['end_frame'] - card['start_frame']) * spec['fps']['denominator'] / spec['fps']['numerator'], 'track': role_index + 1})
            # newText honors host smart-quotes preferences; set exact reviewed
            # text explicitly so those preferences cannot rewrite the handoff.
            props = {'text': card['text'], 'align': 'center', 'fill_color': style['color'], 'fauxBold': False,
                     'fauxItalic': bool(card['italic'] and style.get('syntheticQuoteItalic')),
                     **shadow_layer_props(role, style['renderedFontPx'])}
            client.run('graphics.set', {'clip': graphic['clip'], 'layer': graphic['layer'], 'props': props})
            if style.get('emphasis'):
                apply_character_styles(client, graphic['clip'], graphic['layer'], card)
            motion, opacity = profile_caption_motion(prepared['profile'], frame_ticks,
                card['end_frame'] - card['start_frame'], elapsed_frames=card.get('elapsed_frames', 0),
                center=(spec['width'] / 2, spec['height'] / 2), canvas_height=spec['height'])
            opacity = opacity_for(spec, prepared, card, frame_ticks)
            for effect, parameter, value in [('motion', 'position', motion), ('opacity', 'opacity', opacity)]:
                write_parameter(client, graphic['clip'], effect, parameter, value, card['start_frame'] * frame_ticks)
    return {'status': 'constructed-awaiting-saved-native-verification'}


def verify_native(native_path, spec, prepared, frame_ticks):
    # sequence_inspect prints parameter debug strings and keyframe counts. The
    # saved native project exposes full typed values and every animation key.
    data = read(native_path)
    sequence = data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    layers = sequence['video_tracks'][1:4]
    require(all(layer['enabled'] and not layer['muted'] and not layer['effects'] and not layer['transitions'] for layer in layers), 'Caption lane visibility/effects differ from the handoff')
    require(not any(layer['solo'] for layer in sequence['video_tracks']), 'Solo video lanes require reconciliation before caption verification')
    owner_layers = copy.deepcopy(layers)
    if spec.get('captionVisibility'):
        # First prove the actual visibility curve, then let the unchanged owner
        # validate its original arrival policy on a read-only normalized copy.
        for layer in owner_layers:
            for item, card in zip(layer['items'], prepared['cards']):
                params = next(e['params'] for e in item['effects'] if e['effect'] == 'opacity')
                actual = params['opacity']
                expected = opacity_for(spec, prepared, card, frame_ticks)
                keys = [{'time':k['time'],'value':k['value'],'interp':k['interp']} for k in actual.get('keyframes', [])]
                require(actual['value'] == expected['value'] and keys == expected.get('keyframes', []), 'Caption visibility curve differs')
                _, params['opacity'] = profile_caption_motion(prepared['profile'], frame_ticks,
                    card['end_frame']-card['start_frame'], elapsed_frames=card.get('elapsed_frames', 0),
                    center=(spec['width']/2,spec['height']/2), canvas_height=spec['height'])
    result = verify_native_layers(owner_layers, prepared['cards'], frame_ticks)
    # Comparing actual foreground/shadow typography and motion catches detached duplicates.
    for index, card in enumerate(prepared['cards']):
        native = [layer['items'][index] for layer in layers]
        effects = [{e['effect']: e['params'] for e in item['effects']} for item in native]
        for item in native:
            graphic = next(e for e in item['effects'] if e['effect'] == 'graphic_text')
            require(graphic.get('layer', {}).get('runs', []) == character_styles(card), 'Native caption character emphasis differs; reconcile all three lanes')
            require(item['enabled'] and item['source_in'] == 0 and item['speed'] == 1 and not item['reverse'], 'Caption native playback changed')
            require(all(e['enabled'] for e in item['effects']), 'Caption effect disabled')
            require(len(item['effects']) == 4 and {e['effect'] for e in item['effects']} == {'motion', 'opacity', 'time_remap', 'graphic_text'}, 'Unexpected caption effect; reconcile the requested treatment')
        for name in ['motion', 'opacity']:
            require(all(e[name] == effects[0][name] for e in effects), 'Caption duplicate animation differs')
        for name in ['text', 'font', 'font_style', 'size', 'position', 'faux_bold', 'faux_italic', 'align']:
            require(all(e['graphic_text'][name] == effects[0]['graphic_text'][name] for e in effects), 'Caption duplicate typography differs: ' + name)
        for role, effect in zip(LAYER_ORDER, effects):
            params = effect['graphic_text']
            require(not any(p.get('keyframes') for p in params.values()), 'Animated graphic properties require an explicit supported caption treatment')
            require(effect['time_remap']['speed'] == {'value': {'Float': 100.0}}, 'Caption time remapping differs')
            style = card['style']
            face = style['italicStyle'] if card['italic'] and not style.get('syntheticQuoteItalic') else style['fontStyle']
            for key, value in [('font', {'Text': style['font']}), ('font_style', {'Text': face}),
                               ('size', {'Float': style['size']}), ('position', {'Vec2': {'x': style['position'][0], 'y': style['position'][1]}}),
                               ('faux_bold', {'Bool': False}), ('align', {'Choice': 1})]:
                require(params[key]['value'] == value and not params[key].get('keyframes'), 'Native caption style differs: ' + key)
            for key in ['stroke', 'stroke2', 'background']:
                require(params[key]['value'] == {'Bool': False}, 'Unexpected caption decoration: ' + key)
            require(params['fill']['value'] == {'Bool': True}, 'Caption fill disabled')
            for key in ['scale', 'scale_width', 'opacity']:
                require(params[key]['value'] == {'Float': 100.0} and not params[key].get('keyframes'), 'Unexpected caption graphic transform: ' + key)
            require(params['rotation']['value'] == {'Float': 0.0} and not params['rotation'].get('keyframes'), 'Unexpected caption graphic rotation')
            require(params['shadow']['value']['Bool'] == (role != 'text'), 'Caption shadow role differs')
            if role != 'text':
                require(params['fill_color']['value'] == {'Color': [0, 0, 0, 0]}, 'Shadow fill is not transparent')
                require(params['shadow_color']['value'] == {'Color': [0, 0, 0, 1]}, 'Caption shadow color differs')
                expected = shadow_layer_props(role, card['style']['renderedFontPx'])
                for key in ['shadow_opacity', 'shadow_distance', 'shadow_angle', 'shadow_size', 'shadow_blur']:
                    require(abs(params[key]['value']['Float'] - expected[key]) < 1e-5, 'Native shadow differs: ' + key)
            else:
                expected_color = [int(style['color'][i:i+2], 16) / 255 for i in (1, 3, 5)] + [1]
                require(all(abs(a - b) < 1e-6 for a, b in zip(params['fill_color']['value']['Color'], expected_color)), 'Caption foreground color differs')
        motion, opacity = profile_caption_motion(prepared['profile'], frame_ticks,
            card['end_frame'] - card['start_frame'], elapsed_frames=card.get('elapsed_frames', 0),
            center=(spec['width'] / 2, spec['height'] / 2), canvas_height=spec['height'])
        opacity = opacity_for(spec, prepared, card, frame_ticks)
        for actual, expected in [(effects[0]['motion']['position'], motion), (effects[0]['opacity']['opacity'], opacity)]:
            require(actual['value'] == expected['value'], 'Caption arrival value differs')
            keys = [{'time': k['time'], 'value': k['value'], 'interp': k['interp']} for k in actual.get('keyframes', [])]
            require(keys == expected.get('keyframes', []), 'Caption arrival curve differs')
        for key, expected in [('anchor', {'Vec2': {'x': spec['width'] / 2, 'y': spec['height'] / 2}}), ('scale', {'Float': 100.0}), ('scale_width', {'Float': 100.0}), ('rotation', {'Float': 0.0})]:
            value = effects[0]['motion'][key]
            require(value['value'] == expected and not value.get('keyframes'), 'Unexpected caption clip transform: ' + key)
    return {**result, 'helperHashes': prepared['helperHashes'], 'shadowProfile': PROFILE_ID}

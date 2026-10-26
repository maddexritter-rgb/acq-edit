"""Transport reviewed caption semantics to Filmcraft; never infer editorial quotes.

Uses the owning profile's display normalization and hold settings. The caller must
classify represented speech and supply actual speech releases and protected cuts.
"""
from copy import deepcopy
import math
import re
from caption_profiles import clean_profile_display_words, cap_hold_at_picture_cut, preserve_first_person, validate_display_casing


def centered_text_position(local_bounds, target=(540, 960)):
    """Center visible glyphs, not the point-text baseline or shadow halo.

    Consume isolated rendered foreground ink bounds in local coordinates after
    applying the actual font and run styles. graphics.list localBounds is a logical
    ascent/descent box and is not the visible ink extent.
    Foreground and both shadow duplicates must receive the same placement.
    """
    x0, y0, x1, y1 = map(float, local_bounds)
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
        raise ValueError('Nonempty native glyph bounds required')
    return [float(target[0])-(x0+x1)/2, float(target[1])-(y0+y1)/2]


def foreground_ink_bounds(png_bytes):
    """Measure an isolated light foreground on black, without shadows or footage."""
    from io import BytesIO
    import numpy as np
    from PIL import Image
    rgb = np.asarray(Image.open(BytesIO(png_bytes)).convert('RGB'))
    ys, xs = np.where(rgb.max(axis=2) >= 128)
    if not len(xs):
        raise ValueError('No isolated foreground glyphs in native render')
    return [float(xs.min()), float(ys.min()), float(xs.max()+1), float(ys.max()+1)]


CENTERED_ANIMATION_PRESET = 'measured_fast_settle'
# Approved rendered motion, expressed at 1920px canvas height and 24000/1001fps.
# Retain its real-time speed at other frame rates; these are not delivery-frame indices.
_FAST_SETTLE_SAMPLE_TICKS = 10594584000
_FAST_SETTLE_OFFSETS_1920 = (
    -6.116, -3.403, -2.438, -1.668, -1.156, -0.674,
    -0.385, -0.166, -0.161, -0.142, -0.110, 0.0,
)


def centered_caption_position(ticks_per_frame, card_frames, source_in=0,
                              elapsed_frames=0, center=(540, 960), canvas_height=1920):
    """Fast downward arrival with a gentle settle, sampled from rendered motion.

    Keep card_frames for clock validation, never to accelerate the entrance.
    Short cards show the original curve's visible prefix. A layout continuation
    advances elapsed_frames; its first key evaluates the already elapsed curve.
    source_in is this item's native media clock. Motion anchor/center are canvas
    coordinates, separate from the graphic's measured ink Position. Scale is 100.
    """
    if ticks_per_frame <= 0 or card_frames < 1 or elapsed_frames < 0 or canvas_height <= 0:
        raise ValueError('Positive frame clock/card/canvas and nonnegative elapsed required')
    elapsed = round(elapsed_frames * ticks_per_frame)
    last = (len(_FAST_SETTLE_OFFSETS_1920)-1) * _FAST_SETTLE_SAMPLE_TICKS
    if elapsed >= last:
        offset = 0.0
    else:
        i, fraction = divmod(elapsed, _FAST_SETTLE_SAMPLE_TICKS)
        fraction /= _FAST_SETTLE_SAMPLE_TICKS
        offset = (_FAST_SETTLE_OFFSETS_1920[i] * (1-fraction) +
                  _FAST_SETTLE_OFFSETS_1920[i+1] * fraction)
    x, y = map(float, center)
    def value(offset):
        return {'Vec2': {'x': x, 'y': y + offset * canvas_height / 1920.}}
    p = {'value': value(offset)}
    if elapsed < last:
        p['keyframes'] = [{'time': int(source_in), 'value': value(offset), 'interp': 'Linear'}]
        p['keyframes'] += [
            {'time': int(source_in + i*_FAST_SETTLE_SAMPLE_TICKS - elapsed),
             'value': value(offset), 'interp': 'Linear'}
            for i, offset in enumerate(_FAST_SETTLE_OFFSETS_1920)
            if i*_FAST_SETTLE_SAMPLE_TICKS > elapsed]
    return p


def centered_caption_opacity(ticks_per_frame, source_in=0, elapsed_frames=0,
                             card_frames=None):
    """90->100% in 83.4167ms, retaining speed on short cards and continuations."""
    if ticks_per_frame <= 0 or elapsed_frames < 0 or (card_frames is not None and card_frames < 1):
        raise ValueError('Positive frame clock/card duration and nonnegative elapsed required')
    elapsed = round(elapsed_frames * ticks_per_frame)
    remaining = max(0, 2*_FAST_SETTLE_SAMPLE_TICKS - elapsed)
    start = 100. - 10. * remaining / (2*_FAST_SETTLE_SAMPLE_TICKS)
    p = {'value': {'Float': start}}
    if remaining:
        p['keyframes'] = [
            {'time': int(source_in), 'value': {'Float': start}, 'interp': 'Linear'},
            {'time': int(source_in + remaining), 'value': {'Float': 100.}, 'interp': 'Linear'}]
    return p


def profile_caption_motion(profile, ticks_per_frame, card_frames, source_in=0,
                           elapsed_frames=0, center=(540, 960), canvas_height=1920):
    """Resolve native arrival from explicit profile data, never a backend-wide default."""
    preset = profile.get('filmcraft_caption_motion')
    if preset == 'none':
        return ({'value': {'Vec2': {'x': float(center[0]), 'y': float(center[1])}}},
                {'value': {'Float': 100.}})
    if preset != CENTERED_ANIMATION_PRESET:
        raise ValueError('Explicit supported filmcraft_caption_motion required')
    return (centered_caption_position(ticks_per_frame, card_frames, source_in,
                                     elapsed_frames, center, canvas_height),
            centered_caption_opacity(ticks_per_frame, source_in, elapsed_frames,
                                     card_frames))


def prepare_cards(cards, profile, fps, duration_frames, picture_cuts=(), omissions=()):
    # A stale positional omission index once classified a revenue value as filler.
    # Display cleanup cannot silently remove quantities, negations or conditions.
    protected = {'no', 'not', 'never', "don't", "doesn't", "can't", 'cannot',
                 'without', 'unless', 'if', 'only', 'maybe', 'probably',
                 'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
                 'eight', 'nine', 'ten', 'hundred', 'thousand', 'million',
                 'millions', 'billion', 'percent'}
    for omit in omissions:
        word = str(omit.get('word', ''))
        tokens = re.findall(r"[\w']+", word.lower().replace('’', "'"))
        if (re.search(r'[\d$€£%]', word) or protected.intersection(tokens)) and not (
                omit.get('purpose') == 'replacement' and omit.get('replacement_text')):
            raise ValueError('Meaning-bearing caption omission; retain source words or supply an explicit replacement: ' + word)
    out = deepcopy(cards)
    for i, card in enumerate(out):
        if not isinstance(card.get('quote'), bool):
            raise ValueError('Every reviewed card requires explicit quote true/false')
        if 'speech_end' not in card:
            raise ValueError('Actual mapped speech release required')
        lines = []
        for line in card['text'].split('\n'):
            words = [{'word': token.strip('“”"')} for token in line.split()]
            lines.append(' '.join(w['word'] for w in clean_profile_display_words(words)))
        text = '\n'.join(lines)
        validate_display_casing(text)
        if card.get('remove_question_exclamation'):
            text = text.replace('?', '').replace('!', '')
        # A live speaker's style is independent of represented-speech punctuation.
        live_guest = card.get('role') == 'guest' or card.get('speaker_role') == 'guest'
        card['italic'] = bool((card['quote'] and profile.get('allow_quote_italics')) or
                              (live_guest and profile.get('guest_turn_italics')))
        card['text'] = '“' + text + '”' if card['quote'] else text
        from caption_lint import validate_card_layout
        validate_card_layout(card['text'], profile)
        if 'filmcraft_caption_motion' in profile:
            card['animation_preset'] = profile['filmcraft_caption_motion']
        speech_end = float(card['speech_end'])
        nxt = out[i+1]['start_frame']/fps if i+1<len(out) else None
        hold = float(profile.get('caption_hold_through_seconds', .75))
        trail = float(profile.get('caption_trailing_hold_seconds', .35))
        end = nxt if nxt is not None and nxt-speech_end<=hold else speech_end+trail
        if nxt is not None:
            end = min(end, nxt)
        for omit in omissions:
            if speech_end <= omit['start'] < end:
                end = omit['start']
        end_frame = min(duration_frames, round(end*fps))
        end_frame = cap_hold_at_picture_cut(card['start_frame'], end_frame,
                                           math.ceil(speech_end*fps), picture_cuts)
        if end_frame <= card['start_frame']:
            raise ValueError('Invalid caption interval after protected boundaries')
        card['end_frame'] = end_frame
    return out


def verify_native_layers(layers, cards, ticks_per_frame):
    """Fail before rendering if native text/style/intervals lost reviewed semantics."""
    if len(layers) != 3:
        raise ValueError('Expected foreground plus two shadow layers')
    for layer in layers:
        if len(layer['items']) != len(cards):
            raise ValueError('Native card count differs from reviewed plan')
        for clip, card in zip(layer['items'], cards):
            validate_display_casing(card['text'])
            if preserve_first_person(card['text']) != card['text']:
                raise ValueError('Lowercase first-person pronoun after display normalization')
            p = next(e['params'] for e in clip['effects'] if e['effect']=='graphic_text')
            if card.get('animation_preset') == 'none':
                motion = next(e['params'] for e in clip['effects'] if e['effect']=='motion')
                opacity = next(e['params']['opacity'] for e in clip['effects'] if e['effect']=='opacity')
                if (any(v.get('keyframes') for v in motion.values()) or opacity.get('keyframes') or
                        opacity['value'].get('Float') != 100.):
                    raise ValueError('Profile forbids caption arrival animation')
            if p['text']['value']['Text'] != card['text']:
                raise ValueError('Native punctuation/quotation text differs')
            face = p['font_style']['value']['Text']
            faux = p['faux_italic']['value']['Bool']
            style = card.get('style', {})
            if 'fontStyle' in style:
                synthetic = bool(card['italic'] and style.get('syntheticQuoteItalic'))
                expected = style['italicStyle'] if card['italic'] and not synthetic else style['fontStyle']
                # Exact owner-selected faces may use abbreviated names such as
                # Bold It. Native font preflight establishes their availability.
                if face != expected or faux != synthetic:
                    raise ValueError('Native italic face or synthetic state differs')
            else:
                italic = bool(faux or 'italic' in face.lower())
                if italic != card['italic']:
                    raise ValueError('Native quote italic state differs')
            if (clip['start'], clip['duration']) != (card['start_frame']*ticks_per_frame,(card['end_frame']-card['start_frame'])*ticks_per_frame):
                raise ValueError('Native caption hold/clock differs')
    return {'status':'NATIVE_CAPTION_CONTRACT_VALID','cards':len(cards),'layers':3}

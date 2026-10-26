#!/usr/bin/env python3
"""Resolve normalized words into a native card manifest. Mechanics, not editorial taste.

This script owns the MECHANICAL half of manifest resolution: frame quantization,
phrase grouping, camera-cut splitting, display holds, the no-hole partition, and
turning explicit style decisions into the native word contract. It does NOT
decide what deserves emphasis.

Two producers feed the same manifest contract:

  * the caption director (`native_graphics/resolve_director_style.py`) applies a
    per-word style stream to a manifest this script produced -- the default path;
  * `--editorial` applies an explicit human decision file, for overrides and for
    working without a director.

Neither invents styling. With no decisions at all, every word stays at the
donor's base weight, upright, in its speaker's colour -- and that is reported as
`not_applicable`, never as an approved uniform style.

The five axes are independent:

  weight   per word, over the full ladder base -> strong -> emphasis -> payoff
  italic   per word, carried by a real italic donor face
  colour   per card, meaning speaker ownership ONLY (never a highlight)
  quote    punctuation around a span; it does not imply italic or a colour change
  size     per CARD, never one word inside a cue

Colour is per card because the native contract binds one donor -- one colour --
to a card, so a represented-voice span is also a grouping boundary. That keeps
the axis independent without smuggling two colours into one Graphic.

Nothing here is brand-specific: faces, colours, position and tier multipliers all
come from the style config.

What this does not do: it never SHRINKS text to fit. Where a profile sets
`max_text_width_pct`, rendered width IS measured with the real faces and a card
is split when it would overflow; where it does not, cards are bounded by the word
cap alone, which is a grouping rule and not a fit guarantee. Either way a
width-fit shrink belongs in a separate `width_review` and may never overwrite an
editorial size tier. The manifest's `limitations` block records which of the two
actually ran.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from fractions import Fraction
from pathlib import Path

from native_graphics.caption_render_segments import partition

WORD_TEXT_KEYS = ('text', 'word')
LADDER = ('base', 'strong', 'emphasis', 'payoff')
# The largest cue size resolve_director_style can assign without regrouping
# (its SIZE_TIERS peak, as a scale). Mirrored here so grouping can measure at the
# biggest size a card can still become; a parity test keeps the two in step.
DIRECTOR_PEAK_SCALE = 1.20
# The full ladder, keyed by the base face that identifies the family. Mirrored from
# prepare_native_donor.FACES (test_resolve_cards keeps the two in step). A profile
# declares only its base/italic faces, but the director restyles weight AFTER
# grouping, so the width budget has to be measurable against the heaviest rung.
LADDER_FACES = {
    'ProximaNova-Medium': {
        'base': 'ProximaNova-Medium', 'base_italic': 'ProximaNova-MediumIt',
        'strong': 'ProximaNova-Bold', 'strong_italic': 'ProximaNova-BoldIt',
        'emphasis': 'ProximaNova-Extrabld', 'emphasis_italic': 'ProximaNova-ExtrabldIt',
        'payoff': 'ProximaNova-Black', 'payoff_italic': 'ProximaNova-BlackIt',
    },
}

# ---------------------------------------------------------------------------
# The profile contract.
#
# `profiles/<id>.json` is the single source of truth for how a brand presents
# captions. This grouper used to take a parallel hand-written style file instead,
# so anything the profile DECLARED but the grouper did not IMPLEMENT was silently
# ignored -- which is how a `max_lines: 1` profile shipped two-line cards and an
# `oliver_v2` profile lost its sentence boundaries.
#
# So: every key a profile declares is classified here. A key this resolver does
# not honour is a hard error, not a no-op. Adding a field to a profile without
# teaching the resolver what it means now fails loudly on the next build.
# ---------------------------------------------------------------------------

# Declarative only: nothing downstream has to change to honour these.
PROFILE_DESCRIPTIVE = frozenset({'id', 'display_name', 'shadow_profile',
                                 'premiere_text_style_preset', 'vendored_font'})
# Honoured by THIS resolver.
PROFILE_HONOURED = frozenset({'normalization', 'max_lines', 'allow_weight_variation',
                              'default_y_pct', 'body_font_postscript',
                              'italic_font_postscript', 'emphasis_font_postscript',
                              'max_words_per_card',
                              'font_size_px', 'max_text_width_pct', 'frame_width_px', 'frame_height_px',
                              'progressive_reveal',
                              # Shared with the other grouper: both honour these.
                              'caption_hold_through_seconds',
                              'caption_trailing_hold_seconds'})
# Honoured by the OTHER grouper (caption_profiles.build_profile_manifest).
PROFILE_OTHER_GROUPER = frozenset({'min_words_per_card', 'max_words_per_quote_card',
                                   'reveal_mode', 'line_reveal_min_delay_seconds',
                                   'word_reveal_min_seconds_per_word',
                                   'word_reveal_min_interword_gap_seconds',
                                   'max_chars_per_line', 'allow_quote_italics',
                                   })


def check_profile_contract(profile, style, words):
    """Fail closed on anything the profile declares that is not actually enforced."""
    unknown = set(profile) - PROFILE_DESCRIPTIVE - PROFILE_HONOURED - PROFILE_OTHER_GROUPER
    if unknown:
        raise ValueError(
            f"profile {profile.get('id')!r} declares {sorted(unknown)}, which this resolver "
            "does not implement. Teach resolve_cards what the field means, or move the "
            "profile to the grouper that honours it -- do not leave it silently ignored.")

    elsewhere = sorted(set(profile) & PROFILE_OTHER_GROUPER)
    if elsewhere:
        raise ValueError(
            f"profile {profile.get('id')!r} declares {elsewhere}, which THIS resolver does "
            "not implement -- those fields belong to caption_profiles.build_profile_manifest. "
            "Knowing which grouper owns a field is not permission to ignore it here: route "
            "the profile to that grouper, or drop the fields.")

    if profile.get('progressive_reveal'):
        raise ValueError(
            f"profile {profile.get('id')!r} asks for progressive_reveal, which this resolver "
            "does not implement (it emits whole cards). Use build_profile_manifest, whose "
            "reveal_mode handles staged reveals.")

    if profile.get('max_lines') not in (None, 1):
        raise ValueError(
            f"profile {profile.get('id')!r} declares max_lines {profile['max_lines']!r}; this "
            "resolver only produces single-line cards and has no line-breaking, so a "
            "multi-line profile belongs to build_profile_manifest.")

    if profile.get('normalization') == 'oliver_v2':
        # The sentence boundary survives normalization only as this flag.
        if not any(w.get('sentence_end') is not None for w in words):
            raise ValueError(
                f"profile {profile.get('id')!r} declares normalization 'oliver_v2', but no word "
                "carries a sentence_end flag. Normalize with oliver_format.format_words() "
                "(word level), not format_caption_text() (string level), or sentence boundaries "
                "are lost and cards weld across them.")

    if profile.get('max_lines') == 1 and not style.get('max_text_width_px'):
        raise ValueError(
            f"profile {profile.get('id')!r} declares max_lines 1, so a card must never wrap, but "
            "no max_text_width_px budget was resolved. Premiere re-flows an overlong card onto a "
            "second line; set the budget (or max_text_width_pct + frame_width_px on the profile).")

    if profile.get('allow_weight_variation') is False:
        offenders = sorted({w.get('weight') for w in words
                            if w.get('weight') not in (None, '', 'base')})
        if offenders:
            raise ValueError(
                f"profile {profile.get('id')!r} declares allow_weight_variation false, but "
                f"weights {offenders} were requested.")


def parse_canvas(text):
    """'1080x1920' -> (1080, 1920)."""
    try:
        width, height = (int(v) for v in str(text).lower().split('x'))
    except ValueError:
        raise ValueError(f'Canvas must look like 1080x1920, got {text!r}')
    if width <= 0 or height <= 0:
        raise ValueError(f'Canvas must be positive, got {text!r}')
    return width, height


def style_from_profile(profile, overrides=None, target_canvas=None):
    """Derive this resolver's config FROM the profile, so there is one source of truth.

    A profile's pixel values (font_size_px, the width budget) are authored for its
    own canvas (frame_width_px x frame_height_px). `target_canvas` scales them to
    the sequence actually being captioned, and records the canvas in the manifest so
    the native builder can refuse a manifest built for a different frame. Scaling by
    hand in a job config (e.g. font_size_px: 80 for a 1080 frame) is refused when a
    target canvas is given: it re-declares profile fields the profile owns.
    """
    style = dict(overrides or {})
    scale = 1.0
    width_px, height_px = profile.get('frame_width_px'), profile.get('frame_height_px')
    hand_sized = [k for k in ('font_size_px', 'max_text_width_px') if k in style]
    if target_canvas is not None:
        target_w, target_h = int(target_canvas[0]), int(target_canvas[1])
        if not width_px:
            raise ValueError(f"profile {profile.get('id')!r} declares no frame_width_px, so it "
                             'cannot be scaled to a target canvas')
        scale = target_w / float(width_px)
        if height_px and abs(target_h / float(height_px) - scale) > 1e-9:
            raise ValueError(f"target canvas {target_w}x{target_h} has a different aspect from the "
                             f"profile canvas {width_px}x{height_px}")
        if hand_sized:
            raise ValueError(f'{hand_sized} are derived from the profile and the target canvas; do not '
                             're-declare them in the job config')
        style['canvas_px'] = [target_w, target_h]
    elif width_px and height_px and not hand_sized:
        style['canvas_px'] = [int(width_px), int(height_px)]
    else:
        # Legacy hand-sized job: the canvas is unknown, so nothing downstream can check it.
        style['canvas_px'] = None
    style['resolution_scale'] = scale
    style.setdefault('y_pct', float(profile.get('default_y_pct', 50.0)))
    if profile.get('font_size_px') is not None:
        style.setdefault('font_size_px', profile['font_size_px'] * scale)
    if profile.get('max_words_per_card') is not None:
        style.setdefault('max_words_per_card', profile['max_words_per_card'])
    # The shared hold/blank thresholds, carried through under their profile names so
    # this grouper and caption_profiles.build_profile_manifest read one source.
    for key in ('caption_hold_through_seconds', 'caption_trailing_hold_seconds'):
        if profile.get(key) is not None:
            style.setdefault(key, float(profile[key]))
    pct, width = profile.get('max_text_width_pct'), profile.get('frame_width_px')
    if pct and width:
        style.setdefault('max_text_width_px', float(pct) / 100.0 * float(width) * scale)
    faces = {'base': profile.get('body_font_postscript'),
             'base_italic': profile.get('italic_font_postscript'),
             'emphasis': profile.get('emphasis_font_postscript')}
    declared = {k: v for k, v in faces.items() if v}
    if profile.get('allow_weight_variation'):
        # An explicit declaration always wins; this only supplies the rungs the
        # profile does not name, so the budget can be measured at the top weight.
        declared = {**LADDER_FACES.get(faces.get('base'), {}), **declared}
    if declared:
        # NOT setdefault: when the caller already supplied `fonts`, setdefault
        # returns that value and the merged dict is built and thrown away, so the
        # profile's ladder rungs vanished and the width-budget check then refused
        # the build. A caller's face still wins per key; it only ADDS to the ladder.
        style['fonts'] = {**declared, **(style.get('fonts') or {})}
    # The contract check keys off this, and a caller who derived a style FROM a
    # profile has unambiguously opted into that profile's rules. Leaving it to the
    # caller meant the documented derive-then-resolve path silently enforced
    # nothing: a max_lines:1 profile with no width budget was accepted, which is
    # the two-line wrap this contract exists to prevent.
    style['_profile'] = profile
    return style


def _word_text(word):
    for key in WORD_TEXT_KEYS:
        if isinstance(word.get(key), str) and word[key]:
            return word[key]
    raise ValueError('Word needs a nonempty text/word field')


def load_words(path):
    data = json.loads(Path(path).read_text())
    words = data['words'] if isinstance(data, dict) else data
    if not words:
        raise ValueError('No words to resolve')
    out = []
    for i, w in enumerate(words):
        start, end = w['start'], w['end']
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end < start:
            raise ValueError(f'Word {i} has invalid start/end')
        indices = w.get('source_indices', [i])
        if not indices or any(type(x) is not int for x in indices):
            raise ValueError(f'Word {i} needs integer source_indices')
        out.append(dict(text=_word_text(w), start=start, end=end,
                        source_indices=list(indices),
                        physical_speaker=w.get('physical_speaker', 'host'),
                        # Terminal punctuation is usually STRIPPED by display
                        # normalization, so the boundary only survives as a flag.
                        # None = the normalizer never spoke. Coercing to False made
                        # the key always present, which silently disarmed the
                        # oliver_v2 contract check on the whole CLI path.
                        sentence_end=w.get('sentence_end')))
    return out


def load_cuts(path):
    if path is None:
        return []
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        raw = data.get('cut_frames', data.get('cuts', []))
    else:
        raw = data
    frames = [c['frame'] if isinstance(c, dict) else c for c in raw]
    if any(type(f) is not int or f < 0 for f in frames):
        raise ValueError('Cut frames must be non-negative integers')
    return sorted(set(frames))


def _entries(raw, what):
    """Accept a bare source index or {source_index, text, ...}; keep the named text."""
    out = []
    for entry in raw or []:
        if isinstance(entry, dict):
            i = entry.get('source_index')
            if type(i) is not int:
                raise ValueError(f'A {what} entry needs an integer source_index')
            out.append((i, entry.get('text'), entry))
        elif type(entry) is int:
            out.append((entry, None, {}))
        else:
            raise ValueError(f'Invalid {what} entry {entry!r}')
    return out


def _spans(raw, what):
    out = []
    for span in raw or []:
        if isinstance(span, dict):
            # `from`/`to` (inclusive SOURCE indices) is the contract; `start`/`end` is
            # accepted as an alias because it is the natural spelling and was refused
            # with no hint of the expected keys.
            a = span.get('from', span.get('start'))
            b = span.get('to', span.get('end'))
            extra = span
        else:
            try:
                a, b = span
            except (TypeError, ValueError):
                raise ValueError(f'Invalid {what} span {span!r}')
            extra = {}
        if type(a) is not int or type(b) is not int or a > b:
            raise ValueError(f'A {what} span needs integer inclusive source indices {{"from": i, "to": j}} with from <= to, got {span!r}')
        out.append((a, b, extra))
    return out


def director_voice_runs(stream, words):
    """Contiguous runs of director words marked as another voice, in SOURCE index space.

    caption_director expands its voice_spans into per-word `"c": "guest"` and then
    deliberately empties voice_spans, so per-word `c` is the only place that decision
    survives. Nothing downstream read it, which silently turned every represented
    voice white. Director indices are display positions in the normalized word file.
    """
    marked = sorted(int(k) for k, spec in (stream.get('words') or {}).items()
                    if isinstance(spec, dict) and spec.get('c') not in (None, '', 'alex', 'host'))
    if marked and marked[-1] >= len(words):
        raise ValueError(f'Director stream marks word {marked[-1]} but the word file has {len(words)} '
                         'words; the stream was made from a different normalization')
    runs, start, prev = [], None, None
    for i in marked:
        if start is None:
            start = prev = i
        elif i == prev + 1:
            prev = i
        else:
            runs.append((start, prev))
            start = prev = i
    if start is not None:
        runs.append((start, prev))
    return [(min(words[a]['source_indices']), max(words[b]['source_indices'])) for a, b in runs]


def with_director_voice_spans(editorial, stream, words):
    """Merge the director's represented-voice runs into the editorial decisions."""
    editorial = dict(editorial or {})
    existing = _spans(editorial.get('represented_voice_spans'), 'represented voice')
    covered = {i for a, b, _ in existing for i in range(a, b + 1)}
    added = [(a, b) for a, b in director_voice_runs(stream, words)
             if not set(range(a, b + 1)) <= covered]
    editorial['represented_voice_spans'] = (
        [dict(e, **{'from': a, 'to': b}) for a, b, e in existing]
        + [{'from': a, 'to': b, 'voice': 'guest', 'source': 'caption_director c'} for a, b in added])
    return editorial


_FACE_FILES = None


def _font_root_order():
    """Font roots in the priority the face inventory resolves them in."""
    from caption_font_preflight import LOCAL_FONT_ROOTS
    return list(LOCAL_FONT_ROOTS)


def _scan_dir_faces(directory):
    """(PostScript name, file) for every face under `directory`, in one fc-scan.

    The newline in the format string is load-bearing: a VARIABLE font exposes one
    name per named instance, and without a separator fc-scan concatenates them into
    a single nonsense identifier -- which is how a real face that ships right here
    (e.g. ClashGroteskVariable-Regular) came to look missing.
    """
    try:
        result = subprocess.run(
            ['fc-scan', '--format', '%{postscriptname}\t%{file}\n', str(directory)],
            check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    rows = []
    for line in result.stdout.splitlines():
        name, _, path = line.partition('\t')
        if name.strip() and path.strip():
            rows.append((name.strip(), path.strip()))
    return rows


def face_files():
    """PostScript name -> installed font file, via the existing font inventory.

    Cached: the inventory fc-scans every installed font, which costs seconds. It
    was being rebuilt on every resolve() call, turning a millisecond test suite
    into a 36-second one.
    """
    global _FACE_FILES
    if _FACE_FILES is None:
        from caption_font_preflight import inventory
        installed, activated = inventory()
        # Sorted by font-root priority, NOT by the order fontconfig happened to
        # return: a user-installed copy must keep winning over a system one, or a
        # PostScript name provided by two files can silently start measuring
        # against different metrics.
        def _priority(path):
            for i, root in enumerate(_font_root_order()):
                try:
                    Path(path).relative_to(root)
                    return i
                except ValueError:
                    continue
            return len(_font_root_order())
        files = {name: sorted(paths, key=_priority)[0]
                 for name, paths in {**activated, **installed}.items()}
        # Faces VENDORED with this skill are measurable without being installed
        # system-wide. Without this, width enforcement only worked on a machine
        # that happened to have the fonts installed -- it failed in a fresh-$HOME
        # sandbox and would fail in CI, for faces that ship right here.
        #
        # Scanned HERE rather than through the preflight module: the two skill trees
        # name that helper differently (scan_fonts / scan_font_names / scan_font), and
        # probing for whichever one exists broke all width measurement with an
        # AttributeError the moment a tree did not carry the guessed name. One
        # directory-level fc-scan needs no such guess, and replaces one subprocess
        # per font file with one for the whole directory.
        vendored = Path(__file__).resolve().parent.parent / 'fonts'
        if vendored.is_dir():
            for name, path in _scan_dir_faces(vendored):
                files.setdefault(name, path)
        _FACE_FILES = files
    return _FACE_FILES


def width_measurer(style):
    """A callable(text, face, size_px) -> rendered px, or None when not configured.

    Width enforcement is OPT-IN: the default grouping path stays stdlib-only, so
    the offline build keeps its no-dependency guarantee. Configure
    ``max_text_width_px`` and this measures with the real installed faces --
    Pillow is imported lazily, and a missing dependency or face fails LOUDLY
    rather than silently letting a card overflow into a second line.
    """
    budget = style.get('max_text_width_px')
    if not budget:
        return None, None
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise ValueError('max_text_width_px needs Pillow to measure real text width; '
                         'install it or drop the budget') from exc
    files = face_files()
    cache = {}

    def measure(text, face, size_px):   # face is the widest configured face
        key = (face, int(size_px))
        if key not in cache:
            path = files.get(face)
            if not path:
                raise ValueError(f'Cannot measure width: face {face!r} is not installed')
            cache[key] = ImageFont.truetype(path, int(size_px))
        return cache[key].getlength(text)

    return measure, float(budget)


def group(words, cuts, frame, gap_threshold, max_words, group_ends,
          measure=None, budget=None, face_of=None, size_px=None):
    """Split the word stream into phrases.

    When a width budget is supplied, a card is also split before it would exceed
    it. A single-line profile must never wrap: Premiere re-flows an overlong card
    onto a second line, which reads as scrambled word order. Regrouping is the
    approved response -- shrink only afterwards, and never past the size floor.

    A sentence end is a HARD boundary. Display normalization strips most terminal
    punctuation, so a card that ignores the flag silently welds the end of one
    sentence onto the start of the next ("fucking communicating? are"), which then
    wraps in Premiere and reads as scrambled word order.

    `group_ends` supplies preferred semantic boundaries. Word, character and
    measured-width caps remain hard constraints, including reviewed groupings.
        """
    ends = set(group_ends or [])
    phrases, current = [], []
    for i, w in enumerate(words):
        if current:
            prev = words[current[-1]]
            crosses_cut = any(frame(prev['start']) < c <= frame(w['start']) for c in cuts)
            voice_change = (prev.get('voice', prev['physical_speaker'])
                            != w.get('voice', w['physical_speaker']))
            long_gap = (w['start'] - prev['end']) >= gap_threshold
            full = len(current) >= min(max_words, 4)
            over_chars = len(' '.join(words[j]['text'] for j in current + [i])) > 25
            forced = bool(ends) and max(prev['source_indices']) in ends
            sentence_end = bool(prev.get('sentence_end'))
            too_wide = False
            if measure is not None:
                candidate = current + [i]
                text = ' '.join(words[j]['text'] for j in candidate)
                # measure with the heaviest face present, the widest real case
                widest = max((measure(text, face_of(words[j]), size_px) for j in candidate),
                             default=0.0)
                too_wide = len(current) >= 1 and widest > budget
            if (crosses_cut or voice_change or long_gap or full or forced
                    or sentence_end or too_wide or over_chars):
                phrases.append(current)
                current = []
        current.append(i)
    if current:
        phrases.append(current)
    from caption_lint import validate_card_layout
    for phrase in phrases:
        validate_card_layout(' '.join(words[j]['text'] for j in phrase))
    return phrases


def resolve(words, cuts, style, editorial, uniform_request):
    if not words:
        raise ValueError('No words to resolve; refusing to emit an empty manifest')
    fps = Fraction(style['frame_rate']['numerator'], style['frame_rate']['denominator'])

    def frame(seconds):
        return round(Fraction(str(seconds)) * fps)

    editorial = editorial or {}
    weight_entries = _entries(editorial.get('emphasis_source_indices'), 'emphasis')
    italic_entries = _entries(editorial.get('italic_source_indices'), 'italic')
    size_specs = editorial.get('size_tiers', [])
    quote_spans = _spans(editorial.get('quote_spans'), 'quote')
    voice_spans = _spans(editorial.get('represented_voice_spans'), 'represented voice')
    italic_spans = _spans(editorial.get('italic_spans'), 'italic')

    has_decisions = bool(weight_entries or italic_entries or size_specs
                         or quote_spans or voice_spans or italic_spans)
    if uniform_request and has_decisions:
        raise ValueError('Uniform styling cannot be combined with explicit style decisions')

    profile = style.get('_profile')
    if profile:
        check_profile_contract(profile, style, words)

    voices = style['voices']
    fonts = style.get('fonts') or {}
    tiers = dict(style.get('size_tiers', {}))
    tiers.setdefault('base', 1.0)
    nominal = style['font_size_px']

    for spec in size_specs:
        if spec.get('tier') not in tiers or spec['tier'] == 'base':
            raise ValueError(f"Unknown or non-editorial size tier {spec.get('tier')!r}; "
                             f"declare it in style.size_tiers")
        if type(spec.get('source_index')) is not int:
            raise ValueError('A size tier must name an integer source_index')

    # Decisions live in SOURCE-word index space (the raw transcript), not display
    # position: normalization can merge several source words into one display word.
    available = {i for w in words for i in w['source_indices']}
    owner = {i: w for w in words for i in w['source_indices']}
    named = ([(i, t, 'emphasis') for i, t, _ in weight_entries]
             + [(i, t, 'italic') for i, t, _ in italic_entries]
             + [(s['source_index'], s.get('text'), 'size tier') for s in size_specs])
    stray = sorted({i for i, _, _ in named} - available)
    # Spans are validated the same way. A span that covers no real word used to be
    # silently ignored AND still recorded in the manifest, so the pre-build summary
    # reported a represented voice or an italic run that was never applied.
    for kind, spans in (('represented voice', voice_spans), ('italic', italic_spans),
                        ('quote', quote_spans)):
        for a, b, _ in spans:
            if not (available & set(range(a, b + 1))):
                stray.append(f'{kind} span {a}-{b}')
    if stray:
        raise ValueError(
            f'Editorial source indices match no word: {stray} (the stream covers '
            f'{min(available)}-{max(available)} in SOURCE index space; these are raw '
            'transcript indices, not display-word positions)')
    drifted = [(i, want, owner[i]['text']) for i, want, _ in named
               if want is not None and owner[i]['text'] != want]
    if drifted:
        raise ValueError(
            'Editorial decisions name a different word than the transcript has at that '
            f'source index (index, expected, actual): {drifted[:8]!r} -- these are SOURCE '
            'indices; check them against source_indices in the normalized word file')

    # --- the five axes, resolved independently -------------------------------
    weight_of, italic_of = {}, {}
    for i, _, extra in weight_entries:
        w = extra.get('weight', 'strong')
        if w not in LADDER or w == 'base':
            raise ValueError(f'Emphasis weight must be one of {LADDER[1:]}, got {w!r}')
        weight_of[i] = w
    # Italic is per word. A voice may declare a DEFAULT slant (an italic guest donor
    # is house style), and an explicit decision overrides it in either direction --
    # so quoted terminology can stay upright inside an italic voice, and a host
    # inner thought can be italic while staying host-coloured.
    for i, _, extra in italic_entries:
        italic_of[i] = bool(extra.get('italic', True))
    for a, b, extra in italic_spans:
        for i in range(a, b + 1):
            italic_of[i] = bool(extra.get('italic', True))

    # Represented voice: a span of speech belonging to another voice. Independent of
    # italic and quote -- a host inner thought can stay host-coloured and italic.
    represented = {}
    for a, b, extra in voice_spans:
        voice = extra.get('voice', 'guest')
        if voice not in voices:
            raise ValueError(f'Represented voice {voice!r} is not in style.voices')
        for i in range(a, b + 1):
            represented[i] = voice

    for w in words:
        w['voice'] = next((represented[i] for i in w['source_indices'] if i in represented),
                          w['physical_speaker'])
        if w['voice'] not in voices:
            raise ValueError(f"Speaker {w['voice']!r} is not in style.voices")
        w['weight'] = next((weight_of[i] for i in w['source_indices'] if i in weight_of), 'base')
        explicit = next((italic_of[i] for i in w['source_indices'] if i in italic_of), None)
        w['italic'] = bool(voices[w['voice']].get('italic', False)) if explicit is None else explicit

    gap_threshold = float(style.get('gap_threshold_seconds', 0.75))
    # The hold/blank decision is SHARED with caption_profiles.build_profile_manifest,
    # so it reads the same profile-declared fields that grouper does. It used to read
    # `gap_threshold_seconds`/`trailing_hold_seconds` instead, which meant a profile
    # tuning `caption_hold_through_seconds` changed Leila/Sharran and was silently
    # ignored here -- the two groupers agreed only while their defaults coincided.
    # The legacy style keys still work as a fallback for hand-written job configs.
    trailing_hold = frame(style.get('caption_trailing_hold_seconds',
                                    style.get('trailing_hold_seconds', 0.35)))
    trailing_gap = frame(style.get('caption_hold_through_seconds',
                                   style.get('gap_threshold_seconds', 0.75)))
    max_words = int(style.get('max_words_per_card', 4))
    if max_words < 1:
        raise ValueError('max_words_per_card must be at least 1')

    measure, budget = width_measurer(style)
    face_of = None
    if measure is not None:
        # Grouping runs BEFORE styling, so the eventual weight is unknown here. Measure
        # against the widest face the ladder can produce: a card that fits at the
        # heaviest weight fits at every lighter one, so no later restyle can overflow
        # it onto a second line. Measuring the current (base) weight would only work
        # by luck.
        if not fonts:
            raise ValueError('max_text_width_px needs style.fonts to measure with')
        if (style.get('_profile') or {}).get('allow_weight_variation'):
            missing = [k for w in LADDER for k in (w, f'{w}_italic') if k not in fonts]
            if missing:
                raise ValueError(
                    'the width budget must be measured against every ladder face, but '
                    f'style.fonts lacks {missing}. A profile that allows weight variation '
                    'gets restyled by the director AFTER grouping, so measuring only the '
                    'declared base face lets a payoff-weight card overflow in Premiere.')
        # Size tiers are applied AFTER grouping, and resolve_director_style can lift
        # a card to its peak cue size without regrouping, so a card measured at the
        # nominal size can still overflow once restyled. Measure at the largest size
        # the card can reach, for the same reason we measure the heaviest face.
        scales = [1.0] + [float(v) for v in (style.get('size_tiers') or {}).values()]
        if (style.get('_profile') or {}).get('allow_weight_variation'):
            scales.append(DIRECTOR_PEAK_SCALE)
        measure_size = style['font_size_px'] * max(scales)
        widest_face = max(fonts.values(),
                          key=lambda f: measure('HAMBURGEFONSTIV', f, measure_size))

        def face_of(word):
            return widest_face

    phrases = group(words, cuts, frame, gap_threshold, max_words,
                    editorial.get('group_ends'),
                    measure=measure, budget=budget, face_of=face_of,
                    size_px=(measure_size if measure is not None
                             else style['font_size_px']))

    timeline_end = style.get('timeline_end_frame')
    if timeline_end is None:
        timeline_end = frame(words[-1]['end']) + trailing_hold
    timeline_end = int(timeline_end)

    cards = []
    for n, phrase in enumerate(phrases):
        first, last = words[phrase[0]], words[phrase[-1]]
        start, speech_end = frame(first['start']), frame(last['end'])
        next_start = (frame(words[phrases[n + 1][0]]['start'])
                      if n + 1 < len(phrases) else timeline_end)
        # Hold until the next card when the gap is short; otherwise release shortly
        # after speech ends rather than leaving the card hanging.
        end = next_start if next_start - speech_end <= trailing_gap \
            else min(next_start, speech_end + trailing_hold)
        end = max(start + 1, end)

        voice = first['voice']
        spec = voices[voice]
        out = []
        for i in phrase:
            w = words[i]
            word = dict(text=w['text'], weight=w['weight'], italic=bool(w['italic']),
                        color=spec['color'], source_indices=w['source_indices'])
            # `style.fonts` exists so width can be MEASURED with the real faces.
            # The face is only stamped into the manifest on request, because a
            # director restyles weight afterwards without touching font_postscript
            # -- a stamped face then contradicts the weight and the builder (rightly)
            # refuses. Leaving it out keeps the donor's run map the single source
            # of truth for which face a (weight, italic) pair resolves to.
            if style.get('emit_font_postscript'):
                key = f"{w['weight']}_italic" if w['italic'] else w['weight']
                if key not in fonts:
                    raise ValueError(f'style.fonts has no face for {key!r}')
                word['font_postscript'] = fonts[key]
            out.append(word)

        owned = {i for w in out for i in w['source_indices']}
        applicable = [s['tier'] for s in size_specs if s['source_index'] in owned]
        tier = max(applicable, key=lambda t: tiers[t]) if applicable else 'base'
        size = round(nominal * tiers[tier])

        cards.append(dict(id=f'card-{n:03d}', start_frame=start, end_frame=end,
                          speech_end_frame=speech_end, normalized_indices=phrase,
                          text=' '.join(w['text'] for w in out), speaker=voice,
                          physical_speaker=first['physical_speaker'], words=out,
                          y_pct=float(style['y_pct']),
                          size_tier=tier, font_size_px=size,
                          # Kept so a later width-fit shrink can never be mistaken for,
                          # or silently erase, an editorial size decision.
                          requested_size_tier=tier, requested_font_size_px=size))

    # Quote punctuation: applied to the span's own first and last words, wherever
    # those landed. It adds marks only -- no colour change, no implied italic.
    quoted_spans = []
    if quote_spans:
        flat = [(c, wi, w) for c in cards for wi, w in enumerate(c['words'])]
        for a, b, extra in quote_spans:
            inside = [(c, wi, w) for c, wi, w in flat
                      if any(a <= i <= b for i in w['source_indices'])]
            if not inside:
                raise ValueError(f'Quote span {(a, b)} covers no word')
            (c0, i0, w0), (c1, i1, w1) = inside[0], inside[-1]
            w0['text'] = style.get('quote_open', '“') + w0['text']
            w1['text'] = w1['text'] + style.get('quote_close', '”')
            for c in {id(c0): c0, id(c1): c1}.values():
                c['text'] = ' '.join(x['text'] for x in c['words'])
            quoted_spans.append(dict(**{'from': a, 'to': b},
                                     opened_in=c0['id'], closed_in=c1['id']))

    segments = partition(cards, cuts)

    owners = [i for s in segments if s['source_coverage_owner']
              for w in s['words'] for i in w['source_indices']]
    expected = sorted(available)
    if sorted(owners) != expected or len(owners) != len(expected):
        raise AssertionError('Source coverage is not exactly once per word')
    if any(s['start_frame'] < c < s['end_frame'] for s in segments for c in cuts):
        raise AssertionError('A render segment spans a camera cut')

    from caption_lint import validate_card_layout
    for segment in segments:
        validate_card_layout(segment['text'],style.get('_profile'))

    manifest = dict(
        caption_profile=(style.get('_profile') or {}).get('id','alex'),
        status='MECHANICALLY_RESOLVED_STRUCTURE_ONLY_NOT_EDITORIAL_APPROVAL',
        frame_rate=dict(style['frame_rate']), cards=cards, render_segments=segments,
        canvas_px=style.get('canvas_px'), nominal_font_size_px=nominal,
        resolution_scale=style.get('resolution_scale', 1.0),
        cut_frames=cuts, quoted_spans=quoted_spans,
        represented_voice_spans=[dict(**{'from': a, 'to': b},
                                      voice=e.get('voice', 'guest'))
                                 for a, b, e in voice_spans],
        evidence=dict(source_words=len(expected), source_coverage_complete=True,
                      grouping=('EDITORIAL_ENDPOINTS' if editorial.get('group_ends')
                                else 'MECHANICAL_GAP_CUT_VOICE_AND_WORD_CAP'
                                     + ('_AND_MEASURED_WIDTH' if measure is not None else '')),
                      styling=('EXPLICIT_EDITORIAL_DECISIONS' if has_decisions
                               else 'NONE_ALL_BASE_WEIGHT_UPRIGHT'),
                      scene_boundaries='SUPPLIED_NOT_VISUALLY_VERIFIED_BY_THIS_SCRIPT'),
        limitations=[
            # This block is evidence, so it must not state the opposite of what ran.
            # For an Alex max_lines:1 build the width budget is mandatory and always
            # measured, yet this line claimed otherwise on every such manifest.
            (f'Rendered text width WAS measured against {widest_face!r} at '
             f'{measure_size:.1f}px (the largest size a card can reach after size '
             f'tiers) with a {budget:.1f}px budget; cards are bounded by that budget '
             'and by the word cap.'
             if measure is not None else
             'Rendered text width was not measured; cards are bounded by a word cap only.'),
            'Timing comes from the supplied word timings; no acoustic onset certification.',
            'No native save/reopen or render approval.',
        ])
    manifest['style_review'] = style_review(segments, uniform_request)
    return manifest


def style_review(segments, uniform_request):
    if uniform_request:
        return dict(mode='uniform_requested', user_request=uniform_request)
    weight, italic = [], []
    for card in segments:
        for i, w in enumerate(card['words']):
            if w['weight'] not in (None, '', 'base'):
                weight.append(dict(segment_id=card['id'], word_index=i,
                                   text=w['text'], value=w['weight']))
            if w['italic'] is True:
                italic.append(dict(segment_id=card['id'], word_index=i,
                                   text=w['text'], value=True))
    size = [dict(segment_id=c['id'], tier=c['size_tier'], font_size_px=c['font_size_px'])
            for c in segments if c.get('size_tier') not in (None, '', 'base')]
    review = dict(mode='editorial', reviewed=True,
                  segment_ids=[c['id'] for c in segments])
    review['weight'] = (
        dict(status='applied', targets=weight,
             reason='Per-word weight supplied as an explicit editorial decision list.')
        if weight else
        dict(status='not_applicable',
             reason='No emphasis was supplied; every word stays at the donor base weight.'))
    review['italic'] = (
        dict(status='applied', targets=italic,
             reason='Italic supplied per word or span, rendered by a real italic donor face.')
        if italic else
        dict(status='not_applicable',
             reason='No word in this clip was marked italic.'))
    review['size'] = (
        dict(status='applied', targets=size,
             reason=('Card-level intensity tiers supplied as an explicit editorial decision; '
                     'width fitting is recorded separately and may not alter a tiered card.'))
        if size else
        dict(status='not_applicable',
             reason=('No editorial size tier was assigned. Width measurement, where a '
                     'profile sets a budget, only SPLITS cards -- a fitted size is never '
                     'reported as intentional editorial sizing.')))
    return review


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--words', required=True, help='normalized word JSON')
    p.add_argument('--cuts', help='camera cut frames JSON')
    p.add_argument('--style', required=True, help='faces/colours/position/rate config JSON')
    p.add_argument('--caption-profile', choices=('alex',),
                   help="load profiles/<id>.json as the source of truth and ENFORCE its "
                        "contract. Without it the profile's declarations are unchecked, "
                        "which is how max_lines and normalization were silently ignored.")
    p.add_argument('--editorial', help='explicit editorial decisions JSON')
    p.add_argument('--uniform-request',
                   help="verbatim user request for uniform styling; records "
                        "mode=uniform_requested instead of an editorial review")
    p.add_argument('--target-canvas',
                   help="WxH of the sequence being captioned, e.g. 1080x1920. Scales the "
                        "profile's pixel values from its own canvas and records the canvas so "
                        "the native builder refuses a mismatched sequence.")
    p.add_argument('--director-style',
                   help="caption_director stream: its per-word represented-voice colour (c) "
                        "becomes represented_voice_spans BEFORE grouping, so a colour change is "
                        "also a card boundary. resolve_director_style later applies weight/"
                        "italic/size from the same stream.")
    p.add_argument('--out', required=True)
    a = p.parse_args()

    out = Path(a.out)
    if out.exists():
        raise FileExistsError(out)
    style = json.loads(Path(a.style).read_text())
    if a.caption_profile:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).resolve().parent))
        from caption_profiles import load_profile
        profile = load_profile(a.caption_profile)
        style = style_from_profile(profile, style,
                                   parse_canvas(a.target_canvas) if a.target_canvas else None)
        style['_profile'] = profile
    elif a.target_canvas:
        raise ValueError('--target-canvas scales a profile; pass --caption-profile too')
    words = load_words(a.words)
    editorial = json.loads(Path(a.editorial).read_text()) if a.editorial else None
    if a.director_style:
        editorial = with_director_voice_spans(editorial, json.loads(Path(a.director_style).read_text()),
                                              words)
    manifest = resolve(words, load_cuts(a.cuts), style, editorial, a.uniform_request)
    with out.open('x') as f:
        json.dump(manifest, f, indent=2)
    counts = style_counts(manifest)
    print(json.dumps(dict(cards=len(manifest['cards']),
                          render_segments=len(manifest['render_segments']),
                          source_words=manifest['evidence']['source_words'],
                          style_review=manifest['style_review']['mode'],
                          status=manifest['status'], **counts)))


def style_counts(manifest):
    """The style summary to emit BEFORE building: a flat result is an anomaly."""
    import collections
    segs = manifest.get('render_segments', manifest.get('cards', []))
    weights = collections.Counter(w['weight'] for c in segs for w in c['words'])
    italics = collections.Counter(
        f"{c['speaker']}_{'italic' if w['italic'] else 'upright'}"
        for c in segs for w in c['words'])
    tiers = collections.Counter(c.get('size_tier', 'base') for c in segs)
    return dict(weights=dict(weights), runs_by_voice_and_slant=dict(italics),
                size_tiers=dict(tiers),
                quoted_spans=len(manifest.get('quoted_spans', [])),
                represented_voice_spans=len(manifest.get('represented_voice_spans', [])),
                style_source=manifest.get('style_resolution', {}).get('source')
                             or manifest.get('evidence', {}).get('styling'))


if __name__ == '__main__':
    main()

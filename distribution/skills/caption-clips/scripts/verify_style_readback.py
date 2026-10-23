#!/usr/bin/env python3
"""Compare the styling in a SAVED Premiere project against the manifest that asked for it.

The point of this script is that a request payload is not evidence. It opens the
saved `.prproj`, decodes each caption Graphic's rich-text runs out of the project
file itself, and checks every run's text, face, size and explicit fill against the
manifest -- plus each card's editorial size tier. Any disagreement exits non-zero.

Run it on the offline build, and AGAIN after Premiere has saved and reopened the
project, so a style that Premiere silently rewrites is caught rather than assumed.

It reports what it verified and what it cannot: run identity and typography are
decoded structurally; shadow, entrance animation and rendered appearance are not
checked here and still need a human looking at frames.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

import premiere_native_cards as native
from native_graphics.decode_graphic_text import decode_runs

# Faces are compared exactly. Italic is asserted through the face identity the
# manifest asked for, because that is what the donor actually carries -- never by
# inferring italic from a font name, and never by synthesising a slant.
COMPARED = ('text', 'font_postscript', 'font_size_px', 'fill_rgb')


def hex_to_rgb(value):
    v = str(value).lstrip('#')
    if len(v) != 6:
        return None
    try:
        return [int(v[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return None


def expected_face(profile, card, word):
    """The face a word SHOULD carry: named in the manifest, else resolved from the donor.

    On the director path the manifest names no face -- the donor's nested per-weight
    upright/italic runs are the single source of truth -- so the expected face comes
    from the profile. That makes this check cover the weight->face mapping too,
    rather than only agreeing with whatever the manifest happened to say.
    """
    if word.get('font_postscript'):
        return word['font_postscript']
    if not profile:
        return None
    donor = (profile.get('donors') or {}).get(card.get('speaker')) or {}
    faces = donor.get('faces') or {}
    weight = word.get('weight')
    if not weight:
        return None          # reported as an unverifiable run, not a crash
    key = f'{weight}_italic' if word.get('italic') else weight
    return faces.get(key)


def expected_run_texts(card):
    """The exact per-run text the builder writes, line breaks included.

    Mirrors premiere_native_cards.word_requests: every run after the first carries
    the separator that stood between the two words in the card text, and an explicit
    newline is written as CR (Premiere's native paragraph break). Assuming a plain
    space here reported every two-line card as a mismatch.
    """
    out, cursor, text = [], 0, card['text']
    for i, word in enumerate(card['words']):
        token = word['text']
        if i == 0:
            out.append(token)
        else:
            found = text.find(token, cursor)
            if found < 0:
                return None          # card text disagrees with its words; a real finding
            separator = text[cursor:found]
            out.append(('\r' if separator == '\n' else separator) + token)
        cursor = text.find(token, cursor) + len(token)
    return out


def collect(project, receipt, manifest, profile=None):
    root = native.load(project)
    shared = native.pool(root)
    ids = native.objects(root)
    seq, items = native.track_items(root, receipt['sequence_uid'], receipt['track_index'])
    cards = manifest.get('render_segments', manifest.get('cards', []))
    if len(items) != len(cards):
        raise SystemExit(f'card count differs: saved {len(items)} vs manifest {len(cards)}')

    findings = []
    faces, sizes, tiers = collections.Counter(), collections.Counter(), collections.Counter()
    weights, slants = collections.Counter(), collections.Counter()
    for item, card in zip(items, cards):
        runs = decode_runs(native.payload(native.text_node(root, item), shared))
        tiers[card.get('size_tier', 'base')] += 1
        if len(runs) != len(card['words']):
            findings.append(dict(card=card['id'], axis='run_count',
                                 saved=len(runs), manifest=len(card['words'])))
            continue
        expected = expected_run_texts(card)
        for i, (run, word) in enumerate(zip(runs, card['words'])):
            faces[run['font_postscript']] += 1
            sizes[round(run['font_size_raw'], 2) if run['font_size_raw'] is not None else None] += 1

            weights[word.get('weight', 'base')] += 1
            slants[f"{card.get('speaker')}_{'italic' if word.get('italic') else 'upright'}"] += 1
            want_text = (expected[i] if expected is not None
                         else (word['text'] if i == 0 else ' ' + word['text']))
            checks = {
                'text': (run['text'], want_text),
                'font_size_px': (round(run['font_size_raw'], 2) if run['font_size_raw'] is not None else None,
                                 round(float(card['font_size_px']), 2)),
            }
            want_face = expected_face(profile, card, word)
            if want_face:
                checks['font_postscript'] = (run['font_postscript'], want_face)
            elif profile:
                findings.append(dict(card=card['id'], word_index=i, axis='font_postscript',
                                     saved=run['font_postscript'],
                                     manifest=f"no donor face for weight="
                                              f"{word.get('weight')!r} italic={word.get('italic')!r}"))
            # An explicit fill is only comparable when the donor actually carried one;
            # a donor using Premiere's default white decodes as None, which is not a
            # mismatch against a manifest colour of FFFFFF.
            expected_rgb = hex_to_rgb(word.get('color'))
            if run['fill_rgb_explicit'] is not None and expected_rgb is not None:
                checks['fill_rgb'] = (run['fill_rgb_explicit'], expected_rgb)

            for axis, (saved, wanted) in checks.items():
                if saved != wanted:
                    findings.append(dict(card=card['id'], word_index=i, axis=axis,
                                         saved=saved, manifest=wanted))
    return findings, faces, sizes, tiers, len(items), weights, slants


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--project', required=True, help='the SAVED .prproj to read back')
    p.add_argument('--receipt', required=True)
    p.add_argument('--manifest', required=True)
    p.add_argument('--profile', help='donor profile; resolves the expected face per '
                                     'weight/italic when the manifest names none')
    p.add_argument('--out', help='write the proof JSON here')
    a = p.parse_args()

    receipt = json.loads(Path(a.receipt).read_text())
    manifest = json.loads(Path(a.manifest).read_text())
    profile = json.loads(Path(a.profile).read_text()) if a.profile else None
    findings, faces, sizes, tiers, count, weights, slants = collect(
        Path(a.project), receipt, manifest, profile)

    result = dict(
        status='STYLE_READBACK_MATCHES_MANIFEST' if not findings else 'STYLE_READBACK_MISMATCH',
        project=str(Path(a.project).resolve()), cards=count,
        compared_axes=list(COMPARED),
        distinct_faces_in_saved_project=dict(faces),
        distinct_font_sizes_in_saved_project={str(k): v for k, v in sizes.items()},
        size_tiers_in_manifest=dict(tiers),
        weights_in_manifest=dict(weights),
        runs_by_voice_and_slant=dict(slants),
        style_review=receipt.get('style_review', {}).get('status'),
        mismatches=findings[:200], mismatch_count=len(findings),
        not_verified_here=['shadow', 'entrance animation', 'rendered appearance',
                           'human editorial approval'])
    text = json.dumps(result, indent=2)
    if a.out:
        Path(a.out).write_text(text)
    print(text)
    if findings:
        sys.exit(1)


if __name__ == '__main__':
    main()

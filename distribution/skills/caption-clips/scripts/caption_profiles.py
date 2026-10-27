#!/usr/bin/env python3
"""Shared caption-profile loading and native semantic-card construction."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PROFILE_IDS = ("alex", "leila", "sharran")
FONT_SOURCES = {
    "ClashGroteskVariable-Regular": (Path("__ACQ_ASSETS__") / "fonts" / "ClashGrotesk-Variable.ttf", 0),
    "Inter-Regular": (Path("__ACQ_ASSETS__") / "fonts" / "Inter-Regular.otf", 0),
    "Inter-SemiBold": (Path("__ACQ_ASSETS__") / "fonts" / "Inter-SemiBold.otf", 0),
    "Inter-Italic": (Path("__ACQ_ASSETS__") / "fonts" / "Inter-Italic.otf", 0),
}


def load_profile(profile_id: str | None) -> dict:
    if not profile_id:
        raise ValueError(
            "no caption profile given. The brand is never guessed -- ask which of "
            f"{sorted(PROFILE_IDS)} applies and pass it explicitly.")
    if profile_id not in PROFILE_IDS:
        raise ValueError(f"unknown caption profile: {profile_id}")
    data = json.loads((SKILL / "profiles" / f"{profile_id}.json").read_text())
    if data.get("id") != profile_id:
        raise ValueError(f"profile id mismatch: {profile_id}")
    return data


def sentence_case_words(words: list[dict]) -> list[dict]:
    """Preserve punctuation/proper casing; sentence-case an all-lower stream."""
    out = deepcopy(words)
    sentence_start = True
    for row in out:
        text = str(row.get("word", row.get("text", "")))
        if sentence_start and text:
            m = re.search(r"[A-Za-z]", text)
            if m:
                text = text[:m.start()] + text[m.start()].upper() + text[m.start()+1:]
        if "word" in row:
            row["word"] = text
        else:
            row["text"] = text
        sentence_start = bool(re.search(r"[.!?][\"'”’)]*$", text)) or bool(row.get("sentence_end"))
    return out


def preserve_first_person(text: str) -> str:
    """Restore the English pronoun after any profile-specific lowercase pass."""
    return re.sub(r"(?<![\w])i(?!\.e\.)(?=(?:['’](?:m|ve|ll|d)\b)|\b)", "I", text)


def capitalize_letter_names(text: str) -> str:
    """Capitalize a standalone plural letter name, never a contraction suffix."""
    return re.sub(r"(?<!\w)t(['’]s)\b", r"T\1", text)


def validate_display_casing(text: str) -> None:
    """Refuse the known substring-replacement corruption before native export."""
    if re.search(r"[a-z]T['’]s\b", text):
        raise ValueError('Mixed-case contraction suffix; reconcile display text with source: ' + text)


def clean_profile_display_words(words: list[dict]) -> list[dict]:
    """Apply the shared clean-caption punctuation surface without losing evidence.

    Keep apostrophes, quote marks, question/exclamation marks, numeric separators,
    decimals, domains, and standard abbreviations. Remove prose commas, periods,
    colons, and semicolons from display text only.
    """
    out = deepcopy(words)
    quote_open = False
    for row in out:
        key = "word" if "word" in row else "text"
        text = str(row.get(key, ""))
        if re.search(r"[.!?][\"'”’)]*$", text):
            row["sentence_end"] = True
        low = text.lower().strip('"“”‘’')
        protected_period = (bool(re.search(r"\d\.\d", text))
                            or bool(re.search(r"[a-z0-9]\.[a-z]{2,}", low))
                            or low.rstrip(".,") in {"u.s.", "e.g.", "i.e.", "etc."}
                            or bool(re.fullmatch(r"(?:[a-z]\.){2,}", low.rstrip(","))))
        text = re.sub(r"(?<!\d),(?!\d)", "", text)
        text = re.sub(r"[;:]", "", text)
        if not protected_period:
            text = re.sub(r"\.(?=[\"”’']*$)", "", text)
        text = re.sub(r"[-–—](?=[?!\"”’']*$)", "", text)

        represented = str(row.get("represented_speaker", "")).strip().lower()
        explicit_quote = bool(row.get("quoted") or row.get("italic") or
                              (represented and represented not in {"host", "self"}))
        has_open = "“" in text
        has_close = "”" in text
        straight_quotes = text.count('"')
        row["quote_italic"] = bool(quote_open or explicit_quote or has_open or has_close or straight_quotes)
        if has_open:
            quote_open = True
        if has_close:
            quote_open = False
        if straight_quotes % 2:
            quote_open = not quote_open
        row[key] = preserve_first_person(capitalize_letter_names(text))
    return out


def wrap_two_lines(tokens: list[str], max_chars: int) -> tuple[str, list[str]]:
    """Choose a stable one/two-line break minimizing overflow and imbalance."""
    if not tokens:
        raise ValueError("cannot wrap an empty card")
    one = " ".join(tokens)
    if len(one) <= max_chars:
        return one, [one]
    candidates = []
    for split in range(1, len(tokens)):
        left, right = " ".join(tokens[:split]), " ".join(tokens[split:])
        overflow = max(0, len(left)-max_chars) + max(0, len(right)-max_chars)
        candidates.append((overflow, abs(len(left)-len(right)), split, left, right))
    overflow, _, _, left, right = min(candidates)
    if overflow:
        raise ValueError(f"caption cannot fit two {max_chars}-character lines: {one}")
    return left + "\n" + right, [left, right]


def _word_text(row: dict) -> str:
    return str(row.get("word", row.get("text", ""))).strip()


def _frame(value: float, fps: float) -> int:
    return max(0, int(round(float(value) * fps)))


def _validate_rendered_width(seg: dict, profile: dict) -> None:
    """Fail closed on the exact approved font face before Premiere construction."""
    if "max_text_width_pct" not in profile:
        return
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise ValueError("Pillow is required for caption width preflight") from exc
    size = int(seg["font_size_px"])
    limit = float(profile["frame_width_px"]) * float(profile["max_text_width_pct"]) / 100.0
    fonts = {}
    words = iter(seg["words"])
    for line in seg["lines"]:
        line_words = [next(words) for _ in line.split()]
        width = 0.0
        for position, word in enumerate(line_words):
            face = word["font_postscript"]
            source = FONT_SOURCES.get(face)
            if not source or not source[0].is_file():
                raise ValueError(f"no exact width-preflight face for {face}")
            # The collection index is NOT the word position. Binding both to `index`
            # meant `if index:` read the .ttc index (always 0 here), so the space
            # between words was never measured and a line could clear the budget by
            # ~12-14px per gap while overflowing in Premiere.
            path, ttc_index = source
            if face not in fonts:
                fonts[face] = ImageFont.truetype(str(path), size, index=ttc_index)
            font = fonts[face]
            if position:
                width += font.getlength(" ")
            width += font.getlength(word["text"])
        if width > limit:
            raise ValueError(f"caption line exceeds {profile['max_text_width_pct']}% safe width: {line!r} ({width:.1f}px > {limit:.1f}px)")


def _line_one_word_count(tokens: list[str], lines: list[str]) -> int:
    if len(lines) < 2:
        return len(tokens)
    for split in range(1, len(tokens)):
        if " ".join(tokens[:split]) == lines[0]:
            return split
    raise ValueError("stored line break does not map to card words")


def _display_state_indices(group: list[dict], tokens: list[str], lines: list[str], profile: dict) -> list[int]:
    """Return the last visible word for each display state.

    Complete cards are the default. Leila's adaptive mode admits a conservative
    line reveal for slow delivery and reserves word reveals for exceptionally
    separated speech or an explicit reviewed override.
    """
    final = len(group) - 1
    mode = str(next((row.get("reveal_mode") for row in group if row.get("reveal_mode")),
                    profile.get("reveal_mode", "full_card")))
    if mode == "full_card" or len(group) == 1:
        return [final]
    if mode == "word":
        return list(range(len(group)))

    onsets = [float(row["start"]) for row in group]
    gaps = [b-a for a,b in zip(onsets, onsets[1:])]
    seconds_per_word = (onsets[-1]-onsets[0]) / max(1, len(group)-1)
    slow_word_delivery = (seconds_per_word >= float(profile.get("word_reveal_min_seconds_per_word", 99))
                          and bool(gaps)
                          and min(gaps) >= float(profile.get("word_reveal_min_interword_gap_seconds", 99)))
    if slow_word_delivery:
        return list(range(len(group)))

    if len(lines) == 2:
        split = _line_one_word_count(tokens, lines)
        second_line_delay = onsets[split] - onsets[0]
        if mode == "line" or second_line_delay >= float(profile.get("line_reveal_min_delay_seconds", 99)):
            return [split-1, final]
    return [final]


def split_caption_gap_shift(upper_glyph_bottom, lower_glyph_top, divider_y):
    """Translate rendered foreground glyph bounds so their gap bisects the seam.

    Bounds must be measured after all native transforms, excluding shadow pixels.
    Apply the same delta to all caption layers; never substitute text-box bounds.
    """
    import math
    if not all(math.isfinite(float(v)) for v in (upper_glyph_bottom, lower_glyph_top, divider_y)):
        raise ValueError("nonfinite caption gap geometry")
    if lower_glyph_top <= upper_glyph_bottom:
        raise ValueError("two distinct rendered lines with a positive gap required")
    return float(divider_y) - (float(upper_glyph_bottom) + float(lower_glyph_top)) / 2


def cap_hold_at_picture_cut(start_frame: int, end_frame: int,
                            speech_end_frame: int, picture_cut_frames) -> int:
    """Cap only post-speech dwell. A real spoken continuation survives a cut.

    Call on the whole semantic card BEFORE layout segmentation. Frame intervals
    are half-open; ceil the mapped last spoken sample to obtain speech_end_frame.
    """
    return min([end_frame] + [int(c) for c in picture_cut_frames
               if start_frame < c < end_frame and speech_end_frame <= c])


def build_profile_manifest(words: list[dict], profile: dict, *, fps_num=24000, fps_den=1001,
                           card_gap=0.32, hold=0.24, reviewed_plan: list[dict] | None = None,
                           hold_through: float | None = None,
                           trailing_hold: float | None = None, picture_cut_frames=()) -> dict:
    """Build reviewed-profile candidates with progressive native reveal segments.

    This is deterministic grouping for the two new profiles. It intentionally
    emits a style_review proposal that must be reviewed before native construction.
    """
    if profile["id"] == "alex":
        raise ValueError("alex continues to use the existing Oliver/SPICE manifest path")
    # Match Alex unless the profile says otherwise: hold a card through a pause up
    # to `hold_through`, and otherwise release it `trailing_hold` after speech ends.
    if hold_through is None:
        hold_through = float(profile.get("caption_hold_through_seconds", 0.75))
    if trailing_hold is None:
        trailing_hold = float(profile.get("caption_trailing_hold_seconds", 0.35))
    fps = fps_num / fps_den
    rows = clean_profile_display_words(sentence_case_words(words))
    for normalized_index,row in enumerate(rows):
        row.setdefault("normalized_index",normalized_index)
        row.setdefault("source_indices",[normalized_index])
    groups, group_specs, omissions = [], [], []
    if reviewed_plan is not None:
        cursor = 0
        for number, spec in enumerate(reviewed_plan, 1):
            first, last = int(spec["first"]), int(spec["last"])
            if first != cursor or last < first or last >= len(rows):
                raise ValueError(f"reviewed card {number} must continue exact source coverage at word {cursor}")
            group = deepcopy(rows[first:last+1])
            if spec.get("action") == "omit":
                if spec.get("reason") not in {"nonessential_filler", "listener_backchannel"}:
                    raise ValueError("caption omission requires a supported reviewed reason")
                omissions.append({"reason": spec["reason"],
                    "normalized_indices": [r["normalized_index"] for r in group],
                    "source_indices": [i for r in group for i in r["source_indices"]],
                    "start": float(group[0]["start"]), "end": float(group[-1]["end"]),
                    "text": " ".join(_word_text(r) for r in group), "audio_retained": True})
                cursor = last + 1
                continue
            mode = spec.get("reveal", "full_card")
            if mode not in {"full_card", "line", "word"}:
                raise ValueError(f"reviewed card {number} has unsupported reveal mode: {mode}")
            for row in group:
                row["reveal_mode"] = mode
                if spec.get("quote"):
                    row["quote_italic"] = True
            lines = [str(line) for line in spec["lines"]]
            if not 1 <= len(lines) <= int(profile["max_lines"]):
                raise ValueError(f"reviewed card {number} has invalid line count")
            groups.append(group); group_specs.append({**spec, "lines": lines})
            cursor = last + 1
        if cursor != len(rows):
            raise ValueError(f"reviewed plan stops at word {cursor}; source has {len(rows)} words")
    else:
        current = []
        for row in rows:
            text = _word_text(row)
            if not text:
                continue
            if current:
                gap = float(row["start"]) - float(current[-1]["end"])
                prospective = [_word_text(w) for w in current] + [text]
                style_boundary = bool(row.get("quote_italic")) != bool(current[-1].get("quote_italic"))
                too_wide = False
                try:
                    wrap_two_lines(prospective, int(profile["max_chars_per_line"]))
                except ValueError:
                    too_wide = True
                quote_limit = int(profile.get("max_words_per_quote_card", profile["max_words_per_card"]))
                active_limit = quote_limit if bool(current[-1].get("quote_italic")) else int(profile["max_words_per_card"])
                if gap >= card_gap or style_boundary or current[-1].get("sentence_end") or len(current) >= active_limit or too_wide:
                    groups.append(current); group_specs.append({}); current = []
            current.append(row)
            if re.search(r"[.!?][\"'”’)]*$", text):
                groups.append(current); group_specs.append({}); current = []
        if current:
            groups.append(current); group_specs.append({})

    cards, segments = [], []
    for ci, (group, group_spec) in enumerate(zip(groups, group_specs), 1):
        card_id = f"card-{ci:04d}"
        tokens = [_word_text(w) for w in group]
        if group and all(bool(w.get("quote_italic")) for w in group):
            if not re.match(r'^["“]', tokens[0]):
                tokens[0] = '"' + tokens[0]
            if not re.search(r'["”]$', tokens[-1]):
                tokens[-1] = tokens[-1] + '"'
        if group_spec:
            final_lines = group_spec["lines"]
            expected = " ".join(final_lines)
            actual = " ".join(tokens)
            if expected != actual:
                raise ValueError(f"reviewed card {ci} text mismatch: {expected!r} != {actual!r}")
            final_text = "\n".join(final_lines)
        else:
            final_text, final_lines = wrap_two_lines(tokens, int(profile["max_chars_per_line"]))
        # Card end: HOLD THROUGH a short pause instead of blanking between phrases.
        #
        # This used to be `min(last_word_end, next_card_start)`, which only ever
        # clamped DOWN -- so every pause at or above the grouping threshold left a
        # visible hole on the caption track. Cards split for a non-pause reason
        # (word cap, sentence end, width) closed up by accident, but a genuine
        # 0.3-0.7s breath did not. Alex's rule is the approved one: hold until the
        # next card unless the pause is genuinely long, then release after a
        # trailing hold. Thresholds are profile-declared, not hardcoded.
        speech_end = float(group[-1]["end"])
        floor_end = max(speech_end, float(group[-1]["start"]) + hold)
        if ci < len(groups):
            next_start = float(groups[ci][0]["start"])
            if next_start - speech_end <= hold_through:
                end = next_start
            else:
                end = min(next_start, max(floor_end, speech_end + trailing_hold))
        else:
            # Last card: hold past the final word by the same trailing hold every
            # other card gets, and that the Alex grouper gives its last card. Ending
            # exactly at speech end snapped the closing caption off on the last
            # syllable while every interior card held.
            end = max(floor_end, speech_end + trailing_hold)
        # Do not bridge a deliberately omitted backchannel with the previous card.
        for omitted in omissions:
            if speech_end <= omitted["start"] < end:
                end = omitted["start"]
        # Resolve dwell before creating any layout continuation. Never reintroduce
        # a finished phrase solely because its visual hold crossed a camera cut.
        import math
        speech_end_frame = math.ceil(speech_end * fps)
        cap = cap_hold_at_picture_cut(_frame(group[0]["start"], fps),
                                     _frame(end, fps), speech_end_frame, picture_cut_frames)
        if cap < _frame(end, fps):
            end = cap / fps
        card_words = []
        for wi, row in enumerate(group):
            token = tokens[wi]
            italic = bool(profile.get("allow_quote_italics") and row.get("quote_italic"))
            strong = bool(row.get("emphasis") or row.get("weight") == "strong") and profile.get("allow_weight_variation")
            face = row.get("font_postscript") or (profile.get("emphasis_font_postscript") if strong else (
                profile.get("italic_font_postscript") if italic else profile["body_font_postscript"]))
            card_words.append({"text": token, "weight": "strong" if strong else "base",
                               "font_postscript": face, "color": "FFFFFF", "italic": italic,
                               "source_indices": row["source_indices"]})
        # Reviewed composition overrides historical profile placement for every reveal.
        placement = group_spec or {}
        default_y = 50.0 if placement.get("composition") in {"standing_qa", "seated_medium"} else profile["default_y_pct"]
        y_pct = float(placement.get("y_pct", default_y))
        if not 0 < y_pct < 100:
            raise ValueError(f"reviewed card {ci} has invalid caption y_pct")
        card = {"id": card_id, "semantic_card_id": card_id, "caption_profile": profile["id"],
                "start_frame": _frame(group[0]["start"], fps), "end_frame": _frame(end, fps),
                "start": float(group[0]["start"]), "end": end, "speech_end_frame": speech_end_frame, "speaker": "host", "kind": "speech",
                "text": final_text, "lines": final_lines, "line_breaks": [len(final_lines[0])] if len(final_lines)==2 else [],
                "normalized_indices": [w["normalized_index"] for w in group],
                "y_pct": y_pct, "font_size_px": profile.get("font_size_px", 74),
                "shadow_profile": profile["shadow_profile"], "words": card_words}
        cards.append(card)
        reveal_indices = _display_state_indices(group, tokens, final_lines, profile)
        for ri in reveal_indices:
            state_index = reveal_indices.index(ri)
            prior_ri = reveal_indices[state_index-1] if state_index else -1
            start = float(group[prior_ri+1]["start"])
            stop = float(group[ri+1]["start"]) if state_index+1 < len(reveal_indices) else end
            visible = tokens[:ri+1]
            if group_spec and ri == len(group)-1:
                lines = final_lines
                text = final_text
            elif group_spec and group_spec.get("reveal") == "line" and state_index == 0:
                lines = [final_lines[0]]
                text = final_lines[0]
            else:
                text, lines = wrap_two_lines(visible, int(profile["max_chars_per_line"]))
            reveal_words = deepcopy(card_words[:ri+1])
            segments.append({"id": f"{card_id}/reveal-{ri+1}", "semantic_card_id": card_id,
                "caption_profile": profile["id"], "reveal_index": state_index+1, "source_coverage_owner": ri == len(group)-1,
                "continuation": state_index > 0, "animation_elapsed_frames": max(0, _frame(start, fps)-card["start_frame"]),
                "start_frame": _frame(start, fps), "end_frame": max(_frame(stop, fps), _frame(start, fps)+1),
                "speaker": "host", "kind": "speech", "text": text, "lines": lines,
                "line_breaks": [len(lines[0])] if len(lines)==2 else [], "y_pct": y_pct,
                "font_size_px": profile.get("font_size_px", 74),
                "shadow_profile": profile["shadow_profile"], "words": reveal_words})
            if "max_text_width_pct" in profile:
                segments[-1]["max_text_width_pct"] = profile["max_text_width_pct"]
        if "max_text_width_pct" in profile:
            card["max_text_width_pct"] = profile["max_text_width_pct"]
    # ASR tokens can overlap or arrive out of frame order. Native Graphics cannot;
    # quantize reveal states into a strictly sequential frame partition without
    # deleting source-supported words.
    prior_end = 0
    for seg in segments:
        seg["start_frame"] = max(seg["start_frame"], prior_end)
        seg["end_frame"] = max(seg["end_frame"], seg["start_frame"] + 1)
        prior_end = seg["end_frame"]
    first_by_card={}
    last_by_card={}
    for seg in segments:
        first_by_card.setdefault(seg["semantic_card_id"],seg["start_frame"])
        last_by_card[seg["semantic_card_id"]]=seg["end_frame"]
    for card in cards:
        card["start_frame"]=first_by_card[card["id"]]
        card["end_frame"]=last_by_card[card["id"]]
    seen_cards=set()
    for seg in segments:
        first=seg["semantic_card_id"] not in seen_cards
        seg["continuation"]=not first
        seg["animation_elapsed_frames"]=0 if first else max(1,seg["start_frame"]-first_by_card[seg["semantic_card_id"]])
        seen_cards.add(seg["semantic_card_id"])

    segment_ids = [s["id"] for s in segments]
    if profile["id"] == "sharran":
        style_review = {"mode": "uniform_requested", "user_request":
            "Sharran profile: uniform body weight with no decorative variation; represented speech and quotations use true italics."}
    else:
        italic_targets = []
        weight_targets = []
        for seg in segments:
            for wi, word in enumerate(seg["words"]):
                if word["italic"]:
                    italic_targets.append({"segment_id": seg["id"], "word_index": wi,
                                           "text": word["text"], "value": True})
                if word["weight"] != "base":
                    weight_targets.append({"segment_id": seg["id"], "word_index": wi,
                                           "text": word["text"], "value": word["weight"]})
        style_review = {"mode": "editorial", "reviewed": True, "segment_ids": segment_ids,
            "weight": {"status": "applied" if weight_targets else "not_applicable",
                       "targets": weight_targets, "reason": "Only transcript-marked vocal emphasis changes weight."},
            "size": {"status": "not_applicable", "targets": [],
                     "reason": "Leila reference body captions stay at a compact uniform size."},
            "italic": {"status": "applied" if italic_targets else "not_applicable",
                       "targets": italic_targets, "reason": "True italic is limited to explicit quoted or internal speech."}}
    return {"schema": "spice.native-caption-manifest/v2", "caption_profile": profile["id"],
            "frame_rate": {"numerator": fps_num, "denominator": fps_den}, "picture_cut_frames": sorted(set(picture_cut_frames)), "caption_omissions": omissions, "cards": cards,
            "render_segments": segments,
            "style_review": style_review}


def validate_profile_manifest(data: dict) -> None:
    profile = load_profile(data.get("caption_profile"))
    if data.get("schema") != "spice.native-caption-manifest/v2":
        raise ValueError("unsupported native caption manifest schema")
    cuts = data.get("picture_cut_frames", [])
    for card in data.get("cards", []):
        if cuts and "speech_end_frame" not in card:
            raise ValueError("picture-cut caption check requires mapped speech end")
        if cuts and cap_hold_at_picture_cut(card["start_frame"], card["end_frame"],
                                           card["speech_end_frame"], cuts) != card["end_frame"]:
            raise ValueError("finished caption hold crosses a picture cut")
    prior_end = -1
    owners = {}
    for seg in data.get("render_segments", []):
        if seg["caption_profile"] != profile["id"]: raise ValueError("profile drift")
        if not seg["start_frame"] < seg["end_frame"]: raise ValueError("zero-length reveal")
        if seg["start_frame"] < prior_end: raise ValueError("overlapping reveal states")
        if seg.get("continuation") and seg.get("animation_elapsed_frames", 0) <= 0:
            raise ValueError("continuation replay risk")
        if len(seg.get("lines", [])) > profile["max_lines"]: raise ValueError("too many lines")
        if seg["text"] != "\n".join(seg["lines"]): raise ValueError("line-break drift")
        _validate_rendered_width(seg, profile)
        if profile["id"] == "sharran":
            if any((w["italic"] and w["font_postscript"] != profile["italic_font_postscript"])
                   or (not w["italic"] and w["font_postscript"] != "Inter-SemiBold")
                   for w in seg["words"]):
                raise ValueError("Sharran must remain SemiBold except for reviewed quote italics")
        if seg.get("source_coverage_owner"):
            owners[seg["semantic_card_id"]] = owners.get(seg["semantic_card_id"], 0) + 1
        prior_end = seg["end_frame"]
    if any(v != 1 for v in owners.values()) or len(owners) != len(data.get("cards", [])):
        raise ValueError("each semantic card needs exactly one source coverage owner")

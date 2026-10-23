#!/usr/bin/env python3
"""Normalize a transcript.json before caption generation:
   - Spelled-out numbers → digits ("twenty one" → "21", "five" → "5")
   - Apostrophe spacing fixed ("don ' t" → "don't", "they 're" → "they're")
   - Known acronyms uppercased (AI, USA, etc.)
   Locked from Mozi Team Alex SF V1 MVP Standards (#1, #5, plus user feedback 2026-05-08).
"""
import argparse, json, re
from pathlib import Path

# Single-word digit map
SINGLE = {
    # "zero" intentionally kept as word ("zero exceptions" reads better than "0 exceptions")
    "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90",
}
TENS = {"twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"}
ONES = {"one","two","three","four","five","six","seven","eight","nine"}

ACRONYMS = {"ai","ml","ceo","cfo","cto","coo","ev","ip","kpi","mvp","ui","ux","usa",
            "uk","fbi","cia","nasa","fda","irs","gdp","b2b","b2c","saas","cnn","bbc",
            "dtc","roi","fyi","tldr","faq","api","sdk","cli","gpu","cpu"}

PROPER_NOUNS = {"alex","leila","amir","princeton","harvard","yale","mit","stanford","oxford",
                "cambridge","columbia","brown","duke","apple","google","amazon","microsoft",
                "facebook","meta","twitter","instagram","tiktok","youtube","linkedin","netflix",
                "tesla","spacex","openai","anthropic","claude","new york","los angeles","california",
                "america","american","texas","florida","seattle","chicago","boston","miami",
                "elon","musk","jobs","gates","bezos","zuckerberg","hormozi","trump","biden",
                "shaq","jordan","lebron","kobe","jimi","hendrix","christmas","easter","halloween",
                "monday","tuesday","wednesday","thursday","friday","saturday","sunday",
                "january","february","march","april","may","june","july","august","september","october","november","december"}

KEEP_AS_WORD = {"i","i'm","i'll","i've","i'd"}


def is_spellable_num(w: str) -> bool:
    return w.lower().rstrip(",.!?") in SINGLE


try:
    from wordfreq import zipf_frequency as _zipf
except ImportError:
    def _zipf(w, lang="en"): return 0.0


def _strip_punct(w):
    return re.sub(r"[^A-Za-z']", "", w)


def force_lowercase(words: list) -> list:
    """Lowercase ALL words first (clears Whisper's auto sentence-start caps).
    Acronyms and proper nouns get re-capitalized later by fix_acronyms / fix_proper_nouns.
    Skips all-caps tokens (preserves shouted ALL CAPS if speaker emphasized)."""
    for w in words:
        wt = w["word"]
        # Don't lowercase tokens that are ALL caps (probably acronyms or shouting)
        alpha_only = re.sub(r"[^A-Za-z]", "", wt)
        if alpha_only and alpha_only.isupper() and len(alpha_only) >= 2:
            continue
        w["word"] = wt.lower()
    return words


def dedupe_consecutive(words: list) -> list:
    """Remove consecutive duplicate words (Whisper captures stutters: 'you you' → 'you')."""
    out = []
    prev_clean = None
    for w in words:
        cur_clean = re.sub(r"[^a-zA-Z]", "", w["word"]).lower()
        if cur_clean and cur_clean == prev_clean and len(cur_clean) >= 2:
            # Same as previous content word — skip (extends previous's end time)
            if out:
                out[-1]["end"] = w["end"]
            continue
        out.append(w)
        if cur_clean:
            prev_clean = cur_clean
    return out


def merge_split_words(words: list) -> list:
    """Whisper's word-level mode (-ml 1) splits long/uncommon words into syllables
    (e.g. 'Samar'+'itan' → 'Samaritan', 'audit'+'or'+'ium' → 'auditorium', 'cl'+'unker' → 'clunker').
    Use Zipf frequency (wordfreq) to detect — fragments like 'itan'/'unker'/'ium' have Zipf 0,
    real words like 'be'/'paid'/'a'/'day' have Zipf 5+ so won't accidentally merge.

    Iterative until stable: handles N-way splits (audit+or+ium) by collapsing 2-way pairs
    repeatedly. After 'or'+'ium'→'orium', the next pass merges 'audit'+'orium'.
    """
    merged = [dict(w) for w in words]
    changed = True
    safety = 0
    while changed and safety < 10:
        changed = False
        safety += 1
        i = 0
        while i < len(merged) - 1:
            cur = merged[i]
            nxt = merged[i + 1]
            cur_w = cur["word"]
            nxt_w = nxt["word"]
            cur_clean = _strip_punct(cur_w)
            nxt_clean = _strip_punct(nxt_w)
            if not cur_clean or not nxt_clean:
                i += 1; continue
            # Sentence boundary or apostrophe — don't merge
            if cur_w.rstrip() and cur_w.rstrip()[-1] in ".,!?;:'":
                i += 1; continue
            # New proper noun starts — don't merge
            if nxt_w.lstrip() and nxt_w.lstrip()[0].isupper():
                i += 1; continue
            cur_lc = cur_clean.lower()
            nxt_lc = nxt_clean.lower()
            cur_freq = _zipf(cur_lc, "en")
            nxt_freq = _zipf(nxt_lc, "en")
            cmb_freq = _zipf((cur_clean + nxt_clean).lower(), "en")

            # SINGLE-CHAR FRAGMENT rule: Whisper occasionally outputs a single letter as its
            # own "word" when the speaker emphasizes that letter (e.g. "F"+"ucking", "pans"+"y",
            # "audit"+"or"+"ium"). 1-char tokens that aren't standalone words ("a"/"i"/"o") are
            # always fragments — merge if combined is a real word.
            cur_is_solo_letter = len(cur_clean) == 1 and cur_lc not in ("a", "i", "o")
            nxt_is_solo_letter = len(nxt_clean) == 1 and nxt_lc not in ("a", "i", "o")
            if (cur_is_solo_letter or nxt_is_solo_letter) and cmb_freq >= 1.5:
                cur["word"] = cur_w + nxt_w
                cur["end"] = nxt["end"]
                del merged[i + 1]
                changed = True
                continue

            # MERGE rule (strict, prevents runaway):
            # COMBINED must be a real word (Zipf ≥ 1.5) AND at least one piece must be
            # fragmenty (Zipf < 2.0). Threshold 2.0 (was 1.5) catches 'ium' (1.60) and
            # 'ucking' (1.55) — wordfreq lists them with low but non-zero scores.
            # Never merge two common standalone words (both ≥ 2.5).
            should_merge = False
            if cur_freq >= 2.5 and nxt_freq >= 2.5:
                pass  # both common — leave alone (be+paid, a+day, no+government)
            elif cmb_freq >= 1.5 and (cur_freq < 2.0 or nxt_freq < 2.0):
                should_merge = True

            if should_merge:
                cur["word"] = cur_w + nxt_w
                cur["end"] = nxt["end"]
                del merged[i + 1]
                changed = True
                # don't advance i — re-check this position for further chain merges
            else:
                i += 1
    return merged


def migrate_trailing_apostrophes(words: list) -> list:
    """Whisper sometimes emits sentence-end punctuation with a trailing apostrophe glued on
    (e.g. ".'" or "?'") followed by a capitalized word. The apostrophe really belongs to the
    next word as a leading-contraction marker (e.g. "'cause"). Move it.
    """
    out = []
    i = 0
    while i < len(words):
        cur = dict(words[i])
        cur_w = cur["word"].strip()
        if cur_w.endswith("'") and 1 < len(cur_w) <= 3:
            body = cur_w[:-1]
            if body and all(c in ".,?!:;" for c in body) and i + 1 < len(words):
                nxt = dict(words[i + 1])
                nxt_w = nxt["word"].strip()
                if nxt_w and nxt_w[0].isalpha():
                    cur["word"] = body
                    out.append(cur)
                    nxt["word"] = "'" + nxt_w
                    out.append(nxt)
                    i += 2
                    continue
        out.append(cur)
        i += 1
    return out


def clean_apostrophes(words: list) -> list:
    """Merge stray apostrophe artifacts:
       - 'don' + ''t' → 'don't'
       - 'they' + ''re' → 'they're'
       - "'" + 'cause' → "'cause" (leading-apostrophe contractions)
    """
    out = []
    i = 0
    while i < len(words):
        cur = words[i]
        cur_w = cur["word"].strip()
        if i + 1 < len(words):
            nxt = words[i + 1]
            nxt_w = nxt["word"].strip()
            # Pattern A: word + "'suffix" (e.g. "don" + "'t"). Length >=2 so a standalone "'"
            # falls through to Pattern B (leading-contraction) instead of getting glued backward.
            if nxt_w.startswith("'") and 2 <= len(nxt_w) <= 4 and not cur_w.endswith("'"):
                merged = dict(cur)
                merged["word"] = cur_w + nxt_w
                merged["end"] = nxt["end"]
                out.append(merged)
                i += 2
                continue
            # Pattern B: standalone "'" followed by next word (e.g. "'" + "cause")
            if cur_w == "'" and nxt_w and not nxt_w.startswith("'"):
                merged = dict(cur)
                merged["word"] = "'" + nxt_w
                merged["end"] = nxt["end"]
                out.append(merged)
                i += 2
                continue
        out.append(cur)
        i += 1
    # Also fix in-word weirdness like "don 't" → "don't" within a single word string
    for w in out:
        w["word"] = re.sub(r"(\w)\s+'(\w)", r"\1'\2", w["word"])  # don ' t → don't
        w["word"] = re.sub(r"\s+'", "'", w["word"])  # any leading-space apostrophe
    return out


def numbers_to_digits(words: list) -> list:
    """Convert spelled-out numbers to digits. Handles single (five→5) and compound (twenty one→21)."""
    out = []
    i = 0
    while i < len(words):
        cur = words[i]
        cur_clean = re.sub(r"[^a-z]", "", cur["word"].lower())
        # Compound: TEN word + ONE word → combined digit
        if cur_clean in TENS and i + 1 < len(words):
            nxt_clean = re.sub(r"[^a-z]", "", words[i + 1]["word"].lower())
            if nxt_clean in ONES:
                tens_val = int(SINGLE[cur_clean])
                ones_val = int(SINGLE[nxt_clean])
                trailing_punct = re.search(r"[,.!?]+$", words[i + 1]["word"])
                merged = dict(cur)
                merged["word"] = str(tens_val + ones_val) + (trailing_punct.group(0) if trailing_punct else "")
                merged["end"] = words[i + 1]["end"]
                out.append(merged)
                i += 2
                continue
        # Single
        if cur_clean in SINGLE:
            trailing_punct = re.search(r"[,.!?]+$", cur["word"])
            new = dict(cur)
            new["word"] = SINGLE[cur_clean] + (trailing_punct.group(0) if trailing_punct else "")
            out.append(new)
            i += 1
            continue
        out.append(cur)
        i += 1
    return out


def collapse_am_pm(words: list) -> list:
    """Detect '[digit] [a|p] [m]' or '[digit] [am|pm]' patterns → combined '[digit]AM/PM' (no space).
    Whisper output for "five AM" is often ['5','a','m'] (after numbers_to_digits) or ['5','am']."""
    out = []
    i = 0
    while i < len(words):
        cur = dict(words[i])
        cur_w = cur["word"]
        # Need a digit token (cleaned of punct)
        digit_match = re.match(r"^(\d+)([.,?!]*)$", cur_w)
        if digit_match and i + 1 < len(words):
            digits = digit_match.group(1)
            trailing = digit_match.group(2)
            nxt_clean = re.sub(r"[^A-Za-z]", "", words[i + 1]["word"]).lower()
            # Pattern A: "[digit] am" / "[digit] pm" (already combined)
            if nxt_clean in ("am", "pm", "a.m", "p.m"):
                cur["word"] = f"{digits}{nxt_clean.replace('.','').upper()}{trailing}"
                cur["end"] = words[i + 1]["end"]
                out.append(cur)
                i += 2
                continue
            # Pattern B: "[digit] a [.] m [.]" / "[digit] p [.] m [.]" — multiple tokens with optional periods
            if nxt_clean in ("a", "p"):
                # Look ahead up to 4 more tokens for "m" allowing dots in between
                ahead = []
                k = i + 1
                while k < len(words) and k < i + 5:
                    tok = words[k]["word"].strip()
                    if tok in (".", ","):
                        ahead.append(("punct", k))
                    elif re.fullmatch(r"[A-Za-z]+", tok):
                        ahead.append((tok.lower(), k))
                    else:
                        break
                    k += 1
                # Find the [a/p] token then look for [m]
                if ahead and ahead[0][0] == nxt_clean:
                    for j, (tok, idx) in enumerate(ahead[1:], start=1):
                        if tok == "m":
                            suffix = "AM" if nxt_clean == "a" else "PM"
                            cur["word"] = f"{digits}{suffix}{trailing}"
                            cur["end"] = words[idx]["end"]
                            out.append(cur)
                            i = idx + 1
                            break
                    else:
                        out.append(cur); i += 1
                        continue
                    continue
        out.append(cur)
        i += 1
    return out


def expand_time_range_suffix(words: list) -> list:
    """If we have '[digit] to [digit]AM/PM' (only one side has suffix), copy suffix to both:
    '5 to 9AM' → '5AM to 9AM'."""
    out = []
    i = 0
    while i < len(words):
        cur = dict(words[i])
        cur_w = cur["word"].strip()
        if re.fullmatch(r'\d+', cur_w) and i + 2 < len(words):
            mid = words[i + 1]["word"].strip().lower().rstrip(".,!?")
            if mid == "to":
                nxt_w = words[i + 2]["word"].strip()
                m = re.fullmatch(r'(\d+)(AM|PM|am|pm)([.,!?]*)', nxt_w)
                if m:
                    cur["word"] = cur_w + m.group(2).upper()
                    out.append(cur)
                    i += 1
                    continue
        out.append(cur)
        i += 1
    return out


def combine_number_ranges(words: list) -> list:
    """Merge '[digit/time] to/- [digit/time]' into a single chunk-unit token so the
    caption chunker keeps the range on one line. Uses ' to ' for time-suffixed ranges
    (5AM to 9AM), ' - ' for plain numeric ranges (2 - 4 hour)."""
    out = []
    i = 0
    while i < len(words):
        cur = dict(words[i])
        cur_w = cur["word"].strip()
        # cur must start with a digit (possibly suffixed with AM/PM)
        if re.match(r'^\d', cur_w) and i + 2 < len(words):
            mid = words[i + 1]["word"].strip().lower().rstrip(".,!?")
            if mid in ("to", "-"):
                nxt_w = words[i + 2]["word"].strip()
                if re.match(r'^\d', nxt_w):
                    cur_has_suffix = bool(re.search(r'(AM|PM)$', cur_w, re.IGNORECASE))
                    nxt_has_suffix = bool(re.search(r'(AM|PM)', nxt_w, re.IGNORECASE))
                    sep = " to " if (cur_has_suffix or nxt_has_suffix) else " - "
                    cur["word"] = f"{cur_w}{sep}{nxt_w}"
                    cur["end"] = words[i + 2]["end"]
                    out.append(cur)
                    i += 3
                    continue
        out.append(cur)
        i += 1
    return out


def fix_acronyms(words: list) -> list:
    for w in words:
        # match a word stripped to letters only
        stripped = re.sub(r"[^a-z]", "", w["word"].lower())
        if stripped in ACRONYMS and stripped not in KEEP_AS_WORD:
            # uppercase the alpha part, keep punctuation
            w["word"] = re.sub(r"[a-zA-Z]+", lambda m: m.group(0).upper(), w["word"], count=1)
    return words


def fix_proper_nouns(words: list) -> list:
    """Capitalize known proper nouns: Princeton, Alex, Apple, Monday, etc."""
    for w in words:
        stripped = re.sub(r"[^a-z]", "", w["word"].lower())
        if stripped in PROPER_NOUNS and not stripped == "i":
            # Capitalize first letter, keep rest as-is (preserves trailing punctuation)
            wt = w["word"]
            # Find first alpha char and uppercase
            for i, c in enumerate(wt):
                if c.isalpha():
                    w["word"] = wt[:i] + c.upper() + wt[i+1:].lower()
                    break
    return words


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in", dest="inp", required=True, type=Path)
    p.add_argument("--out", dest="out", required=True, type=Path)
    args = p.parse_args()

    data = json.loads(args.inp.read_text())
    words = data.get("words", data) if isinstance(data, dict) else data
    if isinstance(data, dict) and "words" not in data:
        words = data

    words = merge_split_words(words)  # FIRST: rejoin Whisper syllable splits
    words = dedupe_consecutive(words)  # then drop "you you" / "that that" stutters
    words = force_lowercase(words)  # clear Whisper auto-caps (sentence-start "There" etc)
    words = migrate_trailing_apostrophes(words)
    words = clean_apostrophes(words)
    words = numbers_to_digits(words)
    words = collapse_am_pm(words)
    words = expand_time_range_suffix(words)
    words = combine_number_ranges(words)
    words = fix_acronyms(words)
    words = fix_proper_nouns(words)

    out_data = {"words": words} if isinstance(data, dict) else words
    args.out.write_text(json.dumps(out_data, indent=2))
    print(f"Wrote {args.out}: {len(words)} words")


if __name__ == "__main__":
    raise SystemExit(main())

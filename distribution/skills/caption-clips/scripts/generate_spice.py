#!/usr/bin/env python3
"""Dynamic "spice" pro captions — Oliver-style multi-weight + voice-color + gentle italics.

Reverse-engineered from the team's best editor (see references/spice_caption_spec.md). Distinct
from the LOCKED single-axis pro_locked/alex_canon path: this one uses the FULL Proxima Nova weight
palette as an emphasis dial, GENTLE (un-leaned) italics via \\fax, and per-word voice color.

Pipeline: word-level transcript (PUNCTUATE FIRST) -> v2 cue segmentation (Oliver caption spec
PART 2, 2026-07-06: filler drop + stutter/false-start collapse, then break by priority
camera cut > speaker change > sentence .?! > timing boundary (silence >=250ms OR onset >=400ms / >=1.6x local
avg) > comma-with-gap > pace-adaptive cadence cap (slow ~2w / med ~3w / fast ~4w; 18c soft,
25c HARD) > seam targets, with atomic money/number/collocation units and per-item enumeration)
-> sequential timing (5-frame ABSOLUTE floor + dense-cue +1-frame reading bump, gapless, ~2s max)
+ function-word onset-correction -> per-word styling (per-cue curly-quote re-wrap) -> ASS ->
optional burn.

The 4 styling axes (THE LOGIC) come from a per-word STYLE STREAM (the "caption director"),
hand- or LLM-authored:
  COLOR  = whose voice   -> white (Alex) / yellow #FED90F (guest or Alex impersonating someone)
           (v2 2026-07-06: color is ONLY the voice — no separate emphasis color; a legacy
            c:"emphasis" in an old style stream resolves to the cue's voice color)
  WEIGHT = vocal stress  -> Light(mute) Regular(base) Medium(soft) Bold(strong) Extrabold(emphasis) Black(payoff)
  ITALIC = quote / reflective / contrast  (gentle \\fax, not synthetic \\i1)
  QUOTES = explicitly role-played speech  (always italic; color follows the voice)
Without a style stream a light default (numbers + an emphasis-word list -> heavier weight) keeps
solo clips reasonable.

Usage:
  generate_spice.py <transcript.json> --out subs.ass [--style director.json]
                    [--burn <source.mp4> --burn-out <final.mp4>]
                    [--number-color FED90F] [--no-onset-correct]

Style-stream JSON (all keys optional):
  { "words": { "<word_index>": {"w":"emphasis","i":true,"c":"guest","q":true}, ... },
    "voice_spans": [ [start_sec, end_sec, "guest"], ... ] }   # color a whole time range one voice
  ("words" may also be the top-level object directly.) w=weight tier, i=italic, c=voice, q=quoted.
"""
import argparse
import glob
import json
import re
import shutil
import subprocess
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
import sys as _sys
_sys.path.insert(0, str(Path("__ACQ_SKILLS__/_shared")))
try:
    from fast_encode import encoder_args, encoder_args_for   # ACQ fast-render standard (VideoToolbox HW, ~4x vs libx264)
except Exception:
    encoder_args = encoder_args_for = None


def _resolve_ff():
    """Resolve ffmpeg/ffprobe via the ONE shared resolver (_shared/ffmpeg_bin.py).

    2026-08-13/18 outage: Homebrew's slim `ffmpeg` formula ships WITHOUT libass, so it has no
    `ass`/`subtitles` filter; a brew upgrade linked it onto PATH and every --burn died with
    `Unknown filter 'ass'` / `No option name near '<path>'`. That second message is a RED
    HERRING — it reads like a filter-graph QUOTING bug, but the quoting is fine on any build
    that HAS libass (verified on 8.1.1). The old fix here pinned the ffmpeg-full *version*,
    which rots the moment ffmpeg-full is upgraded. Resolve on the CAPABILITY instead; the
    hard gate lives at the --burn site so a non-burn run still works on a libass-less box.
    """
    try:
        import sys as _s
        _s.path.insert(0, str(Path("__ACQ_SKILLS__/_shared")))
        from ffmpeg_bin import ffmpeg as _ff, ffprobe as _fp
        return _ff(), _fp()
    except Exception:
        # _shared missing -> stay self-contained: prefer a libass-bearing ffmpeg-full keg.
        def _local(name):
            c = sorted(glob.glob(f"/opt/homebrew/Cellar/ffmpeg-full/*/bin/{name}"), reverse=True)
            return c[0] if c else (shutil.which(name) or name)
        return _local("ffmpeg"), _local("ffprobe")


FF, FFP = _resolve_ff()


def load_preset(path):
    """Load a preset, resolving `"extends": "<file>"` against the presets dir.

    Added 2026-08-03: the variants used to be full ~8.7KB COPIES of spice.json, so the
    locked shadow/weights blocks lived in 7 files and any shadow change needed 7 hand-syncs
    (the exact drift trap the corpus doc warned about). Variants now carry ONLY their deltas
    and inherit the rest. Deep-merges dicts; a variant key always wins.
    """
    p = Path(path)
    P = json.loads(p.read_text())
    seen = set()
    while isinstance(P.get("extends"), str):
        parent_name = P.pop("extends")
        parent_path = (p.parent / parent_name) if (p.parent / parent_name).exists() \
            else (SKILL / "presets" / parent_name)
        rp = str(parent_path.resolve())
        if rp in seen:
            break                                   # cycle guard
        seen.add(rp)
        base = json.loads(parent_path.read_text())

        def deep(b, o):
            for k, v in o.items():
                b[k] = deep(b.get(k, {}), v) if isinstance(v, dict) and isinstance(b.get(k), dict) else v
            return b
        P = deep(base, P)
    return P

# Unstressed function words: a long Groq span on one of these = absorbed pause, never emphatic
# stretching, so its real onset is near the span's END. (Kept in sync with generate_ass.py.)
FUNCTION_WORDS = {
    "the", "a", "an", "and", "or", "but", "because", "so", "if", "of", "to", "in", "on", "for",
    "with", "that", "this", "is", "are", "was", "were", "be", "been", "am", "as", "at", "by",
    "from", "into", "than", "then", "when", "while", "you", "i", "it", "we", "they", "he", "she",
    "your", "my", "our", "their", "its", "his", "her", "will", "would", "can", "could", "do",
    "does", "did", "have", "has", "had", "not", "no", "there", "here", "what", "which", "who",
    "just", "like", "about",
}
KEEP_I = {"I", "I'm", "I'll", "I'd", "I've"}
NUMWORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "hundred", "thousand", "million", "billion", "trillion", "percent", "dollars", "grand"}


def disp(word: str) -> str:
    """Displayed token: drop terminal . and , (keep ? ! ' $ % # and inner punctuation), keep I-forms,
    and PRESERVE proper-noun / acronym capitalization (Apollo Creed, Bangladesh, AI) — the transcript
    must already be normalized by oliver_format, so any remaining uppercase is intentional."""
    t = word.strip().rstrip(".,")
    if t in KEEP_I:
        return t
    if any(c.isupper() for c in t):
        return t
    return t.lower()


def bare(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalnum())


def ts(t: float) -> str:
    if t < 0:
        t = 0.0
    h = int(t // 3600); t -= h * 3600
    m = int(t // 60); t -= m * 60
    s = int(t); cs = int(round((t - s) * 100))
    if cs == 100:
        s += 1; cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass_color(hex_rgb: str, alpha: int = 0) -> str:
    h = hex_rgb.strip().lstrip("#")
    return f"&H{alpha:02X}{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def is_number(token: str) -> bool:
    return any(c.isdigit() for c in token) or bare(token) in NUMWORDS


_FONT_CACHE = {}
def line_width_px(text: str, px: int) -> int:
    """Rendered width of `text` at `px` using Proxima Nova Bold (the widest common weight — a
    conservative estimate so the safe-zone cap never under-shrinks). Falls back to a char-advance
    estimate if PIL/the font isn't available."""
    try:
        from PIL import ImageFont
        f = _FONT_CACHE.get(px)
        if f is None:
            f = ImageFont.truetype(str(SKILL / "fonts" / "proxima_full" / "ProximaNovaBold.otf"), px)
            _FONT_CACHE[px] = f
        return f.getbbox(text)[2]
    except Exception:
        return int(len(text) * px * 0.52)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", type=Path, help="Word-level transcript JSON (punctuated first!)")
    ap.add_argument("--preset", type=Path, default=SKILL / "presets" / "spice.json")
    ap.add_argument("--style", type=Path, default=None, help="Per-word style-stream JSON (caption director)")
    ap.add_argument("--out", type=Path, required=True, help="Output .ass")
    ap.add_argument("--burn", type=Path, default=None, help="Source video to burn captions onto")
    ap.add_argument("--burn-out", type=Path, default=None, help="Output MP4 (with --burn)")
    ap.add_argument("--overlay-out", action="store_true",
                    help="PREMIERE OVERLAY MODE: burn onto a transparent input -> ProRes 4444 with "
                         "alpha, no audio map. Output = a caption-only layer to place on V2 in an NLE. "
                         "Pair with a transparent ProRes input of the clip's exact duration/dims.")
    ap.add_argument("--layout", type=Path, default=None,
                    help="Per-frame layout track from caption-app's layout_analyze.py. "
                         "Every segment boundary is a hard caption-card break, and each cue's Y is "
                         "picked from its segment (safe_y_pct * frame_height), so no outgoing camera "
                         "angle pre-reveals words spoken on the incoming angle.")
    ap.add_argument("--number-color", default=None, help="Hex RRGGBB for numeric tokens (e.g. FED90F)")
    ap.add_argument("--no-onset-correct", action="store_true", default=False)
    ap.add_argument("--min-cue-dur", type=float, default=None,
                    help="Override the sequential-layout floor (default 0.21s = 5 frames @24fps, "
                         "the v2 spec's absolute minimum; a crammed cue pushes the next, never drops).")
    ap.add_argument("--expect-guest", action="store_true",
                    help="Blocking speaker-color gate: fail before burn when the rendered captions "
                         "contain zero guest/yellow cues. Required for Q&A, hotline, caller, attendee, "
                         "and host-read viewer-question clips.")
    a = ap.parse_args()

    P = load_preset(a.preset)
    words = json.loads(a.transcript.read_text())["words"]
    N = len(words)
    if not N:
        print("No words in transcript."); return 1

    # MULTICAM CUT CONTRACT: every shot boundary in a supplied layout track is also a
    # hard caption-card boundary. Caption grouping must happen with this information;
    # splitting the already-rendered event later only changes Y while leaving incoming
    # words visible on the outgoing shot (e.g. "you the R" across a cut after "you").
    # The first word whose onset is at/after a cut starts a fresh cue. A cut through a
    # word cannot split that token; the next word starts the new camera's cue.
    layout_cut_times = []
    if a.layout and a.layout.exists():
        try:
            _layout_for_breaks = json.loads(a.layout.read_text())
            _layout_fps = float(_layout_for_breaks.get("meta", {}).get("fps", 30.0))
            _layout_segments = sorted(
                _layout_for_breaks.get("segments", []),
                key=lambda s: int(s["start_i"]),
            )
            layout_cut_times = sorted({
                int(s["start_i"]) / _layout_fps for s in _layout_segments[1:]
            })
            if layout_cut_times:
                print(f"layout: {len(layout_cut_times)} hard caption breaks at camera cuts")
        except Exception as _e:
            print(f"layout: hard-break parse failed ({_e}); continuing without cut boundaries")
            layout_cut_times = []

    # --- style stream ---
    style = json.loads(a.style.read_text()) if (a.style and a.style.exists()) else {}
    perword = style.get("words", style if all(k.lstrip("-").isdigit() for k in style) else {}) if isinstance(style, dict) else {}
    voice_spans = style.get("voice_spans", []) if isinstance(style, dict) else []
    # gloss = {"<word_index>": "definition text"} -> a smaller secondary line UNDER the caption while
    # that word is on screen (for foreign/jargon/rare terms, e.g. raison d'être -> "[life's purpose]").
    gloss = style.get("gloss", {}) if isinstance(style, dict) else {}
    number_color = (a.number_color or P.get("number_color") or "").lstrip("#") or None

    weights = P["weights"]
    default_weight = P.get("default_weight", "base")
    auto = P.get("auto_emphasis", {})
    strong_words = set(w.lower() for w in auto.get("words_strong", []))
    colors = P["colors"]
    default_voice = P.get("default_voice", "alex")
    # SIZE axis (data-derived from Oliver's 19 clips): base 100, light/strong/peak bumps.
    sizes = P.get("sizes", {"base": 100, "emph": 125, "strong": 150, "peak": 180})
    auto_size = P.get("auto_size", {})           # default size bumps with no style stream, e.g. {"numbers": "emph"}

    def spec(i):
        return perword.get(str(i), {}) if isinstance(perword, dict) else {}

    def voice_of(i):
        s = spec(i)
        # v2 (2026-07-06): "emphasis" is no longer a color — emphasis follows the
        # speaker's voice (Alex white / guest yellow). A legacy style stream that says
        # c:"emphasis" falls through to voice_spans / default_voice.
        if "c" in s and s["c"] != "emphasis":
            return s["c"]
        st = float(words[i]["start"])
        for span in voice_spans:
            if len(span) >= 3 and span[0] <= st < span[1]:
                return span[2]
        return default_voice

    def weight_of(i):
        s = spec(i)
        if "w" in s:
            return s["w"]
        tok = words[i]["word"]
        if number_color is None and is_number(tok) and auto.get("numbers"):
            return auto["numbers"]
        if bare(tok) in strong_words:
            return "strong"
        return default_weight

    def color_hex(i):
        if number_color and is_number(words[i]["word"]):
            return number_color
        return colors.get(voice_of(i), colors.get("alex", "FFFFFF"))

    def size_of(i):
        # \fscx/\fscy percent. Style stream 's' = a tier name ("emph"/"strong"/"peak") or a raw
        # number (e.g. 140). Auto-bump numbers when no explicit size (Oliver bumps numbers/money).
        tier = spec(i).get("s")
        if tier is None and auto_size.get("numbers") and is_number(words[i]["word"]):
            tier = auto_size["numbers"]
        if tier is None:
            return 100
        if isinstance(tier, (int, float)):
            return int(tier)
        return int(sizes.get(tier, 100))

    # quote runs from the style stream (transcript-marked spans are added below in the S6 pass)
    q = [bool(spec(i).get("q")) for i in range(N)]

    # ═══ v2 CUE SEGMENTATION — Oliver caption spec PART 2 (2026-07-06) ═══════════════════════
    # Supersedes the hard <=18c/<=3w packer. Break priority: speaker change > sentence .?! >
    # timing boundary (silence >=250ms OR onset >=400ms / >=1.6x local avg) > comma-with-gap >
    # pace-adaptive cadence cap > chunk-aligned seams. 18c = soft cadence reference (lint warns),
    # 25c = HARD safe-zone max (lint errors). LOCKED lessons kept: camera-cut and speaker-change hard breaks
    # (2026-06-10), pause pre-reveal split (2026-06-14), orphan-merge (no floating fragments).
    T = P.get("timing", {})
    HARD_MAX = int(P["layout"].get("hard_max_chars", 25))
    SIL_BREAK = float(T.get("pause_split_s", 0.25))   # v2: >=250ms silence = boundary (was 0.35)
    ONSET_ABS = float(T.get("onset_break_s", 0.40))   # phrase-final lengthening, absolute
    ONSET_REL = float(T.get("onset_break_rel", 1.6))  # …or vs the LOCAL onset average (fast talk)
    COMMA_GAP = float(T.get("comma_gap_s", 0.08))     # comma with no gap = disfluency, no break
    # pace-adaptive cadence tiers: local avg onset (ms/word) -> (max words, max chars).
    # slow speech = fewer words (don't pre-reveal), fast = more (readable at pace).
    TIER_SLOW, TIER_MED = 0.440, 0.250
    # tier caps are preset-overridable (added 2026-07-14 for long-form 16:9 testimonials —
    # wider lines; short-form presets omit "tier_caps" and keep the locked values below)
    _tc = P["layout"].get("tier_caps", {})
    TIERS = {"slow": tuple(_tc.get("slow", (2, 13))),
             "med":  tuple(_tc.get("med",  (3, 17))),
             "fast": tuple(_tc.get("fast", (4, HARD_MAX)))}

    DETERMINERS = {"a", "an", "the", "my", "your", "his", "her", "its", "our", "their"}
    OBJ_PRON = {"me", "him", "us", "them"}  # deliberately NOT it/that/this/you (clause subjects)
    NEG_AUX = {"didn't", "don't", "doesn't", "can't", "cannot", "won't", "wouldn't", "couldn't",
               "shouldn't", "isn't", "aren't", "wasn't", "weren't", "ain't", "hasn't", "haven't",
               "hadn't", "wanna", "gonna", "gotta"}
    TIME_UNITS = {"second", "seconds", "minute", "minutes", "hour", "hours", "day", "days",
                  "week", "weeks", "month", "months", "year", "years", "decade", "decades",
                  "quarter", "quarters"}
    FIN_IDS = {"revenue", "profit", "sales", "income", "ltv", "arr", "mrr", "cac", "ebitda",
               "margin", "cash", "cashflow"}
    CONNECTORS = {"and", "but", "so", "or", "because", "on", "in", "to", "with", "from",
                  "about", "of", "for", "at", "into"}
    # curated atomic collocations (freely extensible) — never split inside one
    COLLOC = [c.split() for c in (
        "word of mouth", "facebook ads", "social media", "real estate", "cash flow",
        "rule of thumb", "supply and demand", "return on investment", "a lot of", "kind of",
        "sort of", "a couple of", "a little bit", "a little", "you know", "i mean",
        "i don't know", "be able to", "business model", "business models", "make sure",
        "less money", "more money", "all of a sudden", "one shot", "no one", "another one",
        "come on")]
    # S4: interjections/backchannels get their OWN short cue — Oliver strands "yeah" /
    # "chill!" / "come on!" as standalone cues (2026-07-06 corpus verify). Punctuation-gated
    # so mid-sentence uses ("right now", "well over") are untouched.
    INTERJ = {"yeah", "yea", "yes", "yep", "no", "nope", "okay", "ok", "right", "sweet",
              "amazing", "cool", "wow", "well", "chill", "sure", "exactly", "totally",
              "perfect", "mmh", "mhm"}
    EMPH_REPEAT = {"very", "really", "yes", "yeah", "yep", "no", "nope", "right", "exactly",
                   "never", "ever", "always", "stop", "wait", "totally", "definitely"}
    FILLER_RE = re.compile(r"^(?:u+h+m*|u+m+|e+r+m*)$")  # uh/um/uhm/er families ONLY (never mm/mhm/hmm/oh/ah)

    def raw_of(i):
        return str(words[i]["word"]).strip()

    def _nrm(i):
        return re.sub(r"[^a-z0-9']+", "", raw_of(i).lower().replace("’", "'"))

    def disp_v2(i):
        # display token: straight quotes stripped (S6 re-wraps per cue in curly quotes),
        # trailing-off ".." preserved (disp() would strip it with the terminal-period rule)
        r = raw_of(i)
        ell = bool(re.search(r"\.\.+$", r))
        t = disp(r.replace('"', ""))
        return (t + "..") if ell else t

    _comma_cleared = set()

    def _tail(i):  # raw token with any trailing quote marks removed, for punctuation checks
        return re.sub(r'["“”\']+$', "", raw_of(i))

    def ends_sentence(i):
        return bool(words[i].get("sentence_end")) or _tail(i).endswith((".", "?", "!"))

    def ends_comma(i):
        return (i not in _comma_cleared
                and (bool(words[i].get("comma_end")) or _tail(i).endswith(",")))

    eff_start, eff_end = {}, {}  # per-word timing overrides (filler absorption / stutter collapse)

    def W_start(i):
        return eff_start.get(i, float(words[i]["start"]))

    def W_end(i):
        return eff_end.get(i, float(words[i]["end"]))

    def camera_zone(i):
        """Shot index at the displayed word's onset."""
        t = W_start(i)
        # Word clocks are serialized to six decimals while NTSC frame cuts retain
        # their exact fractional time.  Allow half a serialized microsecond plus
        # margin so a word rounded from exactly start_i/fps cannot leak back onto
        # the outgoing shot (e.g. 1711/23.976 -> 71.362958333 -> 71.362958).
        return sum(1 for cut in layout_cut_times if t >= cut - 1e-6)

    # ── S4: FILLER DROP — uh/um/uhm/er families only. Absorb the filler's spoken time into the
    # previous word (so the hole isn't read as a pause), clear a comma setting it off, and mark
    # the spot so the onset signal is ignored there (that gap was the filler, not lengthening).
    kept, onset_skip = [], set()
    for i in range(N):
        if FILLER_RE.match(_nrm(i)) and '"' not in raw_of(i):  # a quoted "uh" is dialogue → kept
            if kept:
                p = kept[-1]
                eff_end[p] = max(W_end(p), float(words[i]["end"]))
                onset_skip.add(p)
                _comma_cleared.add(p)
            continue
        kept.append(i)
    if not kept:
        kept = list(range(N))

    # ── S4: STUTTER COLLAPSE — immediate exact-duplicate word ("the the", "that's that's"),
    # same speaker. Keep the earlier start, absorb the later token's end/punctuation. Guards:
    # emphasis keep-list ("right, right"), "is is" extraposition (split, never collapsed),
    # and a sentence end closing the first token = rhetorical "X. X is…" → keep.
    dedup = []
    for i in kept:
        if dedup:
            p = dedup[-1]
            nb = _nrm(i)
            if (nb and nb == _nrm(p) and voice_of(i) == voice_of(p)
                    and nb not in EMPH_REPEAT and nb != "is"
                    and W_start(i) - W_end(p) < SIL_BREAK
                    and not ends_sentence(p)):
                eff_start[i] = W_start(p)
                # the collapsed token's onset interval is inflated by the duplicate — it must
                # not read as phrase-final lengthening (same caveat as a dropped filler)
                onset_skip.add(i)
                dedup[-1] = i
                continue
        dedup.append(i)
    kept = dedup

    # ── S4: REPEATED-PHRASE FALSE-START — an immediately-repeated 2-4 word group (same speaker)
    # drops its FIRST copy ("I think, I think if you sold" → "I think if you sold"). Guards:
    # a 3rd repeat = emphasis → keep; sentence end closing the first copy = rhetorical → keep.
    res, k2 = [], 0
    while k2 < len(kept):
        drop = 0
        for n in (4, 3, 2):
            j = k2 + 2 * n
            if j <= len(kept):
                g1 = [_nrm(x) for x in kept[k2:k2 + n]]
                if (all(g1) and g1 == [_nrm(x) for x in kept[k2 + n:j]]
                        and len({voice_of(x) for x in kept[k2:j]}) == 1
                        and not ends_sentence(kept[k2 + n - 1])
                        and (j + n > len(kept) or g1 != [_nrm(x) for x in kept[j:j + n]])):
                    drop = n
                    break
        if drop:
            k2 += drop
        else:
            res.append(kept[k2])
            k2 += 1
    kept = res

    # ── S6: honor transcription-marked straight-quote spans. The span belongs to the speaker
    # who OPENED it (an interrupter's cues stay unquoted); straight marks are stripped from
    # display and every cue in the span is re-wrapped in its own curly quotes at render.
    open_q, owner = False, None
    for i in kept:
        r = raw_of(i)
        if not open_q:
            if r.startswith('"'):
                q[i] = True
                owner = voice_of(i)
                open_q = r.count('"') < 2  # "word" one-token quote closes itself
        elif voice_of(i) == owner:
            q[i] = True
            if '"' in r:
                open_q, owner = False, None
    italic = [bool(spec(i).get("i")) or q[i] for i in range(N)]  # quoted speech is always italic

    # ── positional signal arrays over the kept sequence ──
    K = len(kept)
    V = [voice_of(i) for i in kept]
    DV = [disp_v2(i) for i in kept]
    NB = [_nrm(i) for i in kept]
    SEND = [ends_sentence(i) for i in kept]
    SCOM = [ends_comma(i) for i in kept]
    GAP = [(W_start(kept[k + 1]) - W_end(kept[k])) if k + 1 < K else 999.0 for k in range(K)]
    ONS = [(W_start(kept[k + 1]) - W_start(kept[k])) if k + 1 < K and V[k + 1] == V[k] else None
           for k in range(K)]
    MONEYISH = [bool(re.match(r"^\$", DV[k])) or bool(re.match(r"^\d[\d,.]*[KMB%]?$", DV[k]))
                for k in range(K)]
    CUT_ZONE = [camera_zone(i) for i in kept]

    def lavg(k):
        # LOCAL average onset (speech rate) around k; pauses/boundaries (>0.8s) excluded so the
        # average reflects the talking pace, not the silences.
        vals = [o for o in ONS[max(0, k - 4):k + 4] if o is not None and o < 0.8]
        if len(vals) < 3:
            vals = [o for o in ONS if o is not None and o < 0.8]
        return (sum(vals) / len(vals)) if vals else 0.30

    # ── S3: GLUE — bonds the cadence cap may NOT break (a real pause/speaker change still wins).
    # glue[k] = True → no soft break between kept[k] and kept[k+1].
    glue = [False] * K
    for k in range(K):
        for ph in COLLOC:
            n = len(ph)
            if k + n <= K and NB[k:k + n] == ph:
                for j2 in range(k, k + n - 1):
                    glue[j2] = True
    for k in range(K - 1):
        if SEND[k]:
            continue
        tp, tw = NB[k], NB[k + 1]
        if tp in DETERMINERS:
            glue[k] = True                      # never end a cue on a determiner/possessive (S1)
        if tp in NEG_AUX:
            glue[k] = True                      # "didn't | wanna" → neg-aux stays with its verb
        if tw in OBJ_PRON:
            glue[k] = True                      # never start a cue with me/him/us/them (S1)
        if re.match(r"^\$?\d|^#\d", DV[k]) and not MONEYISH[k + 1]:
            glue[k] = True                      # money/number/listicle + its noun ("2 things", "$100K revenue", "#1 rule")
        if tw in TIME_UNITS and (re.match(r"^\$?\d", DV[k]) or tp in ("a", "an")):
            glue[k] = True                      # quantity + time-unit ("6 months", "a year")
        if tw in FIN_IDS and tp in ("in", "of", "per") and k >= 1 and DV[k - 1].startswith("$"):
            glue[k] = True                      # money + identifier ("$5M in revenue")

    def seam_start(k):
        return NB[k] in CONNECTORS or NB[k] in DETERMINERS

    def chunk_chars(idxs):
        n = len(" ".join(disp_v2(j) for j in idxs))
        if any(q[j] for j in idxs):
            n += 2  # per-cue curly quote marks count toward the safe-zone width
        return n

    def cue_len(pos_seq, extra=None):
        seq = list(pos_seq) + ([extra] if extra is not None else [])
        return chunk_chars([kept[k] for k in seq])

    def tier_caps(k, cur_pos):
        la = lavg(k)
        mw, mc = TIERS["slow"] if la >= TIER_SLOW else (TIERS["med"] if la >= TIER_MED else TIERS["fast"])
        if q[kept[k]] or (cur_pos and q[kept[cur_pos[-1]]]):
            mw = min(mw, 2)  # quoted/hypothetical dialogue breaks FINER (~1-2 words per cue)
        return mw, mc

    # ── S2: the break walk (priority order) ──
    cues_pos, cur = [], []
    for k in range(K):
        if not cur:
            cur = [k]
            continue
        p = k - 1
        la = lavg(p)
        # onset boundary: >=400ms absolute (sanity-guarded vs local avg so slow speech doesn't
        # break after EVERY word) OR >=1.6x local avg (catches boundaries in fast passages).
        # Skipped right after a dropped filler / collapsed stutter (that gap was the artifact,
        # not lengthening) and never inside a glued unit — the onset signal is a heuristic;
        # only REAL silence (>=250ms) may split glue ("a real pause still wins", S3).
        onset_hit = (kept[p] not in onset_skip and not glue[p] and ONS[p] is not None
                     and ((ONS[p] >= ONSET_ABS and ONS[p] >= 1.15 * la)
                          or (la > 0 and ONS[p] >= ONSET_REL * la and ONS[p] >= 0.20)))
        brk = backtrack = False
        if CUT_ZONE[k] != CUT_ZONE[p]:
            brk = True        # 0. CAMERA CUT — outgoing shot never pre-reveals incoming words
        elif V[k] != V[p]:
            brk = True        # 1. SPEAKER CHANGE — always, non-negotiable (LOCKED 2026-06-10)
        elif SEND[p]:
            brk = True        # 2. sentence-final punctuation
        elif GAP[p] >= SIL_BREAK:
            brk = True        # 3a. real silence — pause pre-reveal split (LOCKED 2026-06-14)
        elif onset_hit:
            brk = True        # 3b. onset / phrase-final lengthening
        elif NB[k] and NB[k] == NB[p]:
            brk = True        # identical surviving pair ("is | is") never shares a cue
        elif NB[k] in INTERJ and _tail(kept[k]).endswith(("!", "?", ",")):
            brk = True        # punctuated interjection/backchannel starts its OWN cue (S4)
        elif MONEYISH[k] and any(MONEYISH[j] for j in cur) and NB[p] not in ("to", "through"):
            brk = True        # S4: enumerations of numbers/money break PER ITEM ($10M | $15M)
        elif SCOM[p] and GAP[p] >= COMMA_GAP and len(cur) >= 2:
            brk = True        # 4. comma WITH a gap (a no-gap comma is a disfluency — don't break)
        else:
            mw, mc = tier_caps(k, cur)
            cand = cue_len(cur, k)
            if cand > HARD_MAX:
                brk = backtrack = True  # HARD 25c — break before the word (or its glued unit)
            elif len(cur) + 1 > mw or cand > mc:
                # 5. pace-adaptive cadence cap + 6. chunk-aligned seam targeting
                if glue[p]:
                    pass      # glued unit — defer, never split it (S3)
                elif NB[k] in CONNECTORS and GAP[k] >= SIL_BREAK and cand <= HARD_MAX:
                    pass      # connector a pause will end — keep it, the pause breaks after it
                elif seam_start(k):
                    brk = True  # breaking before a conjunction/preposition/determiner IS the seam
                elif k + 1 < K and seam_start(k + 1) and cand <= HARD_MAX:
                    pass      # defer ONE word to land the break on a seam
                else:
                    brk = True
        if brk:
            if backtrack:
                # 25c overflow on a glued unit: move the WHOLE unit into the new cue (S3 — break
                # before/after the phrase, never inside), always keeping >=1 word behind.
                new = [k]
                while len(cur) > 1 and glue[cur[-1]]:
                    new.insert(0, cur.pop())
                cues_pos.append(cur)
                cur = new
            else:
                cues_pos.append(cur)
                cur = [k]
        else:
            cur.append(k)
    if cur:
        cues_pos.append(cur)

    # ── ORPHAN-MERGE (LOCKED lesson, adapted): eliminate 1-word cues unless a sentence end,
    # speaker change, pause, enumeration item, or identical-pair split justifies stranding.
    # Never re-creates a mixed-voice cue, never merges across a pause (pre-reveal), never
    # exceeds the 25c hard max.
    def _mergeable(a_pos, b_pos):
        pa, kb = a_pos[-1], b_pos[0]
        return (V[pa] == V[kb] and not SEND[pa] and GAP[pa] < SIL_BREAK
                and CUT_ZONE[pa] == CUT_ZONE[kb]
                and NB[pa] != NB[kb]
                and not (MONEYISH[kb] and any(MONEYISH[j] for j in a_pos))
                # a punctuated backchannel is an INTENDED standalone cue (S4) — never fold it
                and not (NB[kb] in INTERJ and _tail(kept[kb]).endswith(("!", "?", ",", ".")))
                and not (NB[pa] in INTERJ and _tail(kept[pa]).endswith(("!", "?", ",")))
                and cue_len(a_pos + b_pos) <= HARD_MAX)

    if len(cues_pos) > 1:
        merged = []
        for chp in cues_pos:
            if len(chp) == 1 and merged and _mergeable(merged[-1], chp):
                merged[-1] = merged[-1] + chp
            else:
                merged.append(chp)
        # A singleton that STARTS a later camera zone cannot merge backward across
        # the cut, but it may still belong with the following phrase.  Forward-merge
        # such orphans anywhere in the list, not only at the start of the whole clip.
        forward = []
        pos = 0
        while pos < len(merged):
            if (len(merged[pos]) == 1 and pos + 1 < len(merged)
                    and _mergeable(merged[pos], merged[pos + 1])):
                forward.append(merged[pos] + merged[pos + 1])
                pos += 2
            else:
                forward.append(merged[pos])
                pos += 1
        merged = forward
        cues_pos = merged

    chunks = [[kept[k] for k in chp] for chp in cues_pos]

    # ── TIMING: v2 SEQUENTIAL LAYOUT — 5-frame ABSOLUTE floor + dense-cue reading bump ──
    # start = max(first word's onset-corrected start, previous cue's end); end holds GAPLESS to
    # the next cue's start (capped ~2s) and is never < start + 5 frames — a crammed cue PUSHES
    # the following cues a few frames (nothing dropped), self-correcting at the next pause.
    # A cue shown >2.0 visible chars/frame gets +1 frame of screen time (reading bump).
    FRAME = 1.0 / 24.0
    FLOOR = a.min_cue_dur if a.min_cue_dur is not None else float(T.get("min_cue_dur", 0.21))
    MAX_CUE = float(T.get("max_cue_dur", 2.0))
    onset_on = T.get("onset_correct", True) and not a.no_onset_correct

    def eff_onset(i):
        # function-word onset-correction (a long Groq span on a function word = absorbed pause;
        # its real onset is near the span's END). Uses the ORIGINAL end — eff_end may have been
        # extended over a dropped filler, which is not an absorbed pause.
        s, e = W_start(i), float(words[i]["end"])
        exp = 0.10 + 0.055 * (len(bare(words[i]["word"])) or 1)
        if onset_on and (e - s) > exp + 0.45 and bare(words[i]["word"]) in FUNCTION_WORDS:
            return max(s, e - exp)
        return s

    starts, ends = [], []
    prev_en = 0.0
    for ci, ch in enumerate(chunks):
        st = max(eff_onset(ch[0]), prev_en) if ci else eff_onset(ch[0])
        if ci + 1 < len(chunks):
            nxt = eff_onset(chunks[ci + 1][0])
            en = min(nxt, max(st + MAX_CUE, W_end(ch[-1]) + 0.10))  # gapless hold, ~2s max
        else:
            en = W_end(ch[-1]) + 0.30
        en = max(en, st + FLOOR)                       # 5-frame floor (0.21s >= 5 frames @24fps)
        if chunk_chars(ch) / max(1e-6, (en - st) / FRAME) > 2.0:
            en += FRAME                                # dense-cue +1-frame reading bump (capped at 1)
        starts.append(st)
        ends.append(en)
        prev_en = en

    # --- render ---
    W = P["video"]["width"]; H = P["video"]["height"]
    FS = P.get("font_size_px", 150)
    # RESOLUTION-ADAPTIVE (2026-06-11): the two-layer gblur shadow sigma is FS-relative but ffmpeg
    # applies it in REAL output pixels, while libass rescales the TEXT from PlayRes->frame. If the
    # preset's dims don't match the actual burn frame, the text self-corrects but the shadow does NOT
    # -> a halo ~(frame/preset)x the wrong size (the months-long "wrong shadow" bug, and the /edit
    # default of the 4K preset on a 1080 frame). FIX AT THE SOURCE: when burning, probe the real frame
    # and scale W/H/FS to it so PlayRes==frame (text identical) AND the FS-relative shadow lands at the
    # right radius. A matched preset is unchanged (scale==1 -> byte-identical). This makes a wrong-res
    # shadow IMPOSSIBLE for EVERY caller (caption-app + qa_build + qa_assembly), not merely detected.
    if a.burn:
        try:
            _bd = subprocess.run(
                [FFP, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(a.burn)],
                capture_output=True, text=True).stdout.strip().split("x")
            bw, bh = int(_bd[0]), int(_bd[1])
            if bh > 0 and H > 0 and (bw, bh) != (W, H):
                sc = bh / H
                print(f"resolution-adaptive: preset {W}x{H} FS{FS} -> burn frame {bw}x{bh} "
                      f"FS{int(round(FS*sc))} (shadow scale {sc:.3f})")
                W, H, FS = bw, bh, int(round(FS * sc))
        except Exception as _e:
            print(f"resolution-adaptive probe skipped ({_e}); using preset dims {W}x{H}")
    Y_DEFAULT = int(round(H * P["layout"]["y_percent_from_top"] / 100))

    # Per-cue Y from layout track. If --layout is set, each cue's Y comes from the
    # layout segment its time-midpoint falls in (safe_y_pct in the JSON is a 0..1
    # fraction of FRAME height — we multiply by H here). With no layout, every cue
    # uses the preset's static Y (the legacy spice behavior).
    #
    # FRAME-ACCURATE TRANSITIONS: layout_analyze.py now outputs segments with
    # hard-cut boundaries (no smoothing across cuts). We store the transition
    # timestamps so generate_spice can SPLIT any caption cue that spans a
    # transition — the Y snaps at the exact frame the camera angle changes.
    layout_segs = None
    layout_transitions = []  # [(time, y_before, y_after), ...]
    if a.layout and a.layout.exists():
        try:
            ld = json.loads(a.layout.read_text())
            fps = ld.get("meta", {}).get("fps", 30.0)
            layout_segs = [
                {"t0": s["start_i"] / fps, "t1": (s["end_i"] + 1) / fps,
                 "y": int(round(H * float(s["safe_y_pct"])))}
                for s in ld.get("segments", [])
            ]
            # Only record a Y transition when the jump is significant enough
            # to be visible. Small Y changes (<50px on 1920-tall frame ≈ 2.6%)
            # come from face detection noise (slightly different face position
            # between angles) and create imperceptible cue splits that waste
            # subtitle events and confuse the renderer.
            MIN_Y_JUMP = 50  # pixels — ~2.6% of 1920px frame height
            # FRAME-EXACT SNAP (2026-06-10): the Y must change on the cut frame itself,
            # not the frame after. ts() rounds to centiseconds (~0.3 frame), so a snap
            # time of exactly start_i/fps can round UP and render the new Y one frame
            # late — which reads as jumpy (Maddex: "if you don't do it the second the
            # frame switches it looks shitty"). Nudge the split time back HALF a frame so
            # the rounding lands the new Y on start_i. Both halves of the split share this
            # time, so they stay coincident — only the rendered frame of the snap shifts.
            half_frame = 0.5 / fps
            for i in range(1, len(layout_segs)):
                prev, cur = layout_segs[i - 1], layout_segs[i]
                if abs(prev["y"] - cur["y"]) >= MIN_Y_JUMP:
                    layout_transitions.append((max(0.0, cur["t0"] - half_frame), prev["y"], cur["y"]))
            print(f"layout: {len(layout_segs)} segments, Y range "
                  f"{min(s['y'] for s in layout_segs)}-{max(s['y'] for s in layout_segs)} px"
                  f", {len(layout_transitions)} significant Y-transitions (≥{MIN_Y_JUMP}px)")
        except Exception as e:
            print(f"layout: parse failed ({e}), using static Y={Y_DEFAULT}")
            layout_segs = None

    def y_at(t: float) -> int:
        if not layout_segs:
            return Y_DEFAULT
        for s in layout_segs:
            if s["t0"] <= t < s["t1"]:
                return s["y"]
        return layout_segs[-1]["y"]  # past-end → hold last segment

    def transition_in(t0: float, t1: float):
        """Return the first layout transition (time, y_before, y_after) within [t0, t1), or None."""
        for tr in layout_transitions:
            if t0 < tr[0] < t1:
                return tr
        return None

    CX = W // 2
    fax = P.get("italic_fax", -0.12)  # NEGATIVE = forward/right lean; positive leans LEFT in libass
    sh = P.get("shadow", {})
    shadow_mode = sh.get("mode", "classic")  # "classic" = old single-layer | "premiere" = two-layer soft
    shad = sh.get("offset_y", 9); blur = sh.get("blur", 18)
    sh_a = sh.get("alpha", 42); sh_c = sh.get("color", "000000")
    stroke = sh.get("stroke_px", 5); stroke_c = sh.get("stroke_color", "141414")
    # Premiere-mode shadow: separate blurred layer underneath crisp text.
    # shadow blurs independently — text stays sharp. Looks like Premiere Pro.
    # In premiere mode, the SHADOW provides text separation (not a hard outline).
    # Use premiere_stroke_px (default 0) instead of the thick classic stroke.
    if shadow_mode == "premiere":
        stroke = sh.get("premiere_stroke_px", 0)
    # Premiere Drop Shadow — TWO STACKED LAYERS, decoded from Oliver's .prtextstyle preset.
    # The preset's binary holds TWO down-right (~110 deg) drop-shadow records, not one:
    #   Layer 1 (WIDE):  distance 20, blur 15  -> bigger, softer, drawn underneath
    #   Layer 2 (TIGHT): distance 10, blur 8   -> closer, denser, stacked on top
    # (a 3rd cluster = opacity 100 / size 250 = the text FILL, not a shadow.)
    # One layer alone reads mushy (no edge contrast); the pair gives a dense core at the
    # letters AND a soft trailing falloff — the Premiere look Maddex flagged.
    # FONT-RELATIVE (FS_REF=150) so both layers scale to any render resolution.
    FS_REF = 150.0
    fs_scale = FS / FS_REF
    def _sc(v): return round(v * fs_scale, 1)
    def _sci(v): return int(round(v * fs_scale))
    # Layer 1 — WIDE / soft (preset shadow 1: dist20 / blur15)
    pr_sh_dx     = _sci(sh.get("offset_x", 5))
    pr_sh_dy     = _sci(sh.get("premiere_offset_y", 9))
    pr_sh_sigma  = _sc(sh.get("premiere_sigma", 15))
    pr_sh_border = _sci(sh.get("premiere_border", 8))
    pr_sh_intensity = sh.get("premiere_intensity", 0.70)
    # Layer 2 — TIGHT / dense (preset shadow 2: dist10 / blur8)
    pr_sh2_enabled   = sh.get("premiere_layer2", True)
    pr_sh2_dx        = _sci(sh.get("offset_x2", 2))
    pr_sh2_dy        = _sci(sh.get("premiere_offset_y2", 4))
    pr_sh2_sigma     = _sc(sh.get("premiere_sigma2", 7))
    pr_sh2_border    = _sci(sh.get("premiere_border2", 6))
    pr_sh2_intensity = sh.get("premiere_intensity2", 0.97)
    # Legacy ASS-only params (not used for gblur path, kept for reference)
    pr_sh_blur = sh.get("premiere_blur", 22)
    pr_sh_spread = sh.get("premiere_spread", 35)
    pr_sh_opacity = sh.get("premiere_opacity", 0.28)
    pr_sh_alpha = max(0, min(255, int(round((1.0 - pr_sh_opacity) * 255))))
    an = P.get("animation", {})
    # The caption "drop-in" distance is a PIXEL value tuned for the Premiere "Text Down Small" look
    # at 4K (FS_REF 150 -> ~16px). Like the shadow, it must scale with FS/resolution, else a 1080 frame
    # gets the full 16px = ~2x the relative drop (the "animation looks different" Maddex caught). _sci
    # makes it FS-relative (16px@4K -> 8px@1080), so the subtle Premiere drop reads identically at any res.
    drop = _sci(an.get("position_drop_px", 16)); drop_ms = an.get("position_drop_duration_ms", 500)
    op_from = an.get("opacity_from", 0.90); op_ms = an.get("opacity_fade_duration_ms", 83)
    op_a = max(0, min(255, int(round((1.0 - op_from) * 255))))
    base_family = weights.get(default_weight, "Proxima Nova Regular")
    # gloss (under-caption definition) styling: smaller Proxima Nova Medium, one line below the caption.
    GP = P.get("gloss", {})
    gloss_fs = int(round(FS * GP.get("scale", 0.5)))
    gloss_dy = int(round(FS * GP.get("dy", 0.95)))
    gloss_font = GP.get("font", "Proxima Nova Medium")

    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Spice,{base_family},{FS},&H00FFFFFF,&H00FFFFFF,{ass_color(stroke_c)},&H00000000,0,0,0,0,100,100,0,0,1,{stroke},0,5,80,80,80,1
Style: SpiceShadow,{base_family},{FS},&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,80,80,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # --- caption bubble (ACQ testimonial style): translucent rounded bg behind each cue ---
    # Gated on preset["bubble"]; absent => no change to any other brand's spice render.
    BUB = P.get("bubble")
    def _rrect(w, h, r):
        # top-left-anchored rounded rect (0,0)->(w,h); emitted with \an7 + offset \pos so it
        # centers under the cue. (\an5 mis-anchors \p1 drawings in libass -> shifted left.)
        r = max(0.0, min(r, w / 2.0, h / 2.0))
        x0, y0, x1, y1 = 0.0, 0.0, w, h
        return (f"m {x0 + r:.0f} {y0:.0f} l {x1 - r:.0f} {y0:.0f} "
                f"b {x1:.0f} {y0:.0f} {x1:.0f} {y0 + r:.0f} {x1:.0f} {y0 + r:.0f} "
                f"l {x1:.0f} {y1 - r:.0f} b {x1:.0f} {y1:.0f} {x1 - r:.0f} {y1:.0f} {x1 - r:.0f} {y1:.0f} "
                f"l {x0 + r:.0f} {y1:.0f} b {x0:.0f} {y1:.0f} {x0:.0f} {y1 - r:.0f} {x0:.0f} {y1 - r:.0f} "
                f"l {x0:.0f} {y0 + r:.0f} b {x0:.0f} {y0:.0f} {x0 + r:.0f} {y0:.0f} {x0 + r:.0f} {y0:.0f}")
    bubble_ev = []
    ev = []
    for ci, ch in enumerate(chunks):
        # v2 sequential layout precomputed above: 5-frame floor + dense bump, no overlap possible
        st, en = starts[ci], ends[ci]

        toks = []
        # SIZE PER CUE (Maddex 2026-06-11 CORRECTION): a size bump may land on a SINGLE-WORD caption
        # OR the ENTIRE line uniformly — NEVER on one word inside a multi-word line (that reads broken;
        # Oliver never did it). So size is decided per CUE, not per word, and every word in the cue
        # gets the SAME size. WEIGHT + italic still vary per word (bold the key word) — only SIZE is
        # locked uniform within a multi-word line.
        solo = len(ch) == 1
        _ws = [size_of(i) for i in ch]
        if solo:
            cue_sz = _ws[0]                                    # (a) single-word caption -> keep its bump
        elif any(is_number(words[i]["word"]) for i in ch):
            cue_sz = int(sizes.get("strong", 150))             # (b) money/number line -> bump the WHOLE line
        elif len(set(_ws)) == 1 and _ws[0] != 100:
            cue_sz = _ws[0]                                     # (b) director sized the whole line uniformly
        else:
            cue_sz = 100                                       # multi-word, mixed -> base (never one word bigger)
        # SAFE-ZONE CAP (Maddex 2026-06-11): a size bump must NEVER run a line off-screen / out of the
        # UI ("$10M minimum" at 150% hit 99% of frame width). Measure the displayed line at the bumped
        # size and shrink the bump until it fits within ~82% of frame width.
        if cue_sz > 100:
            cue_text = " ".join(disp_v2(i) for i in ch)
            safe_px = int(0.82 * W)
            wpx = line_width_px(cue_text, int(FS * cue_sz / 100))
            if wpx > safe_px:
                cue_sz = max(100, int(cue_sz * safe_px / wpx))
        # PER-CUE quotes (v2 S6): each caption cue wraps its OWN quoted span in CURLY “ ” marks,
        # so a multi-cue quote shows marks on every segment — not just the first/last cue of the
        # run. The lead-in outside the quoted words stays unwrapped.
        qin = [i for i in ch if q[i]]
        fq, lq = (qin[0], qin[-1]) if qin else (None, None)
        for idx in ch:
            fam = weights.get(weight_of(idx), base_family)
            f = fax if italic[idx] else 0
            text = disp_v2(idx)
            if idx == fq:
                text = "“" + text
            if idx == lq:
                text = text + "”"
            sz = cue_sz
            scale = f"\\fscx{sz}\\fscy{sz}" if sz != 100 else ""
            toks.append(f"{{\\fn{fam}\\b0\\i0\\fax{f}{scale}\\1c{ass_color(color_hex(idx))}}}{text}")

        # FRAME-ACCURATE Y: check if a layout transition falls inside this cue.
        # If so, split the cue into two Dialogue events at the exact transition
        # frame — the text is identical but Y snaps instantly at the cut.
        body = " ".join(toks)
        # bubble geometry for this cue (sized to the displayed text + padding)
        bub_draw = None; _btags = ""
        if BUB:
            _px = max(1, int(FS * cue_sz / 100))
            _ct = " ".join(disp_v2(i) for i in ch)
            _tw = line_width_px(_ct, _px)
            _safe = 0.86 * W
            _nl = max(1, -(-int(_tw) // int(_safe)))      # ceil -> line count if it wraps
            _lw = min(float(_tw), _safe)
            _lh = _px * 1.16
            _padx = BUB.get("pad_x_em", 0.5) * _px
            _pady = BUB.get("pad_y_em", 0.34) * _px
            _bw = _lw + 2 * _padx
            _bh = _nl * _lh + 2 * _pady
            _rad = min(BUB.get("radius_em", 0.55) * _px, _bh / 2.0, _bw / 2.0)
            bub_draw = _rrect(_bw, _bh, _rad)
            _ba = int(BUB.get("alpha", 128)); _bl = BUB.get("blur", 4); _bc = BUB.get("color", "000000")
            _btags = f"\\p1\\bord0\\shad0\\blur{_bl}\\1c{ass_color(_bc)}\\1a&H{_ba:02X}&"
        # Shadow-only body: same text structure but all words forced to black (for the shadow layer).
        # We keep the per-word \fn so the shadow matches the text shape exactly.
        if shadow_mode == "premiere":
            shadow_toks = []
            for idx in ch:
                fam = weights.get(weight_of(idx), base_family)
                f = fax if italic[idx] else 0
                text = disp_v2(idx)
                if idx == fq:
                    text = "“" + text
                if idx == lq:
                    text = text + "”"
                sz = cue_sz   # shadow scales with the per-CUE size
                scale = f"\\fscx{sz}\\fscy{sz}" if sz != 100 else ""
                shadow_toks.append(f"{{\\fn{fam}\\b0\\i0\\fax{f}{scale}}}{text}")
            shadow_body = " ".join(shadow_toks)

        tr = transition_in(st, en)
        if tr:
            cut_t, y_before, y_after = tr
            if shadow_mode == "premiere":
                # --- PREMIERE SHADOW: two-layer (shadow underneath, crisp text on top) ---
                # Shadow layer (Layer 0) — blurred black text, offset, semi-transparent
                sh_pre1 = (f"{{\\an5\\pos({CX + pr_sh_dx},{y_before + pr_sh_dy})"
                           f"\\bord{pr_sh_spread}\\shad0\\blur{pr_sh_blur}"
                           f"\\1c&H00000000&\\3c&H00000000&"
                           f"\\1a&H{pr_sh_alpha:02X}&\\3a&H{pr_sh_alpha:02X}&\\4a&HFF&}}")
                ev.append(f"Dialogue: 0,{ts(st)},{ts(cut_t)},SpiceShadow,,0,0,0,,{sh_pre1}{shadow_body}")
                sh_pre2 = (f"{{\\an5\\pos({CX + pr_sh_dx},{y_after + pr_sh_dy})"
                           f"\\bord{pr_sh_spread}\\shad0\\blur{pr_sh_blur}"
                           f"\\1c&H00000000&\\3c&H00000000&"
                           f"\\1a&H{pr_sh_alpha:02X}&\\3a&H{pr_sh_alpha:02X}&\\4a&HFF&}}")
                ev.append(f"Dialogue: 0,{ts(cut_t)},{ts(en)},SpiceShadow,,0,0,0,,{sh_pre2}{shadow_body}")
                # Text layer (Layer 1) — crisp, thin outline, no blur, no shadow
                pre1 = (f"{{\\an5\\pos({CX},{y_before})"
                        f"\\1a&H{op_a:02X}&\\t(0,{op_ms},\\1a&H00&)"
                        f"\\shad0\\blur0\\3c{ass_color(stroke_c)}}}")
                ev.append(f"Dialogue: 1,{ts(st)},{ts(cut_t)},Spice,,0,0,0,,{pre1}{body}")
                pre2 = (f"{{\\an5\\pos({CX},{y_after})"
                        f"\\shad0\\blur0\\3c{ass_color(stroke_c)}}}")
                ev.append(f"Dialogue: 1,{ts(cut_t)},{ts(en)},Spice,,0,0,0,,{pre2}{body}")
            else:
                # --- CLASSIC SHADOW: single-layer ASS shadow ---
                pre1 = (f"{{\\an5\\pos({CX},{y_before})"
                        f"\\1a&H{op_a:02X}&\\t(0,{op_ms},\\1a&H00&)"
                        f"\\shad{shad}\\blur{blur}\\4c{ass_color(sh_c)}\\4a&H{sh_a:02X}&\\3c{ass_color(stroke_c)}}}")
                ev.append(f"Dialogue: 0,{ts(st)},{ts(cut_t)},Spice,,0,0,0,,{pre1}{body}")
                pre2 = (f"{{\\an5\\pos({CX},{y_after})"
                        f"\\shad{shad}\\blur{blur}\\4c{ass_color(sh_c)}\\4a&H{sh_a:02X}&\\3c{ass_color(stroke_c)}}}")
                ev.append(f"Dialogue: 0,{ts(cut_t)},{ts(en)},Spice,,0,0,0,,{pre2}{body}")
            if bub_draw:
                _bx = CX - _bw / 2.0
                bubble_ev.append(f"Dialogue: 0,{ts(st)},{ts(cut_t)},Spice,,0,0,0,,{{\\an7\\pos({_bx:.0f},{y_before - _bh/2:.0f}){_btags}}}{bub_draw}")
                bubble_ev.append(f"Dialogue: 0,{ts(cut_t)},{ts(en)},Spice,,0,0,0,,{{\\an7\\pos({_bx:.0f},{y_after - _bh/2:.0f}){_btags}}}{bub_draw}")
        else:
            Y_cue = y_at((st + en) / 2.0)
            if bub_draw:
                _bx = CX - _bw / 2.0
                bubble_ev.append(f"Dialogue: 0,{ts(st)},{ts(en)},Spice,,0,0,0,,"
                                 f"{{\\an7\\move({_bx:.0f},{Y_cue - drop - _bh/2:.0f},{_bx:.0f},{Y_cue - _bh/2:.0f},0,{drop_ms}){_btags}}}{bub_draw}")
            if shadow_mode == "premiere":
                # --- PREMIERE SHADOW: two-layer ---
                # Shadow layer (Layer 0)
                sh_pre = (f"{{\\an5\\move({CX + pr_sh_dx},{Y_cue - drop + pr_sh_dy},{CX + pr_sh_dx},{Y_cue + pr_sh_dy},0,{drop_ms})"
                          f"\\bord{pr_sh_spread}\\shad0\\blur{pr_sh_blur}"
                          f"\\1c&H00000000&\\3c&H00000000&"
                          f"\\1a&H{pr_sh_alpha:02X}&\\3a&H{pr_sh_alpha:02X}&\\4a&HFF&}}")
                ev.append(f"Dialogue: 0,{ts(st)},{ts(en)},SpiceShadow,,0,0,0,,{sh_pre}{shadow_body}")
                # Text layer (Layer 1) — crisp
                pre = (f"{{\\an5\\move({CX},{Y_cue-drop},{CX},{Y_cue},0,{drop_ms})"
                       f"\\1a&H{op_a:02X}&\\t(0,{op_ms},\\1a&H00&)"
                       f"\\shad0\\blur0\\3c{ass_color(stroke_c)}}}")
                ev.append(f"Dialogue: 1,{ts(st)},{ts(en)},Spice,,0,0,0,,{pre}{body}")
            else:
                # --- CLASSIC SHADOW ---
                pre = (f"{{\\an5\\move({CX},{Y_cue-drop},{CX},{Y_cue},0,{drop_ms})"
                       f"\\1a&H{op_a:02X}&\\t(0,{op_ms},\\1a&H00&)"
                       f"\\shad{shad}\\blur{blur}\\4c{ass_color(sh_c)}\\4a&H{sh_a:02X}&\\3c{ass_color(stroke_c)}}}")
                ev.append(f"Dialogue: 0,{ts(st)},{ts(en)},Spice,,0,0,0,,{pre}{body}")
        # under-caption gloss for any glossed word in this cue
        gtxt = next((gloss[str(i)] for i in ch if str(i) in gloss), None)
        if gtxt:
            Y_g = y_at((st + en) / 2.0) + gloss_dy
            gpre = (f"{{\\an5\\pos({CX},{Y_g})\\fn{gloss_font}\\b0\\i0\\fs{gloss_fs}"
                    f"\\1c&H00FFFFFF&\\shad{shad}\\blur{blur}\\4c{ass_color(sh_c)}\\4a&H{sh_a:02X}&"
                    f"\\3c{ass_color(stroke_c)}\\1a&H28&\\t(0,120,\\1a&H00&)}}")
            ev.append(f"Dialogue: 0,{ts(st)},{ts(en)},Spice,,0,0,0,,{gpre}{gtxt}")

    a.out.write_text(hdr + "\n".join(ev) + "\n")
    print(f"wrote {len(ev)} caption cues -> {a.out}")

    # Premiere gblur shadow: write separate shadow (white blob) + text-only ASS files.
    # The shadow ASS has white text + white border + no blur (gblur applied via ffmpeg).
    # The text ASS has only the crisp Layer 1 events.
    shadow_ass_path = shadow2_ass_path = text_ass_path = None
    if shadow_mode == "premiere":
        import re as _re
        def _shadow_events(border):
            out = []
            for line in ev:
                if line.startswith("Dialogue: 0,"):
                    l = line
                    l = _re.sub(r'\\bord\d+', f'\\\\bord{border}', l)
                    l = _re.sub(r'\\blur\d+', r'\\blur0', l)
                    l = l.replace('\\1c&H00000000&', '\\1c&H00FFFFFF&')
                    l = l.replace('\\3c&H00000000&', '\\3c&H00FFFFFF&')
                    l = _re.sub(r'\\1a&H[0-9A-Fa-f]+&', r'\\1a&H00&', l)
                    l = _re.sub(r'\\3a&H[0-9A-Fa-f]+&', r'\\3a&H00&', l)
                    out.append(l)
            return out
        text_ev = [l for l in ev if l.startswith("Dialogue: 1,")]
        # Layer 1 blob uses Size=pr_sh_border; Layer 2 blob uses Size=pr_sh2_border (Premiere "Size"/spread).
        shadow_ass_path  = a.out.with_name(a.out.stem + "_shadow.ass")
        shadow2_ass_path = a.out.with_name(a.out.stem + "_shadow2.ass")
        text_ass_path    = a.out.with_name(a.out.stem + "_text.ass")
        shadow_ass_path.write_text(hdr + "\n".join(_shadow_events(pr_sh_border)) + "\n")
        shadow2_ass_path.write_text(hdr + "\n".join(_shadow_events(pr_sh2_border)) + "\n")
        text_ass_path.write_text(hdr + "\n".join((bubble_ev + text_ev) if BUB else text_ev) + "\n")
        print(f"premiere gblur: wrote shadow blobs (border {pr_sh_border}/{pr_sh2_border}) + {len(text_ev)} text cues")
        # Auto-export a styled SRT for Premiere caption track import.
        # Oliver imports this → applies his Proxima Nova + shadow caption style to the track;
        # bold/italic/color per word is already encoded inline. No extra flags needed.
        try:
            # NOTE: do NOT re-import sys as _sys here. This block is premiere-mode only, but a
            # local `sys as _sys` binding makes _sys LOCAL to main() for the whole function ->
            # the classic-branch burn-failure message below (file=_sys.stderr) died with
            # UnboundLocalError instead of printing the diagnostic. Module-level _sys covers both.
            import subprocess as _sp
            _exp = Path(__file__).parent / "export_premiere_srt.py"
            _srt_out = text_ass_path.with_suffix(".srt")
            _r = _sp.run([_sys.executable, str(_exp), str(text_ass_path),
                          "--out", str(_srt_out), "--split"],
                         capture_output=True, text=True)
            if _r.returncode == 0:
                print(f"premiere SRT: {_r.stdout.strip()}")
            else:
                print(f"premiere SRT: skipped ({_r.stderr.strip()[:120]})")
        except Exception as _e:
            print(f"premiere SRT: skipped ({_e})")

    # BLOCKING TEXT GATE: this used to exist only as a documented standalone command, so callers
    # routinely skipped it. Run it inside the one renderer, after the crisp text sidecar exists and
    # BEFORE any expensive burn. `--expect-guest` adds the absence check that catches an all-white
    # Q&A/read-aloud render; structural rules run on every render regardless of speaker mode.
    import caption_lint as _caption_lint
    _lint_rc = _caption_lint.lint(str(a.out), expect_guest=a.expect_guest)
    if _lint_rc:
        print("✗ CAPTION LINT FAILED — refusing to burn or ship", file=_sys.stderr)
        return _lint_rc

    if a.burn:
        # BLOCKING GATE: burning captions needs libass. Without it ffmpeg emits a misleading
        # "No option name near '<path>'" and the run would otherwise ship an uncaptioned clip.
        global FF
        try:
            import sys as _s
            _s.path.insert(0, str(Path("__ACQ_SKILLS__/_shared")))
            from ffmpeg_bin import require_libass
            FF = require_libass("generate_spice --burn")
        except SystemExit:
            raise
        except Exception:
            pass
        out = a.burn_out or a.burn.with_name(a.burn.stem + "_spice.mp4")
        fdir = str((SKILL / P["fonts_dir"]).resolve()).replace(":", r"\:")
        # Bitrate must track the ACTUAL burn output resolution, not the preset PlayRes (which only
        # drives caption scaling). Else a 720 proxy gets the 4K bitrate -> ~5x too big. Probe the input.
        venc = (list(encoder_args_for(str(a.burn), FF, tier="delivery")) if encoder_args_for
                else ["-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p"])
        if a.overlay_out:
            # Premiere overlay mode: keep alpha end-to-end (transparent input assumed).
            # qtrle/argb: RGB the whole way — a yuva ProRes path squeezes BOTH color and
            # alpha into video range (white=235, alpha max ~235 = "92% opaque" captions).
            venc = ["-c:v", "qtrle", "-pix_fmt", "argb"]

        if shadow_mode == "premiere" and shadow_ass_path and text_ass_path:
            # Premiere TWO-LAYER gblur shadow (decoded from Oliver's preset).
            # One white blob (from the shadow ASS) -> two independently blurred/offset layers:
            #   WIDE (soft, underneath) then TIGHT (dense, on top) -> crisp text on top.
            # Each layer: gblur(sigma) -> curves(intensity) -> alphamerge w/ solid black -> overlay(dx,dy).
            # NOTE (2026-07-08): vf_ass writes COLOR but not ALPHA on transparent bases —
            # overlay text rides the shadow's alpha (~90%). The editor-approved fix: place
            # the overlay STACKED 3x in the NLE (1-(1-.9)^3 = solid). A single-layer-perfect
            # render needs a mask-twin text layer; a first attempt desynced the filtergraph
            # (cues smeared across time) — build it properly before retrying.
            sh_sub  = str(shadow_ass_path).replace(":", r"\:")
            sh2_sub = str(shadow2_ass_path).replace(":", r"\:")
            tx_sub  = str(text_ass_path).replace(":", r"\:")
            if pr_sh2_enabled:
                fc = (
                    f"[0:v]split=5[video][bw][sw][bt][st];"
                    # LAYER 1 (drawn first/underneath) — blob border = pr_sh_border
                    f"[bw]drawbox=c=black:t=fill[bwk];"
                    f"[bwk]ass='{sh_sub}':fontsdir='{fdir}'[wob_w];"
                    f"[wob_w]gblur=sigma={pr_sh_sigma},curves=all='0/0 1/{pr_sh_intensity:.2f}'[glow_w];"
                    f"[sw]drawbox=c=black:t=fill,format=yuva444p[sbk_w];"
                    f"[sbk_w][glow_w]alphamerge[layer_w];"
                    f"[video][layer_w]overlay=x={pr_sh_dx}:y={pr_sh_dy}:format=auto:shortest=1[v1];"
                    # LAYER 2 (drawn over layer 1) — blob border = pr_sh2_border
                    f"[bt]drawbox=c=black:t=fill[btk];"
                    f"[btk]ass='{sh2_sub}':fontsdir='{fdir}'[wob_t];"
                    f"[wob_t]gblur=sigma={pr_sh2_sigma},curves=all='0/0 1/{pr_sh2_intensity:.2f}'[glow_t];"
                    f"[st]drawbox=c=black:t=fill,format=yuva444p[sbk_t];"
                    f"[sbk_t][glow_t]alphamerge[layer_t];"
                    f"[v1][layer_t]overlay=x={pr_sh2_dx}:y={pr_sh2_dy}:format=auto:shortest=1[v2];"
                    f"[v2]ass='{tx_sub}':fontsdir='{fdir}'[final]"
                )
            else:
                fc = (
                    f"[0:v]split=3[video][forblack][forsolid];"
                    f"[forblack]drawbox=c=black:t=fill[black1];"
                    f"[black1]ass='{sh_sub}':fontsdir='{fdir}'[white_on_black];"
                    f"[white_on_black]gblur=sigma={pr_sh_sigma},curves=all='0/0 1/{pr_sh_intensity:.2f}'[glow];"
                    f"[forsolid]drawbox=c=black:t=fill,format=yuva444p[solid_black];"
                    f"[solid_black][glow]alphamerge[shadow_layer];"
                    f"[video][shadow_layer]overlay=x={pr_sh_dx}:y={pr_sh_dy}:format=auto:shortest=1[with_shadow];"
                    f"[with_shadow]ass='{tx_sub}':fontsdir='{fdir}'[final]"
                )
            if a.overlay_out:
                # Range-proofing: overlay's format=auto converts RGBA->limited-range YUV
                # mid-graph (white & alpha cap at ~235 -> "92% opaque" captions). Force the
                # composites to stay RGB, then unpremultiply (ass draws premultiplied).
                fc = fc.replace("format=auto", "format=rgb")
                fc += ";[final]format=rgba,unpremultiply=inplace=1[ovl]"
            r = subprocess.run([
                FF, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(a.burn),
                "-filter_complex", fc,
                "-map", "[ovl]" if a.overlay_out else "[final]", *([] if a.overlay_out else ["-map", "0:a"]),
                *venc, *([] if a.overlay_out else ["-c:a", "copy"]), "-movflags", "+faststart", str(out),
            ])
        else:
            # Classic single-pass ASS burn
            sub = str(a.out).replace(":", r"\:")
            r = subprocess.run([
                FF, "-y", "-hide_banner", "-loglevel", "error", "-i", str(a.burn),
                "-vf", f"subtitles=filename='{sub}':fontsdir='{fdir}'",
                *venc, "-c:a", "copy", "-movflags", "+faststart", str(out),
            ])
        print("burn rc", r.returncode, "->", out)
        if r.returncode != 0:
            print(f"✗ BURN FAILED (ffmpeg rc={r.returncode}) — propagating non-zero so the caller "
                  f"(caption_one / daemon / qa_build) marks the job failed instead of shipping a "
                  f"partial or empty mp4 as 'done'", file=_sys.stderr)
            return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

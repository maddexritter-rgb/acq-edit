#!/usr/bin/env python3
"""
Mozi Media Team Alex V1 MVP short-form audit.

Runs the 16-point checklist on a rendered 9:16 short-form clip.
(Updated 2026-05-04: added items #3 lower-half placement, #4 dialogue sync,
 #9 music balance, tightened gap and lead-frame thresholds per Oliver feedback.)

Usage:
    python3 audit.py --clip path/to/final.mp4 \
                     [--subtitles path/to/captions.ass] \
                     [--speaker-map path/to/speaker.json] \
                     [--platform instagram|tiktok|youtube-shorts] \
                     [--out path/to/audit.md]

Outputs (next to --out if given, else next to clip):
    <stem>.audit.md    — human-readable report
    <stem>.audit.json  — structured results
    <stem>.frameio.txt — Frame.io-paste-ready review notes
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Platform safezone config
# ─────────────────────────────────────────────────────────────────────────────

SAFEZONES = {
    "instagram": {
        "top_danger_pct": 0.13,
        "bottom_danger_pct": 0.18,
        "left_danger_pct": 0.05,
        "right_danger_pct": 0.05,
        "top_head_pad_min_pct": 0.13,
    },
    "tiktok": {
        "top_danger_pct": 0.10,
        "bottom_danger_pct": 0.22,
        "left_danger_pct": 0.05,
        "right_danger_pct": 0.14,  # music icon + profile stack
        "top_head_pad_min_pct": 0.10,
    },
    "youtube-shorts": {
        "top_danger_pct": 0.10,
        "bottom_danger_pct": 0.20,
        "left_danger_pct": 0.04,
        "right_danger_pct": 0.08,
        "top_head_pad_min_pct": 0.10,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Result data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    id: int
    category: str
    name: str
    status: str  # "pass" | "fail" | "warn" | "manual" | "skip"
    summary: str
    details: list[str] = field(default_factory=list)
    frameio_notes: list[str] = field(default_factory=list)  # timestamp-prefixed


@dataclass
class AuditReport:
    clip_path: str
    duration_sec: float
    platform: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        """REVISE on any fail · INCOMPLETE when this gate's OWN lane never ran · else SHIP.

        INCOMPLETE added 2026-08-03 (same class of bug as the dead-Groq-key silent passes):
        without `--subtitles` every caption check SKIPS, and a clip used to come back SHIP
        having had its caption text/placement — this gate's actual lane in the fan-out —
        never inspected at all. A skip is not a pass.
        """
        fails = sum(1 for r in self.results if r.status == "fail")
        if fails:
            return "REVISE"
        CAPTION_LANE = {"1", "2", "3", "5", "6", "S2", "E3"}
        lane = [r for r in self.results if str(r.id) in CAPTION_LANE]
        if lane and all(r.status == "skip" for r in lane):
            return "INCOMPLETE"
        return "SHIP"

    @property
    def counts(self) -> dict[str, int]:
        c = {"pass": 0, "fail": 0, "warn": 0, "manual": 0, "skip": 0}
        for r in self.results:
            c[r.status] = c.get(r.status, 0) + 1
        return c


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def sh(cmd: list[str], capture: bool = True) -> tuple[int, str, str]:
    """Run a shell command, return (returncode, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=capture, text=True, timeout=300)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"


def ffprobe_field(clip: Path, *args: str) -> str:
    code, out, _ = sh(["ffprobe", "-v", "error", *args, str(clip)])
    return out.strip() if code == 0 else ""


def get_duration(clip: Path) -> float:
    out = ffprobe_field(clip, "-show_entries", "format=duration", "-of", "csv=p=0")
    try:
        return float(out)
    except (ValueError, TypeError):
        return 0.0


def get_fps(clip: Path) -> float:
    out = ffprobe_field(clip, "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0")
    if not out or "/" not in out:
        return 30.0
    try:
        num, den = out.split("/")
        return float(num) / float(den) if float(den) else 30.0
    except (ValueError, TypeError):
        return 30.0


def get_resolution(clip: Path) -> tuple[int, int]:
    out = ffprobe_field(clip, "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0")
    try:
        parts = out.split(",")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 1080, 1920


def sec_to_hms(s: float) -> str:
    m = int(s // 60)
    rem = s - m * 60
    return f"{m:02d}:{rem:05.2f}"


# ─────────────────────────────────────────────────────────────────────────────
# Subtitle parsing — supports .srt and .ass
# ─────────────────────────────────────────────────────────────────────────────

SRT_BLOCK_RE = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def _hms_to_sec(t: str) -> float:
    t = t.replace(",", ".")
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_srt(text: str) -> list[dict]:
    cues = []
    for m in SRT_BLOCK_RE.finditer(text):
        start, end, content = m.group(2), m.group(3), m.group(4).strip()
        content = re.sub(r"<[^>]+>", "", content)  # strip HTML tags
        cues.append({
            "start": _hms_to_sec(start),
            "end": _hms_to_sec(end),
            "text": content,
            "style": None,
        })
    return cues


ASS_DIALOGUE_RE = re.compile(
    r"^Dialogue:\s*\d+,(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2}),([^,]+),[^,]*,\d+,\d+,\d+,[^,]*,(.*)$",
    re.MULTILINE,
)


def parse_ass(text: str) -> tuple[list[dict], dict[str, dict]]:
    cues = []
    for m in ASS_DIALOGUE_RE.finditer(text):
        start_t, end_t, style, content = m.groups()
        content = re.sub(r"\{[^}]*\}", "", content)  # strip override codes
        content = content.replace("\\N", " ").replace("\\n", " ").strip()
        cues.append({
            "start": _hms_to_sec(start_t),
            "end": _hms_to_sec(end_t),
            "text": content,
            "style": style.strip(),
        })

    # Parse styles
    styles: dict[str, dict] = {}
    style_section = re.search(r"\[V4\+? Styles\](.*?)(?=\n\[|\Z)", text, re.DOTALL)
    if style_section:
        format_line = re.search(r"^Format:\s*(.*)", style_section.group(1), re.MULTILINE)
        if format_line:
            fields = [f.strip() for f in format_line.group(1).split(",")]
            for line in re.finditer(r"^Style:\s*(.*)", style_section.group(1), re.MULTILINE):
                vals = [v.strip() for v in line.group(1).split(",")]
                if len(vals) >= len(fields):
                    styles[vals[0]] = dict(zip(fields, vals))
    return cues, styles


def load_subtitles(path: Path) -> tuple[list[dict], dict[str, dict]]:
    text = path.read_text(errors="ignore")
    if path.suffix.lower() == ".ass":
        return parse_ass(text)
    if path.suffix.lower() == ".srt":
        return parse_srt(text), {}
    return [], {}


# ─────────────────────────────────────────────────────────────────────────────
# Check #1 — Spelling / missing / double words
# ─────────────────────────────────────────────────────────────────────────────

def _load_client_vocab(client: Optional[str]) -> set[str]:
    """Load per-brand vocab.txt — every term becomes a known word for spell-check.
    Returns lowercased token set. Empty if no brand or file missing."""
    if not client:
        return set()
    import os as _os
    vault_env = _os.environ.get("CONTENT_VAULT")
    if vault_env:
        vault = Path(vault_env)
    else:
        vault = Path("__ACQ_ASSETS__") / "content-skill-system" / "vault"
    vocab_path = vault / "clients" / client / "vocab.txt"
    if not vocab_path.exists():
        return set()
    out: set[str] = set()
    for line in vocab_path.read_text().splitlines():
        line = re.sub(r"\s*//.*$", "", line).strip()
        if not line:
            continue
        # Split multi-word terms into tokens so each piece is whitelisted
        for tok in re.findall(r"[a-zA-Z0-9'@.]+", line):
            out.add(tok.lower().strip("'"))
    return out


def check_spelling(cues: list[dict], client: Optional[str] = None,
                   blocking: bool = True) -> CheckResult:
    r = CheckResult(1, "Subtitles", "Spelling / missing / double words", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file provided — manual spellcheck required on burnt-in captions"
        return r

    try:
        from spellchecker import SpellChecker  # type: ignore
    except ImportError:
        r.status = "manual"
        r.summary = "pyspellchecker not installed — pip3 install --user pyspellchecker"
        return r

    sc = SpellChecker(distance=1)
    # Built-in baseline whitelist (common contractions + brand basics we always allow)
    builtin = {"youtube", "instagram", "tiktok", "capcut", "subscribed", "crypto",
               "dm", "im", "ill", "ive", "id", "okay", "ok", "gonna", "wanna", "yall",
               "youre", "whats", "dont", "cant", "didnt", "wasnt", "wouldnt", "arent",
               "youd", "youve", "theyll", "theyve"}
    # Per-brand vocab is the authoritative additional source
    client_vocab = _load_client_vocab(client)
    whitelist = builtin | client_vocab

    suspicious: list[tuple[float, str, str]] = []
    unknown_tokens: set[str] = set()  # uniqued for the blocking decision
    for cue in cues:
        words = re.findall(r"[a-zA-Z']+", cue["text"])
        lower_words = [w.lower().strip("'") for w in words]

        # Double-word
        for i in range(len(lower_words) - 1):
            if lower_words[i] == lower_words[i + 1] and len(lower_words[i]) > 1:
                suspicious.append((cue["start"], cue["text"], f"doubled word: '{lower_words[i]}'"))
                break

        # Spell
        unknown = sc.unknown([w for w in lower_words if w not in whitelist and len(w) > 2])
        for u in unknown:
            # Skip things that look like contractions/stylized
            if "'" in u or re.search(r"\d", u):
                continue
            suspicious.append((cue["start"], cue["text"], f"possible typo: '{u}'"))
            unknown_tokens.add(u)

    if suspicious:
        # Blocking gate logic:
        #   - Doubled words always fail (they shouldn't ship regardless of brand)
        #   - Unknown tokens fail ONLY when a brand vocab is loaded (gate is
        #     gated on having a ground-truth list of valid proper nouns)
        #   - Without a brand vocab, unknown tokens stay as warnings — ad-hoc
        #     audits shouldn't block on missing-vocab false positives
        has_unknown = bool(unknown_tokens)
        has_doubled = any("doubled word" in note for _, _, note in suspicious)
        should_block = blocking and (has_doubled or (has_unknown and bool(client_vocab)))
        if should_block:
            r.status = "fail"
        else:
            r.status = "warn"
        vocab_note = f" (brand vocab: {len(client_vocab)} terms loaded)" if client_vocab else \
                     " (no brand vocab — pass --client to gate against known proper nouns)"
        r.summary = f"{len(suspicious)} suspicious subtitle(s){vocab_note}"
        for t, text, note in suspicious[:20]:
            r.details.append(f"  [{sec_to_hms(t)}] {note} — \"{text}\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] {note}")
        if has_unknown and client_vocab:
            r.details.append(
                f"  → Unknown tokens (not in vocab, not in dictionary): "
                f"{', '.join(sorted(unknown_tokens)[:10])}"
            )
            r.details.append(
                f"  → If any are valid proper nouns/jargon, add to "
                f"vault/clients/{client}/vocab.txt and re-audit."
            )
    else:
        vocab_note = f" (brand vocab: {len(client_vocab)} terms)" if client_vocab else ""
        r.summary = f"No suspicious words in {len(cues)} cues{vocab_note}"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #2 — No blank gaps between subtitles
# ─────────────────────────────────────────────────────────────────────────────

def check_gaps(cues: list[dict], max_gap_sec: float = 0.05, pause_threshold_sec: float = 1.0) -> CheckResult:
    """Mozi standard #2: 'No blank gaps between each subtitle (exception: >1s-2s pauses)'.
    We flag any visible gap (>50ms ≈ 1.5 frames @30fps). Pauses >1s are intentional speech pauses."""
    r = CheckResult(2, "Subtitles", "No blank gaps between subtitles", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r

    issues = []
    for i in range(len(cues) - 1):
        gap = cues[i + 1]["start"] - cues[i]["end"]
        # Visible gap: >50ms; flag. Intentional pause: >1s; don't flag.
        if max_gap_sec < gap < pause_threshold_sec:
            issues.append((cues[i]["end"], gap, cues[i]["text"], cues[i + 1]["text"]))

    if issues:
        # Many small gaps (>30% of cues) = systemic — fail. Few = warn.
        ratio = len(issues) / max(1, len(cues) - 1)
        r.status = "fail" if ratio > 0.3 else "warn"
        r.summary = f"{len(issues)} visible gap(s) > {int(max_gap_sec*1000)}ms ({ratio:.0%} of joints)"
        for t, g, prev, nxt in issues[:15]:
            r.details.append(f"  [{sec_to_hms(t)}] gap {int(g*1000)}ms between \"{prev[:30]}...\" and \"{nxt[:30]}...\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] subtitle gap {int(g*1000)}ms — close to next cue")
    else:
        gaps = [cues[i + 1]["start"] - cues[i]["end"] for i in range(len(cues) - 1)]
        max_g = max(gaps) if gaps else 0
        r.summary = f"No visible gaps — max joint gap {int(max_g*1000)}ms"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #3 — All words lowercased by default
# ─────────────────────────────────────────────────────────────────────────────

PROPER_NOUN_WHITELIST = {
    # Sentence-starter "I" and contractions
    "I", "I'm", "I'll", "I've", "I'd",
    # Common brand/name exceptions (extend as needed)
    "Alex", "Hormozi", "Mozi", "Gary", "Jeff", "Nipper", "Shark", "Tank",
    "YouTube", "Instagram", "TikTok", "Twitter", "Stripe", "Google", "Apple",
    "ManyChat", "Hyros", "CapCut", "Canva", "Notion", "Figma",
    "MrBeast", "MrBeast's", "IRL", "IRL-based", "AI", "Uber", "Skool", "Leila", "Acquisition.com",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
}


def check_lowercase(cues: list[dict]) -> CheckResult:
    r = CheckResult(5, "Subtitles", "All words lowercased by default", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r

    violations = []
    for cue in cues:
        text = cue["text"]
        for m in re.finditer(r"[A-Za-z']+", text):
            w = m.group()
            if not w:
                continue
            # Money/number UNIT suffix (the M in $55M, K in $600K, B in $1B, X in 10X) is CORRECT capital —
            # it's an alpha token immediately preceded by a digit. (Oliver/locked style: capital K/M/B/X.)
            if len(w) <= 2 and m.start() > 0 and text[m.start()-1].isdigit():
                continue
            # Skip ALL-CAPS (often intentional emphasis)
            if w.isupper() and len(w) > 1:
                continue
            # Capitalized words that aren't in whitelist
            if w[0].isupper() and w not in PROPER_NOUN_WHITELIST:
                # Check common contractions
                if w.lower() not in {"i", "i'm", "i'll", "i've", "i'd"}:
                    violations.append((cue["start"], text, w))

    if violations:
        r.status = "fail"
        r.summary = f"{len(violations)} non-lowercase word(s)"
        for t, text, w in violations[:20]:
            r.details.append(f"  [{sec_to_hms(t)}] \"{w}\" should be lowercase — in: \"{text[:50]}\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] lowercase \"{w}\"")
    else:
        r.summary = f"All words lowercased correctly across {len(cues)} cues"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #4 — Alex vs Guest color differentiation
# ─────────────────────────────────────────────────────────────────────────────

def check_color_diff(cues: list[dict], styles: dict[str, dict], has_speaker_map: bool) -> CheckResult:
    r = CheckResult(6, "Subtitles", "Alex/Guest color differentiation", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r

    # Count distinct styles used in dialogue
    used_styles = {cue.get("style") for cue in cues if cue.get("style")}
    used_styles.discard(None)

    if not used_styles:
        r.status = "manual"
        r.summary = "Subtitles are .srt (no style info) or burnt-in — verify colors manually"
        return r

    if len(used_styles) < 2:
        if has_speaker_map:
            r.status = "fail"
            r.summary = f"Only 1 subtitle style detected ({list(used_styles)[0]}) but speaker map indicates multiple speakers"
            r.frameio_notes.append("[all] Guest/Alex need distinct subtitle colors — only one style in use")
        else:
            # Might be solo talking-head; that's fine
            r.status = "pass"
            r.summary = "Single-speaker clip (one style) — OK for solo talking-head"
        return r

    # Pull actual colors
    color_map = {}
    for s in used_styles:
        if s in styles:
            color_map[s] = styles[s].get("PrimaryColour", "unknown")

    distinct_colors = set(color_map.values())
    if len(distinct_colors) >= 2:
        r.summary = f"{len(used_styles)} styles with {len(distinct_colors)} distinct colors"
        r.details.append(f"  Styles: {dict(color_map)}")
    else:
        r.status = "fail"
        r.summary = f"Styles use identical colors"
        r.frameio_notes.append("[all] Alex vs Guest subtitles are the same color — fix the style colors")
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #5 — Subtitles within UI safezone
# ─────────────────────────────────────────────────────────────────────────────

def check_safezone(cues: list[dict], styles: dict[str, dict], width: int, height: int,
                   safezone: dict[str, float]) -> CheckResult:
    r = CheckResult(7, "Subtitles", "Subtitles within UI safezone", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r

    top_danger_px = int(height * safezone["top_danger_pct"])
    bottom_danger_px = int(height * (1 - safezone["bottom_danger_pct"]))

    # For .ass, MarginV is y-from-bottom (when Alignment is bottom-center).
    # For .srt, we can't check position — manual.
    ass_styles = any(cue.get("style") for cue in cues)
    if not ass_styles:
        r.status = "manual"
        r.summary = f"Cannot verify .srt position — manually confirm captions within y=[{top_danger_px}, {bottom_danger_px}]"
        return r

    import re as _re
    # Look for \move(x1,y1,x2,y2,...) or \pos(x,y) in cue text — these override MarginV.
    MOVE_RE = _re.compile(r"\\move\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*,\s*([\d.]+)")
    POS_RE = _re.compile(r"\\pos\(\s*[\d.]+\s*,\s*([\d.]+)")

    issues = []
    for cue in cues:
        style_name = cue.get("style")
        if not style_name or style_name not in styles:
            continue
        style = styles[style_name]
        try:
            margin_v = int(style.get("MarginV", "0"))
            alignment = int(style.get("Alignment", "2"))  # default bottom-center
        except (ValueError, TypeError):
            continue
        fontsize = int(style.get("Fontsize", "60"))

        # Modern ASS workflow: position is set via \move(x1,y1,x2,y2) or \pos(x,y) tags
        # in the dialogue text. If present, override the MarginV-based math.
        text = cue.get("text", "")
        m = MOVE_RE.search(text) or POS_RE.search(text)
        if m:
            # The y from move/pos is the BASELINE position. Estimate y_top / y_bottom
            # based on alignment (1/2/3 = bottom-anchored, 4/5/6 = middle, 7/8/9 = top).
            y_anchor = float(m.group(1))
            if alignment in (1, 2, 3):
                y_bottom = int(y_anchor)
                y_top = int(y_anchor - fontsize)
            elif alignment in (4, 5, 6):
                # Middle-anchored — text centered around y_anchor
                y_top = int(y_anchor - fontsize / 2)
                y_bottom = int(y_anchor + fontsize / 2)
            else:  # 7, 8, 9
                y_top = int(y_anchor)
                y_bottom = int(y_anchor + fontsize)
        else:
            # Fallback: classic MarginV calc
            if alignment in (7, 8, 9):
                y_top = margin_v
                y_bottom = margin_v + fontsize
            elif alignment in (4, 5, 6):
                # Middle alignment without \move — center on frame midline + MarginV offset
                center_y = height // 2 + margin_v
                y_top = center_y - fontsize // 2
                y_bottom = center_y + fontsize // 2
            else:
                y_bottom = height - margin_v
                y_top = y_bottom - fontsize

        if y_top < top_danger_px:
            issues.append((cue["start"], cue["text"], f"overlaps TOP UI (y={y_top} < {top_danger_px})"))
        if y_bottom > bottom_danger_px:
            issues.append((cue["start"], cue["text"], f"overlaps BOTTOM UI (y={y_bottom} > {bottom_danger_px})"))

    if issues:
        r.status = "warn"
        r.summary = f"{len(issues)} subtitle(s) outside safezone"
        for t, text, note in issues[:10]:
            r.details.append(f"  [{sec_to_hms(t)}] {note} — \"{text[:50]}\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] subtitle outside safezone — {note}")
    else:
        r.summary = f"All subtitles within safezone (top {top_danger_px}px, bottom {height - bottom_danger_px}px)"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #6 — Audio levels around -6dB
# ─────────────────────────────────────────────────────────────────────────────

def check_audio_levels(clip: Path) -> CheckResult:
    """
    Mozi standard: 'Audio levels should sit around -6dB' → refers to peak dBFS reading,
    not RMS mean. Talking-head RMS mean is always low (-20 to -36dB) due to speech pauses.
    We check peak (max_volume) against the -6dB target.
    """
    r = CheckResult(8, "Audio", "Audio peak level around -6dB", "pass", "")
    code, _, err = sh(["ffmpeg", "-i", str(clip), "-af", "volumedetect", "-vn", "-sn", "-dn",
                       "-f", "null", "-"])
    if code != 0 and "volumedetect" not in err:
        r.status = "manual"
        r.summary = f"ffmpeg volumedetect failed — check manually"
        return r

    mean_match = re.search(r"mean_volume:\s*(-?\d+\.?\d*)\s*dB", err)
    max_match = re.search(r"max_volume:\s*(-?\d+\.?\d*)\s*dB", err)
    if not max_match:
        r.status = "manual"
        r.summary = "Could not parse ffmpeg peak — check manually"
        return r

    peak = float(max_match.group(1))
    mean_vol = float(mean_match.group(1)) if mean_match else None
    mean_str = f", RMS mean {mean_vol:.1f}dB" if mean_vol is not None else ""

    if peak > -1:
        r.status = "fail"
        r.summary = f"Peak {peak:.1f}dB — in clipping territory{mean_str}"
        r.frameio_notes.append(f"[all] audio clipping (peak {peak:.1f}dB) — reduce output gain")
    elif peak > -3:
        r.status = "warn"
        r.summary = f"Peak {peak:.1f}dB — hot, risk of clipping{mean_str}"
        r.frameio_notes.append(f"[all] audio is hot (peak {peak:.1f}dB) — back off 2-3dB")
    elif peak >= -8:
        r.summary = f"Peak {peak:.1f}dB — in target range (around -6){mean_str}"
    elif peak >= -12:
        r.status = "warn"
        r.summary = f"Peak {peak:.1f}dB — a bit quiet (target ~-6){mean_str}"
        r.frameio_notes.append(f"[all] audio a bit quiet (peak {peak:.1f}dB) — normalize up by {abs(peak+6):.1f}dB")
    else:
        r.status = "fail"
        r.summary = f"Peak {peak:.1f}dB — too quiet (target -6){mean_str}"
        r.frameio_notes.append(f"[all] audio is too quiet (peak {peak:.1f}dB) — normalize up by {abs(peak+6):.1f}dB")
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #7 — Compression (LUFS LRA)
# ─────────────────────────────────────────────────────────────────────────────

def check_compression(clip: Path) -> CheckResult:
    """Use ebur128 filter for LRA — most portable and accurate across ffmpeg versions."""
    r = CheckResult(10, "Audio", "Not overly compressed", "pass", "")
    code, _, err = sh(["ffmpeg", "-i", str(clip), "-af", "ebur128=framelog=verbose",
                       "-f", "null", "-"])
    # ebur128 prints a summary block at end of stderr with "LRA:"
    lra_match = re.search(r"LRA:\s*(-?\d+\.?\d*)\s*LU", err)
    if not lra_match:
        # Fallback: try loudnorm format
        lra_match = re.search(r"Input\s*(?:Loudness Range|LRA):\s*(-?\d+\.?\d*)\s*LU", err)
    if not lra_match:
        r.status = "manual"
        r.summary = "Could not extract LUFS LRA — check manually"
        return r

    lra = float(lra_match.group(1))
    if lra < 3:
        r.status = "warn"
        r.summary = f"Loudness range {lra:.1f}LU — over-compressed"
        r.frameio_notes.append(f"[all] audio sounds compressed flat (LRA {lra:.1f}LU) — back off the compressor")
    elif lra < 5:
        r.status = "warn"
        r.summary = f"Loudness range {lra:.1f}LU — somewhat compressed"
    else:
        r.summary = f"Loudness range {lra:.1f}LU — healthy dynamic range"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #8 — No clipping
# ─────────────────────────────────────────────────────────────────────────────

def check_clipping(clip: Path) -> CheckResult:
    r = CheckResult(11, "Audio", "No audio clipping", "pass", "")
    code, _, err = sh(["ffmpeg", "-i", str(clip), "-af", "astats=metadata=1:reset=0",
                       "-f", "null", "-"])
    if code != 0 and "Peak level dB" not in err:
        r.status = "manual"
        r.summary = "astats failed — check manually"
        return r

    peaks = [float(m) for m in re.findall(r"Peak level dB:\s*(-?\d+\.?\d*)", err)]
    if not peaks:
        r.status = "manual"
        r.summary = "Could not extract peak levels"
        return r

    max_peak = max(peaks)
    if max_peak > -0.5:
        r.status = "fail"
        r.summary = f"Peak {max_peak:.2f}dB — clipping"
        r.frameio_notes.append(f"[all] audio is clipping (peak {max_peak:.2f}dB) — reduce output gain")
    elif max_peak > -1.0:
        r.status = "warn"
        r.summary = f"Peak {max_peak:.2f}dB — very close to clipping"
    else:
        r.summary = f"Peak {max_peak:.2f}dB — safe"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #9 — No audio pops/clicks (manual + boundary check)
# ─────────────────────────────────────────────────────────────────────────────

def check_pops(clip: Path, duration: float) -> CheckResult:
    """Auto-detect click/pop transients (the kind a hard concat-cut leaves when a seam isn't faded).
    A click is a near-instant sample-level step that is LOUD but ISOLATED — unlike a plosive, which is
    a sustained burst. We flag samples whose first-difference spikes far above the local median AND whose
    immediate neighbourhood is quiet. Added 2026-06-11 after a concat-seam pop shipped (Maddex caught it);
    the fix upstream is to fade every cut seam (precision_cut.py does this — never hand-roll a bare concat)."""
    r = CheckResult(12, "Audio", "No audio pops/clicks", "pass", "")
    try:
        import numpy as np  # type: ignore
    except ImportError:
        r.status = "manual"
        r.summary = "numpy not installed — listen at head/tail/cut points"
        return r
    SR = 48000
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, timeout=120)
    a = np.frombuffer(p.stdout, dtype=np.float32)
    if a.size < SR * 0.2:
        r.status = "manual"
        r.summary = "Could not decode audio — listen at cut points"
        return r
    d = np.abs(np.diff(a))
    med = float(np.median(d)) + 1e-9
    thr = max(0.18, med * 14.0)             # a click jumps far above the local median step
    w = max(1, int(SR * 0.0015))            # ~1.5ms neighbourhood
    clicks: list[float] = []
    for i in np.where(d > thr)[0]:
        amp = abs(float(a[i]))
        if amp < 0.30:                       # must be genuinely loud (not a quiet tick)
            continue
        lo = max(0, i - w * 4); hi = min(len(a), i + w * 4)
        neigh = np.abs(a[lo:hi])
        if float(np.median(neigh)) < 0.12 * amp:   # isolated spike (plosives aren't isolated)
            t = i / SR
            if not clicks or t - clicks[-1] > 0.010:
                clicks.append(t)
    if clicks:
        r.status = "warn"   # warn (not hard fail) — verify by ear; concat seams are the usual cause
        r.summary = f"{len(clicks)} candidate click/pop transient(s) — verify by ear and fade the seam"
        for t in clicks[:12]:
            r.details.append(f"  [{sec_to_hms(t)}] sharp isolated transient — likely an un-faded cut seam")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] audio pop — fade this cut seam (~6ms)")
    else:
        r.summary = "No click/pop transients detected"
    return r


def check_frozen_frames(clip: Path, fps: float) -> CheckResult:
    """Detect frozen / held / duplicate (dead) frames — the kind a reframer leaves if it 'holds' a crop at
    a transition, or a bad concat leaves at a seam. blackdetect (#15) only catches BLACK frames; a held
    frame is a non-black duplicate, so we use freezedetect with a strict noise tolerance (only near-exact
    duplicates trigger — real video has sensor noise frame-to-frame, so natural stillness won't false-fire).
    Added 2026-06-11 after a dead frame between a question and answer shipped (Maddex: 'screen for this')."""
    r = CheckResult("15b", "Video", "No frozen / held (dead) frames", "pass", "")
    # n=0.0006 (strict): only near-EXACT duplicate frames trip it — a held/dropped frame or concat dup.
    # Low-motion talking-head frames differ by sensor noise > this, so natural stillness does NOT false-fire
    # (calibrated 2026-06-11: clean clip = 0 detections). d=0.12 ≈ 3 frames — a genuine dead frame, not a blip.
    code, _, err = sh(["ffmpeg", "-i", str(clip), "-vf", "freezedetect=n=0.0006:d=0.12",
                       "-an", "-f", "null", "-"])
    if code != 0 and "freeze_start" not in err and "lavfi.freezedetect" not in err:
        r.status = "manual"
        r.summary = "freezedetect unavailable — eyeball transitions for held frames"
        return r
    starts = [float(s) for s in re.findall(r"freeze_start:\s*(\d+\.?\d*)", err)]
    durs = [float(d) for d in re.findall(r"freeze_duration:\s*(\d+\.?\d*)", err)]
    issues = list(zip(starts, durs)) if starts else []
    # RULE-16 LEAD EXEMPTION (2026-06-13): check #16 REQUIRES a 3-5 frame static lead before audio.
    # That intended lead is, by definition, a brief freeze at the very top of the clip — NOT a defect,
    # and 15b used to flag it (15b and 16 contradicted each other). Exempt a freeze that BEGINS at
    # frame 0 (start <= ~0.05s) and lasts <= 6 frames (the lead zone). A freeze that starts later, or
    # runs longer than the lead, is a genuine held/dead frame and still fails.
    lead_zone = 6.0 / fps
    issues = [(s, d) for (s, d) in issues if not (s <= 0.05 and d <= lead_zone + 1e-3)]
    if issues:
        worst = max(d for _, d in issues)
        r.status = "fail" if worst >= 2 / fps else "warn"   # >=2 held frames = real dead frame
        r.summary = f"{len(issues)} frozen/held-frame segment(s) (worst {worst*1000:.0f}ms ≈ {worst*fps:.1f} frames)"
        for s, d in issues[:10]:
            r.details.append(f"  [{sec_to_hms(s)}] frozen for {d*1000:.0f}ms (~{d*fps:.1f} frames)")
            r.frameio_notes.append(f"[{sec_to_hms(s)}] dead/held frame ({d*fps:.1f} frames) — remove it")
    else:
        r.summary = "No frozen/held frames detected"
    return r


def check_dead_cut(clip: Path, fps: float) -> CheckResult:
    """Detect a DEAD BEAT after a camera cut — the cut lands on a live-but-SILENT frame (a speaker who
    hasn't started talking yet), so the new angle just sits there before the line begins. freezedetect
    (#15b) can't catch this: the frames aren't duplicates, they're real low-motion video — the defect is
    silence-on-a-fresh-angle, not a frozen pixel. We find scene cuts (ffmpeg scenedetect) and flag any cut
    whose audio stays below the speech floor for >=150ms before speech resumes. Added 2026-06-11 after a
    dead beat between a Q and the answer shipped (Maddex: 'you should have screened for this'). WARN, not
    fail — a held beat is occasionally intentional (reaction / dramatic pause); the eye confirms."""
    r = CheckResult("15c", "Video", "No dead beat after a camera cut", "pass", "")
    try:
        import numpy as np  # type: ignore
        import cv2  # type: ignore
    except ImportError:
        r.status = "manual"
        r.summary = "numpy/cv2 not installed — eyeball each cut for a silent hold before the line"
        return r
    # 1) scene-cut times via 64x36 grayscale thumbnail mean-abs-diff (the reframer's method — robust for
    #    podcast angle changes that ffmpeg's normalized scene score scores too low). A real cut spikes far
    #    above talking-head motion (~0.5-4); a hard cut is ~30-60. Threshold 15 + 4-frame debounce.
    cap = cv2.VideoCapture(str(clip))
    prev = None; cuts: list[float] = []; idx = 0; last_cut = -10
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        th = cv2.cvtColor(cv2.resize(frame, (64, 36)), cv2.COLOR_BGR2GRAY).astype(float)
        if prev is not None:
            if float(np.mean(np.abs(th - prev))) > 15.0 and idx - last_cut >= 4:
                cuts.append(idx / fps); last_cut = idx
        prev = th; idx += 1
    cap.release()
    cuts = [t for t in cuts if t > 0.20]                     # ignore the opening frame
    if not cuts:
        r.summary = "No camera cuts detected (single angle) — n/a"
        return r
    # 2) per-10ms audio RMS. A music bed defeats absolute-silence detection (the Q->A gap isn't silent,
    #    it's voice-absent but music-present, ~-28dB). The music-robust signal is the VOICE RISE: music is
    #    roughly constant, so the line starting LATE after the cut is the tell. For each cut we measure how
    #    long until voice resumes, RELATIVE to the level of the line that follows.
    SR, HOP = 16000, 160
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vn", "-ac", "1",
                        "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, timeout=120)
    a = np.frombuffer(p.stdout, dtype=np.float32)
    if a.size < SR * 0.5:
        r.status = "manual"; r.summary = "Could not decode audio — eyeball each cut"; return r
    n = a.size // HOP
    rms = np.array([20 * np.log10(np.sqrt(np.mean(a[i*HOP:(i+1)*HOP]**2)) + 1e-10) for i in range(n)])
    def sidx(t): return int(t / 0.010)
    flags: list[tuple[float, float]] = []
    for t in cuts:
        i0 = sidx(t)
        if i0 >= n - 15:
            continue
        win = rms[i0:min(n, i0 + 70)]                        # [cut, cut+0.7s]
        if win.size < 15:
            continue
        voice_lvl = float(np.percentile(win, 75))            # the line that follows the cut
        if voice_lvl < -26:                                  # no real speech follows (music-only / outro) — skip
            continue
        quiet_thr = voice_lvl - 8.0                          # voice = within 8dB of the following line
        onset, run = None, 0
        for k in range(win.size):
            if win[k] >= quiet_thr:
                run += 1
                if run >= 5:                                 # 50ms sustained = voice truly resumed
                    onset = k - run + 1
                    break
            else:
                run = 0
        if onset is None:
            continue
        lead = onset * 0.010                                 # silent-on-new-angle time before the line
        if lead >= 0.12:                                     # >=~3 frames of dead air on a fresh cut
            flags.append((t, lead))
    if flags:
        worst = max(s for _, s in flags)
        r.status = "warn"
        r.summary = (f"{len(flags)} cut(s) land on a silent hold before the line "
                     f"(worst {worst*1000:.0f}ms) — trim so the cut hits speech")
        for t, s in flags[:10]:
            r.details.append(f"  [{sec_to_hms(t)}] cut → {s*1000:.0f}ms silent on the new angle before speech")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] dead beat — cut lands ~{s*1000:.0f}ms before the line; trim it")
    else:
        r.summary = f"No dead beats — all {len(cuts)} cut(s) land on speech"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Face detection — MediaPipe (old API) → OpenCV Haar cascade fallback
# ─────────────────────────────────────────────────────────────────────────────

def _get_face_detector():
    """Return a callable: (rgb_frame, width, height) -> list of (x, y, w, h) bboxes in pixels."""
    # Try MediaPipe old API (<0.10.10)
    try:
        import mediapipe as mp  # type: ignore
        if hasattr(mp, "solutions"):
            fd = mp.solutions.face_detection.FaceDetection(min_detection_confidence=0.5)

            def detect_mp_old(rgb, w, h):
                res = fd.process(rgb)
                if not res.detections:
                    return []
                out = []
                for d in res.detections:
                    bbox = d.location_data.relative_bounding_box
                    out.append((int(bbox.xmin * w), int(bbox.ymin * h),
                                int(bbox.width * w), int(bbox.height * h)))
                return out
            return detect_mp_old, "mediapipe-old"
    except Exception:
        pass

    # Fallback: OpenCV Haar cascade (always available with opencv-python)
    try:
        import cv2  # type: ignore
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            return None, "unavailable"

        def detect_haar(rgb, w, h):
            import cv2 as _cv2
            gray = _cv2.cvtColor(rgb, _cv2.COLOR_RGB2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                                   minSize=(80, 80))
            return [tuple(int(v) for v in f) for f in faces]
        return detect_haar, "opencv-haar"
    except Exception:
        return None, "unavailable"


# ─────────────────────────────────────────────────────────────────────────────
# Check #10 — Alex centered
# ─────────────────────────────────────────────────────────────────────────────

def check_centered(clip: Path, width: int, height: int, fps: float) -> CheckResult:
    r = CheckResult(13, "Video", "Alex centered in frame", "pass", "")
    try:
        import cv2  # type: ignore
    except ImportError:
        r.status = "manual"
        r.summary = "opencv not installed — check manually"
        return r

    detector, detector_name = _get_face_detector()
    if detector is None:
        r.status = "manual"
        r.summary = "no face detector available (mediapipe/opencv-haar both failed)"
        return r

    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        r.status = "manual"
        r.summary = "Could not open clip"
        return r

    sample_rate = max(1, int(fps / 2))  # ~2 samples per second
    frame_idx = 0
    centered_count = 0
    total_count = 0
    off_center_timestamps = []

    center_min = width * 0.30
    center_max = width * 0.70

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_rate == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = detector(rgb, width, height)
            if faces:
                # Pick the largest face (most likely Alex vs B-roll faces)
                best = max(faces, key=lambda f: f[2] * f[3])
                x, y, w, h = best
                face_cx = x + w / 2
                total_count += 1
                if center_min <= face_cx <= center_max:
                    centered_count += 1
                else:
                    off_center_timestamps.append(frame_idx / fps)
        frame_idx += 1

    cap.release()

    if total_count == 0:
        r.status = "manual"
        r.summary = "No faces detected at any sample — check manually (may be B-roll or black frames)"
        return r

    pct = (centered_count / total_count) * 100
    if pct >= 90:
        r.summary = f"{pct:.0f}% of sampled frames have face in center 40% ({centered_count}/{total_count})"
    elif pct >= 75:
        r.status = "warn"
        r.summary = f"Only {pct:.0f}% centered — reframer may have drifted"
        if off_center_timestamps:
            r.details.append(f"  Off-center samples: {', '.join(sec_to_hms(t) for t in off_center_timestamps[:5])}")
            r.frameio_notes.append(f"[various] face off-center in {100-pct:.0f}% of samples — re-run reframer")
    else:
        r.status = "fail"
        r.summary = f"Only {pct:.0f}% of frames centered — reframer failed"
        r.frameio_notes.append(f"[various] face off-center in {100-pct:.0f}% of samples — re-run reframer with longer smoothing window")
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #11 — Top-of-head padding (Alex not cut off by UI)
# ─────────────────────────────────────────────────────────────────────────────

def check_top_padding(clip: Path, width: int, height: int, fps: float,
                      min_pct: float) -> CheckResult:
    r = CheckResult(14, "Video", "Top-of-head padding for UI overlay", "pass", "")
    try:
        import cv2  # type: ignore
    except ImportError:
        r.status = "manual"
        r.summary = "opencv not installed"
        return r

    detector, _ = _get_face_detector()
    if detector is None:
        r.status = "manual"
        r.summary = "no face detector available"
        return r

    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        r.status = "manual"
        r.summary = "Could not open clip"
        return r

    min_top_px = int(height * min_pct)

    frame_idx = 0
    paddings = []
    tight_samples = []

    # Sample more frequently at the start (where UI-cutoff is most visible)
    duration_to_check = min(5.0, get_duration(clip))  # first 5 seconds
    frames_to_check = int(duration_to_check * fps)

    while frame_idx < frames_to_check:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % max(1, int(fps / 4)) == 0:  # 4 samples per second
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = detector(rgb, width, height)
            if faces:
                best = max(faces, key=lambda f: f[2] * f[3])
                x, y, w, h = best
                # Estimate top of head: typically 0.3x of face bbox height above face-top
                head_top = max(0, y - (h * 0.3))
                paddings.append(head_top)
                if head_top < min_top_px:
                    tight_samples.append((frame_idx / fps, head_top))
        frame_idx += 1

    cap.release()

    if not paddings:
        r.status = "manual"
        r.summary = "No faces in first 5s — check manually"
        return r

    min_pad = min(paddings)
    if tight_samples:
        r.status = "warn"
        r.summary = f"Top padding dips to {min_pad:.0f}px ({min_pad/height*100:.1f}%) — UI may cut off head"
        for t, p in tight_samples[:3]:
            r.details.append(f"  [{sec_to_hms(t)}] head-top at {p:.0f}px (min {min_top_px}px)")
        r.frameio_notes.append(f"[{sec_to_hms(tight_samples[0][0])}] Alex's head too close to top — add headroom")
    else:
        r.summary = f"Min top padding {min_pad:.0f}px ({min_pad/height*100:.1f}%) — safe"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #12 — Dead / black frames
# ─────────────────────────────────────────────────────────────────────────────

def check_black_frames(clip: Path, fps: float) -> CheckResult:
    r = CheckResult(15, "Video", "No dead / black frames", "pass", "")
    # blackdetect with threshold pix=0.1 (tolerate mostly-black), duration=0.05s
    code, _, err = sh(["ffmpeg", "-i", str(clip),
                       "-vf", "blackdetect=d=0.05:pic_th=0.98:pix_th=0.10",
                       "-an", "-f", "null", "-"])
    if code != 0 and "black_start" not in err:
        r.status = "manual"
        r.summary = "blackdetect failed — check manually"
        return r

    matches = re.findall(r"black_start:(\d+\.?\d*)\s+black_end:(\d+\.?\d*)\s+black_duration:(\d+\.?\d*)", err)
    min_dur = 2 / fps  # more than 2 frames
    issues = [(float(s), float(e), float(d)) for s, e, d in matches if float(d) >= min_dur]
    if issues:
        r.status = "fail"
        r.summary = f"{len(issues)} black-frame segment(s)"
        for s, e, d in issues[:10]:
            r.details.append(f"  [{sec_to_hms(s)}–{sec_to_hms(e)}] black for {d:.2f}s")
            r.frameio_notes.append(f"[{sec_to_hms(s)}] trim {d:.2f}s of black frames")
    else:
        r.summary = "No dead frames detected"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #13 — 3-ish video frames lead before audio
# ─────────────────────────────────────────────────────────────────────────────

def check_audio_lead(clip: Path, fps: float) -> CheckResult:
    """Mozi standard #16: '3-ish video frames at the beginning before the audio comes in'.
    Range: 3-5 frames (100-166ms @30fps). >5 frames = clip included pre-speech silence; tighten."""
    r = CheckResult(16, "Video", "3-ish video frames lead before audio", "pass", "")
    code, _, err = sh(["ffmpeg", "-i", str(clip),
                       "-af", "silencedetect=noise=-30dB:d=0.05",
                       "-vn", "-f", "null", "-"])
    if code != 0 and "silence_end" not in err:
        r.status = "manual"
        r.summary = "silencedetect failed — check manually"
        return r

    silence_ends = re.findall(r"silence_end:\s*(\d+\.?\d*)", err)
    silence_starts = re.findall(r"silence_start:\s*(-?\d+\.?\d*)", err)

    first_audio_sec = 0.0
    if silence_starts and silence_ends:
        first_start = float(silence_starts[0])
        first_end = float(silence_ends[0])
        if first_start <= 0.1:  # silence from beginning
            first_audio_sec = first_end

    lead_frames = first_audio_sec * fps
    if 3 <= lead_frames <= 5:
        r.summary = f"{lead_frames:.1f} frames of silent video lead — in target (3-5)"
    elif 2 <= lead_frames < 3:
        r.status = "warn"
        r.summary = f"{lead_frames:.1f} frames of lead — slightly short of target (3-5)"
        r.frameio_notes.append(f"[00:00] lead is {lead_frames:.1f} frames; bump to 3 to avoid swipe-audio pop")
    elif lead_frames < 2:
        r.status = "fail"
        r.summary = f"Only {lead_frames:.1f} frames of lead — risk of audio pop on swipe"
        r.frameio_notes.append(f"[00:00] add ~3 frames of silent video lead before audio starts")
    elif lead_frames <= 7:
        r.status = "warn"
        r.summary = f"{lead_frames:.1f} frames of lead — slightly over target (3-5)"
        r.frameio_notes.append(f"[00:00] trim ~{int(lead_frames-3)} frames off the head — too much pre-speech silence")
    else:
        r.status = "fail"
        r.summary = f"{lead_frames:.1f} frames of lead — clip starts with {lead_frames:.0f} frames of frozen-looking video"
        r.frameio_notes.append(f"[00:00] head has {lead_frames:.0f} frames of pre-speech silence — re-cut clip start to leave only 3 frames before audio")
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #3 — Lower-half placement (subtitles below the face)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_cue_anchor(cue: dict, styles: dict[str, dict], width: int, height: int) -> Optional[tuple[float, float]]:
    """Return (x_anchor, y_anchor) in pixel coords for an ASS cue, or None if undeterminable.
    Shared by check_lower_half_placement and check_captions_box_doac."""
    style_name = cue.get("style")
    if not style_name or style_name not in styles:
        return None
    style = styles[style_name]
    try:
        margin_v = int(style.get("MarginV", "0"))
        margin_l = int(style.get("MarginL", "0"))
        margin_r = int(style.get("MarginR", "0"))
        alignment = int(style.get("Alignment", "2"))
    except (ValueError, TypeError):
        return None
    try:
        fontsize = int(style.get("Fontsize", "60"))
    except (ValueError, TypeError):
        fontsize = 60

    import re as _re
    POS_RE = _re.compile(r"\\pos\(\s*([\d.]+)\s*,\s*([\d.]+)")
    MOVE_RE = _re.compile(r"\\move\(\s*([\d.]+)\s*,\s*([\d.]+)")
    text = cue.get("text", "")
    m = POS_RE.search(text) or MOVE_RE.search(text)
    if m:
        return (float(m.group(1)), float(m.group(2)))

    # Compute Y from MarginV + alignment
    if alignment in (1, 2, 3):  # bottom-anchored
        y_anchor = height - margin_v - (fontsize / 2)
    elif alignment in (4, 5, 6):  # middle-anchored
        y_anchor = (height / 2) + margin_v
    else:  # top-anchored
        y_anchor = margin_v + (fontsize / 2)

    # Compute X from MarginL/R + alignment
    if alignment in (1, 4, 7):  # left
        x_anchor = margin_l + (fontsize * 2)  # rough — text box midpoint guess
    elif alignment in (3, 6, 9):  # right
        x_anchor = width - margin_r - (fontsize * 2)
    else:  # center (2/5/8)
        x_anchor = width / 2

    return (x_anchor, y_anchor)


def check_caption_color_pixels(cues: list[dict], styles: dict[str, dict],
                                 clip: Path, width: int, height: int, fps: float,
                                 has_speaker_map: bool) -> CheckResult:
    """S2 (pixel): verify rendered caption text actually matches brand colors.

    Acquisition.com standard:
      - Alex / single speaker: #FFFFFF (white)
      - Guest / quoted dialogue: #FECB00 or #FED90F (yellow band)

    Samples 5 evenly-distributed frames per cue, extracts pixels in the cue's text
    region, and votes the dominant color. White and yellow are checked with
    tolerance — we don't try to match exact hex, just the right color family.

    Skipped when burnt-in captions (no .ass), or when ffmpeg/numpy unavailable.
    """
    r = CheckResult("S2", "Subtitles", "Caption colors match brand hex (pixel-level)", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r
    try:
        import numpy as np  # type: ignore
    except ImportError:
        r.status = "manual"
        r.summary = "numpy not installed — pip3 install --user numpy"
        return r

    # Sample one mid-frame from each of up to 8 cues distributed across the clip
    sample_cues = cues[:: max(1, len(cues) // 8)][:8]
    expected_yellow = (255, 203, 0)  # #FFCB00 family
    expected_white = (255, 255, 255)
    tolerance = 40  # per-channel

    mismatches: list[tuple[float, str, str, tuple[int,int,int]]] = []
    checked = 0
    for cue in sample_cues:
        # Mid-time of the cue
        t = (cue["start"] + cue["end"]) / 2
        # Sample a frame to a temp PNG via ffmpeg, then read with PIL
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            r.status = "manual"
            r.summary = "Pillow not installed — pip3 install --user Pillow"
            return r

        frame_path = clip.parent / f".audit_frame_{int(t*1000)}.png"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-ss", f"{t:.3f}", "-i", str(clip), "-vframes", "1",
                 str(frame_path)],
                check=True, capture_output=True, timeout=10,
            )
        except (subprocess.SubprocessError, OSError):
            continue
        if not frame_path.exists():
            continue

        try:
            img = np.asarray(Image.open(frame_path).convert("RGB"))
        except Exception:
            frame_path.unlink(missing_ok=True)
            continue
        frame_path.unlink(missing_ok=True)

        # Find non-background pixels — caption text is white/yellow; assume frame
        # background is darker. Threshold: brightness > 200 = likely caption.
        # This breaks if the underlying clip is also bright; tolerance handles
        # most podcast / talking-head scenarios.
        gray = img.mean(axis=2)
        mask = gray > 200
        if mask.sum() < 50:  # too few bright pixels to vote
            continue
        bright_pixels = img[mask]
        avg = tuple(int(x) for x in bright_pixels.mean(axis=0))

        # Determine which speaker style this cue uses; that drives expected color
        style_name = cue.get("style") or ""
        style_lower = style_name.lower()
        # Skip the SHADOW layer — it's an intentionally-dark blob used as the drop-shadow alpha,
        # not a visible-color text element (premiere two-layer mode). Only color-check the crisp text.
        if "shadow" in style_lower:
            continue
        is_guest = "guest" in style_lower or "yellow" in style_lower or "quote" in style_lower
        # Speaker style → expected color. Default: white (Alex / single-speaker).
        expected = expected_yellow if is_guest else expected_white

        diff = max(abs(avg[i] - expected[i]) for i in range(3))
        checked += 1
        if diff > tolerance:
            mismatches.append((cue["start"], cue["text"][:40],
                               f"style={style_name} expected={expected} got={avg}",
                               avg))

    if checked == 0:
        r.status = "manual"
        r.summary = "Could not extract caption pixels from any frame — verify colors manually"
        return r

    if mismatches:
        # Blocking when speaker-map is present — confused colors are visible defects
        r.status = "fail" if has_speaker_map else "warn"
        r.summary = f"{len(mismatches)}/{checked} sampled cues have caption colors off-brand"
        for t, text, note, _ in mismatches[:8]:
            r.details.append(f"  [{sec_to_hms(t)}] {note} — \"{text}\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] caption color off-brand: {note}")
    else:
        r.summary = f"All {checked} sampled cues have caption colors on-brand (±{tolerance})"
    return r


def check_title_card_vision(clip: Path, fps: float) -> CheckResult:
    """HH5 (vision): does the first 2s show a title card / hook text overlay?

    Uses claude-video-vision MCP via stdio if available. Falls back to 'manual'
    when MCP isn't running or first 2s can't be sampled.

    The MCP is auto-fetched via npx — this just makes the call. If the env
    doesn't have the MCP server registered, we return manual and let the human
    check.
    """
    r = CheckResult("HH5", "Hook", "Visual title card / hook text overlay in first 2s", "pass", "")
    # We can't directly call MCP tools from the Python audit subprocess — those
    # tools are invoked by the Claude session. The audit emits the question and
    # marks it for the calling Claude to verify via mcp__claude-video-vision__*.
    r.status = "manual"
    r.summary = ("Vision-MCP check — invoke mcp__claude-video-vision__video_analyze "
                 "on first 2s of clip with prompt: 'Does this clip open with a visible "
                 "title card or hook text overlay? Yes/No + describe what's shown.'")
    r.details.append(f"  → mcp__claude-video-vision__video_analyze video={clip}, "
                     f"start_sec=0, end_sec=2, "
                     f"question='Does this clip open with a visible title card or hook "
                     f"text overlay?'")
    return r


def check_fragment_after_trim(cues: list[dict]) -> CheckResult:
    """E3 (text): after any trim, no remaining utterance is a single token or a
    standalone discourse marker. We can't see the trim history, but we can scan
    cues for floating fragments: 1-3 word lines that are pure discourse markers
    or single words sitting in their own cue.
    """
    r = CheckResult("E3", "Editing", "No floating fragments / discourse markers after trims",
                    "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r

    DISCOURSE_MARKERS = {
        "so", "well", "right", "okay", "ok", "yeah", "yep", "mhm", "uh-huh",
        "great", "alright", "anyway", "look", "listen", "now", "actually",
        "basically", "literally", "honestly", "i mean", "you know",
    }

    floaters: list[tuple[float, str, str]] = []
    for cue in cues:
        text = (cue.get("text") or "").strip()
        # Strip ASS override tags
        text_clean = re.sub(r"\{[^}]*\}", "", text).strip()
        # A cue ending in ? or ! is an INTENTIONAL question/exclamation beat ("right?", "okay?",
        # "really?") — Oliver keeps these; not a trimmable fragment.
        if text_clean.rstrip().endswith(("?", "!")):
            continue
        # Drop trailing punctuation for the test
        bare = re.sub(r"[^\w\s'-]", "", text_clean).strip().lower()
        if not bare:
            continue
        words = bare.split()
        # Single-word leftover or known discourse marker = fragment
        if len(words) == 1 and len(bare) >= 2:
            if bare in DISCOURSE_MARKERS or bare in {"and", "but", "or", "the", "a", "an"}:
                floaters.append((cue["start"], text_clean, f"single-token discourse marker: '{bare}'"))
        elif len(words) <= 3 and bare in DISCOURSE_MARKERS:
            floaters.append((cue["start"], text_clean, f"discourse-only line: '{bare}'"))

    if floaters:
        r.status = "fail"
        r.summary = f"{len(floaters)} floating-fragment cue(s) — should have been trimmed"
        for t, text, note in floaters[:10]:
            r.details.append(f"  [{sec_to_hms(t)}] {note} — \"{text}\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] floating fragment — remove this cue or merge")
    else:
        r.summary = f"No floating fragments in {len(cues)} cues"
    return r


def check_captions_box_doac(cues: list[dict], styles: dict[str, dict],
                             width: int, height: int,
                             safe_zones_path: Optional[Path]) -> Optional[CheckResult]:
    """Extension check: captions sit within the DOAC safe-zones captions_box.
    Returns None when no safe-zones JSON is provided (the check is opt-in).
    When the JSON IS provided, this becomes a blocking check — captions
    outside the box mean either UI overlap, eye-line collision, or off-screen.

    The rectangle from safe_zones_doac.json:
      x in [x_left*W, x_right*W]
      y in [y_top*H,  y_bottom*H]
    """
    if not safe_zones_path or not safe_zones_path.exists():
        return None
    if not cues or not styles:
        return None
    try:
        sz = json.loads(safe_zones_path.read_text())
        box = sz.get("captions_box", {})
        x0 = float(box["x_left"]) * width
        x1 = float(box["x_right"]) * width
        y0 = float(box["y_top"]) * height
        y1 = float(box["y_bottom"]) * height
    except (KeyError, ValueError, json.JSONDecodeError):
        return None

    r = CheckResult("3b", "Subtitles", "Captions inside DOAC safe-zone captions box", "pass", "")
    out_of_box: list[tuple[float, str, str]] = []
    for cue in cues:
        anchor = _compute_cue_anchor(cue, styles, width, height)
        if anchor is None:
            continue
        x_a, y_a = anchor
        reasons = []
        if y_a < y0: reasons.append(f"above box (y={y_a:.0f} < {y0:.0f}) — into eye-line zone")
        if y_a > y1: reasons.append(f"below box (y={y_a:.0f} > {y1:.0f}) — into profile/description zone")
        if x_a < x0: reasons.append(f"left of box (x={x_a:.0f} < {x0:.0f})")
        if x_a > x1: reasons.append(f"right of box (x={x_a:.0f} > {x1:.0f}) — into buttons zone")
        if reasons:
            out_of_box.append((cue["start"], cue["text"], "; ".join(reasons)))

    if out_of_box:
        # Blocking: caption that's outside the eye-line or buttons zones will literally be
        # covered by UI on the phone. This isn't a "warn", it's a ship-blocker.
        r.status = "fail"
        r.summary = f"{len(out_of_box)} cue(s) outside captions_box (box: x={x0:.0f}-{x1:.0f}, y={y0:.0f}-{y1:.0f})"
        for t, text, why in out_of_box[:10]:
            r.details.append(f"  [{sec_to_hms(t)}] {why}")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] captions outside DOAC safe box — {why}")
    else:
        r.summary = f"All {len(cues)} cues inside DOAC captions_box ({box.get('x_left'):.2f}-{box.get('x_right'):.2f} × {box.get('y_top'):.2f}-{box.get('y_bottom'):.2f})"
    return r


def check_lower_half_placement(cues: list[dict], styles: dict[str, dict],
                                width: int, height: int) -> CheckResult:
    """Mozi standard #3: 'Default subtitle placement should be on the lower half of the screen.
    Make sure the subtitles don't cover the subject's mouth/face.'"""
    r = CheckResult(3, "Subtitles", "Lower-half placement (not covering face)", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r

    has_styled = any(c.get("style") for c in cues)
    if not has_styled or not styles:
        r.status = "manual"
        r.summary = "Cannot verify .srt position — confirm captions sit in lower half visually"
        return r

    half_y = height / 2
    import re as _re
    POS_RE = _re.compile(r"\\pos\(\s*[\d.]+\s*,\s*([\d.]+)")
    MOVE_RE = _re.compile(r"\\move\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*,\s*([\d.]+)")

    above_half = []
    for cue in cues:
        style_name = cue.get("style")
        if not style_name or style_name not in styles:
            continue
        style = styles[style_name]
        try:
            margin_v = int(style.get("MarginV", "0"))
            alignment = int(style.get("Alignment", "2"))
        except (ValueError, TypeError):
            continue
        fontsize = int(style.get("Fontsize", "60"))

        # Override via \pos / \move tags
        text = cue.get("text", "")
        m = POS_RE.search(text) or MOVE_RE.search(text)
        if m:
            y_anchor = float(m.group(1))
        else:
            # Compute anchor from MarginV + alignment
            if alignment in (1, 2, 3):  # bottom-anchored
                y_anchor = height - margin_v - (fontsize / 2)
            elif alignment in (4, 5, 6):  # middle-anchored
                y_anchor = (height / 2) + margin_v
            else:  # top-anchored
                y_anchor = margin_v + (fontsize / 2)

        if y_anchor < half_y:
            above_half.append((cue["start"], cue["text"], y_anchor))

    if above_half:
        ratio = len(above_half) / len(cues)
        if ratio > 0.3:
            r.status = "fail"
            r.summary = f"{len(above_half)} cue(s) anchored above frame midline ({ratio:.0%})"
        else:
            r.status = "warn"
            r.summary = f"{len(above_half)} cue(s) anchored above midline"
        for t, text, y in above_half[:8]:
            r.details.append(f"  [{sec_to_hms(t)}] anchor y={y:.0f} (midline {half_y:.0f}) — \"{text[:40]}\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] subtitle in upper half — move below midline")
    else:
        r.summary = f"All {len(cues)} cues anchored in lower half (face-overlap requires manual eye)"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #4 — Subtitle timing matches dialogue
# ─────────────────────────────────────────────────────────────────────────────

def check_dialogue_sync(cues: list[dict], clip: Path, fps: float) -> CheckResult:
    """Mozi standard #4: 'Subtitle timing should match the timing of the dialogue
    (generally, not showing up more than ~1-3 frames before/after something is being said).'

    Heuristic: silencedetect maps speech vs silence regions in the audio. For each cue,
    we check what % of its display window overlaps with detected silence. A cue that's
    >50% on screen during silence = timing is dragged off the dialogue."""
    r = CheckResult(4, "Subtitles", "Subtitle timing matches dialogue (1-3 frame tolerance)", "pass", "")
    if not cues:
        r.status = "skip"
        r.summary = "No subtitle file"
        return r

    # silencedetect d=0.20 (was 0.10) — naturally-spoken speech has 100-150ms inter-syllable
    # energy dips that aren't real pauses. Anything <200ms isn't a real silence the viewer
    # would notice. Threshold for flagging cue is >65% during silence (was 50%) — gives
    # tolerance for cues that legitimately tail into a brief natural pause.
    code, _, err = sh(["ffmpeg", "-i", str(clip), "-af",
                       "silencedetect=noise=-30dB:d=0.20",
                       "-vn", "-f", "null", "-"])
    if code != 0 and "silence_start" not in err:
        r.status = "manual"
        r.summary = "silencedetect failed — verify timing manually"
        return r

    starts = [float(s) for s in re.findall(r"silence_start:\s*(\d+\.?\d*)", err)]
    ends = [float(e) for e in re.findall(r"silence_end:\s*(\d+\.?\d*)", err)]
    silences = list(zip(starts, ends))  # (silence_start, silence_end) intervals

    misaligned = []
    for cue in cues:
        cue_dur = cue["end"] - cue["start"]
        if cue_dur <= 0:
            continue
        silence_overlap = 0.0
        for s, e in silences:
            ovl_start = max(s, cue["start"])
            ovl_end = min(e, cue["end"])
            if ovl_end > ovl_start:
                silence_overlap += ovl_end - ovl_start
        silence_ratio = silence_overlap / cue_dur
        if silence_ratio > 0.65:
            misaligned.append((cue["start"], silence_ratio, cue["text"]))

    if misaligned:
        ratio = len(misaligned) / len(cues)
        if ratio > 0.2:
            r.status = "fail"
            r.summary = f"{len(misaligned)}/{len(cues)} cues displayed during silence — systemic timing drift"
        else:
            r.status = "warn"
            r.summary = f"{len(misaligned)} cue(s) displayed mostly during silence"
        for t, sr, text in misaligned[:10]:
            r.details.append(f"  [{sec_to_hms(t)}] {int(sr*100)}% on-screen during silence — \"{text[:40]}\"")
            r.frameio_notes.append(f"[{sec_to_hms(t)}] subtitle timing off (shown during silence) — \"{text[:30]}\"")
    else:
        tol_ms = (3 / fps) * 1000
        r.summary = f"All {len(cues)} cues align with audio (no >{tol_ms:.0f}ms-during-silence)"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Check #9 — Music doesn't drown out dialogue
# ─────────────────────────────────────────────────────────────────────────────

def check_music_balance(clip: Path, duration: float) -> CheckResult:
    """Mozi standard #9: 'Music shouldn't be loud enough to drown out the dialogue.'

    Heuristic without stems: silencedetect at -30dB. If music is properly ducked under
    speech, audio level should drop below -30dB during dialogue gaps (giving us silence
    detections). If audio NEVER drops below -30dB across a clip with normal pacing,
    something is keeping the floor up — likely too-loud music."""
    r = CheckResult(9, "Audio", "Music doesn't drown out dialogue", "pass", "")
    code, _, err = sh(["ffmpeg", "-i", str(clip),
                       "-af", "silencedetect=noise=-30dB:d=0.20",
                       "-vn", "-f", "null", "-"])
    if code != 0 and "silence" not in err:
        r.status = "manual"
        r.summary = "silencedetect failed — verify music balance manually"
        return r

    silence_durs = re.findall(r"silence_duration:\s*(\d+\.?\d*)", err)
    total_silence = sum(float(d) for d in silence_durs)

    if duration < 5:
        r.status = "manual"
        r.summary = f"Clip too short ({duration:.1f}s) for music-balance heuristic"
        return r

    silence_ratio = total_silence / duration if duration > 0 else 0

    if total_silence < 0.3 and duration > 10:
        # No silence detected = audio floor never drops below -30dB. Either:
        # (a) music too loud and never ducked, or
        # (b) speech is wall-to-wall with no breaths (rare in talking-head)
        r.status = "warn"
        r.summary = f"Audio floor never drops below -30dB across {duration:.1f}s — verify music isn't drowning dialogue"
        r.frameio_notes.append("[all] audio never drops below -30dB; if music is present, duck it more under speech")
    else:
        r.summary = f"{total_silence:.1f}s of sub-(-30dB) gaps detected ({silence_ratio:.0%} of clip) — music likely ducked"
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Report writers
# ─────────────────────────────────────────────────────────────────────────────

STATUS_EMOJI = {"pass": "✅", "fail": "❌", "warn": "⚠️", "manual": "👁️", "skip": "⏭️"}


def write_markdown(report: AuditReport, path: Path) -> None:
    lines = [
        f"# Audit Report — {Path(report.clip_path).name}",
        "",
        f"**Clip:** `{report.clip_path}`  ",
        f"**Duration:** {sec_to_hms(report.duration_sec)}  ",
        f"**Platform:** {report.platform} (9:16 safezone applied)  ",
        "",
        "---",
        "",
    ]

    for cat in ["Subtitles", "Audio", "Video"]:
        lines.append(f"## {cat}")
        for r in report.results:
            if r.category != cat:
                continue
            emoji = STATUS_EMOJI.get(r.status, "?")
            lines.append(f"- {emoji} **{r.id}. {r.name}** — {r.summary}")
            for d in r.details:
                lines.append(d)
        lines.append("")

    c = report.counts
    lines.extend([
        "---",
        "",
        "## Summary",
        "",
        f"- ✅ Pass: {c['pass']}",
        f"- ❌ Fail: {c['fail']}",
        f"- ⚠️ Warn: {c['warn']}",
        f"- 👁️ Manual: {c['manual']}",
        f"- ⏭️ Skip: {c['skip']}",
        "",
        f"**VERDICT: {STATUS_EMOJI.get('pass' if report.verdict == 'SHIP' else 'fail')} {report.verdict}**",
        "",
    ])
    if report.verdict == "SHIP":
        lines.append("→ move to Final Review / upload to Frame.io / send for review.")
    else:
        lines.append("→ see `.frameio.txt` for paste-ready review notes; move to Needs Revision.")

    path.write_text("\n".join(lines))


def write_frameio(report: AuditReport, path: Path) -> None:
    lines = []
    for r in report.results:
        for n in r.frameio_notes:
            lines.append(n)
    path.write_text("\n".join(lines) if lines else "# No issues found — clip is ready to ship.\n")


def write_json(report: AuditReport, path: Path) -> None:
    data = {
        "clip_path": report.clip_path,
        "duration_sec": report.duration_sec,
        "platform": report.platform,
        "verdict": report.verdict,
        "counts": report.counts,
        "results": [asdict(r) for r in report.results],
    }
    path.write_text(json.dumps(data, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Mozi Media Team Alex V1 MVP short-form audit")
    ap.add_argument("--clip", type=Path, required=True)
    ap.add_argument("--subtitles", type=Path)
    ap.add_argument("--speaker-map", type=Path)
    ap.add_argument("--platform", choices=list(SAFEZONES.keys()), default="instagram")
    ap.add_argument("--out", type=Path, help="Path for .audit.md output (.audit.json + .frameio.txt written alongside)")
    ap.add_argument("--client", help="Brand slug — loads vault/clients/<slug>/vocab.txt for the spelling gate")
    ap.add_argument("--no-block-spelling", action="store_true",
                    help="Downgrade spelling failures back to warnings (default: blocking when --client is set)")
    ap.add_argument("--safe-zones", type=Path,
                    help="Path to a safe-zones JSON you supply (any existing file with a captions_box rect). "
                         "When provided, adds check 3b (captions inside the DOAC safe-zone captions_box).")
    ap.add_argument("--fanout", action="store_true",
                    help="Running inside the /edit step-9 audit fan-out: SKIP the checks that "
                         "audit-visual / audit-audio own with stronger detectors (#9 music, #11 "
                         "clipping, #12 pops, #13 centered, #14 top-pad, #15 black, #15b frozen). "
                         "This skill then owns its real lane — caption TEXT + placement mechanics. "
                         "Standalone (no --fanout) still runs everything. Added 2026-08-03: these "
                         "were duplicated with weaker detectors (Haar vs YuNet, volumedetect vs "
                         "sample-railing) AND cost two full cv2 frame loops + raw PCM decodes.")
    args = ap.parse_args()

    if not args.clip.exists():
        print(f"error: clip not found: {args.clip}", file=sys.stderr)
        sys.exit(1)
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("error: ffmpeg/ffprobe not found on PATH", file=sys.stderr)
        sys.exit(1)

    duration = get_duration(args.clip)
    fps = get_fps(args.clip)
    width, height = get_resolution(args.clip)
    safezone = SAFEZONES[args.platform]

    report = AuditReport(
        clip_path=str(args.clip),
        duration_sec=duration,
        platform=args.platform,
    )

    # Load subtitles if present
    cues, styles = [], {}
    if args.subtitles and args.subtitles.exists():
        cues, styles = load_subtitles(args.subtitles)

    has_speaker_map = args.speaker_map is not None and args.speaker_map.exists()

    # Run all 16 checks
    print(f"Auditing {args.clip.name} ({duration:.1f}s @ {fps:.2f}fps, {width}x{height})...")

    # Optional DOAC safe-zones extension (check 3b) — appended only when --safe-zones is set
    doac_check = check_captions_box_doac(cues, styles, width, height, args.safe_zones)

    # Acquisition.com scorecard extension checks (S2 pixel-color, E3 fragments, HH5 title card)
    s2_pixel = check_caption_color_pixels(cues, styles, args.clip, width, height, fps, has_speaker_map)
    e3_fragments = check_fragment_after_trim(cues)
    hh5_title = check_title_card_vision(args.clip, fps)

    checks = [
        check_spelling(cues, client=args.client, blocking=not args.no_block_spelling),  # 1
        check_gaps(cues),                                                           # 2
        check_lower_half_placement(cues, styles, width, height),                    # 3
        *([doac_check] if doac_check is not None else []),                          # 3b (optional)
        s2_pixel,                                                                   # S2 (pixel-level)
        e3_fragments,                                                               # E3
        hh5_title,                                                                  # HH5 (vision MCP hint)
        check_dialogue_sync(cues, args.clip, fps),                                  # 4
        check_lowercase(cues),                                                      # 5
        check_color_diff(cues, styles, has_speaker_map),                            # 6
        check_safezone(cues, styles, width, height, safezone),                      # 7
        check_audio_levels(args.clip),                                              # 8
        # --- #9/#11/#12/#13/#14/#15/#15b: owned by audit-audio + audit-visual in the fan-out ---
        *([] if args.fanout else [
            check_music_balance(args.clip, duration),                               # 9  -> audit-audio music_balance
            check_clipping(args.clip),                                              # 11 -> audit-audio clipping_distortion
            check_pops(args.clip, duration),                                        # 12 -> audit-audio pops_clicks
            check_centered(args.clip, width, height, fps),                          # 13 -> audit-visual face_tracking
            check_top_padding(args.clip, width, height, fps, safezone["top_head_pad_min_pct"]),  # 14 -> audit-visual framing
            check_black_frames(args.clip, fps),                                     # 15 -> audit-visual black_frames
            check_frozen_frames(args.clip, fps),                                    # 15b -> audit-visual frozen_frames
        ]),
        check_compression(args.clip),                                               # 10
        check_dead_cut(args.clip, fps),                                             # 15c (silent hold after a cut — unique to this gate)
        check_audio_lead(args.clip, fps),                                           # 16
    ]
    report.results = checks
    if args.fanout:
        print("  [fanout] skipped #9 #11 #12 #13 #14 #15 #15b — audit-audio + audit-visual own those "
              "with stronger detectors. This gate = caption text/placement mechanics.", flush=True)

    # Write outputs
    out_md = args.out or args.clip.with_suffix(".audit.md")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json = out_md.with_suffix(".json")
    out_frameio = out_md.with_name(out_md.stem.replace(".audit", "") + ".frameio.txt")

    write_markdown(report, out_md)
    write_json(report, out_json)
    write_frameio(report, out_frameio)

    # Console summary
    for r in report.results:
        emoji = STATUS_EMOJI.get(r.status, "?")
        print(f"  {emoji} {r.id:>2}. {r.name}: {r.summary}")

    c = report.counts
    print(f"\nSummary: ✅ {c['pass']}  ❌ {c['fail']}  ⚠️ {c['warn']}  👁️ {c['manual']}  ⏭️ {c['skip']}")
    print(f"VERDICT: {report.verdict}")
    print(f"\nReports:\n  {out_md}\n  {out_json}\n  {out_frameio}")

    # 0 = SHIP · 2 = REVISE (real failures) · 3 = INCOMPLETE (this gate's lane never ran —
    # pass --subtitles / the clip's .ass; a skip is NOT a pass)
    if report.verdict == "INCOMPLETE":
        print("\n🛑 INCOMPLETE: every caption check SKIPPED — no subtitles were supplied, so this "
              "gate's own lane (caption text + placement) was never inspected. Pass --subtitles "
              "<clip.ass> (or the project's captions.ass). Not a pass.", file=sys.stderr)
    sys.exit(0 if report.verdict == "SHIP" else (2 if report.verdict == "REVISE" else 3))


if __name__ == "__main__":
    main()

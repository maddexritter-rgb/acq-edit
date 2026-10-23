#!/usr/bin/env python3
"""spice_caption.py — the ONE "video in -> LOCKED spice-captioned video out" entry point.

THE SINGLE SOURCE OF TRUTH for burning the locked Oliver/spice captions onto a clip:
  transcribe (Groq) -> oliver_format (Oliver's 9-rule text spec, timestamp-preserving) -> caption_director
  -> generate_spice --burn (two-layer gblur Premiere shadow, resolution-adaptive, per-word color) -> caption_qc.

It is the same proven chain the caption-app's caption_one.py runs; lifting it into the caption-clips
skill so the render skill (/edit step 8) and any other caller share ONE caption engine instead of
re-implementing a plain `subtitles=` burn (which shipped the wrong, shadow-less captions in /edit).

Usage:
  spice_caption.py <input.mp4> <output.mp4> [--context "..."] [--work DIR] [--preset PATH]

Resolution -> preset is auto-picked (spice.json >=2100px, else spice_1080.json) unless --preset given.
generate_spice is resolution-adaptive on top of that, so the shadow/animation land correctly at any res.
Requires GROQ_API_KEY (transcription). ANTHROPIC_API_KEY drives the director's color/emphasis; without
it the director falls back to deterministic styling (still spice, just no LLM-chosen guest color).

SPLIT MODES (2026-06-12) — the caption pipeline has two halves with different dependencies:
  • GENERATE (transcribe -> oliver_format -> director) depends ONLY on the audio/words. It's the slow
    LLM part (~40-80s) and is IDENTICAL across any pixel-only change (reframe/zoom/grade/split).
  • BURN (layout on the video + generate_spice --burn) depends on the VIDEO PIXELS and must redo
    whenever the framing changes.
  --gen-only            run GENERATE on <input>'s audio, write transcript/spice_norm/director_stream
                        into --work, then STOP (no layout, no burn). <output> optional/ignored.
  --burn-from <gendir>  skip GENERATE; load spice_norm.json + director_stream.json from <gendir>;
                        run layout on <input> + generate_spice --burn -> <output>. No GROQ/LLM needed.
  (no flag)             FULL = gen then burn on the same input (the original, unchanged behavior).
The render `captions` stage uses these to cache GENERATE across pixel-only revisions (so a reframe
tweak reuses the styled caption file and skips the director re-roll — faster AND byte-consistent).
"""
import argparse, os, re, subprocess, sys, tempfile, time
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent          # caption-clips/
SC = SKILL / "scripts"
LAYOUT = SKILL.parent / "horizontal-to-vertical" / "scripts"  # layout analyzer lives with reframe assets
PRESETS = SKILL / "presets"


def apply_pinned_speaker_truth(transcript_path, normalized_path, stream_path):
    """Project trusted pinned speaker labels onto normalized words by time."""
    import json as _json
    source_words = _json.loads(Path(transcript_path).read_text()).get("words", [])
    if not source_words or not any("speaker" in w for w in source_words):
        return {"applied": False, "reason": "no pinned speaker labels"}
    host_labels = {"host", "alex", "primary", "speaker_0"}
    guest_labels = {"guest", "caller", "attendee", "participant", "speaker_1"}
    intervals = []
    for word in source_words:
        label = str(word.get("speaker", "")).strip().lower()
        if label not in guest_labels:
            continue
        start, end = float(word["start"]), float(word["end"])
        if intervals and start <= intervals[-1][1] + 0.35:
            intervals[-1][1] = max(intervals[-1][1], end)
        else:
            intervals.append([start, end])
    if not intervals:
        return {"applied": False, "reason": "no trusted guest labels"}
    normalized = _json.loads(Path(normalized_path).read_text()).get("words", [])
    stream = _json.loads(Path(stream_path).read_text()) if Path(stream_path).exists() else {}
    perword = stream.setdefault("words", {})
    marked = []
    for i, word in enumerate(normalized):
        midpoint = (float(word["start"]) + float(word["end"])) / 2.0
        if any(lo <= midpoint <= hi for lo, hi in intervals):
            perword.setdefault(str(i), {})["c"] = "guest"
            marked.append(i)
    stream["pinned_speaker_truth"] = {
        "transport": "time_overlap_after_normalization",
        "guest_intervals": intervals,
        "marked_normalized_word_indices": marked,
        "host_labels": sorted(host_labels),
        "guest_labels": sorted(guest_labels),
    }
    Path(stream_path).write_text(_json.dumps(stream, indent=2) + "\n")
    return {"applied": bool(marked), "guest_intervals": intervals, "marked": len(marked)}


def expects_guest(args):
    """Whether this clip is required to contain at least one yellow/guest cue."""
    if args.speaker_mode in {"qa", "read-aloud"}:
        return True
    if args.speaker_mode == "monologue":
        return False
    # Burn-only calls often omit the original context. Preserve the generation-time speaker contract
    # beside the cached style stream so a cache reuse cannot silently drop the zero-yellow gate.
    if args.burn_from:
        contract = Path(args.burn_from) / "caption_contract.json"
        if contract.exists():
            try:
                import json as _json
                return bool(_json.loads(contract.read_text()).get("expect_guest"))
            except Exception:
                pass
    ctx = (args.context or "").lower()
    return any(k in ctx for k in (
        "q&a", "guest", "caller", "attendee", "hotline", "viewer question", "read-aloud",
        "reads a question", "reads the question",
    ))


def load_key(name):
    v = os.environ.get(name)
    if v:
        return v
    zshrc = Path.home() / ".zshrc"
    if zshrc.exists():
        m = re.search(rf'(?m)^\s*export\s+{name}=["\']?([^"\'\n]+)', zshrc.read_text())
        if m:
            return m.group(1).strip()
    return None


def run(cmd, step, env, fatal=True):
    t = time.time()
    print(f"  → {step} …", flush=True)
    p = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        print(f"  ✗ {step} FAILED (exit {p.returncode})", file=sys.stderr)
        print((p.stdout or "")[-1500:], file=sys.stderr)
        print((p.stderr or "")[-1500:], file=sys.stderr)
        if fatal:
            raise SystemExit(p.returncode)
    else:
        print(f"  ✓ {step}  ({time.time()-t:.1f}s)", flush=True)
    return p


def probe_height(path):
    h = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=height", "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
                       capture_output=True, text=True).stdout.strip()
    return int(h) if h.isdigit() else 1920


def _probe_dur(path):
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       capture_output=True, text=True).stdout.strip()
    return float(d) if d else 0.0


def do_gen(inp, gendir, env, args):
    """GENERATE half — audio/words only, PIXEL-INDEPENDENT. Writes transcript.json, spice_norm.json,
    director_stream.json into gendir. This is the slow LLM part; cache it across pixel-only changes."""
    gendir.mkdir(parents=True, exist_ok=True)
    word = gendir / "transcript.json"
    spice = gendir / "spice_norm.json"
    stream = gendir / "director_stream.json"
    dur = _probe_dur(inp)

    if args.words and Path(args.words).exists():
        import shutil as _sh
        _sh.copyfile(args.words, word)
        print(f"spice_caption: pinned transcript {args.words} — transcription skipped", flush=True)
    else:
        run(["python3", str(SC / "transcribe_lv3.py"), str(inp), "--out", str(word),
             "--start", "0", "--end", f"{dur:.3f}"], "transcribe (Groq)", env)
    if args.corrections and args.corrections.exists():
        import json as _json, re as _re
        cmap = {k.lower(): v for k, v in _json.loads(args.corrections.read_text()).items()}
        wj = _json.loads(word.read_text())
        words = wj.get("words", [])
        def _bare(w): return _re.sub(r"^\W+|\W+$", "", w.get("word", ""))
        n_fixed = 0
        # PHRASE pass first: multi-token keys (e.g. "make common" -> "make.com", "and aiden" -> "and n8n")
        # merge the N matched tokens into ONE token spanning first.start..last.end. Whisper splits
        # spoken tech terms ("make.com", "n8n") into 2+ words, which token-level fixes can't rejoin.
        # Longest keys first so they win over shorter overlapping ones.
        for key in sorted((k for k in cmap if " " in k), key=lambda k: -len(k.split())):
            parts = key.split()
            i = 0
            while i <= len(words) - len(parts):
                if [_bare(words[i+j]).lower() for j in range(len(parts))] == parts:
                    merged = dict(words[i]); merged["word"] = cmap[key]
                    last = words[i+len(parts)-1]
                    if "end" in last: merged["end"] = last["end"]
                    words[i:i+len(parts)] = [merged]
                    n_fixed += 1
                else:
                    i += 1
        # TOKEN pass: single-token 1:1 fixes (e.g. "8n" -> "n8n", "maddox" -> "Maddex")
        for w in words:
            bare = _bare(w)
            rep = cmap.get(bare.lower())
            if rep is not None:
                w["word"] = w["word"].replace(bare, rep)
                n_fixed += 1
        wj["words"] = words
        word.write_text(_json.dumps(wj))
        print(f"spice_caption: corrections applied ({n_fixed} word(s))", flush=True)
    # Align word.start to the TRUE acoustic onset (ffmpeg silencedetect) BEFORE formatting/chunking.
    # Fixes the premature-reveal bug (2026-06-14): Whisper/Groq place a post-pause word's start INSIDE
    # the preceding silence, so its caption flashes up before it's spoken. align_to_silence pushes any
    # word whose start falls in a detected silence to silence_end, so downstream timing/chunking sees
    # real onsets. fatal=False: if silencedetect finds nothing, words pass through unchanged.
    # SKIP when the transcript is PINNED (--words): a hand-supplied transcript carries authoritative
    # times already; align can mis-detect a quiet trailing word as silence and shove it ~1s late
    # (StudioL ShovelVsBulldozer 2026-06-17 — pinned "done?"@21.8 got pushed to 22.7, delaying the cue
    # and overflowing the tail). Pinned times win; align only helps RAW ASR output.
    pinned = bool(args.words and Path(args.words).exists())
    if not pinned:
        run(["python3", str(SC / "align_to_silence.py"), "--in", str(word), "--out", str(word),
             "--audio", str(inp)], "align-to-silence (onset)", env, fatal=False)
    else:
        print("spice_caption: pinned transcript — skipping align-to-silence (pinned times authoritative)", flush=True)
    if args.caption_profile == "alex":
        # Existing deterministic Alex formatter; keep byte-for-byte routing unchanged.
        run(["python3", str(SC / "oliver_format.py"), "--words", str(word), str(spice)],
            "oliver-format (caption normalize)", env)
    else:
        from caption_profiles import sentence_case_words
        import json as _json
        payload=_json.loads(word.read_text());payload["words"]=sentence_case_words(payload.get("words",[]))
        spice.write_text(_json.dumps(payload,indent=2)+"\n")
        print(f"caption profile {args.caption_profile}: sentence-case transcript preserved",flush=True)
    mode_rule = {
        "qa": "This is Q&A: every real guest/caller turn must be guest-yellow.",
        "read-aloud": ("The host reads a viewer/caller question aloud before answering. Treat the ENTIRE "
                       "read-aloud question as the viewer's voice: guest-yellow, then switch to white on "
                       "the exact first word of the host's answer."),
        "monologue": ("This is a solo monologue, but reported/role-played/quoted speech still follows the "
                       "yellow quote rule. Never interpret monologue as an absolute all-white command."),
        "auto": "Infer real guest turns and host-read viewer questions from the transcript.",
    }[args.speaker_mode]
    ctx = args.context or (
        "Short-form clip. Read the TRANSCRIPT: IF a guest/caller/attendee asks a question or describes "
        "their situation, emit voice_spans over every contiguous guest line (YELLOW); host lines stay "
        "WHITE. If the host reads a viewer question aloud, that complete read-aloud question is also "
        "guest-yellow even though the host physically says it; switch to white at the answer. " + mode_rule)
    if args.caption_profile == "alex":
        run(["python3", str(SC / "caption_director.py"), str(spice), "--out", str(stream), "--context", ctx],
            "director", env, fatal=False)
    else:
        stream.write_text('{"words":{},"voice_spans":[],"profile":"'+args.caption_profile+'"}\n')
    speaker_truth = {"applied": False, "reason": "not pinned"}
    if pinned:
        speaker_truth = apply_pinned_speaker_truth(word, spice, stream)
        if speaker_truth.get("applied"):
            print(f"spice_caption: pinned speaker truth -> {speaker_truth['marked']} guest words", flush=True)
    import json as _json
    (gendir / "caption_contract.json").write_text(_json.dumps({
        "speaker_mode": args.speaker_mode,
        "caption_profile": args.caption_profile,
        "expect_guest": expects_guest(args),
        "context": ctx,
        "pinned_speaker_truth": speaker_truth,
    }, indent=2) + "\n")
    return spice, stream


def do_burn(inp, out, gendir, work, env, args, preset):
    """BURN half — PIXEL-DEPENDENT. layout on the video + generate_spice --burn, using the spice_norm
    + director_stream produced by do_gen (from gendir). Re-runs whenever the framing changes."""
    spice = gendir / "spice_norm.json"
    stream = gendir / "director_stream.json"
    if not spice.exists():
        raise SystemExit(f"--burn-from: missing {spice} (run gen first)")
    work.mkdir(parents=True, exist_ok=True)
    ass = work / "subs.ass"
    # Caption Y source, in priority order:
    #   1. --layout-file PATH  : a pre-made per-segment layout (e.g. the render stage's auto per-section
    #                            layout: split panels on the seam, close-ups below the chin). Skip the analyzer.
    #   2. layout_analyze      : per-angle Y from the BURN input's pixels (default).
    #   3. --no-layout         : the preset's STATIC y_percent_from_top.
    layout = None
    if args.layout_file and Path(args.layout_file).exists():
        layout = Path(args.layout_file)
        print(f"spice_caption: using provided layout {layout.name} (per-section Y)", flush=True)
    elif not args.no_layout and (LAYOUT / "layout_analyze.py").exists():
        layout = work / "layout.json"
        run(["python3", str(LAYOUT / "layout_analyze.py"), str(inp), str(layout), "--sample-every", "1"],
            "layout analyze (per-angle Y)", env, fatal=False)
    if args.no_layout and not (args.layout_file and Path(args.layout_file).exists()):
        print("spice_caption: --no-layout -> using preset STATIC y_percent_from_top", flush=True)
    spice_cmd = ["python3", str(SC / "generate_spice.py"), str(spice), "--preset", str(preset),
                 "--out", str(ass), "--burn", str(inp), "--burn-out", str(out)]
    if stream.exists():
        spice_cmd.extend(["--style", str(stream)])
    if layout and Path(layout).exists():
        spice_cmd.extend(["--layout", str(layout)])
    if expects_guest(args):
        spice_cmd.append("--expect-guest")
    run(spice_cmd, "render spice (generate_spice --burn, gblur shadow)", env)
    # GATE: prove this is the locked spice render (gblur sidecars + spice preset) — abort if not.
    sys.path.insert(0, str(SC))
    import caption_qc
    caption_qc.check_or_die(str(ass), str(preset), label="spice_caption qc")
    if not out.exists():
        raise SystemExit("generate_spice reported success but output missing")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output", nargs="?", default=None,
                    help="output mp4 (full/burn modes). Optional/ignored with --gen-only.")
    ap.add_argument("--gen-only", action="store_true", default=False,
                    help="run GENERATE (transcribe->format->director) into --work, then stop (no burn).")
    ap.add_argument("--burn-from", type=Path, default=None,
                    help="skip GENERATE; burn using spice_norm.json + director_stream.json from this dir.")
    ap.add_argument("--layout-file", type=Path, default=None,
                    help="pre-made per-segment layout.json (skip the analyzer); drives per-cue caption Y.")
    ap.add_argument("--context", default=None, help="director context (e.g. Q&A speaker-color hint)")
    ap.add_argument("--speaker-mode", choices=("auto", "monologue", "qa", "read-aloud"), default="auto",
                    help="Explicit speaker/color contract. qa and read-aloud fail closed if the final "
                         "ASS contains zero yellow cues; use read-aloud when the host voices a viewer's "
                         "question before answering it.")
    ap.add_argument("--caption-profile", choices=("alex", "leila", "sharran"), default="alex",
                    help="Caption brand profile. Direct callers default to alex for backward compatibility.")
    ap.add_argument("--native-manifest-out", type=Path, default=None,
                    help="For leila/sharran, write the editable native two-line/reveal manifest here.")
    ap.add_argument("--caption-plan", type=Path, default=None,
                    help="Reviewed semantic-card plan for production Leila native manifests.")
    ap.add_argument("--work", type=Path, default=None, help="work dir for intermediates (default tempdir)")
    ap.add_argument("--preset", type=Path, default=None, help="override preset (else auto by height)")
    ap.add_argument("--no-layout", action="store_true", default=False,
                    help="skip the per-angle layout analyzer; use the preset's STATIC y_percent_from_top. "
                         "Use for single-angle talking-head where a FIXED caption height is wanted (e.g. "
                         "Alex desk clips pinned at the mic/tank-top line) instead of per-shot auto-height.")
    ap.add_argument("--words", type=Path, default=None,
                    help="pre-made word-level transcript JSON ({words:[{word,start,end}]}) for the "
                         "input clip — SKIPS the Groq transcription so the caption layer is "
                         "deterministic across re-renders (re-rolling ASR on crosstalk/laughter "
                         "hears different words each run; pin the good roll).")
    ap.add_argument("--corrections", type=Path, default=None,
                    help="JSON file of per-clip word-text fixes {\"heard\": \"burned\"} applied to the "
                         "transcription before formatting (case-insensitive match on the bare word; "
                         "punctuation preserved). For reviewer-flagged caption words the ASR mishears.")
    args = ap.parse_args()

    if args.gen_only and args.burn_from:
        raise SystemExit("--gen-only and --burn-from are mutually exclusive")

    inp = Path(args.input).resolve()
    if not inp.exists():
        raise SystemExit(f"input not found: {inp}")

    env = dict(os.environ)
    # GROQ is only needed when we actually transcribe (gen without pinned words). Burn-only never does.
    will_transcribe = (not args.burn_from) and not (args.words and Path(args.words).exists())
    groq = load_key("GROQ_API_KEY")
    if will_transcribe and not groq:
        raise SystemExit("missing GROQ_API_KEY (transcription) — not in env or ~/.zshrc")
    if groq:
        env["GROQ_API_KEY"] = groq
    ak = load_key("ANTHROPIC_API_KEY")
    if ak:
        env["ANTHROPIC_API_KEY"] = ak
    elif not args.burn_from:
        print("  ⚠ no ANTHROPIC_API_KEY — director uses deterministic styling (spice, no LLM color)", flush=True)

    work = args.work or Path(tempfile.mkdtemp(prefix="spicecap_"))
    work.mkdir(parents=True, exist_ok=True)

    # ONE preset for everything — generate_spice is resolution-adaptive, so spice.json (4K-calibrated)
    # scales itself to any frame (1080/4K/etc.). No spice_1080 variant: one style, no drift.
    preset = args.preset or (PRESETS / "spice.json")

    # ── GEN-ONLY: produce the styled caption file (audio/words only) and stop. ──
    if args.gen_only:
        print(f"spice_caption [gen-only]: {inp.name} -> {work}  (transcript/spice_norm/director_stream)", flush=True)
        do_gen(inp, work, env, args)
        if args.native_manifest_out:
            if args.caption_profile == "alex":
                raise SystemExit("--native-manifest-out currently uses the existing Alex ASS/native adapter; choose leila or sharran")
            if args.caption_profile in {"leila", "sharran"} and not args.caption_plan:
                raise SystemExit("production Leila/Sharran manifests require --caption-plan with reviewed semantic cards")
            command=["python3",str(SC/"build_profile_manifest.py"),str(work/"spice_norm.json"),
                     str(args.native_manifest_out),"--caption-profile",args.caption_profile]
            if args.caption_plan: command.extend(["--plan",str(args.caption_plan)])
            run(command,"native profile manifest",env)
        print(f"✓ spice_caption gen done -> {work}", flush=True)
        return

    if args.caption_profile != "alex":
        raise SystemExit("Leila/Sharran are editable-native profiles: use --gen-only --native-manifest-out, then premiere_native_cards.py")
    out = Path(args.output).resolve() if args.output else None
    if not out:
        raise SystemExit("output is required (full/burn modes)")
    out.parent.mkdir(parents=True, exist_ok=True)

    # ── BURN-FROM: reuse a cached gen dir; just layout + burn onto this (re-framed) video. ──
    if args.burn_from:
        gendir = Path(args.burn_from).resolve()
        print(f"spice_caption [burn-from {gendir.name}]: {inp.name} -> {out.name}  (preset {Path(preset).name})", flush=True)
        do_burn(inp, out, gendir, work, env, args, preset)
        print(f"✓ spice_caption burn done -> {out}  ({out.stat().st_size//1024} KB)", flush=True)
        return

    # ── FULL (default, unchanged behavior): gen then burn on the same input. ──
    print(f"spice_caption: {inp.name} -> {out.name}  (preset {Path(preset).name})", flush=True)
    do_gen(inp, work, env, args)
    do_burn(inp, out, work, work, env, args, preset)
    print(f"✓ spice_caption done -> {out}  ({out.stat().st_size//1024} KB)", flush=True)


if __name__ == "__main__":
    main()

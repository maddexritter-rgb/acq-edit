#!/usr/bin/env python3
"""set_caption_context — wire a tam_select candidate's hook_type into manifest.json.

After tam_select runs (step 3) and you've chosen which candidate to cut (step 4),
run this to write a rich caption director context into manifest.json → stages.captions.context.
The render engine passes that string to spice_caption.py --context, which passes it to
caption_director.py, where it tells the director WHICH hook payload word to peak-size and
HOW to calibrate emphasis for the clip's emotional register.

Usage:
    python3 set_caption_context.py \\
        --tam    10_WORK/tam.json \\
        --rank   1 \\
        --manifest manifest.json \\
        [--speakers 1|2]   # 1 = solo monologue, 2 = Q&A/hotline (default: auto from tam format)
        [--dry-run]         # print context string, don't write

The context string it writes looks like:
    "Alex Hormozi Q&A clip. hook_type: bold_claim. Guest (YELLOW), Alex (WHITE).
     Bold_claim hook — peak-size the declarative claim payload word in the opening line."
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


# Emphasis hint injected per hook_type — tells the caption director WHERE its peak emphasis lands.
HOOK_HINTS = {
    "story":       "Story hook — peak-size the PAYOFF word at the narrative turn (the moment the story resolves).",
    "bold_claim":  "Bold_claim hook — peak-size the declarative CLAIM word in the opening line.",
    "fear":        "Fear hook — peak-size the RISK or LOSS word (the thing the viewer stands to lose).",
    "mistake":     "Mistake hook — peak-size the MISTAKE or WRONG-BELIEF word in the opening line.",
    "contrarian":  "Contrarian hook — peak-size the word that FLIPS the conventional wisdom.",
    "curiosity":   "Curiosity hook — peak-size the GAP word (the surprising thing they don't know yet).",
    "how_to":      "How-to hook — peak-size the OUTCOME word (the result of following the instruction).",
    "money":       "Money hook — peak-size the $ FIGURE (this number IS the hook payload).",
    "question":    "Question hook (weak — 0.48x lift). Don't peak the question; find the ANSWER in the next 2-3 lines and peak its payload word instead.",
    "other":       "Emphasize the key payload word that carries the most meaning in the opening line.",
}

# Emotion hint — what kind of words to reach for.
EMOTION_HINTS = {
    "empathy":    "empathy (1.75x) — emphasize emotional connection phrases and shared-struggle words.",
    "excitement": "excitement (1.65x) — emphasize energetic action words and positive outcomes.",
    "humor":      "humor (1.60x) — peak-size the punchline word.",
    "surprise":   "surprise (1.50x) — peak-size the unexpected reveal.",
    "anger":      "anger (1.50x) — peak-size the injustice or wrongdoing word.",
    "fear":       "fear (1.49x) — peak-size the stakes/risk/loss word.",
    "confidence": "confidence (1.48x) — peak-size the declarative power-statement word.",
    "urgency":    "urgency (1.21x) — peak-size the time-sensitive or call-to-action word.",
    "inspiration":"inspiration (1.33x) — peak-size the aspirational outcome word.",
    "neutral":    "neutral tone (0.87x — lower lift). Still emphasize clearly; look for any latent confidence or story in the body.",
}


def build_context(candidate: dict, speakers: int) -> str:
    hook_type = (candidate.get("hook_type") or "other").lower().strip()
    emotion   = (candidate.get("emotion")   or "").lower().strip()
    topic     = (candidate.get("topic")     or "").strip()
    hook_text = (candidate.get("hook")      or "").strip()

    # Speaker color hint
    if speakers == 2:
        speaker_hint = ("Two-speaker clip. Guest/caller speaks first — their ENTIRE turns are YELLOW "
                        "(voice_spans ALL-OR-NOTHING, every word including function words). "
                        "Alex's turns are WHITE. Watch for Alex's brief 1-3 word interjections "
                        "(\"Cool\", \"Love it\", \"Got it\") mid-guest-turn — re-open a new guest span after them.")
    else:
        speaker_hint = "Solo Alex monologue — all WHITE. Use yellow only for quoted/role-played speech."

    # Hook emphasis hint
    hook_hint = HOOK_HINTS.get(hook_type, HOOK_HINTS["other"])

    # Emotion hint (optional, only add if emotion is known and useful)
    em_hint = ""
    if emotion and emotion in EMOTION_HINTS:
        em_hint = f" Emotional register: {EMOTION_HINTS[emotion]}"

    # Topic note (for Pricing/Relationships etc. where numbers are the hook)
    topic_note = ""
    if topic in ("Pricing", "Sales", "Wealth"):
        topic_note = f" Topic: {topic} (high-lift) — any revenue/price numbers are emphasis priorities, size UP one level."
    elif topic:
        topic_note = f" Topic: {topic}."

    # Opening line hint so the director knows what it's working with
    hook_preview = f" Opening line: \"{hook_text[:120]}\"" if hook_text else ""

    parts = [
        f"Alex Hormozi clip. hook_type: {hook_type}.",
        speaker_hint,
        hook_hint,
        em_hint,
        topic_note,
        hook_preview,
    ]
    return " ".join(p for p in parts if p)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tam",      required=True,  help="Path to tam.json from tam_select.py")
    ap.add_argument("--rank",     type=int, default=1, help="Rank of the selected candidate (default 1)")
    ap.add_argument("--manifest", required=True,  help="Path to manifest.json")
    ap.add_argument("--speakers", type=int, default=0,
                    help="1=solo, 2=Q&A/two-person. 0=auto-detect from tam format field (default)")
    ap.add_argument("--dry-run",  action="store_true", help="Print context string; don't write manifest")
    a = ap.parse_args()

    tam_path = Path(a.tam).expanduser()
    manifest_path = Path(a.manifest).expanduser()

    if not tam_path.exists():
        sys.exit(f"ERROR: tam file not found: {tam_path}")
    if not a.dry_run and not manifest_path.exists():
        sys.exit(f"ERROR: manifest.json not found: {manifest_path}")

    tam = json.loads(tam_path.read_text())
    candidates = tam.get("candidates", [])
    if not candidates:
        sys.exit("ERROR: tam.json has no candidates")

    # Find the selected rank
    cand = next((c for c in candidates if c.get("rank") == a.rank), None)
    if cand is None:
        # Fallback: use list index
        idx = a.rank - 1
        if 0 <= idx < len(candidates):
            cand = candidates[idx]
        else:
            sys.exit(f"ERROR: no candidate with rank={a.rank} in {tam_path}")

    # Detect speakers from tam format field if not given
    speakers = a.speakers
    if speakers == 0:
        fmt = tam.get("format", "qa")
        speakers = 2 if fmt in ("qa", "hotline", "podcast") else 1

    context = build_context(cand, speakers)

    if a.dry_run:
        print(f"[dry-run] context string for rank={a.rank}:")
        print(f"  {context}")
        return

    # Write into manifest.json → stages.captions.context
    manifest = json.loads(manifest_path.read_text())
    stages = manifest.setdefault("stages", {})
    captions = stages.setdefault("captions", {})
    captions["context"] = context
    manifest_path.write_text(json.dumps(manifest, indent=2))

    print(f"[set_caption_context] rank={a.rank} ({cand.get('hook_type','?')} / {cand.get('emotion','?')}) "
          f"→ written to {manifest_path}")
    print(f"  context: {context[:140]}{'…' if len(context) > 140 else ''}")


if __name__ == "__main__":
    main()

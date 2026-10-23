# Q&A CALIBRATION CORPUS — the compounding loop ("cut like Oliver")

> **Why this exists.** Reading the SOP isn't enough — the proof that the editorial layer is improving is
> whether a BLIND cut (raw transcript + SOP only, never having seen Oliver's version) lands close to how
> **Oliver** (our master editor) actually cut the same footage. This folder is the growing answer key.
> Every time Oliver publishes a reel we ALSO have the raw session for, we add a case. The set only grows;
> the score only goes up. That is the compounding.

## How a case is built
1. Find an Oliver-published Q&A reel where we have the raw session footage (we usually do — it's our footage).
2. `yt-dlp` the reel → `whisper-cli -m ~/.cache/whisper/ggml-base.en.bin -f reel.wav` → Oliver's cut transcript.
3. Pull the matching RAW interaction window from the session transcript (`10_WORK/_transcripts/session_segments.json`).
4. Save `case_NNN_<slug>.json` here with: `RAW_full_interaction`, `OLIVER_published_cut`, `oliver_published_seconds`,
   and (optional) `MY_shipped_cut` for the before/after.

## How to USE it (every Q&A session, and to test a skill change)
```
# 1. Produce a BLIND cut of a case's raw (you, or an agent) using ONLY the SOP / clipper_ai_prompt.md
# 2. Score it against Oliver's ground truth:
python3 __ACQ_SKILLS__/edit/scripts/qa_calibration_score.py \
    --case __ACQ_SKILLS__/edit/references/qa_calibration/case_001_skin_cancer_surgeon.json \
    --candidate "<your blind cut transcript>"
# → hook_match / payoff_match / similarity 0-100 + the specific divergences from Oliver.
```
Run the whole corpus after ANY change to the SOP / gate / cut-design to confirm you got closer to Oliver,
not further. This is the regression test for editorial taste.

## THE COMPOUNDING ARCHITECTURE (how lessons stop evaporating)
A lesson only compounds if the safe path is the DEFAULT and the unsafe path is BLOCKED. Four layers, in order:
1. **DEFAULTS** — bake the fix into the engine so a session gets it even if it never read the lesson
   (contrast hook + HOOK→PAYOFF→TENSION order in the cut step; both-mics@1.0; dynamic target framing;
   `--music-ss` past slow intros; substance floor). Make safe automatic, not opt-in.
2. **GATES (measure + BLOCK, never warn)** — `qa_editorial_score.py` (hook class / payoff principle /
   portability / one-arc / substance floor) and `qa_prebuild_audit.py` (6 visual/mechanical gates) must
   EXIT 0 before encode/delivery. "Gate, don't warn" — a detected failure blocks, it doesn't print a note.
3. **ORCHESTRATOR** — every job runs through `/edit`. Ad-hoc cutting/reframing bypasses layers 1–2, so it
   is where the rules live. No side-door renders.
4. **CALIBRATION CORPUS (this folder)** — the growing answer key + scorer that MEASURES whether layers 1–3
   are actually moving cuts toward Oliver. New case every time Oliver publishes on footage we have raw for.

A lesson learned in a session must land in at least one of: a DEFAULT (engine), a GATE (blocking check),
a SKILL DOC ([`QA_MASTER_SOP.md`](../QA_MASTER_SOP.md)), and a MEMORY pointer — or it will be re-learned next time.

## Finding new pairs (the scrape→match method — 2026-06-17)
clip-intel is the source (it's fresh — check `data_freshness`; no IG re-scrape needed). To link a raw
session's clips: (1) `top_performers`/`search_clips` for recent @hormozi IG clips; (2) `find_source_moments`
for each clip's spoken transcript; (3) match against the raw session by **distinctive-noun overlap**, NOT
raw n-gram (n-gram gave a false positive on generic business-advice phrasing — DYrpt88SuQM scored 27.8% but
its nouns were absent). Tools left in the L1 project's `_oliver_calibration/`: `match_ig_to_raw.py`,
`fetch-ig-transcripts` workflow, `LINKAGE_MAP.md`.

## Cases
- **cases 002–007 — the L1 Workshop session (6 verified Oliver pairs).** Tanya/parent-child, surgeon,
  Nedu/overnight-babies, pelvic-floor coaching, Thomas/Vietnamese-coffee, Trey/golf-carts. Two findings that
  became SOP corrections: (a) **every** Oliver hook is the contrast hook (activity→revenue; golf carts leans
  into the mundane); (b) **Oliver's Q&A cuts run 68–172s, median ~109s** — not 60–90s — because he keeps the
  full reasoning ladder. See `L1_session_oliver_pairs.json`.
- **case_001 — skin-cancer surgeon (underpriced course).** Oliver 101s. My shipped V1 = a ~38s skeleton that
  opened on "Sweet" and ended mid-word on the "$25K + 5K/yr" TACTIC. Oliver opened on the contrast hook
  ("I'm a plastic and reconstructive surgeon… 250K in revenue" — reached back for the credential), kept the
  full reasoning, and ended on the PORTABLE PRINCIPLE: *"people need a reason and an excuse to buy… the
  excuse is if I just learn one thing, it pays for itself."* The lessons from the blind-cut calibration are
  appended to [`QA_MASTER_SOP.md`](../QA_MASTER_SOP.md) and enforced by `qa_editorial_score.py`.

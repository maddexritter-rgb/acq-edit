# Alex Q&A SF — Visual Guide (angles · grade · captions · title cards)

**Source of truth.** From the official *Alex Q&A SF Visual Guide* PDF (`references/qa_hotline_sops/`) + reverse-engineering
8 of Oliver's June Q&A exports (downloaded refs were in `2026-06-05_QAWorkshopClips/10_WORK/_oliver_june_ref/`). Pairs with
the canonical rubric [`../TEAM_ALEX_QA_HOTLINE_SOP.md`](../TEAM_ALEX_QA_HOTLINE_SOP.md). Format: **4K vertical 2160×3840, ~24fps (23.976)**.

## Visual hierarchy (the thing most easily gotten wrong)
**Alex is the visual star, not the guest.** The guest is mostly *heard* (yellow captions) + shown briefly. Most screen
time is Alex. Even while the guest talks, you often HOLD on Alex (listening/reacting) with the guest's words in yellow.
Do NOT put a long full-screen tight portrait of a random guest on screen — that inverts the hierarchy.

## Camera angles (cut between these; static shots + hard cuts; + emphasis zooms)
Editors keep BOTH a close and a wide per speaker and cut between them for dynamism:
- **Split-screen 50/50** — Alex above, Guest below, same proportions, **drop shadow on Alex's (top) half**. Used for the
  question. (`qa_build` cam=`split`.)
- **Alex Main** — close, ~chest/waist-up, centered.
- **Alex Wide** — fuller 3/4 "cowboy" stage shot (head→mid-thigh). For our footage: `qa_reframe_stage --zoom 1.7 --eye-y 0.20`.
- **Guest Main** — head-and-shoulders close.
- **Guest Wide** — guest in the audience/crowd with depth (NOT an isolated headshot).
- Hook visual: **text title card** (SF Pro) → split-screen → switch to full-screen. (Title cards are handled by another
  team — text-hook stays OFF for these renders.)

## Motion / grade / polish
- **Zooms: dynamic + emphasis** — punch in on key words/numbers/reveals. (Subtle, not constant.)
- **Color grade (moderate, "default Premiere preset" punch — not a heavy LUT):** Guest = **cool / blue tones**; Alex =
  **bright / saturated**. Split-screen: individual CC on each half + drop shadow on Alex's half.
- **Upscale: Topaz to 4K at original FPS.**
- ❌ NO red hook box (an earlier guess — not in any real clip). NO music-killing; music IS used (see audio doc).

## Captions (EXACT spec — matches our locked caption-clips / oliver_caption.json)
- Font **Proxima Nova**, size **80**, text box **150** (avoid UI cutoff). Center, ~48% height (under the chin). Soft shadow, no hard stroke. No karaoke; whole 1–3 word chunk swaps on the beat. **No dead gaps** between subtitles.
- **Color = voice:** Guest → **#FED90F or #FECB00**, style **Medium Italic** (highlight **Black Italic**). Alex → **#FFFFFF**, style **Medium** (highlight **Black**).
- **Case:** lowercase EXCEPT proper nouns and "I / I'm / I'd / I've / I'll". Single line default.
- **Money/symbols:** always "$" prefix; symbols not words ($ not "dollars", % not "percentages"). Abbreviate >$100K → $250K / $1.2M / $20M / $3B; <$100K may stay literal or abbreviate. Always spell-check.

## Title cards (reference only — another team owns these)
SF Pro, **Black**, ALL CAPS, ~160px, leading −40, tracking −30. Colors white / black / yellow (#FECB00; add subtle black
stroke on white bg). Background dark grey **#1A1A1A**, opacity 100%, size 60, corner radius 50.

## How this maps to our tools
`qa_build.py` cam modes already cover it: `split` (Alex-top/guest-bottom), `alex` (tracked — set zoom/eye per Main vs Wide),
`guest` (crop — Main close vs Wide in-crowd), `wide`. Per-guest framing differs (each guest sits/stands elsewhere) — set
GUEST_CROP / GUEST_HALF / ALEX_ZOOM / ALEX_EYE via a job-local wrapper (don't edit the locked tool). Grade + emphasis zooms
are not yet wired into qa_build (TODO: optional guest-cool/Alex-bright CC + punch-in zoom pass).

---
name: music
description: Select and apply clip-specific background music from the approved local library using semantic audio matching, acoustic section analysis, rotation, real-clip auditioning, and link-only discovery batches. Use for /music, add music, choose music, replace a music bed, soundtrack clips, or when another editing skill needs music selection. Do not use for general audio cleanup or sound effects.
---

# Music

## Scoped production guidance

→ Load [scoped production policy](../edit/references/scoped-brand-policy.md), including on direct invocation, before selecting music.
Honor the matching `audio` stage's music default; an explicit music/no-music test keeps dialogue and picture identical and labels both variants.

For any Premiere access, follow [Premiere Agent startup and advanced stage routing](../edit/references/premiere_start_here.md). Use the configured new bridge by default; if MCP tools are missing in this chat, use its CLI. Keep this skill’s existing creative scope and read-only limits.


Own the complete music capability. `/edit` and other editing workflows route here; they must not maintain separate song-selection logic.


## Native bridge execution

Follow the [shared execution contract](../edit/references/premiere_execution_contract.md) and the [native music bridge reference](references/native_music_bridge.md) on the default Premiere Agent profile with a music scope.
Use `scripts/apply_native_music.py` to consume the existing selection/audition receipt, prepare/place an owned audio item into an empty range, and apply its calibrated envelope. Use source-offset-aware timing to align the chosen musical turn with the clip’s payoff and shape the owned envelope around dialogue. Placement/envelope have bounded native fixture evidence; replacement, new native tracks and EQ remain unsupported through this route. Do not claim a music bed is audible from item presence alone.
For newly prepared/grafted tracks, the same reference requires explicit master-inlet routing and actual rendered music presence; item/envelope readback alone is insufficient.
Preserve dialogue, graphics and picture state; verify native source/envelope readback, then save/reopen and compare/listen to the rendered full mix before claiming acceptance.

## Outcome

Given one or more locked clips, choose a different track for each clip when the pool allows, select the strongest section of each track, apply it under dialogue, and leave an auditable receipt. The user should not have to browse folders or operate the matcher.

## Select

1. Read the complete assembled transcript and inspect the actual cut's delivery, pacing, and emotional turn.
2. Write `music_brief.json` with `profile`, continuous `valence`, `energy`, `tension`, `warmth`, `momentum`, `dialogue_space`, plus `arc`, `role`, `tags`, and `avoid`.
3. Run:

```bash
python3 __ACQ_SKILLS__/music/scripts/pick_music.py \
  --transcript <assembled_transcript.txt> \
  --brief-json <music_brief.json> \
  --duration <clip-seconds> \
  --used '<recent-track>|<recent-track>' \
  --n 5 --json
```

Only review-room `Keep` tracks are eligible. Reject, Maybe, unreviewed, blacklisted, missing, too-short, and recently used tracks are hard filters. Never override these filters with filename intuition or folder-wide random selection.

The ranker combines CLAP semantic audio similarity with four measured acoustic sections per track. Treat its top five as candidates, not automatic editorial truth.

## Audition and decide

Audition the top three against the actual cut at their returned start positions. The agent chooses the winner; do not make the user operate the matcher. Reject candidates with lyrics or spoken intros, dialogue masking, tonal mismatch, melodrama, meme energy, or a build/drop that fights the clip. Escalate only if none of the five fits.

Use a different winner per clip when possible and pass the batch's prior winners through `--used`. Align a build or drop to a real editorial turn or payoff; do not force a beat event where the clip has none.

## Apply and verify

For a manifest project, → Use skill: `render` and change only the mix layer. For an existing native Premiere project, add the chosen music as an editable audio layer and preserve the approved cut.

Keep speech intelligible, carve music presence frequencies, duck under dialogue when appropriate, and avoid audible music heads/tails that feel accidental. Compare the result with the dialogue-only source and confirm the selection improves the clip rather than merely adding energy.

Write `10_WORK/<clip>/music_selection.json` containing the brief, all candidates, winner, start point, reasons, rejected audition candidates, and recent-track exclusions. Log the winner in the parent workflow's run ledger when one exists.

## Library maintenance

The approved library lives at `__ACQ_ASSETS__/content-skill-system/(1) Tik Tok/`. Selection is non-destructive. Do not delete, move, blacklist, or reclassify library files unless the user explicitly requests library maintenance.

### Discovery batches

When asked to grow the pool, begin with a small, taste-led scout batch—not a bulk import. If a curated Keep library exists, discovery starts with the actual kept song names: resolve representative seeds to their canonical YouTube uploads, group them by artist/world, and use artist-neighbor and YouTube-related results as the primary source. Every new candidate must name the kept seed that led to it. Exclude already-kept songs, duplicates, loops, mashups, playlists, non-music recommendations, and generic keyword-fillers. Use broad semantic/vibe search only when the seed graph has no useful neighbor.

Create a separate local review room containing only direct YouTube embeds/links, the seed lineage, why-it-fits notes, decisions, permission status, and an exportable shortlist. A decision must persist and immediately advance to the next visible candidate.

### Link-only review-room playback

The review room must have a real embedded audition player; do not make a watch-page link the primary listening path. Use a standard YouTube iframe with an explicit local `origin`, `referrerpolicy="origin"`, `playsinline=1`, and an `allow` attribute that includes `autoplay` and `encrypted-media`.

Put a large room-level **Play track** gate above the iframe. On that user click, replace/reload the iframe with `autoplay=1`. This avoids depending on the tiny nested YouTube play button, which can fail to receive the first gesture in some browser shells. Once it starts, leave YouTube's normal embedded seek, volume, pause, and fullscreen controls available.

Serve the local room with `Cache-Control: no-store, max-age=0, must-revalidate` and fingerprint its JavaScript asset URLs. This prevents an old player implementation from surviving a room update. Keep decisions and notes in local storage so reloads do not lose review work.

The Codex in-app browser may intermittently leave a remote YouTube iframe blank even when the same embed is valid. Verify actual playback in Chrome before handing the room over; if the in-app browser flakes, open the **same localhost review room in Chrome** rather than sending the user to YouTube. A direct YouTube link may remain as a secondary source/rights link, never the required playback route. Do not call an embed fixed based only on page load—confirm that the player has initialized and is playing.

Discovery is link-only: do not download audio, copy media into the approved library, or treat a video title/channel as permission. A `Shortlist` means “worth pursuing,” not “cleared.” Before any song enters the approved pool, the user must independently confirm appropriate written permission or choose a licensed substitute; only then may authorized library intake and index rebuild occur.

After an authorized library change, rebuild the acoustic and semantic indexes:

```bash
python3 __ACQ_SKILLS__/music/scripts/music_index.py '<music-root>'
python3 __ACQ_SKILLS__/music/scripts/music_semantic_index.py '<music-root>'
```

The legacy `_shared` script paths are compatibility shims only. `__ACQ_SKILLS__/music/scripts/` is the canonical implementation.

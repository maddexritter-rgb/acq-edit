# /edit execution runbook


## Run mode and backend

Read [execution backends](references/execution-backends.md) first. The historical
Premiere steps below remain the Premiere route; Filmcraft uses
[its execution adapter](references/filmcraft.md) with the same owning skills.
An explicit end-to-end request authorizes intermediate finishing and local exports;
the interactive “cuts done” and export stops below apply to assembly-review mode.
Never invent human approval, skip actual output checks, or infer external delivery.

## Bridge profile and execution evidence

For Premiere native operations, follow [Premiere Agent startup](references/premiere_start_here.md) and [the execution contract](references/premiere_execution_contract.md). Use the new default connector and typed stage drivers; direct mailbox commands and the old global MCP installation are retired.

## Default assembly-cut route — stop at editor review

This is the route for “make assembly cuts.” Use `long-form-ingest` for the primary
dialogue word transcript, then `assembly-design` as the single owner of exact
spoken clips, every kept span and internal edit, source-frame resolution, and the
playable 16:9 review timeline. No audit, agent review,
worksheet, job record, packet, or approval receipt is required to make the timeline.
The remaining evidence-heavy Steps 1–8A are optional strict mode, not prerequisites.

The in-session model writes `edit.assembly-selection/v2` for new cuts, including
the complete source-order `paper_cut` KEEP/CUT ledger. The example below is an
older v1 shape for historical replay only. One row per clip; word ranges are
inclusive and kept ranges are in intended playback order. The model
must read the complete interaction and its relevant editorial precedents first.
When a separate writer places new cuts, it accepts only a pinned v2 selection,
its compiled literal playback/continuation receipt, and the corresponding resolved
frames. Reject custom span-only packets, v1 selections, and raw moment windows;
do not reconstruct their intent from notes or an older timeline. This is a
provenance check, not an editorial approval gate.

```json
{
  "schema": "edit.assembly-selection/v1",
  "clips": [{
    "id": "clip_01",
    "media": "/absolute/path/to/source.mp4",
    "source_words": "/absolute/path/to/corrected_words.json",
    "interaction_word_range": [100, 250],
    "hook_word_range": [120, 132],
    "reasoning_word_range": [145, 167],
    "payoff_word_range": [205, 215],
    "kept_word_ranges": [[120, 167], [205, 215]],
    "editorial_intent": "One source-faithful idea and why these passages earn it"
  }]
}
```

The interaction range is the actual complete source exchange, not narrowed to hide
omitted material. For a genuinely clean one-span clip, add a specific
`continuous_source_rationale`. A batch of broad one-span excerpts is not ready.
Compile the design against its transcript; this prints and saves the exact joined
speech and all beat text directly from source words:

```bash
python3 scripts/compile_assembly.py --design 10_WORK/assembly_selection.v1.json \
  --out 10_WORK/compiled_assembly.v1.json
```

The model must read that printed playback and repair the *selection* if its literal
opening, transitions or payoff do not work. This is the editorial thinking pass, not
an independent audit. Assembly Design then resolves every kept word span:

```bash
python3 ../assembly-design/scripts/resolve_review_edges.py \
  --compiled 10_WORK/compiled_assembly.v1.json \
  --out 10_WORK/resolved_assembly.v1.json
```

The resolver tries measured speech gaps first. A refused seam keeps the selected
words on a provisional, source-linked timeline with uncertainty in the clip marker;
it is not a certified cut. The output has this shape:

```json
{
  "schema": "edit.resolved-assembly/v1",
  "compiled_path": "/absolute/path/to/compiled_assembly.v1.json",
  "compiled_sha256": "SHA256 of that exact compiled file",
  "clips": [{
    "id": "clip_01",
    "source_frames": [[2400, 3090], [3680, 3810]],
    "status": "MEASURED_EDGES",
    "boundary_issues": [],
    "note": "Editor review; listening and approval pending"
  }]
}
```

`source_frames` is half-open [in,out) at the source's rational frame rate. Do not
derive a **certified** edge by rounding raw ASR labels. For an unresolved review
seam only, Assembly Design uses its calibrated frame-grid audio placement and
labels it `PROVISIONAL_SEAM`;
listening/manual adjustment remain pending. If a word choice changes during
resolution, revise and recompile the selection first. The
builder refuses a raw moment/window manifest, stale design, changed transcript,
missing selected span, or frame ranges that do not match the selected words.

Build the editable 16:9 V1/A1 XML with:

```bash
python3 scripts/review_xml.py --assemblies 10_WORK/resolved_assembly.v1.json \
  --name 01_CUTS__SessionSlug --out 10_WORK/01_CUTS__SessionSlug.xml
```

Import into the isolated shoot sequence/bin in the target weekly Premiere project, save, reopen, and read back source
media, in/out frames, item order, V1/A1 parity, and offline status. These are technical
construction checks, not editorial audits. On a bridge import failure, use the
documented guarded `app.project.importFiles` fallback. Put all selected clips in one
sequence with gaps and markers. Add more as found; do not wait to mine every lead or
sync unused cameras. Stop after the playable 16:9 timeline and tell the editor what is
there. The editor's timeline decisions are authoritative for subsequent work.

## Current route

The following is optional strict-mode history. Use the owning skills in edit/SKILL.md.
Read the job-control contract in [references/assembly_job.md](references/assembly_job.md).
For historical projects, preserve existing files and approved timelines; explicit
adoption of this route requires a new pinned job record, not retrospective PASS receipts.

Three phases remain separate: source-linked 16:9 cuts review, approved native finishing,
then explicitly authorized export/delivery. An automated PASS never advances human approval.

## 🛑 THE PREMIERE MODEL / EDITABILITY INVARIANT — the entire point of this workflow. Violating it = FAILED delivery.

**At every stage, what's in Premiere is LIVE and editable — cuts, framing, captions, music.
NOTHING gets rendered/baked locally and imported as a finished file.** Two sequences, both native:
Phase 1 → 16:9 CUTS-APPROVAL sequence (source format, cuts only, editor tweaks by hand);
Phase 2 → 9:16 VERTICAL sequence rebuilt from the editor's LOCKED cuts — tracked, captioned,
scored, still fully editable at every layer.

**🚫 THE ANTI-PATTERN (seen in bad sessions, banned):** ffmpeg-render the finished clip locally
(cuts baked, reframe baked, captions burned, music mixed) and import that MP4. That's an
uneditable brick — no visible cuts, no keyframes, captions fused into pixels. "What's the
fucking point." The ONLY baked renders permitted anywhere in the flow: (a) tiny caption-gen
proxies, (b) the caption overlay .movs themselves (which sit as editable track items),
(c) prenormalized music beds, (d) approved illustration plates kept as separate picture-layer media,
(e) the FINAL Phase-3 exports from the approved timeline.

**How each layer lands, concretely:**
- **Every cut** = a real clipitem referencing the ORIGINAL source media at in/out points —
  razor-able, slip-able, extendable; cut points are visible seams on V1, not baked pixels.
  Split additionally at every verified camera-switch frame.
- **Reframe/face-tracking** = native Motion Position/Scale KEYFRAMES on the V1 items (diamonds
  the editor can grab), applied via ExtendScript AFTER import, at MEDIA time. Same-angle
  adjacent items inherit identical framing so butts are seamless.
- **Captions** = editable independent graphics/layers using the current `caption-clips`
  native workflow. Caption revisions do not replace the underlying source video.
- **Audio** = separate lanes: host / caller / music, each its own track items with clip-level
  volume. Swap a music track by swapping the item.
- **Small change after review?** Fix the ITEMS (razor/move/relink/keys) — never re-render the
  clip outside Premiere. Export is the ONLY bake, from the sequence's current state.

---

# PHASE 1 — CUTS-APPROVAL SEQUENCE (deliverable: ONE 16:9 sequence, then STOP)

## STEP 0 — Reuse the toolkit project, ingest and preflight
Read `project.json` for the exact project root and fixed backend. For new work use
`node "__ACQ_TOOLKIT__/dist/cli.js" project "<title>"`; for existing work use
`projects` and `open PROJECT_ID`. Never create a competing weekly production project.
→ Use skill: footage-fetch for verified intake into this project's `00_SOURCE`.
Keep intermediates under `10_WORK` and immutable published exports under `20_DELIVER`.
Use the toolkit's clip registration and selected native adapter; the remaining
Premiere-specific mechanics below apply only to a scoped Premiere project.
→ Follow [native execution routing](__ACQ_TOOLKIT__/docs/AGENT_WORKFLOW.md#native-execution-routing).

- Verify source is horizontal ≥1080p, real fps (a 5fps "wrong file" wasted a session once —
  `ffprobe` it and EYEBALL one frame).
- Start `10_WORK/00_RUN_LEDGER.md` and log every step (a step with no row did not happen).
- Banned-guest registry ≤14 days old: probe `banned_guest_gate.py` with a dummy text file;
  exit 3 = re-sync BEFORE starting.
- Premiere open with the target project + Premiere Agent Lab panel running; startup doctor and live snapshot passed.
- **BRIDGE SINGLE-WRITER GATE (session-start coordination):** before any open, relink,
  timeline mutation, save, or export, check whether another active task is using the Premiere
  bridge. Coordinate the exact `.prproj` path and sequence name, and wait for that task to
  explicitly release ownership. Work in an isolated sequence/bin inside the
  exact weekly project; never switch to a fresh stage-specific project copy by
  default. On release, report which project and sequence may remain active in Premiere.
- **🛑 PER-CALL PROJECT CHECK — a standing rule for the whole session, not a Step 0 checkbox.**
  The active project and active sequence are shared global state that follow whichever window
  or session last had focus. They change **without any action of yours** — the editor clicks
  into another project, or a second session touches the bridge, and the target moves under you.
  A check you ran three calls ago is already stale. So: immediately before **each individual**
  mutating call — `remove_selected_clips`, `select_all_clips`, `insert_from_source`,
  `overwrite_from_source`, `set_source_in_out`, any save, any export, any ExtendScript op —
  read back project **and** sequence identity (`ping` / `get_project_info`) and refuse to
  proceed on any mismatch. A batch of mutations is not one check; each one needs its own.
  Verifying once and then firing several calls in a row is exactly how a delete lands in
  someone else's timeline.
  **If a wrong-project mutation happens anyway:** the bridge's own `undo` / `multiple_undo`
  are unreliable — `app.project.undo is not a function` and `0 undone` have both been observed.
  Do not count on them. Stop every further mutating call, do **not** save that project, tell
  the user immediately and precisely which project/sequence and how many items were hit, and
  have them run Edit → Undo in the Premiere UI — that is the only confirmed recovery path.
  An unsaved wrong mutation is recoverable; a saved one may not be.
- **GATE:** project folder exists, source verified, gate probe exit 0, bridge answers ping.

## STEPS 1–5 — Source, discovery, design and acoustic execution

→ Use skill: `long-form-ingest` for raw/corrected transcripts and actual audio evidence.
→ Use skill: `assembly-design` for ordered full coverage, per-moment profiles,
spoken construction, self-check, compilation and retained-word reconciliation.
Assembly Design uses `_shared/speech_map_cut.py` for measured boundaries in
selection-preserving mode; this is not a second editorial handoff.

Before designing, register all supplied sources/voices/cameras in the session inventory;
pin the ready source subset and its actual read ranges in the active job.
Full-source coverage does not mean one clip per row. Record excluded/deferred interactions
with reasons; do not silently discard a camera or guest because of the selected brand.
Measure dialogue-source clocks and coverage gaps before design. Verify a guest-camera
picture mapping only when a selected cut will use that angle; the primary program picture
can carry an otherwise complete Q&A while optional angles remain unverified.

After coverage of a ready dialogue source, take the first strong design group through self-check, frame resolution,
and playable native placement. Continue mining and append later groups to the same review
sequence. Do not hold the first group while finishing every optional camera check or
every lead's worksheet or unrelated media copy. Record time to first playable sequence and time spent in ingest,
design, boundary repair, and native construction separately.

Before compilation, the authorized plan and design comparison must match the job revision.
The compile CLI checks this automatically. Preserve meaningful pauses and performance;
acoustic tools cannot change the editorial selection to obtain a clean boundary.

Before native construction run:
```bash
python3 scripts/assembly_job.py prepare-native --job JOB.json --clip-id ID --out NATIVE_PACKET.json
```
For v4, the packet binds source, compiled plan, resolved boundaries, reconciled words and
one independent final editorial review of that exact executable dialogue. Build only from
its `source_spans`, not a rediscovered broad window.
For a complete source-backed candidate awaiting listening or lexical reconciliation,
use `assembly_job.py prepare-provisional-native --job JOB.json --clip-id ID
--cut PROVISIONAL_CUT.json --out PACKET.json`. This creates a guarded review-only packet
with exact source frames, actual selected source words, and explicit unresolved issues.
Use the canonical `edit/scripts/review_xml.py` adapter for a mixed-source provisional
review sequence. A provisional packet cannot enter clean approval or claim an acoustic,
editorial, or human PASS. Build a new revision after any word or frame change.
Recheck the packet with `check-native` immediately before each native mutation.
Project-local XML/bridge adapters must call `validate_native_packet` before emission;
record their adapter path/hash. A packet is not permission to overwrite approved items.

## STEP 6 — Camera-switch cuts (exact frame, once per stream)
```
ffmpeg scene scan @0.06 → __ACQ_SKILLS__/live-clip/scripts/verify_switches.py
```
- Verification kills gesture false-positives via face-box IoU/height-jump across the cut
  frame; catches subtle "zoomed out a little" switches. Save `switches_only.json`.
- EVERY span is split at every verified switch inside it (`--switch-times` on the XMLs) —
  so keyframing never drags across a framing change.
- **GATE:** verified list exists; spot-check 3 switches by eye (zoom on the cut frame).

## STEP 7 — Machine-ear verify (never trust labels at the edges)
- Cut the actual audio at the resolved spans (ffmpeg concat) → Groq whisper-large-v3 re-ASR
  the head (3s), tail (4s), and EVERY internal seam (±3s window), and READ the assembled cut —
  loop until it reads clean. **Groq needs a browser User-Agent header or Cloudflare 403s
  (error 1010).**
- A transcript can NEVER confirm a word is intact (ASR re-reads clipped words as whole) — it
  catches leaked/missing/doubled words; word integrity requires acoustic review of the actual audio under Assembly Design's boundary procedure; a padding formula cannot certify it.
- Known false-fail classes (do not "fix" these): overlapping-label ghost tokens, AAI-missed
  quiet trailing words (Silero is right), spelled acronyms (SMB), name aliases (Layla→Leila),
  rate-limit JSON as transcript (backoff+retry).
- **GATE:** 0 fails after false-fail filtering. A real fragment ("money. They—") = fix the
  boundary and re-run from STEP 5.

## STEP 8 — Build the approval sequence (ONE timeline, guarded ops)
- **🛑 CODEC GATE first:** ffprobe the master. PPro 25.0 CANNOT decode AV1 (yt-dlp 4K sources
  usually are) — importFiles succeeds but every clip is silently OFFLINE. Do NOT transcode the
  whole master; transcode ONLY each clip's window (span ± ~20s handles, parallel ×3, HEVC
  VideoToolbox ~10M, frame-aligned window start) and build the XML against the per-clip files
  with window-relative in/outs + `media_offsets.json` ({slug:{file,t0}}). H.264/HEVC masters
  need none of this.
- One 16:9 sequence at SOURCE format in the shoot's bin of the active weekly project (create only if absent) via the bridge (or the batch equivalent of
  `live-clip/scripts/live_review_xml.py`): V1/A1 = source-linked pairs, 20s gaps BETWEEN clips,
  one marker per clip named `C## | <readable title> | <hook summary> -> <payoff summary>`.
  Name the combined assembly sequence `01_CUTS__<session>`, and place it in
  `03_SEQUENCES/01_ASSEMBLY`. If the source
  audio lacks one side of the calls (program feed), lay that feed on A2 at exact footprints
  through an accepted typed route with exact source/timing readback; do not hand-roll a mailbox mutation.
- **Use the advanced typed construction route.** → Use skill: `assembly-design`,
  `scripts/apply_native_assembly.py`, on the default profile and exact-project assembly
  scope. It consumes the existing compiler chain and checks native AV links and exact
  source/timeline ticks. Use its audio-plan route for independently chosen sample edges.
  Do not fall back to generic XML import, source-seed construction, raw ExtendScript or
  `move_clip` after a refusal. Preserve the original receipt and fix the specific failed
  precondition. Sequence creation, frame capture and undo claims from the retired
  connector do not establish support on this host. For frame review use the installed
  typed frame schema and check the image; source frames alone do not prove native layout.
  A tool success is not proof: read back source/timeline ticks, speed, linkage, gaps and
  overlaps. Unsupported extra-track construction remains an explicit implementation gap.
  Save the unmodified `get_sequence_structure` response as JSON and run
  `python3 scripts/bridge_readback_guard.py --structure STRUCTURE.json --frame-ticks TICKS`
  (TICKS from `get_sequence_settings.frameRate.ticks`; add `--allow-gap-frames N`
  only for each exact inter-clip gap length authorized by the native packet) before the
  save. Any tiny gap, overlap, off-grid edge, or source/timeline duration mismatch
  blocks construction; reconcile longer intentional gaps against the native packet.
- xmeml rules: full `<file>` def inline on FIRST clipitem only, absolute `file://localhost`
  pathurls, NO standalone wav/mp3 file defs (silently rejected — audio lays go post-import).
- **EVERY ExtendScript op is guarded** — this is Step 0's PER-CALL PROJECT CHECK restated at
  the point of use, the same rule, not a lighter one: first line checks `app.project.name`
  equals the target project — the editor clicks around mid-run and the active project WILL
  switch under you. Wrong project = raise, wait, retry; never proceed on a mismatch.
  `get_project_info` immediately before **every mutating call, individually** — a batch of
  several mutations is not one check, and the check does not carry over to the next call.
- PPro 25.0 gotchas (all learned the hard way): sequences CANNOT be deleted via API (moveBin
  to an archive bin); relink = set_offline → changeMediaPath → VERIFY in a separate call;
  alphaUsage reset to 1 after every relink/import of overlay movs; `setInPoint/setOutPoint`
  FLOOR to frame — pad requests +half a frame (ask 7617.95 to get 7617.9333);
  `trackItem.move(delta)` is relative; bins are `type===2` (not 3) when walking the tree.
- **GATE:** read the sequence back; item count + in/outs match the engine spans exactly;
  integrity scan (no overlaps < −0.005s, no slivers < 0.05s except caption stacks); frame-QC
  one clip (a blank frame at a GAP position is normal — re-probe inside a clip); save; report
  the clip list with durations (`SEG04 PricingCaller in — short 41s, 3 cuts.`). Proceed to Step 8A before handoff.

## STEP 8A — Native readback and human-review preparation

V4 already ran one independent combined editorial/source-fidelity review on the exact
resolved and reconciled dialogue. Do not pay for another editorial review merely because
the same words were placed in Premiere.

- Read back the exact saved project/sequence, source in/out points, order, tracks, gaps,
  speed and A/V parity. Reconcile the kept words from native ranges to the current packet.
- If words/order changed, invalidate the final review, regenerate the design/frame-resolution/reconciliation
  and run one new `final_editorial` review. Timing-only frame adjustments that preserve the
  same complete words require boundary/readback verification, not another prose audit.
- Clean PASS candidates go in `CUTS_APPROVAL`. Subjective but playable pacing or seam cases
  go in a media-bearing `EDITOR_REVIEW` sequence with exact notes. When the user requests
  one review timeline, place both types in one sequence with explicit status and unresolved
  issues on each marker; provisional clips never count as clean approvals. Never substitute
  an empty marker-only holding sequence for clips the editor needs to hear.
- Truly incomplete, misleading, clipped or source-unsupported candidates remain withheld.
- Run the matching approved or provisional packet validator and bridge readback guard
  immediately before saving.
  Record the exact counts and evidence in the run ledger, then show both playable sequences
  to the editor and **STOP**. Structural success is not human approval.

Historical v1-v3 jobs retain their existing executable assembly-review gate. Do not silently
reuse v4's lean handoff for their older review receipts.

## ⏸ EDITOR REVIEW — hard stop between Phase 1 and Phase 2
- The editor adjusts/deletes/approves ON THE TIMELINE. Continue only on his word ("cuts done").
- After his pass, **his items are the truth**: read the timeline live via the bridge
  (ExtendScript dump of V1 clips), group segments into clips by TIMELINE GAPS >5s, identify
  each clip by SOURCE-time ranges — **NEVER by markers** (ripple-deletes strand them; a
  marker-grouped read once put segments under the wrong clip). Note deleted clips; every
  downstream artifact uses the LIVE positions/durations (import can extend a clipitem by frames).
- Never re-derive spans, never rebuild his items, never touch his keyframes — surgical
  razor/delete/move only; keys survive razors (they're media-time).

---

# PHASE 2 — VERTICAL BUILD (only after "cuts done")

**Doodle checkpoint:** → Use skill: [book-doodle](../book-doodle/SKILL.md) on the locked batch before Step 9; follow its proposal/decision workflow and integrate only approved moments.

## STEP 9 — The in-Premiere finish (per approved clip; rolling mode: as each is approved)
1. Read back the approved native items; preserve their source selections and manual changes.
2. → Use skill: `horizontal-to-vertical` for source-linked native framing and camera layouts.
3. → Use skill: `caption-clips` for current editable captions, speaker attribution and verification.
4. → Use skill: `music` when the brief calls for music; do not import historical duration-based music bans.
5. → Use skill: `ad-edit` for paid-media CTA, watermark and transition logic when applicable.
6. Keep independent audio lanes, native video items and editable graphic layers. No flat finished-video import.
   Keep every approved clip in the one combined `02_FINALS__<session>__CURRENT`
   sequence under `03_SEQUENCES/02_FINALS`; use stable `C##` markers and gaps so
   individual clips remain easy to locate and export. Place prior finals snapshots
   under `03_SEQUENCES/03_REVISION_HISTORY`.
7. Run one delivered-file integrity check; audits are opt-in under edit/SKILL.md. Save, show the current sequence,
   then stop for final approval. No export or publishing authorization is inferred.

---

# PHASE 3 — EXPORT + PUSH (only on explicit per-batch approval)

## STEP 10 — Export (current state only, gated)
→ Follow [exact native export](references/native-export.md) and use
`scripts/pp_export_clips.py` for guarded script preparation and rendered-file QA.
The live approved timeline controls every export. Exact range/restore readback,
exact frame counts and both-end/full-file black checks are mandatory; no automatic
head nudge, content trimming or existing-output replacement.
Keep the existing loudness target (−14..−18 LUFS, about −16) and final visual/audio
review. Delivery names use verified source dates; use a publication date only when
the user approves that fallback. Never substitute today's date.

## STEP 11 — Delivery (explicit push only)
- Links-first batch (`frame_batch_push.py <deliver-dir> --maddex-approved --monday`): create
  ALL assets in ONE invocation (view_urls live immediately) → Monday rows from the manifest →
  parallel byte-push (3 workers) → poll transcoded. Duplicate-safe rerun; broken-pipe partials
  (status != transcoded) get DELETED before retry. Never upload one-at-a-time.
- **Revisions (V2+): VERSION STACK** — mondayframeworkflow SKILL §A3, LAW 6/6b/7 apply (pull
  Frame comments → duplicate the current combined finals sequence as
  `R##__BEFORE__02_FINALS__<session>__CURRENT` → read back its UID and move it to
  `03_SEQUENCES/03_REVISION_HISTORY` → record the feedback and affected clip IDs
  with `project_library.py revision` → surgical fixes on the current finals sequence
  → record each new export with `project_library.py export` → version stacks on
  the same links). Test ONE, verify the old link redirects (V2 on top, comments preserved),
  then batch. Monday: status → Final Review by item id only; never touch link columns.

## Archive and retrieval

`project_library.py complete` records the actual project path when editorial work is
complete. After 14 days, `project_library.py archive --remote <configured-B2-remote>`
uploads all project-owned source footage, Premiere files, decision records, revision
notes and finals. It excludes named regenerable cache/preview directories, writes a
SHA-256 manifest, checks the remote copy, and enforces the 6 TB storage alert threshold.
Immediately before archiving, read all Premiere-linked media paths from the exact
project and save one absolute path per line in `10_WORK/Premiere/media_paths.txt`;
the archive command refuses external or missing links. Copy any project-owned media
into `00_SOURCE/` and relink/read back in Premiere before retrying.
Restore to a new local folder with `project_library.py restore`; the restored files
must pass manifest checksums. Open the restored `.prproj` in Premiere, read back the
assembly/finals/revision sequences and check for zero offline media before considering
the original working copy removable. The script never deletes a local project.

---

## FAILURE DISCIPLINE
- 2 consecutive failures of the same operation → STOP and tell the editor what's failing.
- Record newly discovered defects in the job. Change canonical skills only with the
  required authority and at an explicit revision checkpoint, never silently mid-batch.


## Default execution policy

Follow [timed execution](references/timed-execution.md) from intake through local delivery.
Before any final export, use Assembly Design’s [pre-render construction](../assembly-design/references/pre-render-construction.md) command wrapper.
During normal `/edit` runs this replaces repeated delivered-media audits; preserve
native readback and file-integrity checks. Strict audits apply only when requested.

# Premiere capability discovery and routing

Use this reference when a skill reads or changes Premiere. It supplements the existing creative owner; it does not start a different editing workflow. Follow [the execution contract](premiere_execution_contract.md) for project identity, ownership, mutation receipts and recovery.

## Discover only the operation needed

The adjacent `premiere_capabilities.json` is a pinned, searchable inventory snapshot, not a live permission or availability check. It includes operation parameters, backend, minimum version, host eligibility and fixture evidence. Search it rather than loading the whole catalog into context:

```bash
python3 __ACQ_SKILLS__/edit/scripts/premiere_capabilities.py --query "relink"
python3 __ACQ_SKILLS__/edit/scripts/premiere_capabilities.py --host-tested --limit 30
python3 __ACQ_SKILLS__/edit/scripts/premiere_capabilities.py --operation lab_import_prepared_caption_sequence
```

The snapshot covers project/media/bin management, timeline editing and trimming, effects/transitions, Motion/keys, graphics/MOGRTs, audio, color, masks, metadata, proxies/relinking, interchange and export. Read an operation's exact schema and limitations. Catalog presence, an upstream wrapper, or a newer Adobe API does not establish usable access on the current host.

Before execution, discover tools from the selected running connector and compare its version/schema with the snapshot. Use the existing owning stage driver for assembly, reframe, captions or music; these drivers add checks that a raw low-level call does not. Research or unsupported operations stay on disposable fixtures. Do not broaden an operation's fixture evidence into acceptance of every argument, source type or workflow.

## What has actually been demonstrated

On Premiere 26.3.0, one combined synthetic assembly → reframe → native Graphics → music → export fixture demonstrated:

| Capability | Tested scope and practical boundary |
| --- | --- |
| Source-linked assembly | Canonical source-word compiler, linked video/audio groups, exact ticks at 24000/1001, repeated sources and intentional gaps |
| Native vertical reframing | Separate 1080×1920 sequence, item-local sparse Anchor Point keys, native float32 Scale, protected dialogue/source clocks; synthetic framing rather than real-face quality proof |
| Editable Graphics transport | Guarded prepared-sequence import, semantic card/native ID mapping, saved text/style/geometry; distinct from subtitle tracks |
| Targeted caption revisions | Rebuild affected semantic-card segments and preserve unaffected repeated cards; separate revised sequence, not in-place replacement. Native frame-independent exports changed only the planned interval |
| Native music | Existing selection/audition receipt, source-offset-aware new placement within existing sequence duration, measured −12/−24/−60 dB Level values and seven automation keys; source replacement/new tracks/EQ unaccepted |
| Protected composition | Reframe preserves dialogue, caption transfer preserves picture/Motion/audio, music preserves picture and captions, revision preserves PCM |
| Persistence and export | Save/close/reopen with exact bounded snapshots; native video/PCM comparisons, sampled visual review and actual-audio model review. Human listening and click/edit-box behavior remain separate |
| Failure handling | Wrong target, stale state, duplicate/conflicting IDs and writer contention rejected; uncertain partial writes and lost replies retained for inspection without blind replay |

The installed snapshot contains 501 operations, with 12 operations carrying bounded passed postconditions and five observed read operations. These are inventory counts, not a percentage of every Premiere button. Consult per-operation evidence instead of treating these counts as an allowlist.

## Which route to use

Follow [Premiere Agent startup](premiere_start_here.md). The default is now the upgraded
connector for Codex, Claude and CLI stage drivers. Exact-project scopes cover the existing
assembly, audio-edge, reframe, Graphics transfer, music and export tools. General API
research remains on disposable fixtures. A scope does not turn fixture evidence into
universal production acceptance; verify the actual stage result.

The profile's `cwd` locates source, reports and host evidence. Use live `search` and
`schema` for the installed surface; this bundled snapshot is historical. Never hand-edit
evidence statuses or retry a possibly completed mutation through another backend.

## Explicit limits

UXP operations are cataloged but the UXP adapter has not passed local host acceptance. QE remains experimental; only the bounded shot/panel operations described in the reframe guide have local evidence; native SDK feasibility lacks the required local SDK headers. APIs requiring 26.5 are disabled on 26.3. Native subtitle editing is not interchangeable with native Graphics. Appearance, audio, arbitrary source effects/routing and real-face/split-layout quality still require the relevant stage review. Background APIs require Premiere running. UI access authorized for Lab setup/recovery does not authorize UI editing.

## Scoped production reframe

The upgraded reframe profile supports an expiring exact-project scope without widening the Lab fixture root. → Use [horizontal-to-vertical advanced native reframe](../../horizontal-to-vertical/references/advanced-native-reframe.md) for its accepted operations, preparation and evidence requirements. This does not promote unrelated Lab tools to production.

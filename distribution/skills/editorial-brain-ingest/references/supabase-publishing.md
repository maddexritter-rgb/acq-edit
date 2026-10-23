# Publishing packets to the shared Supabase index

The owning project is identified by its confirmed Supabase project ref and private
`editorial_brain` schema. Do not bake a personal project ref or credentials into this
portable skill. The current pilot schema has `source_documents`, `decision_cards`,
`retrieval_events`, `editorial_feedback`, and active `editorial_playbooks`. Inspect the live schema before writing;
local SQL files and old handoffs may be stale. The Supabase connector may not be
present in every Codex or Claude Code task.

## Preflight

1. Confirm the intended project with the user or saved project configuration and
   inspect the live private schema read-only. Confirm the packet's evidence URI is
   accessible to future curators; local-only paths are a temporary pilot limitation.
2. Search by `card_id`, source hash/URI, case ID, and semantic problem for duplicates.
   Compare conflicting cards and versions; do not `ON CONFLICT DO NOTHING` and call
   it success, or overwrite prior evidence silently.
3. Keep `editorial_brain` private. Never expose a secret/service-role key in a skill,
   transcript, browser, or client app. Use the authenticated server-side connector or
   an approved server-side ingest endpoint. Do not make the database publicly writable
   to simplify ingestion.

## Mapping and write

For each validated packet, insert one `source_documents` row with a stable source ID,
the packet URI and SHA-256, `source_kind` (`research`, `sop`,
`assembly_calibration`, or `editor_feedback` in the current schema), exact
`evidence_class`, and a verification note that states what is and is not proven.
Insert one `decision_cards` row: stable `card_id`, source ID, title, problem,
observed choice, transferable lesson, exception, applicable formats, stage, matching
evidence class, status, and revision. Use a transaction. A reviewed SOP/prompt source
may include its complete exact text in the private `source_body` field with a hash
and revision; do not load that entire body into every assembly context. Active
playbooks are separate, versioned, hash-pinned rows and must cite their source IDs.
Match the live constraints;
do not change schema or widen grants ad hoc to make a packet fit. If richer evidence
does not fit, keep it in the packet and link it; propose a migration separately.

Use parameterized writes when a supported connector provides them. If the only
approved interface is a SQL executor, generate safely quoted SQL from the validated
packet with `scripts/prepare_sql.py`, inspect the exact targets and values, then
execute one narrow transaction. The helper prepares **new-card inserts only** and
intentionally fails on duplicate IDs; it does not run SQL or update existing cards.
Handle revisions only after reading the old row and reviewing a specific update that
preserves the previous packet and increments `revision`.
Never concatenate untrusted transcript/comment text into SQL. Do not bulk-import an
entire directory because files are present. A successful SQL result is not a successful
ingest until the inserted rows are read back and a bounded problem search returns the
card with the right stage, format, status, citation, and exception.

The assembly consumer is `find-precedents`' assembly-card lane. It returns at most
3–5 cards to `assembly-design`, with evidence level and exception visible; it does
not choose source words. Exclude the current project and held-out cases. Record actual
human editor feedback only after timeline review. Do not fabricate `retrieval_events`
or `editorial_feedback` from an agent's own judgment. Feedback never automatically
promotes a development card or rewrites a skill.

## Failure state

If the connector is missing, authentication fails, the project is ambiguous, source
identity is unresolved, or readback disagrees, stop the write and preserve the local
packet as `NOT_PUBLISHED`. Report the precise blocker and the next safe step. New
assembly design stops if its live playbook read fails; no local reference may be
represented as a live Supabase response.

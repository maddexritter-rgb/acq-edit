# Execution backend and run mode

Choose these separately and record them in the existing run ledger:

- `mode: assembly-review` builds editable 16:9 cuts and stops for the editor.
- `mode: end-to-end` is selected by an explicit request for raw footage to finished/postable clips or an entire editing pipeline. It authorizes the owning skills' finishing and local exports without repeating the assembly approval question. It does not invent human approval or authorize upload/publishing. Preserve any narrower user stop point.
- `backend: premiere` uses the current Premiere Agent Lab MCP bridge (or its configured CLI), exact-project scope and exclusive ownership. This remains the fallback when no backend is specified or established by the current project.
- `backend: filmcraft` uses the Filmcraft engine/MCP and editable `.fcproj` files. Use it when requested or already established for this project. Read [Filmcraft execution](filmcraft.md).

Carry forward the user's backend choice. Never switch because one operation failed; preserve the failed receipt and resolve the exact issue or report the missing capability. Filmcraft success does not certify Premiere, and a project extension change is not interchange.

## End-to-end orchestration

→ Use the sibling skills in `edit/SKILL.md`'s ownership order. Assembly Design owns the waveform-first cutting method for both backends. RUNBOOK still owns execution and delivery; its interactive assembly/finishing stops apply to assembly-review mode, not a fresh end-to-end authorization.

Keep the intermediate assembly, source links, editable framing/captions and revision history. Read current native state before revisions; manual changes supersede old plans. Do not flatten a completed video into a timeline and call it editable output.

Optional additions requiring a separate creative choice, such as drawing cutaways, are omitted/deferred when not requested; they must not stall the authorized basic finish. Use each owner's current defaults and the established project style. Do not invent creative rules in the backend.

Default to pre-render construction checks and one delivered-file integrity check; run model audits only when explicitly requested. A render with unresolved checks is a review draft, not certified postable output. Preserve the specific unresolved issue and a playable result when possible; ask only for a missing decision that actually blocks the authorized work. Final shipping approval and external delivery remain separate.

For every run, follow [timed execution](timed-execution.md) from the first executable action. Record full wall time, input-cache state, time to first playable clip, boundary work, native construction, captions, exports and verification. Include repairs and agent inspection. Report final human review separately; never present encoding time as end-to-end throughput.

For repeated batches, → Use `assembly-design`'s fast pre-render checks before finishing,
and `horizontal-to-vertical`'s source-range cache binding. Both backends consume the
same current decisions; changed geometry invalidates dependent finishing artifacts.

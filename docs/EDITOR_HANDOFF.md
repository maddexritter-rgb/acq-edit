# Changing editors for an ACQ clip

Ask the user which editor to use for each new editing job unless already specified. Keep
existing project backends fixed. If the user changes their mind, explain that ACQ creates
a linked destination project and reconstructs editable layers from the saved decisions.
It never imports a finished MP4 as the editable result.

Use the source runtime:

```sh
acq-edit --engine filmcraft handoff SOURCE_PROJECT premiere /absolute/project/10_WORK/plan.json
```

Use the destination runtime to import the returned checkpoint:

```sh
acq-edit --engine premiere handoff-import /absolute/project/10_WORK/handoffs/ID/checkpoint.json
acq-edit --engine premiere worker
```

Reverse engine names for Premiere → FilmCraft. Both installations share verified assets and
credentials but use separate native runtimes/configuration/state. The importer copies verified
source bytes and evidence into a new dated project and queues native reconstruction. Originals,
finished versions and feedback are preserved. Repeated import returns the original destination.
An interrupted import retains its reservation and partial project for reconciliation.

If a job/render/native operation is active or uncertain, preparation writes
`waiting-for-safe-checkpoint`. Let the operation settle or reconcile it; resume preparation
with the latest valid plan. Do not kill an editor render or reuse a stale checkpoint. This is
agent-driven resumption, not an automatic background switch. Completed checkpoints require a
fresh native inspection matching the saved fingerprint. Manual edits pause for the editor's
choice; they are never silently discarded.

The agent reads the copied evidence index, maps source IDs/paths, and recompiles owner contracts
against the destination project. Preserve exact cut frames, speech samples, caption text/style,
framing curves and audio. Revalidate every dependent hash; do not edit hashes just to pass.
Unsupported effects, arbitrary project fields, unbound native construction, and missing evidence
return `needs-editor-choice` before a destination is created. Explain what cannot transfer and
ask whether to retain, recreate or explicitly omit it. Preserve the request until answered.

This is an experimental ACQ checkpoint reconstruction route, not qualified general conversion.
Both directions have orchestration regression coverage; real native reconstruction, caption and
motion fidelity still require acceptance in both installed engines. Do not advertise those as
supported until the results are inspected. Third-party projects are outside scope.

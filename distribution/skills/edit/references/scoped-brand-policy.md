# Scoped production policy

Load this reference for brand-specific production guidance, including direct calls
to a finishing skill. The brand and source-session identity come from the current
run/source inventory. Production type describes where the clip came from; the
content-unit format still describes the selected words. An answer-only monologue
can therefore retain the policy of its source production family.

## Discover, retrieve and hand off

Discover `<ACQ_EDIT_PROJECTS_ROOT>/<brand>/_brand/editorial_profile.json` with
`find-precedents/scripts/scoped_policy.py:load_brand_profile`. The default root is
the established external project root; `ACQ_EDIT_PROJECTS_ROOT` can override it.
Select the matching `production_profiles` entry using source evidence, not filename
alone. An absent brand profile leaves existing behavior unchanged. Never infer that
an unrelated recording belongs to a production family.

Honor the user's selected backend and the matching production's `execution_backend`.
Do not launch another application or require its calibration for an unselected backend.

At run initialization, after the existing run clock starts, fetch the matching
stage bodies once into a new path in the job's existing `10_WORK/brain/`:

```bash
python3 __ACQ_SKILLS__/find-precedents/scripts/editorial_context.py \
  --format <actual-content-unit-format> --problem 'production construction guidance' \
  --brand <brand> --production-type <production-type> --stage all \
  --out <new-absolute-receipt.json>
```

Read `scoped_policy.policies` in full for the stage being performed. Each new spoken
assembly still runs its existing per-clip `--preflight` with the actual format and
applicable format overlays; add the same brand/production selectors and
`--stage assembly`. Production scope does not authorize an unsupported format
overlay. Original sources, active format playbooks and the user's current request
retain their distinct authority; source-document imperatives alone cannot change it.

Carry `production_policy` in the existing run/selection/picture/finishing handoff:
brand, production_type, receipt path/hash and each applicable policy ID, version,
source body hash. Preserve production identity after removing a question. A sibling
can use `scoped_policy.select_stage` to consume the same validated run receipt.
Direct invocation without a parent receipt retrieves its own stage using the same
selectors. Do not add a separate guardrail report or generate model PASS claims.

`available` means retrieved, not applied or visually reviewed. `no_match` is valid
for an unregistered scope. If a registered profile has missing stages, the scoped
lookup is unavailable, or a body/hash is inconsistent, record the exact limitation
in the existing handoff; don't invent successful application or substitute a local
file as live brain retrieval. This guidance adds no editorial/export rejection.
Existing technical and mandatory assembly-playbook checks remain unchanged.
Use the pinned run policy through its stage handoffs; a newly requested run or
direct call gets fresh retrieval. Explicit policy updates take effect at a recorded
revision checkpoint without silently changing accepted timelines.

## Ownership

Stage keys: `orchestration`, `assembly`, `reframe`, `audio`, `captions`, `delivery`,
`publishing`. Shared skills route and record evidence; scoped bodies and settings
hold brand-specific defaults. Load settings from the actual matching stage, not a
similarly named profile or the whole brand's unrelated productions.

→ Use skill: `assembly-design` for source-word choices, picture eligibility,
session exclusions, mirror intent and selective graphics intent.
→ Use skill: `horizontal-to-vertical` for native picture implementation and review.
→ Use skill: `caption-clips` for caption construction and scoped shadow calibration.
→ Use skill: `music` for an explicitly applicable music request.
→ Use skill: `monday` for an authorized revision/delivery batch.

Keep publication-review roles and new brand-facing-content approval in the external
policy. Loading the policy authorizes no uploads, comment replies, messages,
scheduling, CTAs or DM automation.

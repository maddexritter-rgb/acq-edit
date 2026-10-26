# Editing skill dependency inventory

The current owner/file/route counts are recorded in `distribution/SOURCE_MANIFEST.json` and `distribution/SKILL_DEPENDENCIES.json`. The opening-headline owner has been removed from the package, exporter and active editing routes. `slop-detector` remains available for requested copy cleanup.

The inventory pins each route's source, line numbers, distributed hash, target owner and availability, plus the complete manifest and reviewed exception policy. A packaged target must have a manifest-owned `SKILL.md` entrypoint.

The scanner reads explicit `Use skill:` instructions, sibling `SKILL.md` links and
normalized skill-root paths. It is a static route inventory; dynamically constructed
paths, implicit prose references, licensed assets, third-party executables and native
capabilities still need their own checks. A packaged route is not proof that its
native execution is implemented or qualified.

## Scoped external routes

Seven source/target pairs are deliberately classified in
`scripts/skill-dependency-policy.json`. These exceptions apply to exact files; they
do not make the target globally optional.

| Target | Scope | Behavior |
| --- | --- | --- |
| `monday` | Two explicitly authorized delivery references | External opt-in; not part of local clip creation/review |
| `cut` | Explicitly retired research source | Historical only; Assembly Design owns active cutting |
| `highlight` | Two optional live-stream references | Unavailable; repair/qualify that workflow before use |
| `copy` | Source-library's conditional video-ideas route | Separate opt-in planning workflow |
| `slack-voice` | Copy cleanup's conditional Slack drafting | Separate opt-in writing workflow; not needed for the ordinary editing loop |

Unknown missing targets stop verification. Stale exceptions also stop verification,
so a removed reference cannot leave an unnoticed blanket allowance. The installer
checks the inventory before creating a runtime and pins its hash and external routes
in the runtime receipt. Doctor exposes those routes separately from private-path
warnings. Existing installations remain unchanged; adopt this package in a fresh
checkout as described in [INSTALLATION.md](INSTALLATION.md).

## Updating the package

After a canonical export, review any newly missing routes and package required owners.
Do not classify a required editing dependency as optional merely to pass verification.
Then regenerate and check the inventory:

```sh
python3 scripts/skill_dependencies.py --write
python3 scripts/skill_dependencies.py
npm run audit:distribution
```

The distribution audit and materializer compare the generated inventory against
actual source hashes and policy. Four tests cover required transitive dependencies,
refusal before runtime creation, exact exception scope, stale exceptions, changed
routes/policy and modified skill contents. The full Python suite passes 182 tests.
These checks establish dependency availability and provenance; real hook copy,
native editable cards, rendering and human review remain separate acceptance work.

A fresh checkout copy in a path containing spaces materialized and verified all 683
files and 38 routed entrypoints, exposed the seven scoped external routes, and
resolved the hook-to-cleanup link inside its own runtime. Repeating installation
preserved every runtime file timestamp. Canonical cleanup skill/metadata hashes
were unchanged. This is development-Mac dependency evidence, not a clean-Mac or
native hook-render acceptance result.

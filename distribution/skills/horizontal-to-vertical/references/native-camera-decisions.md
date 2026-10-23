# Camera decisions belong to Assembly Design

→ Use skill: `assembly-design` [camera decisions](../../assembly-design/references/camera-decisions.md).
Horizontal-to-vertical implements that source-bound shot and panel plan; it does not reselect shots.

Consume its `production_policy` and `mirror_intent`; inspect inherited clip/nest flip
state, apply the intended final state once with native editable controls, and inspect
the composed eyeline, readable text and top clearance. Record unsupported operations
or unsuitable coverage in the existing handoff and return picture choices to the owner.

`scripts/picture_policy.py:mirror_update` computes the item-local change from the
inspected item and contributing parent flip states. Reapplying the same intent is
idempotent; unknown parent state requests inspection rather than assuming no flip.
Bind its plan to the current native item and use the supported effect/control route;
the helper itself applies no effects and cannot establish a correct eyeline from pixels.

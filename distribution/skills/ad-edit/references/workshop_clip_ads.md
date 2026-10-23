# Workshop and event clip ads

Use this route when an approved editorial clip from a workshop, stage session, roundtable,
podcast recording or similar event becomes paid media by adding a CTA. The organic assembly
is owned by `edit` and `assembly-design`; this route must not silently recut it.

## Decide the offer from the teaching

Classify the actual clip, not the file, event or speaker:

- marketing: acquisition, advertising, content, brand, leads, funnels, testimonials or positioning
- sales: scripts, qualification, objections, sales teams, calls, pipeline or closing
- scaling: constraints, systems, leadership, hiring, delegation, operations or growth infrastructure
- other: use the brand profile's generic workshop offer

Choose a current approved CTA for that offer. Compare more than one eligible take when
available and prefer the one whose promise and energy follow naturally from the payoff.
User-deleted, rejected or superseded takes are ineligible.

## Speaker-claim safety

Transcribe the CTA and reject it when its speaker falsely claims involvement in the clip.
This includes claims equivalent to "you just watched me," "I just showed you," or "I just
broke down a business" when that CTA speaker did not appear in the preceding organic.
Generic first-person claims about the offer are allowed when true. Store the CTA transcript,
offer, approval state and participation-claim flag in the plan.

## Preserve the approved cut

- Treat the reviewed organic endpoint as locked. A CTA operation may not shorten it, restore
  removed material or replace source-linked edits.
- Stop captions at the CTA boundary unless the CTA has its own approved caption treatment.
- End the organic watermark at or before the CTA start. Never let it bleed into the CTA.
- Use the profile's transition. For the current workshop pattern, use a restrained red glare
  centered on the cut rather than a one- or two-frame white flash; keep the audio transition
  smooth and audition the join.
- Slides, doodles and B-roll are comprehension devices. If a speaker walks through multiple
  slides, show the relevant slide as each reference changes; one representative slide is not
  enough. If the speaker leaves frame, preserve approved audio only when an accurate visual
  bridge covers the full absence.

## Brand overlay profile

Keep exact assets and brand values outside this reusable skill. The active profile must name
the transparent lockup, placement, opacity and shadow stack. Do not add a stroke unless the
profile explicitly requires it. For light and variable footage, prefer two black shadows: a
tight separation shadow plus a broader ambient shadow. Inspect the actual rendered logo over
the lightest shot; settings alone are not visual acceptance.

The overlay belongs only to the organic portion. It must use the full approved lockup when the
profile calls for both mark and wordmark.

## Required plan and gate

Write a JSON plan with one entry per clip and run:

```bash
python3 scripts/validate_workshop_ad_plan.py PLAN.json --profile BRAND_PROFILE.json
```

Each clip entry must include: `id`, `content_lane`, `cta_offer`, `cta_status`,
`cta_claims_preceding_participation`, `cta_speaker_appears_in_organic`, `organic_end`,
`cta_start`, `watermark_end`, and copies of the active profile's `transition` and
`brand_overlay` objects. Use `cta_status: "approved"` only after checking the current
library and user rejections.

The gate checks topic-to-offer routing, CTA participation claims, rejected CTA status,
watermark/CTA timing, transition profile and overlay construction. A pass proves plan
consistency, not listening quality or editorial acceptance. After the native build, read back
the timeline and verify those same properties on the saved sequence before export.

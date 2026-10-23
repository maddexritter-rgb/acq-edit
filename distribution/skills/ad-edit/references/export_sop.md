# Export SOP — non-negotiables before anything leaves

From the org's standing ad review SOP. **Creative goes straight from editor to media buyers
with no approval step in between — the editor is the gate.** Self-QA against this list.

---

## 1. Disclaimer — on EVERY ad, no exceptions

> **Information not typical. These are examples not guarantees. Results may vary.**

Renderer: `"disclaimer": true` (on by default). It renders small, bottom of frame, above the
platform description zone. Do not ship without it.

## 2. Hard rules

| Rule | Check |
|---|---|
| Cursing bleeped **and** censored in the subtitles | audio + caption text |
| Subtitles: no typos, **lower half**, never over the mouth, in sync | see note below |
| Button/CTA overlays never cover a face or mouth | measure the chin, place below it |
| No Tony Robbins podcast footage | source check |
| No Alex with celebrities | source check |
| Nothing unflattering to the principals | eyes pass |
| No mention of investor losses | transcript scan |

**On "subtitles lower half":** that rule comes from the organic short-form standard. Paid ads
in this house style run a *big hook headline up top* for the first ~5s (see
`ad_style_spec.md`) — that is deliberate and matches shipped ads. The lower-half rule still
governs the running caption track. If in doubt, ask the reviewer rather than guessing.

## 3. Dimensions

9:16 · 16:9 · 1:1. **~90% of what runs is 9:16** — build that first.

## 4. Naming

- Footage folders: `YYYYMMDD_TALENT_LOCATION_TYPE` (e.g. `20260501_ALEX_StudioA_DTC_Ads`)
- Short-form files: `ALEX_SF_<FORMAT>_<Topic>_<Editor>_<date>_FINAL`

Naming has caused real incidents — a "TY page VSL" that was actually an ad. Get it right at
export, not later.

## 5. Handoff — verbatim template

Post in the paid-creative channel, tag the AP lead + both media buyers:

```
New Upload Alert: <batch name>
‣ Category:  Ads / AI Ads / VSL / Testimonials / SOPs
‣ Offer:     Scaling Roadmap / Scaling Workshop / Marketing Workshop / Offers / Constraint Finder
‣ Frame Review:  <f.io link>
‣ Google Drive:  <finished files>
‣ Raw Footage:   <YYYYMMDD_TALENT_LOCATION_TYPE folder>
‣ Paid Media Tracker: <link>
‣ Status:    Ready for review
‣ Notes:
```

Then log each piece in the Paid Media Tracking Sheet.

## 6. Volume discipline

A 650-ad drop once created a QA jam nobody could work through. **Group deliveries by batch,
keep them varied, never send twenty versions of one idea.** The target is 30 *varied* pieces
a week, not 30 polished ones — volume exists to buy lottery tickets, and the hit rate is
roughly 3 standouts per 30–50 versions.

---

## Known AI failure modes — start past these

Already learned the hard way on previous vendor batches:

- **No blinking.** Avatars don't blink; it reads uncanny. Open fix item since mid-July.
- **Hue/colour drift between scenes** — a Seedance artifact. Grade for it.
- **Speed:** house treatment is a bump to **1.2×**. Past that the speech tuning gets strange.
  Solving faster-without-artifacts is a real unlock.
- **Backdrops must be screenshots of real footage**, not AI-generated scenes. Real backgrounds
  hold up; generated ones don't.
- **The B-roll library is stale** — old advisors, smart boards, formats that don't match the
  current presentation. Flag what you can't use; don't quietly ship it.
- **Full-AI ads underperformed.** Metrics worse across the board, 2–3 calls, none standout,
  none still running. This is exactly why the *hybrid* callout (AI for the callout only,
  proven footage for the body) is the priority format.

## What's actually working (the receipts)

- Two recent organic-to-ad winners hit **1.9× and 4× ROAS**; blended Meta average is ~**2×**.
- Both were the same format: **organic clip + CTA cut onto the end**. One cuts abruptly to the
  CTA at 23s. Not polished. It worked.
- Take the note: polish is not the variable. Volume and variety are.

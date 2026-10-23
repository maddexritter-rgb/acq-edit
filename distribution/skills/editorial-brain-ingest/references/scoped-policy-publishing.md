# Publish a scoped production policy

Use this lane when the user explicitly adopts a production policy for one brand.
Keep the original document's draft/review status and the user's corrections distinct.
This is not automatic promotion of feedback into a universal playbook or verified final.

1. Preserve a versioned original in the external brand folder. Pin original bytes
   and extracted-text hashes separately. Create source-document rows for the original
   and each derived stage body, with exact source locators and verification limits.
2. Inspect live schema and duplicates as in [Supabase publishing](supabase-publishing.md).
   Insert versioned `editorial_brain.scoped_policy_bindings`: policy ID/version,
   brand, production_type, stage, derived source_id, original_source_id, status,
   priority_note and optional machine-readable settings. One active binding per
   brand/production/stage; preserve prior versions when replacing a policy.
3. Keep bindings private with no anonymous/authenticated Data API access. The
   authenticated retrieval Edge Function uses the service-only
   `public.editorial_scoped_policy` SECURITY INVOKER RPC. Do not grant public access
   or change the existing format-policy indexes to accommodate a brand rule.
4. Read back both original and derived rows. Retrieve each intended stage through
   `editorial_context.py --brand <brand> --production-type <production> --stage <stage>`;
   verify versions, exact scope and body hashes, plus unrelated-brand/production
   isolation and unchanged legacy format retrieval. `--stage all` is a run handoff.
5. Store discovery IDs and calibration references in the external brand's
   `_brand/editorial_profile.json`. Generic skills route through the shared
   [scoped policy procedure](../../edit/references/scoped-brand-policy.md).

No synthetic reviewer feedback, automatic verified-final cards or fabricated
application claims. Source copying and retrieval do not prove a good cut, source
listening, native framing, human review, delivery or publication approval.

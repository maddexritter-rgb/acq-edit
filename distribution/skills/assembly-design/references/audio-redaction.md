# User-requested audio redaction

Assembly Design owns the identity decision, exact occurrence and audio interval.
Use only an explicitly requested concealment, with a role label supported by the
source or editor. Preserve the raw transcript and source word IDs; record the
replacement separately. A caption substitution alone does not conceal spoken audio.

Resolve the entire name against the actual played dialogue waveform, including
consonants and releases. Put the small blend ramps outside intelligible name speech,
inside inspected safe margins. Never low-pass the original name and assume it is
unintelligible. Replace the central speech with silence or a quiet synthetic masked
sound as requested; retain sample count, sync and all samples outside the interval.
Work on the final dialogue stem after enhancement, before adding music. Keep the
original stem and reference the new project-owned stem in either execution backend.
For a soft mask, use `scripts/redact_dialogue.py` with the inspected sample interval.
Listen to this targeted interval when deciding whether the identity is concealed;
waveform checks alone cannot establish unintelligibility.

Hand caption-clips the same source word IDs and output interval, plus the approved
bracketed role label. The caption owner implements the display-only substitution on
foreground and shadow layers without changing neighboring speech clocks. Do not add
bold or italics automatically; apply the requested or existing style. If source cuts
change, remap the redaction and caption together before rendering. This is a local
construction step, not a whole-clip audit loop.

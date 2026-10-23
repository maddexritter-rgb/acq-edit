# Mozi audio + music presets (Q&A / Hotline)

Premiere/AudioUnit presets from the Team Alex SOP drop, preserved verbatim in `presets/audio/` (use these in Premiere).
Below = what each chain does + a practical **ffmpeg** approximation for our automated `qa_build` pipeline (we don't run
Premiere). Exact Premiere param values live in the `.prfpset.xml` blobs; the ffmpeg values are sensible starting points —
tune by ear against a reference clip.

## 1. Mozi Clean Audio Preset — the voice chain (Alex + guest/caller dialogue)
Premiere chain: **DeNoise → Parametric Equalizer (5 bands + low/high shelf) → Hard Limiter → Volume (Auto + Make-Up Gain)**.
Intent: clean, present, broadcast-loud spoken voice.
ffmpeg approximation (apply per-voice before the final loudnorm):
```
afftdn=nf=-25,                                   # DeNoise (spectral)
highpass=f=80, lowpass=f=12000,                  # roll off rumble + hiss
equalizer=f=200:t=q:w=1:g=-2,                    # tame low-mud
equalizer=f=3000:t=q:w=1.5:g=3,                  # presence/intelligibility
equalizer=f=8000:t=h:g=2,                        # air (high shelf)
acompressor=threshold=-18dB:ratio=3:attack=5:release=120:makeup=3,
alimiter=limit=-1.5dB                            # Hard Limiter
```
Then the existing 2-pass `loudnorm=I=-14:TP=-1.5` in qa_build. (qa_build currently does loudnorm only — adding this
chain ahead of it would match "Mozi Clean Audio." TODO if we want the exact house sound.)

## 2. Mozi Preset For Music (2026) — the background-music bed
Premiere chain: **Parametric EQ (5 bands) → Stereo Expander → Volume** (+ optional AUMatrixReverb; ships a "NO REVERB" variant).
Intent: widen + EQ the music so it sits under the voice without masking it.
ffmpeg approximation for the music track before mixing under dialogue:
```
highpass=f=40, equalizer=f=300:t=q:w=1:g=-3,     # carve space for voice mids
equalizer=f=2500:t=q:w=2:g=-4,                   # duck where speech presence lives
extrastereo=m=1.6,                               # Stereo Expander (widen)
volume=-18dB                                     # sits ~16–20 LU under the -14 voice
```
Prefer **sidechain ducking** so music dips under speech:
`[music][voice]sidechaincompress=threshold=0.05:ratio=8:attack=5:release=300`.
Use the **NO-REVERB** variant by default; reverb only for stylistic beds.

## 3. Mozi Custom Reverb Fade — AUMatrixReverb tail
A reverb tail for fade-outs / transitions (e.g. let a line ring out into a cut). ffmpeg: `aecho=0.8:0.7:60:0.3` or an
`afir` convolution with a short hall IR, applied only to the tail of the segment being faded.

## 4. Mozi Hotline – Flashback Vocal Reverb (OBA) — hotline-only
A vocal reverb for the Hotline "flashback"/phone feel on the caller. ffmpeg approximation for caller audio:
```
aecho=0.6:0.5:90:0.35, highpass=f=300, lowpass=f=3400   # reverb + telephone band-limit (phone feel)
```
Apply ONLY to the caller in hotline clips (not Alex), and keep it subtle — the SOP still wants information density over the
"live call" illusion.

## Notes
- We always feed clean mics (lav/board), never camera audio. qa_build picks the active-speaker mic per run.
- These are starting points — A/B against an actual Oliver/published clip and trust your ears over the numbers.

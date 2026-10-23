#!/usr/bin/env python3
"""speaker_diarize.py — PER-WORD speaker (Alex vs guest) for Q&A captions.

The EDL 'speaker' is per CAMERA SHOT, so a short turn-response word ("yes", "cool", "no")
spoken at a turn boundary gets mis-attributed to whoever held the previous shot — coloring
the caption for the WRONG speaker (Alex's "cool" painted yellow; the guest's "yes" painted
white). Two signals fix it, in priority order:

  1. MIC ENERGY (ground truth): Q&A clips have separate per-speaker mics, so whoever's mic is
     louder during a word said it. Trusted outright when one mic wins by >= CONF dB.
  2. CONVERSATIONAL TURN-TAKING (Maddex): at a turn boundary the mics are low-margin
     (bleed/overlap) and can't decide. There, a short REPLY token ("yes"/"cool"/"right") belongs
     to the RESPONDER — i.e. the OTHER speaker from the word before it. That's why Alex's "cool"
     after the guest's line is Alex, and the guest's "yes" after Alex's "are you the biggest?"
     is the guest, even when the two mics read ~equal.
  3. EDL shot-speaker — fallback only when neither signal applies.

Used by edit/scripts/qa_assembly.py AND qa_build.py so the rule is identical everywhere.
"""
import os, math, subprocess

_SR = 16000
CONF = 6.0   # mic margin (dB) trusted outright
SOFT = 3.0   # weak mic lean, used only when the word is NOT a turn-reply token
RESPONSE = {"yes", "yeah", "yep", "yup", "no", "nope", "cool", "okay", "ok", "right", "exactly",
            "sure", "totally", "absolutely", "correct", "gotcha", "nice", "wow", "agreed",
            "perfect", "great"}


def _load_mic(name, cam_dir, ff, max_t):
    p = name if os.path.isabs(name) else f"{cam_dir}/{name}"
    if not os.path.exists(p):
        return None
    raw = subprocess.run([ff, "-v", "error", "-ss", "0", "-t", f"{max_t:.3f}", "-i", p,
                          "-ac", "1", "-ar", str(_SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    if not raw:
        return None
    import numpy as np
    return np.frombuffer(raw, dtype=np.float32)


def _bare(s):
    return "".join(c for c in str(s).lower() if c.isalpha())


def resolve_speakers(words, segdur, segs, speaker_at, spk_mic, cam_dir, ff="ffmpeg", debug=False):
    """Return (guest_index_set, per_word_list[(speaker, mic_ddb_or_None)])."""
    import numpy as np
    max_t = max((ve for _, ve in segdur), default=0) + 1.0
    amic = _load_mic(spk_mic["alex"], cam_dir, ff, max_t) if spk_mic.get("alex") else None
    gmic = _load_mic(spk_mic["guest"], cam_dir, ff, max_t) if spk_mic.get("guest") else None

    # clip-time -> mic-source-time (cumulative segdur; segdur stores mic times)
    clipcum, tt = [], 0.0
    for i in range(len(segs)):
        d = segdur[i][1] - segdur[i][0]; clipcum.append((tt, tt + d, segdur[i][0])); tt += d

    def mic_t(ct):
        for c0, c1, m0 in clipcum:
            if c0 <= ct < c1:
                return m0 + (ct - c0)
        return clipcum[-1][2] + (ct - clipcum[-1][0]) if clipcum else ct

    def rms(sig, t0, t1):
        if sig is None:
            return 0.0
        a = max(0, int((t0 - 0.04) * _SR)); b = min(len(sig), int((t1 + 0.04) * _SR))
        if b <= a:
            return 0.0
        s = sig[a:b]; return float(np.sqrt(np.mean(s * s)))

    def feats(w):
        if amic is None or gmic is None:
            return (None, 0.0, 0.0)
        mt0, mt1 = mic_t(float(w["start"])), mic_t(float(w["end"]))
        ra, rg = rms(amic, mt0, mt1), rms(gmic, mt0, mt1)
        if ra <= 1e-7 and rg <= 1e-7:
            return (None, ra, rg)
        return (20 * math.log10((rg + 1e-9) / (ra + 1e-9)), ra, rg)   # ddb>0 => guest louder

    import statistics as _st
    db = lambda r: (20 * math.log10(r + 1e-9))
    feat = [feats(w) for w in words]

    # ABSOLUTE speech floor: word-tails / pauses / mic bleed read LOW on BOTH mics. A word is only
    # mic-decidable if its LOUDER mic is at real speech level (>= ABS_FLOOR dB). Below that, the mic
    # comparison is bleed noise — fall back to the shot-speaker.
    ABS_FLOOR = -40.0

    # CALIBRATE to THIS clip's mics, anchored on the EDL shot-labels (mostly right). One mic can sit
    # hotter than the other (gain/proximity), so "louder = guest" is wrong in general — instead learn
    # the per-clip midpoint between how shot-guest vs shot-alex words read, and only trust the mic if
    # the two anchors actually SEPARATE. If they don't (poor isolation, e.g. swindle's guest barely on
    # any mic), mic stays OFF and we use the shot-speaker + conversational turn-taking. This is what
    # makes it robust: the mic only overrides the editor's shot-call when it can clearly tell them apart.
    g_anc = [ddb for (w, (ddb, ra, rg)) in zip(words, feat)
             if ddb is not None and db(max(ra, rg)) >= ABS_FLOOR and speaker_at(float(w["start"])) == "guest"]
    a_anc = [ddb for (w, (ddb, ra, rg)) in zip(words, feat)
             if ddb is not None and db(max(ra, rg)) >= ABS_FLOOR and speaker_at(float(w["start"])) == "alex"]
    SEP_MIN, CONF_MARGIN, SOFT_MARGIN, STRONG = 6.0, 6.0, 3.0, 12.0
    mic_ok, mid = False, 0.0
    if len(g_anc) >= 3 and len(a_anc) >= 3:
        gm, am = _st.median(g_anc), _st.median(a_anc)
        if gm - am >= SEP_MIN:                              # mics demonstrably separate the speakers
            mic_ok, mid = True, (gm + am) / 2.0

    # Only OVERRIDE the editor's shot-call when the clip's mics demonstrably separate the speakers
    # (mic_ok). If they don't (poor isolation — e.g. swindle's guest barely on any mic, Alex's lav
    # ~17 dB hot even on the guest's words), the mic and the turn-taking heuristic both mislead, so
    # we trust the shot-speaker entirely. When the mics ARE good, the calibrated mic is ground truth
    # and turn-taking only resolves the quiet/ambiguous reply words it can't call.
    other = lambda sp: "alex" if sp == "guest" else "guest"
    spk, prev = [], None
    for w, (ddb, ra, rg) in zip(words, feat):
        prior = speaker_at(float(w["start"]))
        if not mic_ok:
            sp = prior                                      # mics don't separate -> trust the shot-call
        else:
            loud = (ddb is not None) and (db(max(ra, rg)) >= ABS_FLOOR)
            if loud and abs(ddb - mid) >= CONF_MARGIN:
                sp = "guest" if ddb > mid else "alex"       # confident (calibrated) mic = ground truth; beats turn-taking
            elif _bare(w["word"]) in RESPONSE and prev is not None:
                sp = other(prev)                            # quiet/ambiguous reply at a turn -> the responder
            elif loud and abs(ddb - mid) >= SOFT_MARGIN:
                sp = "guest" if ddb > mid else "alex"       # soft (calibrated) mic lean
            else:
                sp = prior                                  # too close to call -> trust the shot-speaker
        spk.append((sp, ddb, ra, rg)); prev = sp

    guest = {i for i, t in enumerate(spk) if t[0] == "guest"}
    mic_on = amic is not None and gmic is not None
    src = (f"calibrated mic (mid {mid:+.0f}dB, anchors g={len(g_anc)}/a={len(a_anc)})" if mic_ok
           else ("mics DON'T separate -> shot-speaker + turn-taking" if mic_on else "no per-speaker mics -> shot-speaker"))
    print(f"  [captions] per-word speaker: {src}; {len(guest)} guest / {len(words) - len(guest)} alex", flush=True)
    if debug:
        for i, (w, (s, ddb, ra, rg)) in enumerate(zip(words, spk)):
            pr = speaker_at(float(w["start"]))
            flag = " *FLIP*" if s != pr else ""
            low = " LOW" if (ddb is None or db(max(ra, rg)) < ABS_FLOOR) else ""
            d = f"d{ddb:+.0f} a{db(ra):.0f} g{db(rg):.0f}" if ddb is not None else "prior"
            print(f"    w{i:3d} {float(w['start']):6.2f}s {str(w['word'])[:13]:13} "
                  f"shot={pr:5} -> {s:5} ({d}){low}{flag}", flush=True)
    return guest, spk

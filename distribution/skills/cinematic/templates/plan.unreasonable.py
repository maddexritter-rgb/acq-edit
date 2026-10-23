#!/usr/bin/env python3
"""plan_v2.py — shot plan for "Unreasonable To Fail" (Modern Wisdom x Hormozi).

Cut comes from /edit: cut/cut_spans.json, two spans, 24.40s total.
Caption timing is driven ENTIRELY by measured word onsets in cut/timeline_words.json.

🛑 EVERY SHOT BOUNDARY BELOW IS A CAPTION CUE BOUNDARY. A cut landing mid-cue splits the cue
across two plates and no single ink colour is right for both halves — gen_captions.py gates it.
"""
import json, os
D = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.expanduser("__ACQ_ASSETS__/assets/broll_lib/pp")   # pp/ = H.264, never raw/
B = lambda n: f"{LIB}/{n}.mp4"

DUR, TAIL = 23.857, 1.70   # 24.399 minus the 0.52s host interjection ("Admission.") lifted at 12.58

# 🛑 MEASURED WITH cropdetect, NOT ASSUMED. Both Whiplash clips are 2.4:1 cinemascope baked into
# a 1080 frame: real picture is 1920x800 with a 140px black bar top and bottom. Declaring them as
# 1080 scaled the BARS into the card, so the b-roll sat letterboxed inside the rounded square
# instead of filling it. Every film source must be cropdetect-ed before it goes in the CROP table.
CROP = {
    "whiplash_practice": (1920, 800, 0, 140),
    "whiplash_finale":   (1920, 800, 0, 140),
}

# kind: a=A-roll · b=film · card=flat colour · dot=white card + black dot
SHOTS = [
 # ---- THEMED B-ROLL: every cutaway is WHIPLASH. One film, one argument. The whole movie is
 # "do so much volume that it would be unreasonable to fail" taken to its end point, so the
 # b-roll IS the thesis rather than decoration. Practice reel = the grind (cool, harsh);
 # finale reel = the performance (warm gold). The tonal flip lands on the pivot at 12.68.
 dict(t0=0.00,  t1=3.20,  k="a", ss=0.00),                                 # hook, hold
 # "so much volume" -> the kit, then the grind
 dict(t0=3.20,  t1=3.92,  k="b", src="whiplash_practice", ss=3.0),
 dict(t0=3.92,  t1=5.08,  k="b", src="whiplash_practice", ss=15.0),
 dict(t0=5.08,  t1=6.54,  k="a", ss=5.08),
 dict(t0=6.54,  t1=8.14,  k="b", src="whiplash_practice", ss=39.0),        # "if you do fail"
 dict(t0=8.14,  t1=10.58, k="a", ss=8.14),                                 # "I did my part"
 dict(t0=10.58,  t1=11.78, k="b", src="whiplash_practice", ss=33.0),        # the sweat = the part he did
 dict(t0=11.78,  t1=12.86, k="a", ss=11.78),
 # PIVOT -> "people think after they fail". Tone flips to the finale's warm gold.
 dict(t0=12.86,  t1=13.52, k="b", src="whiplash_finale",   ss=60.0),        # Fletcher, the judgment
 dict(t0=13.52,  t1=14.30, k="b", src="whiplash_finale",   ss=300.0),
 dict(t0=14.30,  t1=16.06, k="a", ss=14.82),
 dict(t0=16.06,  t1=16.90, k="b", src="whiplash_finale",   ss=540.0),       # the rumination
 dict(t0=16.90,  t1=17.68, k="a", ss=17.42),
 # "think about what you're going to say when you fail" -> the pre-mortem, played forward
 dict(t0=17.68,  t1=18.96, k="b", src="whiplash_finale",   ss=460.0),
 dict(t0=18.96,  t1=19.88, k="b", src="whiplash_finale",   ss=380.0),
 dict(t0=19.88,  t1=21.26, k="a", ss=20.40),
 dict(t0=21.26,  t1=22.34, k="card", fill="black"),                         # "BEFORE YOU FAIL"
 dict(t0=22.34,  t1=DUR,   k="a", ss=22.86),                                # payoff, hold
]

FLASH = [12.86, 17.68, 21.26]      # 2-frame white flash at the three turns

def words():
    return json.load(open(f"{D}/cut/timeline_words.json"))

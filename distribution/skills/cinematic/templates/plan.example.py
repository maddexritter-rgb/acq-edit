#!/usr/bin/env python3
"""plan.py — the per-job shot plan. COPY this into <job>/10_WORK/plan.py and edit.

DUR must match the LOCKED cut from /edit (cut/cuts.json). TAIL is the black run-out.
Caption timing is driven ENTIRELY by measured word onsets in cut/timeline_words.json.
B-roll carries measured letterbox crops so every card FILLS the 980 square (V1 note 3).
"""
import json, os
D = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.expanduser("__ACQ_ASSETS__/assets/broll_lib/pp")   # H.264, never raw/
B = lambda n: f"{LIB}/{n}.mp4"

DUR, TAIL = 32.12, 0.15          # <- DUR from your locked cut. TAIL 0.15: see RUNBOOK 'THE TAIL'.

# --- required by build_xml.py / preview.py ------------------------------------
# build_xml.py / preview.py read these from <project>/premiere/assets/ :
#   AROLL_window.mp4  — the cut zone transcoded to H.264 (PPro cannot decode AV1)
#   VOICE_cut.wav     — the CUT voice: cuts.json spans concatenated with 12ms edge fades
#                       🛑 NEVER a continuous pull from the master — that desyncs by exactly
#                          however much /edit removed, and it shows up worst at the ending
#   MUSIC_bed.wav     — prenormalised: -vn (strips cover art), loudnorm I=-29, fades baked
# ------------------------------------------------------------------------------

# measured with cropdetect — strips the film letterbox so the card fills the square
CROP = {
    "matrix_white_void":     (1920, 1080, 0, 0),
    "whiplash_practice":     (1920, 800, 0, 140),
    "whiplash_finale":       (1920, 800, 0, 140),
    "american_psycho_office":(1920, 800, 0, 140),
    "social_network_coding": (1920, 798, 0, 0),
    "wolf_party":            (1280, 534, 0, 0),
}

# kind: a=A-roll · b=film · card=flat colour · dot=white card + black dot · split=stacked pair
SHOTS = [
 dict(t0=0.00,  t1=3.10,  k="a",    ss=0.00),
 dict(t0=3.10,  t1=4.62,  k="b", src="matrix_white_void",      ss=9.5),
 dict(t0=4.62,  t1=6.33,  k="b", src="matrix_white_void",      ss=244.0),
 dict(t0=6.33,  t1=7.63,  k="card", fill="white"),
 dict(t0=7.63,  t1=8.03,  k="dot"),
 dict(t0=8.03,  t1=10.43, k="a",    ss=8.03),
 dict(t0=10.43, t1=11.79, k="dot"),                                  # INTERSTITIAL
 dict(t0=11.79, t1=13.01, k="a",    ss=11.79),
 dict(t0=13.01, t1=14.75, k="b", src="whiplash_practice",       ss=29.6),
 dict(t0=14.75, t1=16.37, k="b", src="social_network_coding",   ss=198.0),
 dict(t0=16.37, t1=18.06, k="a",    ss=16.37),
 dict(t0=18.06, t1=19.08, k="b", src="american_psycho_office",  ss=69.8),
 dict(t0=19.08, t1=20.00, k="b", src="wolf_party",              ss=7.5),
 dict(t0=20.00, t1=20.80, k="b", src="wolf_party",              ss=18.5),
 dict(t0=20.80, t1=21.22, k="split", top="wolf_party", tss=22.6,
                                     bot="social_network_coding", bss=234.0),
 dict(t0=21.22, t1=22.56, k="a",    ss=21.22),
 dict(t0=22.56, t1=23.68, k="b", src="whiplash_practice",       ss=20.2),
 dict(t0=23.68, t1=24.84, k="b", src="whiplash_practice",       ss=23.4),
 dict(t0=24.84, t1=26.32, k="a",    ss=24.84),
 dict(t0=26.32, t1=27.58, k="b", src="social_network_coding",   ss=162.0),
 dict(t0=27.58, t1=28.54, k="b", src="social_network_coding",   ss=270.5),
 dict(t0=28.54, t1=29.60, k="b", src="whiplash_finale",         ss=476.0),
 dict(t0=29.60, t1=30.06, k="card", fill="black"),                   # INTERSTITIAL invert
 dict(t0=30.06, t1=DUR,   k="a",    ss=30.06),
]

FLASH = [10.43, 20.80, 29.60]      # 2-frame white flash at the three turns

G, WH, BK = "white", "white", "black"   # MEASURED: 97% of reference caption text is
# pure white (mean RGB 252.7,251.8,251.1). The gold gradient was my invention — retired.
LEFT   = dict(x=70,  y=430, align="left")
CENTRE = dict(x=490, y=500, align="center")
LOW    = dict(x=490, y=760, align="center")

# i0/i1 = word indices in timeline_words.json — the caption appears on word i0's MEASURED onset
GROUPS = [
 dict(i0=0,  i1=3,  lines=[[("if you had a", "sm")]],                            lay=dict(**LEFT, fill=G)),
 dict(i0=4,  i1=5,  lines=[[("if you had a", "sm")], [("WHITE ROOM", "hero")]],   lay=dict(**LEFT, fill=G)),
 dict(i0=6,  i1=10, lines=[[("WHITE ROOM", "hero")], [("locked into", "mid")]],   lay=dict(x=70, y=470, align="left", fill=G)),
 dict(i0=11, i1=12, lines=[[("and there", "mid")]],                               lay=dict(**CENTRE, fill=WH)),
 dict(i0=13, i1=14, lines=[[("was", "sm")], [("NOTHING", "hero")]],               lay=dict(x=490, y=470, align="center", fill=WH)),
 dict(i0=15, i1=18, lines=[[("in the white room", "mid")]],                       lay=dict(**CENTRE, fill=WH)),
 dict(i0=19, i1=21, lines=[[("except for one", "serif_sm")]],                     lay=dict(**CENTRE, fill=BK)),
 dict(i0=22, i1=23, lines=[[("BLACK DOT", "hero")]],                              lay=dict(**LOW,    fill=BK)),
 dict(i0=24, i1=26, lines=[[("what is the", "sm")]],                              lay=dict(**LEFT, fill=G)),
 dict(i0=27, i1=29, lines=[[("what is the", "sm")], [("MOST INTERESTING", "mid")]], lay=dict(**LEFT, fill=G)),
 dict(i0=30, i1=32, lines=[[("MOST INTERESTING", "mid")], [("thing in that room?", "sm")]], lay=dict(x=70, y=470, align="left", fill=G)),
 dict(i0=33, i1=36, lines=[[("the one black dot.", "serif")]],                    lay=dict(**LOW,    fill=BK)),
 dict(i0=37, i1=39, lines=[[("and so people", "mid")]],                           lay=dict(x=70, y=470, align="left", fill=G)),
 dict(i0=40, i1=40, lines=[[("STRUGGLE", "hero")]],                               lay=dict(**CENTRE, fill=WH)),
 dict(i0=41, i1=43, lines=[[("to get", "sm")], [("motivated", "mid")]],           lay=dict(x=490, y=470, align="center", fill=WH)),
 dict(i0=44, i1=46, lines=[[("to do", "sm")]],                                    lay=dict(**CENTRE, fill=WH)),
 dict(i0=47, i1=48, lines=[[("THE WORK", "hero")]],                               lay=dict(**CENTRE, fill=WH)),
 dict(i0=49, i1=50, lines=[[("because there are", "sm")]],                        lay=dict(x=70, y=470, align="left", fill=G)),
 dict(i0=51, i1=51, lines=[[("other", "mid")]],                                   lay=dict(**CENTRE, fill=WH)),
 dict(i0=52, i1=53, lines=[[("MORE", "hero")], [("INTERESTING", "mid")]],         lay=dict(x=490, y=460, align="center", fill=WH)),
 dict(i0=54, i1=57, lines=[[("things to do", "mid")]],                            lay=dict(**CENTRE, fill=WH)),
 dict(i0=58, i1=59, lines=[[("than", "sm")], [("THE WORK", "hero")]],             lay=dict(x=490, y=440, align="center", fill=WH)),
 dict(i0=60, i1=64, lines=[[("and so you're", "sm")], [("not going to", "mid")]], lay=dict(x=70, y=450, align="left", fill=G)),
 dict(i0=66, i1=66, lines=[[("WILLPOWER", "hero")]],                              lay=dict(**CENTRE, fill=WH)),
 dict(i0=67, i1=69, lines=[[("your way", "sm")], [("through", "mid")]],           lay=dict(x=490, y=470, align="center", fill=WH)),
 dict(i0=70, i1=73, lines=[[("making work", "sm")], [("more interesting", "mid")]], lay=dict(x=490, y=470, align="center", fill=WH)),
 dict(i0=74, i1=76, lines=[[("but you can", "sm")]],                              lay=dict(**LEFT, fill=G)),
 dict(i0=77, i1=78, lines=[[("but you can", "sm")], [("ABSOLUTELY", "hero")]],    lay=dict(**LEFT, fill=G)),
 dict(i0=79, i1=81, lines=[[("put yourself", "sm")], [("in a", "mid")]],          lay=dict(x=490, y=470, align="center", fill=WH)),
 dict(i0=82, i1=83, lines=[[("SITUATION", "hero")], [("where", "sm")]],           lay=dict(x=490, y=460, align="center", fill=WH)),
 dict(i0=84, i1=85, lines=[[("work becomes", "mid")]],                            lay=dict(**CENTRE, fill=WH)),
 dict(i0=86, i1=89, lines=[[("the most", "sm")], [("INTERESTING", "mid")], [("THING", "hero")]], lay=dict(x=490, y=430, align="center", fill=WH)),
 dict(i0=90, i1=90, lines=[[("and", "serif_sm")]],                                lay=dict(**CENTRE, fill=WH)),
 dict(i0=91, i1=93, lines=[[("THAT IS HOW", "mid")]],                             lay=dict(x=70, y=470, align="left", fill=G)),
 dict(i0=94, i1=96, lines=[[("THAT IS HOW", "mid")], [("YOU DO A", "mid")]],      lay=dict(x=70, y=440, align="left", fill=G)),
 dict(i0=97, i1=99, lines=[[("THAT IS HOW", "mid")], [("YOU DO A", "mid")],
                            [("SHITLOAD", "hero")], [("OF WORK.", "mid")]],       lay=dict(x=70, y=400, align="left", fill=G)),
]

def words():
    return json.load(open(f"{D}/cut/timeline_words.json"))

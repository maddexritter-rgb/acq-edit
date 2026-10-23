#!/usr/bin/env python3
"""Regression: a camera cut starts a fresh caption card even when Y is unchanged."""
from __future__ import annotations
import json, re, subprocess, tempfile
from pathlib import Path

SKILL=Path(__file__).resolve().parents[1]
GEN=SKILL/'scripts/generate_spice.py'
PRESET=SKILL/'presets/spice.json'

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    words={'words':[
        {'word':'you','start':0.00,'end':0.20},
        {'word':'the','start':0.20,'end':0.40},
        {'word':'R','start':0.40,'end':0.60},
    ]}
    # Same Y on both shots proves the boundary is semantic, not a height-change side effect.
    layout={'meta':{'fps':25.0},'segments':[
        {'start_i':0,'end_i':4,'safe_y_pct':0.60,'camera':'angle_a'},
        {'start_i':5,'end_i':24,'safe_y_pct':0.60,'camera':'angle_b'},
    ]}
    wp=td/'words.json'; lp=td/'layout.json'; out=td/'out.ass'
    wp.write_text(json.dumps(words)); lp.write_text(json.dumps(layout))
    subprocess.run(['python3',str(GEN),str(wp),'--preset',str(PRESET),'--layout',str(lp),'--out',str(out)],check=True,capture_output=True,text=True)
    cues=[]
    for line in out.read_text().splitlines():
        if not line.startswith('Dialogue: 1,'): continue
        body=line.split(',',9)[9]
        cues.append(re.sub(r'\{[^}]*\}','',body).strip())
    assert 'you the R' not in cues, cues
    assert 'you' in cues, cues
    assert 'the R' in cues, cues
print('PASS multicam cut is a hard caption-card boundary')

# NTSC regression: serialized six-decimal word time is microscopically earlier
# than the exact frame fraction, but still belongs to the incoming shot.
with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    fps=24000/1001
    cut_frame=1711
    rounded_cut=round(cut_frame/fps, 6)
    words={'words':[
        {'word':'like $8K','start':70.042125,'end':71.262125},
        {'word':'they','start':rounded_cut,'end':rounded_cut+0.205},
        {'word':'buy','start':rounded_cut+0.205,'end':rounded_cut+0.425},
        {'word':'anything','start':rounded_cut+0.425,'end':rounded_cut+0.785},
        {'word':'anything','start':rounded_cut+1.125,'end':rounded_cut+1.905},
    ]}
    layout={'meta':{'fps':fps},'segments':[
        {'start_i':0,'end_i':cut_frame-1,'safe_y_pct':0.56,'camera':'angle_a'},
        {'start_i':cut_frame,'end_i':1860,'safe_y_pct':0.56,'camera':'angle_b'},
    ]}
    wp=td/'words.json'; lp=td/'layout.json'; out=td/'out.ass'
    wp.write_text(json.dumps(words)); lp.write_text(json.dumps(layout))
    subprocess.run(['python3',str(GEN),str(wp),'--preset',str(PRESET),'--layout',str(lp),'--out',str(out)],check=True,capture_output=True,text=True)
    cues=[]
    for line in out.read_text().splitlines():
        if not line.startswith('Dialogue: 1,'): continue
        body=line.split(',',9)[9]
        cues.append(re.sub(r'\{[^}]*\}','',body).strip())
    assert not any('$8K' in cue and 'they' in cue for cue in cues), cues
    assert any(cue.startswith('they buy') for cue in cues), cues
    assert 'they' not in cues, cues
    assert sum(cue.split().count('anything') for cue in cues) == 2, cues
print('PASS rounded NTSC cut onset stays on incoming caption card')

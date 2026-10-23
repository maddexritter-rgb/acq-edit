#!/usr/bin/env python3
"""build_assembly_xml.py — a 16:9 ASSEMBLY CUT as xmeml (FCP7 XML) for Premiere.

This is the HANDOFF artifact for the editor-owns-the-cut workflow:

    mine moments -> THIS XML -> editor extends/retimes the cuts in Premiere -> read the
    sequence back over the MCP -> apply the cinematic 9:16 treatment to THEIR cut.

🛑 WHY IT IS BUILT THIS WAY
· Each moment references a **1080p H.264 proxy window** with a 60s handle on each side, not the
  4K AV1 master. Premiere scrubs AV1 at 4K miserably, and trimming outward is the entire point —
  the handle is the room to do it. `win_start` records the window's offset in master time so the
  editor's final in/out can be mapped straight back.
· Every moment is a real clipitem with in/out points (razor-able, trimmable). Nothing baked.
· Video and audio are LINKED via <link> so trimming the picture takes the sound with it.
· A named marker sits at the head of each moment so the slug is visible on the timeline.
· A multi-span moment is laid as ADJACENT clipitems, so the interior seam is trimmable too.

xmeml rules that bite (same ones as build_xml.py):
· the full <file> definition goes inline on the FIRST clipitem that uses it; later uses reference
  it by id only — repeating the definition makes Premiere drop the media
· pathurl must be absolute file://localhost/...
· NTSC 23.976 = timebase 24 + <ntsc>TRUE</ntsc>; getting this wrong drifts every edit
"""
import json, os, sys, urllib.parse

D = os.path.dirname(os.path.abspath(__file__))
MOMENTS = json.load(open(f"{D}/assembly_moments.json"))
SEQ = sys.argv[1] if len(sys.argv) > 1 else "ACQ_ASSEMBLY_16x9"
OUT = f"{D}/assembly/{SEQ}.xml"

FPS, TB, NTSC = 24000 / 1001.0, 24, "TRUE"
# 🛑 GAP BETWEEN MOMENTS. A contiguous assembly cannot be EXTENDED — dragging a clip's out-point
# outward just collides with the next clip. 20s of empty timeline between moments gives every
# one room to grow in BOTH directions independently, which is the entire point of the handoff.
# (Spans WITHIN one moment stay butted — that seam is the cut itself.)
GAP_S = 20.0
W, H = 1920, 1080

def fr(t):                       # seconds -> whole frames (frame-snap; half-frames open black)
    return int(round(t * FPS))

def url(p):
    return "file://localhost" + urllib.parse.quote(os.path.abspath(p))

def rate():
    return f"<rate><timebase>{TB}</timebase><ntsc>{NTSC}</ntsc></rate>"

vid, aud, links, markers = [], [], [], []
seen_files = set()
playhead = 0
clip_n = 0

for m in MOMENTS:
    fid = f"file_{m['slug']}"
    for si, (a, b) in enumerate(m["spans"]):
        clip_n += 1
        vname, aname = f"cv{clip_n}", f"ca{clip_n}"
        # span times are MASTER time; the proxy starts at win_start
        s_in, s_out = fr(a - m["win_start"]), fr(b - m["win_start"])
        dur = s_out - s_in
        start, end = playhead, playhead + dur
        label = m["slug"] if si == 0 else f"{m['slug']}_{si+1}"

        if fid not in seen_files:      # full definition ONCE
            seen_files.add(fid)
            fdef = (f'<file id="{fid}"><name>{m["slug"]}_win.mp4</name>'
                    f'<pathurl>{url(m["win_file"])}</pathurl>{rate()}'
                    f'<duration>{fr(m["win_dur"])}</duration>'
                    f'<media><video><samplecharacteristics>{rate()}'
                    f'<width>{W}</width><height>{H}</height></samplecharacteristics></video>'
                    f'<audio><channelcount>2</channelcount></audio></media></file>')
        else:
            fdef = f'<file id="{fid}"/>'

        vid.append(
            f'<clipitem id="{vname}"><name>{label}</name>{rate()}'
            f'<start>{start}</start><end>{end}</end><in>{s_in}</in><out>{s_out}</out>'
            f'{fdef}<link><linkclipref>{vname}</linkclipref></link>'
            f'<link><linkclipref>{aname}</linkclipref></link></clipitem>')
        aud.append(
            f'<clipitem id="{aname}"><name>{label}</name>{rate()}'
            f'<start>{start}</start><end>{end}</end><in>{s_in}</in><out>{s_out}</out>'
            f'<file id="{fid}"/><sourcetrack><mediatype>audio</mediatype>'
            f'<trackindex>1</trackindex></sourcetrack>'
            f'<link><linkclipref>{vname}</linkclipref></link>'
            f'<link><linkclipref>{aname}</linkclipref></link></clipitem>')
        if si == 0:
            markers.append(f'<marker><name>{m["slug"]} — {m["status"]}</name>'
                           f'<in>{start}</in><out>{start}</out></marker>')
        playhead = end
    playhead += int(round(GAP_S * FPS))          # breathing room before the next moment

xml = (f'<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE xmeml><xmeml version="4">'
       f'<sequence id="seq_{SEQ}"><name>{SEQ}</name><duration>{playhead}</duration>{rate()}'
       f'<media><video><format><samplecharacteristics>{rate()}'
       f'<width>{W}</width><height>{H}</height></samplecharacteristics></format>'
       f'<track>{"".join(vid)}</track></video>'
       f'<audio><format><samplecharacteristics><depth>16</depth>'
       f'<samplerate>48000</samplerate></samplecharacteristics></format>'
       f'<track>{"".join(aud)}</track></audio></media>'
       f'{"".join(markers)}</sequence></xmeml>')

os.makedirs(f"{D}/assembly", exist_ok=True)
open(OUT, "w").write(xml)
print(f"  {OUT}")
print(f"  {clip_n} clipitems from {len(MOMENTS)} moments · "
      f"{playhead} frames = {playhead/FPS:.1f}s @ 23.976")

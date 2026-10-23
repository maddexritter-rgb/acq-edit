#!/usr/bin/env python3
"""/live-clip XMEML generator — one assembly-cut sequence per completed
interaction, ready to import into the open Premiere project (MCP
import_fcp_xml, or File > Import). Format cloned from the proven-importable
shorts-cuts XMLs (xmeml v4, linked V+A clipitems laid back-to-back).

  python3 live_xml.py --media <seg.mp4> --media-start 720.0 \
      --spans '[[843.2,871.0],[874.5,902.3]]' --name SEG03_PricingCaller_SHORT \
      --out <proj>/10_WORK/live_xml/SEG03_PricingCaller_SHORT.xml \
      [--switch-times switches.json]

Spans are ABSOLUTE stream seconds (straight from rolling_words.json);
--media-start is the media file's absolute start (from live_extract's .json).
A mid is one span (Q-in → A-out); a short is several.

--switch-times: JSON list of camera-switch times (absolute stream seconds, or
[{"t": ...}] objects). Every span is SPLIT at each switch inside it — adjacent
clipitems, zero gap — so the timeline has a cut at the EXACT frame the program
feed changes angle and downstream keyframing never drags across a framing
change (Maddex requirement, 2026-07-31).
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).parent))
from live_common import video_props, ffprobe_duration

RATE = "<rate><timebase>{tb}</timebase><ntsc>{ntsc}</ntsc></rate>"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--media-start", type=float, required=True)
    ap.add_argument("--spans", required=True, help="JSON [[t0,t1],...] absolute secs")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--switch-times", help="JSON file of camera-switch times "
                    "(absolute secs, or [{'t':...}]) — spans split at each")
    a = ap.parse_args()

    media = Path(a.media).expanduser().resolve()
    spans = json.loads(a.spans)
    if a.switch_times:
        raw = json.loads(Path(a.switch_times).expanduser().read_text())
        sw = sorted(x["t"] if isinstance(x, dict) else float(x) for x in raw)
        split = []
        for t0, t1 in spans:
            edges = [t0] + [t for t in sw if t0 + 0.10 < t < t1 - 0.10] + [t1]
            split += [[edges[i], edges[i + 1]] for i in range(len(edges) - 1)]
        n_cuts = len(split) - len(spans)
        spans = split
        print(f"switch-split: +{n_cuts} angle cuts -> {len(spans)} clip items")
    props = video_props(media)
    fps = props["fps"]
    ntsc = "TRUE" if abs(fps - round(fps)) > 0.01 else "FALSE"
    tb = round(fps)
    rate = RATE.format(tb=tb, ntsc=ntsc)
    media_dur = int(ffprobe_duration(media) * fps)
    w, h = props["width"], props["height"]
    pathurl = "file://localhost" + str(media).replace(" ", "%20")

    file_def_written = False

    def file_ref(fid: str) -> str:
        nonlocal file_def_written
        if file_def_written:
            return f'<file id="{fid}"/>'
        file_def_written = True
        return (f'<file id="{fid}"><name>{escape(media.name)}</name>'
                f'<pathurl>{pathurl}</pathurl><duration>{media_dur}</duration>'
                f'<width>{w}</width><height>{h}</height>{rate}<media>'
                f'<video><samplecharacteristics><width>{w}</width><height>{h}</height>{rate}'
                f'<anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio>'
                f'<fielddominance>none</fielddominance></samplecharacteristics></video>'
                f'<audio><samplecharacteristics><depth>16</depth>'
                f'<samplerate>48000</samplerate></samplecharacteristics>'
                f'<channelcount>2</channelcount></audio></media></file>')

    v_items, a_items, tl = [], [], 0
    for n, (t0, t1) in enumerate(spans, 1):
        src_in = int(round((t0 - a.media_start) * fps))
        src_out = int(round((t1 - a.media_start) * fps))
        if src_in < 0:
            sys.exit(f"span {n} starts before media_start — extract a wider segment")
        dur = src_out - src_in
        vid, aid = f"clipitem-{2 * n - 1}", f"clipitem-{2 * n}"
        links = (f'<link><linkclipref>{vid}</linkclipref><mediatype>video</mediatype>'
                 f'<trackindex>1</trackindex><clipindex>{n}</clipindex></link>'
                 f'<link><linkclipref>{aid}</linkclipref><mediatype>audio</mediatype>'
                 f'<trackindex>1</trackindex><clipindex>{n}</clipindex>'
                 f'<groupindex>1</groupindex></link>')
        common = (f'<name>{escape(a.name)}_{n:02d}</name><enabled>TRUE</enabled>'
                  f'<duration>{dur}</duration><start>{tl}</start><end>{tl + dur}</end>'
                  f'<in>{src_in}</in><out>{src_out}</out>')
        v_items.append(f'<clipitem id="{vid}">{common}{file_ref("file-1")}{links}</clipitem>')
        a_items.append(f'<clipitem id="{aid}">{common}{file_ref("file-1")}'
                       f'<sourcetrack><mediatype>audio</mediatype>'
                       f'<trackindex>1</trackindex></sourcetrack>{links}</clipitem>')
        tl += dur

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<xmeml version="4">
 <sequence id="{escape(a.name)}">
  <duration>{tl}</duration>
  <name>{escape(a.name)}</name>
  <width>{w}</width><height>{h}</height>
  {rate}
  <media>
   <video>
    <format><samplecharacteristics><pixelaspectratio>square</pixelaspectratio><anamorphic>FALSE</anamorphic><fielddominance>none</fielddominance><colordepth>24</colordepth><width>{w}</width><height>{h}</height>{rate}</samplecharacteristics></format>
    <track>{''.join(v_items)}</track>
   </video>
   <audio>
    <format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>
    <track>{''.join(a_items)}</track>
   </audio>
  </media>
 </sequence>
</xmeml>
"""
    out = Path(a.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml)
    print(f"{out}  ({len(spans)} span(s), {tl / fps:.1f}s timeline)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

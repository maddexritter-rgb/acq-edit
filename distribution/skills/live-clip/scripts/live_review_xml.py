#!/usr/bin/env python3
"""One review sequence: all clips on one timeline, 20s gaps between clips,
a named sequence marker at each clip's first frame (edit skill 8B-1 layout).

  python3 combined_xml.py --media <src> --name LIVE_CLIPS --out combined.xml \
      --clips '[{"name": "T1_...", "spans_file": "refined_T1.json"}, ...]' \
      [--switch-times switches_only.json] [--gap 20]
"""
from __future__ import annotations
import argparse, json, sys
from fractions import Fraction
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "live-clip/scripts"))
from live_common import video_props, ffprobe_duration

RATE = "<rate><timebase>{tb}</timebase><ntsc>{ntsc}</ntsc></rate>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media")
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    inputs = ap.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--clips", help="Legacy/live discovery inputs; not a guarded assembly")
    inputs.add_argument("--assembly-packets", help="JSON list of guarded native packet paths")
    inputs.add_argument("--multicam-plan", help="Guarded measured two-camera picture/audio plan")
    ap.add_argument("--switch-times")
    ap.add_argument("--gap", type=float, default=20.0)
    a = ap.parse_args()
    if a.multicam_plan:
        from measured_multicam_xml import build
        if a.media or a.switch_times:
            ap.error('--multicam-plan carries pinned source identity and independent picture intervals')
        try:
            result = build(Path(a.multicam_plan), Path(a.out))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            ap.error(str(exc))
        print(json.dumps(result, indent=2))
        return
    if not a.media:
        ap.error('--media is required for identity-clock and legacy inputs')
    if a.assembly_packets and Path(a.out).exists():
        ap.error('guarded output exists; use a new revision path')

    media = Path(a.media).expanduser().resolve()
    packet_rates = []
    if a.assembly_packets:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'edit/scripts'))
        from assembly_job import validate_native_packet, load
        clips = []
        for packet_path in json.loads(a.assembly_packets):
            packet = validate_native_packet(packet_path)
            mapping = load(packet['source_mapping']['path'])
            if mapping['clock_basis'] != 'identical' or Path(mapping['media']['path']).resolve() != media:
                ap.error('this adapter requires identity-clock packets for the supplied media; use a verified multicamera adapter')
            clips.append({'name': packet['clip_id'], 'spans': packet['source_spans']})
            packet_rates.append(float(Fraction(packet['fps'])))
    else:
        clips = json.loads(a.clips)
        print('UNVERIFIED legacy/live inputs: not assembly-design authorization', file=sys.stderr)
    sw = []
    if a.switch_times:
        raw = json.loads(Path(a.switch_times).expanduser().read_text())
        sw = sorted(x["t"] if isinstance(x, dict) else float(x) for x in raw)

    props = video_props(media)
    fps = props["fps"]
    if any(abs(rate - fps) > 0.000001 for rate in packet_rates):
        ap.error('packet/source frame rate mismatch; re-resolve and reconcile at the actual media rate')
    tb = round(fps)
    ntsc = "TRUE" if abs(fps - tb) > 0.01 else "FALSE"
    rate = RATE.format(tb=tb, ntsc=ntsc)
    media_dur = int(ffprobe_duration(media) * fps)
    w, h = props["width"], props["height"]
    pathurl = "file://localhost" + str(media).replace(" ", "%20")

    file_written = False

    def file_ref(fid="file-1"):
        nonlocal file_written
        if file_written:
            return f'<file id="{fid}"/>'
        file_written = True
        return (f'<file id="{fid}"><name>{escape(media.name)}</name>'
                f'<pathurl>{pathurl}</pathurl><duration>{media_dur}</duration>'
                f'<width>{w}</width><height>{h}</height>{rate}<media>'
                f'<video><samplecharacteristics><width>{w}</width><height>{h}</height>{rate}'
                f'<anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio>'
                f'<fielddominance>none</fielddominance></samplecharacteristics></video>'
                f'<audio><samplecharacteristics><depth>16</depth>'
                f'<samplerate>48000</samplerate></samplecharacteristics>'
                f'<channelcount>2</channelcount></audio></media></file>')

    v_items, a_items, markers = [], [], []
    tl = 0  # frames
    cid = 0
    for clip in clips:
        spans = clip['spans'] if 'spans' in clip else json.loads(Path(clip["spans_file"]).read_text())
        split = []
        for t0, t1 in spans:
            edges = [t0] + [t for t in sw if t0 + 0.10 < t < t1 - 0.10] + [t1]
            split += [[edges[i], edges[i + 1]] for i in range(len(edges) - 1)]
        markers.append((tl, clip["name"]))
        for k, (t0, t1) in enumerate(split, 1):
            src_in, src_out = int(round(t0 * fps)), int(round(t1 * fps))
            dur = src_out - src_in
            cid += 1
            vid, aid = f"clipitem-{2 * cid - 1}", f"clipitem-{2 * cid}"
            links = (f'<link><linkclipref>{vid}</linkclipref><mediatype>video</mediatype>'
                     f'<trackindex>1</trackindex><clipindex>{cid}</clipindex></link>'
                     f'<link><linkclipref>{aid}</linkclipref><mediatype>audio</mediatype>'
                     f'<trackindex>1</trackindex><clipindex>{cid}</clipindex>'
                     f'<groupindex>1</groupindex></link>')
            common = (f'<name>{escape(clip["name"])}_{k:02d}</name><enabled>TRUE</enabled>'
                      f'<duration>{dur}</duration><start>{tl}</start><end>{tl + dur}</end>'
                      f'<in>{src_in}</in><out>{src_out}</out>')
            v_items.append(f'<clipitem id="{vid}">{common}{file_ref()}{links}</clipitem>')
            a_items.append(f'<clipitem id="{aid}">{common}{file_ref()}'
                           f'<sourcetrack><mediatype>audio</mediatype>'
                           f'<trackindex>1</trackindex></sourcetrack>{links}</clipitem>')
            tl += dur
        tl += int(round(a.gap * fps))
    total = tl

    marker_xml = "".join(
        f"<marker><name>{escape(n)}</name><comment/><in>{f}</in><out>-1</out></marker>"
        for f, n in markers)

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<xmeml version="4">
 <sequence id="{escape(a.name)}">
  <duration>{total}</duration>
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
  {marker_xml}
 </sequence>
</xmeml>
"""
    Path(a.out).write_text(xml)
    print(f"{a.out}: {len(clips)} clips, {cid} clip items, {total / fps:.1f}s timeline")


if __name__ == "__main__":
    main()

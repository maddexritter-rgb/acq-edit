#!/usr/bin/env python3
"""Guarded, source-linked XMEML for a measured two-camera assembly.

This is an adapter for ``live_review_xml.py``.  Editorial selections come only from a
current edit.native-build-packet/v1; picture and speaker-audio choices are supplied
separately in a pinned review plan.  It never decides cuts or camera switches.
"""
from __future__ import annotations

import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from live_common import ffprobe_duration, video_props

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "edit/scripts"))
from assembly_job import load, pin, pinned, require, same_pin, validate_native_packet


def _frame(seconds, fps):
    return int(round(float(seconds) * fps))


def _rate(fps):
    rounded = round(fps)
    return f"<rate><timebase>{rounded}</timebase><ntsc>{'TRUE' if abs(fps-rounded) > .01 else 'FALSE'}</ntsc></rate>"


def _file_xml(media, fid, fps, width, height, duration_frames):
    path = Path(media).resolve()
    url = "file://localhost" + quote(str(path), safe="/")
    rate = _rate(fps)
    return (f'<file id="{fid}"><name>{escape(path.name)}</name><pathurl>{url}</pathurl>'
            f'<duration>{duration_frames}</duration><width>{width}</width><height>{height}</height>{rate}'
            '<media><video><samplecharacteristics>'
            f'<width>{width}</width><height>{height}</height>{rate}'
            '<anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio>'
            '<fielddominance>none</fielddominance></samplecharacteristics></video>'
            '<audio><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate>'
            '</samplecharacteristics><channelcount>2</channelcount></audio></media></file>')


def _picture_filter(panel, layout, side, width, height):
    framing = panel.get("framing")
    require(isinstance(framing, dict), "each picture panel needs explicit editable framing")
    scale = framing.get("scale")
    pos = framing.get("position")
    crop = framing.get("crop")
    require(isinstance(scale, (int, float)) and 1 <= scale <= 1000,
            "invalid panel Motion scale")
    require(isinstance(pos, list) and len(pos) == 2 and
            all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in pos),
            "invalid normalized panel Motion position")
    require(isinstance(crop, dict) and set(crop) == {"left", "right", "top", "bottom"}
            and all(isinstance(v, (int, float)) and 0 <= v < 100 for v in crop.values()),
            "invalid editable panel Crop values")
    if layout == "split":
        require(side in {"left", "right"}, "split panel needs left/right side")
        require(crop["left"] + crop["right"] >= 49.5,
                "split panel must mask to a half-frame or narrower")
        require(abs(pos[0] - (.25 if side == "left" else .75)) <= .25,
                "panel position is outside its assigned half")
    else:
        require(side == "full", "single picture needs full side")
    # Premiere 26 native readback maps XMEML center offsets directly to Position.
    # The post-import native-layout pass below is authoritative for Crop controls.
    horiz = pos[0] - .5
    vert = pos[1] - .5
    motion = ('<filter><effect><name>Basic Motion</name><effectid>basic</effectid>'
              '<effectcategory>motion</effectcategory><effecttype>motion</effecttype>'
              '<mediatype>video</mediatype>'
              '<parameter authoringApp="PremierePro"><parameterid>scale</parameterid>'
              f'<name>Scale</name><valuemin>0</valuemin><valuemax>1000</valuemax><value>{scale:.6f}</value></parameter>'
              '<parameter authoringApp="PremierePro"><parameterid>center</parameterid>'
              f'<name>Center</name><value><horiz>{horiz:.8f}</horiz><vert>{vert:.8f}</vert>'
              '</value></parameter></effect></filter>')
    return motion


def _tiles(rows, total, label):
    require(isinstance(rows, list) and rows, f"{label} intervals missing")
    cursor = 0
    for row in rows:
        bounds = row.get("timeline_frames")
        require(isinstance(bounds, list) and len(bounds) == 2 and
                all(type(v) is int for v in bounds) and bounds[0] == cursor and
                cursor < bounds[1] <= total, f"{label} intervals must tile the entire selection")
        cursor = bounds[1]
    require(cursor == total, f"{label} does not reach the last selected frame")


def _chunks(interval, spans):
    a, b = interval
    for span in spans:
        start, end, source_start = span
        lo, hi = max(a, start), min(b, end)
        if lo < hi:
            yield lo, hi, source_start + lo - start


def build(plan_path: Path, out_path: Path):
    plan_path, out_path = Path(plan_path).resolve(), Path(out_path).resolve()
    require(not out_path.exists(), "guarded XML output exists; use a new revision path")
    plan = load(plan_path)
    require(plan.get("schema") == "edit.native-measured-multicam-plan/v1", "wrong multicamera plan schema")
    packet = validate_native_packet(pinned(plan["native_packet"]))
    mapping = load(pinned(packet["source_mapping"]))
    require(mapping["clock_basis"] == "measured", "measured adapter requires measured source mapping")
    require(same_pin(plan.get("sync_index"), mapping.get("sync_evidence")),
            "plan sync index must equal the packet's pinned mapping evidence")
    sync = load(pinned(plan["sync_index"]))
    require(sync.get("schema") == "edit.source-sync-index/v1", "wrong sync index schema")
    master = Path(mapping["media"]["path"]).resolve()
    require(Path(sync["master"]).resolve() == master, "sync mapping direction/master mismatch")
    guest = pinned(plan["guest_media"])
    matches = [row for row in sync.get("children", []) if Path(row["child"]).resolve() == guest]
    require(len(matches) == 1 and matches[0].get("verdict") == "PASS", "guest camera lacks one accepted sync map")
    child = matches[0]
    require(len(child.get("anchors", [])) >= 3, "guest camera lacks three measured anchors")
    coefficients = child["mapping"]
    require(coefficients.get("master_time_s") == "intercept_s + child_time_s * (1 + drift_s_per_s)",
            "unexpected mapping direction/formula")
    intercept = float(coefficients["intercept_s"])
    slope = 1.0 + float(coefficients["drift_s_per_s"])
    require(math.isfinite(intercept) and math.isfinite(slope) and .99 < slope < 1.01,
            "invalid measured camera coefficients")
    acceptance = sync.get("acceptance", {})
    max_residual = float(acceptance.get("maximum_fit_residual_s", 1 / float(Fraction(packet["fps"]))))
    min_peak = float(acceptance.get("minimum_peak_ratio", 1.05))
    for anchor in child["anchors"]:
        require(abs(intercept + float(anchor["child_anchor_s"]) * slope -
                    float(anchor["master_anchor_s"])) <= max_residual,
                "measured anchor contradicts clock mapping")
        require(float(anchor.get("confidence_peak_ratio", 0)) >= min_peak,
                "measured anchor is ambiguous")
    require(float(child.get("fit_max_residual_s", 0)) <= max_residual,
            "measured fit residual exceeds acceptance")
    fps_fraction = Fraction(packet["fps"])
    fps = float(fps_fraction)
    require(sync.get("fps") == packet["fps"], "sync index/source frame rate mismatch")
    props = {"master": video_props(master), "guest": video_props(guest)}
    durations = {"master": ffprobe_duration(master), "guest": ffprobe_duration(guest)}
    width, height = props["master"]["width"], props["master"]["height"]
    for label, p in props.items():
        require(abs(p["fps"] - fps) < 1e-6 and p["width"] == width and p["height"] == height,
                f"{label} picture format differs from packet")
    require(abs(float(child["duration_s"]) - durations["guest"]) <= .2,
            "guest duration differs from sync measurement")
    source_spans = []
    total = 0
    for lo, hi in packet["source_spans"]:
        a, b = _frame(lo, fps), _frame(hi, fps)
        require(0 <= a < b <= _frame(durations["master"], fps), "selected master span out of bounds")
        source_spans.append((total, total + b - a, a))
        total += b - a
    _tiles(plan.get("audio"), total, "audio")
    _tiles(plan.get("picture"), total, "picture")
    # An audio route is a single deliberate dialogue stream. Picture has no audio items.
    for route in plan["audio"]:
        require(route.get("source") in {"master", "guest"}, "invalid audio source")
        require(route.get("why") and route.get("speaker"), "audio routing needs observed speaker/reason")
    for shot in plan["picture"]:
        require(shot.get("id") and shot.get("why") and shot.get("evidence"),
                "picture occurrence needs identity, reason and visual evidence")
        pinned(shot["evidence"])
        panels = shot.get("panels")
        require(shot.get("layout") in {"single", "split"}, "unknown picture layout")
        require(isinstance(panels, list) and len(panels) == (2 if shot["layout"] == "split" else 1),
                "picture layout/panel count mismatch")
        require({p.get("side") for p in panels} == ({"left", "right"} if shot["layout"] == "split" else {"full"}),
                "split must have one independent left and right panel")
        for panel in panels:
            require(panel.get("source") in {"master", "guest"}, "unknown picture source")
            _picture_filter(panel, shot["layout"], panel["side"], width, height)

    files = {"master": _file_xml(master, "file-master", fps, width, height, _frame(durations["master"], fps)),
             "guest": _file_xml(guest, "file-guest", fps, width, height, _frame(durations["guest"], fps))}
    written = set()
    def file_ref(source):
        fid = "file-" + source
        if source not in written:
            written.add(source)
            return files[source]
        return f'<file id="{fid}"/>'

    def mapped_start(source, master_frame, duration):
        master_sec = master_frame / fps
        source_sec = master_sec if source == "master" else (master_sec - intercept) / slope
        src = _frame(source_sec, fps)
        require(src >= 0 and src + duration <= _frame(durations[source], fps),
                f"{source} mapping outside source bounds")
        mapped_start_master = src / fps if source == "master" else intercept + src / fps * slope
        require(abs(mapped_start_master - master_sec) <= .5 / fps + 1e-7,
                f"{source} start mapping misses the selected frame")
        mapped_end = (src + duration) / fps if source == "master" else intercept + (src + duration) / fps * slope
        intended_end = (master_frame + duration) / fps
        require(abs(mapped_end - intended_end) <= 1.0 / fps,
                f"{source} drift exceeds one frame within a native item; subdivide picture/audio interval")
        return src

    tracks = {"video_full": [], "video_left": [], "video_right": [], "audio": []}
    layout_items = []
    item_id = 0
    for shot in plan["picture"]:
        for lo, hi, master_frame in _chunks(shot["timeline_frames"], source_spans):
            for panel in shot["panels"]:
                item_id += 1
                source = panel["source"]
                src = mapped_start(source, master_frame, hi - lo)
                filt = _picture_filter(panel, shot["layout"], panel["side"], width, height)
                name = escape(f'{packet["clip_id"]}_{shot["id"]}_{panel["side"]}')
                tracks["video_" + panel["side"]].append(
                    f'<clipitem id="clipitem-{item_id}"><name>{name}</name><enabled>TRUE</enabled>'
                    f'<duration>{hi-lo}</duration><start>{lo}</start><end>{hi}</end>'
                    f'<in>{src}</in><out>{src+hi-lo}</out>{file_ref(source)}{filt}</clipitem>')
                layout_items.append({'name': f'{packet["clip_id"]}_{shot["id"]}_{panel["side"]}',
                    'track': {'full':0,'left':1,'right':2}[panel['side']],
                    'timeline_frames':[lo,hi], 'source':str(master if source=='master' else guest),
                    'framing':panel['framing']})
    for route in plan["audio"]:
        for lo, hi, master_frame in _chunks(route["timeline_frames"], source_spans):
            item_id += 1
            source = route["source"]
            src = mapped_start(source, master_frame, hi - lo)
            name = escape(f'{packet["clip_id"]}_{route["speaker"]}_dialogue')
            tracks["audio"].append(
                f'<clipitem id="clipitem-{item_id}"><name>{name}</name><enabled>TRUE</enabled>'
                f'<duration>{hi-lo}</duration><start>{lo}</start><end>{hi}</end>'
                f'<in>{src}</in><out>{src+hi-lo}</out>{file_ref(source)}'
                '<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex>'
                '</sourcetrack></clipitem>')
    rate = _rate(fps)
    sequence_name = plan["sequence_name"]
    require(isinstance(sequence_name, str) and sequence_name.strip(), "review sequence name missing")
    video_xml = ''.join('<track>' + ''.join(tracks[k]) + '</track>'
                        for k in ("video_full", "video_left", "video_right"))
    audio_xml = '<track>' + ''.join(tracks["audio"]) + '</track>'
    xml = (f'<?xml version="1.0" encoding="utf-8"?><xmeml version="4"><sequence id="{escape(sequence_name)}">'
           f'<duration>{total}</duration><name>{escape(sequence_name)}</name><width>{width}</width><height>{height}</height>{rate}'
           '<media><video><format><samplecharacteristics><pixelaspectratio>square</pixelaspectratio>'
           '<anamorphic>FALSE</anamorphic><fielddominance>none</fielddominance><colordepth>24</colordepth>'
           f'<width>{width}</width><height>{height}</height>{rate}</samplecharacteristics></format>{video_xml}</video>'
           '<audio><format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate>'
           f'</samplecharacteristics></format>{audio_xml}</audio></media></sequence></xmeml>')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(xml)
    adapter = Path(__file__).resolve()
    receipt = {'schema': 'edit.native-adapter-receipt/v1', 'adapter': pin(adapter),
               'entrypoint': pin(SKILLS / 'live-clip/scripts/live_review_xml.py'),
               'plan': pin(plan_path), 'native_packet': plan['native_packet'],
               'sync_index': plan['sync_index'], 'sequence_name': sequence_name,
               'source_spans': packet['source_spans'], 'timeline_frames': total,
               'picture_items': sum(len(tracks[k]) for k in ("video_full", "video_left", "video_right")),
               'layout_items': layout_items, 'native_layout': 'PENDING',
               'audio_items': len(tracks["audio"]), 'audio_tracks': 1,
               'xml': pin(out_path)}
    receipt_path = out_path.with_suffix(out_path.suffix + '.adapter.json')
    require(not receipt_path.exists(), "adapter receipt exists; use a new revision path")
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def apply_native_layout(receipt_path: Path, project_path: Path):
    """Apply editable Premiere Motion/Crop after XMEML import, then save/read back.

    Premiere 26 imports Basic Motion but drops XMEML's Crop effect. This stage sets
    the intrinsic native Crop controls and verifies the saved result. It does not
    change dialogue items, source ranges or audio routing.
    """
    receipt_path = Path(receipt_path).resolve()
    project_path = Path(project_path).resolve()
    receipt = load(receipt_path)
    require(receipt.get('schema') == 'edit.native-adapter-receipt/v1', 'wrong adapter receipt')
    for key in ('adapter','entrypoint','plan','native_packet','sync_index','xml'):
        pinned(receipt[key])
    require(Path(receipt['adapter']['path']).resolve() == Path(__file__).resolve(),
            'adapter revision changed since XML emission')
    sys.path.insert(0, str(SKILLS / 'edit/scripts'))
    from pp_export_clips import es

    def probe():
        return es('return {path:app.project?app.project.path:null,'
                  'sequence:app.project&&app.project.activeSequence?app.project.activeSequence.name:null};',30)

    def guarded(body, timeout=90):
        before = probe()
        require(before.get('path') == str(project_path) and
                before.get('sequence') == receipt['sequence_name'],
                'wrong active Premiere project/sequence before layout mutation: '+json.dumps(before))
        guard = ('if(!app.project||app.project.path!==' + json.dumps(str(project_path)) +
                 '||!app.project.activeSequence||app.project.activeSequence.name!==' +
                 json.dumps(receipt['sequence_name']) +
                 ')throw new Error("NATIVE_IDENTITY_CHANGED");')
        return es(guard+body,timeout)

    for item in receipt['layout_items']:
        # Every occurrence is located by its own track, name, source and frame bounds;
        # a matching marker or filename elsewhere cannot receive these controls.
        body = ('var s=app.project.activeSequence,r=' + json.dumps(item) +
                ',t=s.videoTracks[r.track],matches=[];'
                'for(var i=0;i<t.clips.numItems;i++){var c=t.clips[i];'
                'if(c.name===r.name&&c.projectItem.getMediaPath()===r.source&&'
                'Math.abs(c.start.seconds-r.timeline_frames[0]/' +
                str(float(Fraction(load(pinned(receipt['native_packet']))['fps']))) +
                ')<0.001)matches.push(c);}'
                'if(matches.length!==1)throw new Error("PICTURE_ITEM_IDENTITY_MISMATCH "+r.name);'
                'var c=matches[0],motion=null;'
                'for(var e=0;e<c.components.numItems;e++)'
                'if(c.components[e].displayName==="Motion")motion=c.components[e];'
                'if(!motion){if(r.track===0&&r.framing.scale===100&&'
                'r.framing.position[0]===0.5&&r.framing.position[1]===0.5&&'
                'r.framing.crop.left===0&&r.framing.crop.right===0&&'
                'r.framing.crop.top===0&&r.framing.crop.bottom===0)'
                'return {name:r.name,track:r.track,defaultMotion:true};'
                'throw new Error("NATIVE_MOTION_MISSING "+r.name);}'
                'function set(n,v){if(!app.project||app.project.path!==' +
                json.dumps(str(project_path)) +
                '||app.project.activeSequence.name!==' + json.dumps(receipt['sequence_name']) +
                ')throw new Error("NATIVE_IDENTITY_CHANGED_DURING_LAYOUT");'
                'for(var j=0;j<motion.properties.numItems;j++){var p=motion.properties[j];'
                'if(p.displayName===n){p.setValue(v,1);return;}}'
                'throw new Error("MOTION_PROPERTY_MISSING "+n);}'
                'set("Position",r.framing.position);set("Scale",r.framing.scale);'
                'set("Crop Left",r.framing.crop.left);set("Crop Right",r.framing.crop.right);'
                'set("Crop Top",r.framing.crop.top);set("Crop Bottom",r.framing.crop.bottom);'
                'return {name:r.name,track:r.track};')
        guarded(body)
    guarded('app.project.save();return {path:app.project.path,sequence:app.project.activeSequence.name};',90)
    # A saved-project readback is required. Do not infer that setValue survived import.
    readback = guarded(
        'var p=app.project.path,n=app.project.activeSequence.name;'
        'app.project.closeDocument(0,0);app.openDocument(p);'
        'if(!app.project||app.project.path!==p)throw new Error("NATIVE_REOPEN_FAILED");'
        'var s=null;for(var i=0;i<app.project.sequences.numSequences;i++)'
        'if(app.project.sequences[i].name===n)s=app.project.sequences[i];'
        'if(!s)throw new Error("NATIVE_SEQUENCE_MISSING_AFTER_REOPEN");'
        'app.project.openSequence(s.sequenceID);'
        'var rows=[];for(var t=0;t<s.videoTracks.numTracks;t++)'
        'for(var c=0;c<s.videoTracks[t].clips.numItems;c++){var x=s.videoTracks[t].clips[c],v={};'
        'for(var e=0;e<x.components.numItems;e++)if(x.components[e].displayName==="Motion")'
        'for(var j=0;j<x.components[e].properties.numItems;j++){var q=x.components[e].properties[j];'
        'if(q.displayName==="Position"||q.displayName==="Scale"||q.displayName.indexOf("Crop ")===0)'
        'v[q.displayName]=q.getValue();}'
        'rows.push({name:x.name,track:t,source:x.projectItem.getMediaPath(),'
        'start:x.start.seconds,end:x.end.seconds,values:v});}'
        'var audio=[];for(var a=0;a<s.audioTracks.numTracks;a++)'
        'for(var k=0;k<s.audioTracks[a].clips.numItems;k++){var y=s.audioTracks[a].clips[k];'
        'audio.push({track:a,source:y.projectItem.getMediaPath(),start:y.start.seconds,end:y.end.seconds});}'
        'return {path:app.project.path,sequence:s.name,id:s.sequenceID,picture:rows,audio:audio};',180)
    fps = float(Fraction(load(pinned(receipt['native_packet']))['fps']))
    for expected in receipt['layout_items']:
        rows = [r for r in readback['picture'] if r['name'] == expected['name'] and
                r['track'] == expected['track'] and r['source'] == expected['source'] and
                abs(r['start'] - expected['timeline_frames'][0]/fps) < .001 and
                abs(r['end'] - expected['timeline_frames'][1]/fps) < .001]
        require(len(rows) == 1, 'saved Premiere picture item differs: '+expected['name'])
        values, framing = rows[0]['values'], expected['framing']
        if not values and expected['track'] == 0 and framing == {
                'scale':100,'position':[.5,.5],
                'crop':{'left':0,'right':0,'top':0,'bottom':0}}:
            continue
        require(abs(values.get('Scale',-1)-framing['scale']) < .01,
                'saved native scale differs: '+expected['name'])
        require(isinstance(values.get('Position'),list) and
                all(abs(a-b)<.001 for a,b in zip(values['Position'],framing['position'])),
                'saved native position differs: '+expected['name'])
        for key in ('left','right','top','bottom'):
            require(abs(values.get('Crop '+key.title(),-1)-framing['crop'][key]) < .01,
                    'saved native crop differs: '+expected['name']+' '+key)
    require(len(readback['audio']) == receipt['audio_items'] and
            {a['track'] for a in readback['audio']} == {0},
            'saved Premiere audio topology differs from one deliberate mix')
    out = receipt_path.with_suffix('.native-readback.json')
    require(not out.exists(), 'native readback exists; use a new revision')
    out.write_text(json.dumps(readback,indent=2)+'\n')
    return {'status':'NATIVE_LAYOUT_READBACK_MATCH', 'readback':pin(out),
            'project':str(project_path),'sequence':receipt['sequence_name']}

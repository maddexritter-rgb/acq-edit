#!/usr/bin/env python3
"""Create an editable, item-local 9:16 reframe in the active Premiere project.

This is the canonical horizontal-to-vertical implementation. It never renders or
imports replacement video. It duplicates the active sequence, analyzes every
source-linked picture item at its exact source in/out, writes sparse Motion >
Anchor Point keys in media time, saves, verifies, and leaves the review sequence
open in Premiere.

The script uses the configured Premiere Agent through the shared MCP client. It is
intentionally fail-closed for nested/overlapping picture layouts; build native
split-screen panels first, then run this on each source sequence independently.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import uuid
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
MODEL = HERE / "yunet.onnx"
LAB_SESSION = None
TICKS_PER_SECOND = 254_016_000_000

PRESETS = {
    "alex-listicle": {"zoom": 1.6, "eye_y": 0.25, "roi": (0.20, 0.05, 0.80, 0.70)},
    "alex-stage": {"zoom": 1.6, "eye_y": 0.18, "roi": (0.05, 0.05, 0.82, 0.55)},
    "center-stage": {
        "zoom": 1.6,
        "eye_y": 0.18,
        "roi": (0.35, 0.05, 0.65, 0.55),
    },
    "alex-split-top": {"zoom": 1.4, "eye_y": 0.22, "roi": (0.05, 0.05, 0.82, 0.55)},
    "guest": {"zoom": 1.4, "eye_y": 0.24, "roi": (0.25, 0.15, 0.75, 0.68)},
    "podcast": {"zoom": 1.0, "eye_y": 0.22, "roi": (0.10, 0.05, 0.90, 0.75), "min_face_height720": 48},
}


def jsx_string(value: str | Path) -> str:
    return json.dumps(str(value))


def bridge_call(label: str, jsx: str, timeout: float = 45.0) -> dict:
    raise RuntimeError('Direct mailbox execution is retired. Use the default Premiere Agent profile and typed ReframeSession; run edit/scripts/premiere_agent.py doctor.')


INSPECT_JSX = r"""
try{
function motionProp(c,n){for(var i=0;i<c.components.numItems;i++){var fx=c.components[i];if(fx.displayName=='Motion'){for(var j=0;j<fx.properties.numItems;j++){if(fx.properties[j].displayName==n)return fx.properties[j];}}}return null;}
function anchorKeys(a){var out=[];if(!a||!a.isTimeVarying())return out;var keys=a.getKeys();if(!keys)return out;for(var ki=0;ki<keys.length;ki++){var k=keys[ki];out.push({ticks:String(k.ticks),value:a.getValueAtKey(k)});}return out;}
var s=app.project.activeSequence;if(!s)throw new Error('NO_ACTIVE_SEQUENCE');
var vt=[];
for(var ti=0;ti<s.videoTracks.numTracks;ti++){
 var clips=[];
 for(var ci=0;ci<s.videoTracks[ti].clips.numItems;ci++){
  var c=s.videoTracks[ti].clips[ci],path='';try{path=c.projectItem.getMediaPath();}catch(_e){}
  var a=motionProp(c,'Anchor Point'),p=motionProp(c,'Position'),sc=motionProp(c,'Scale');
  clips.push({track_index:ti,item_index:ci,name:c.name,media_path:path,start:c.start.seconds,end:c.end.seconds,source_in:c.inPoint.seconds,source_out:c.outPoint.seconds,speed:c.getSpeed(),motion:{anchor:a?a.getValue():null,position:p?p.getValue():null,scale:sc?sc.getValue():null,anchor_time_varying:a?a.isTimeVarying():null,position_time_varying:p?p.isTimeVarying():null,scale_time_varying:sc?sc.isTimeVarying():null,anchor_keys:anchorKeys(a),anchor_display_start:a?a.getValueAtTime(c.inPoint):null,anchor_display_end:a?a.getValueAtTime(c.outPoint):null}});
 }
 vt.push({index:ti,name:s.videoTracks[ti].name,clips:clips});
}
var st=s.getSettings();
__result({project_path:app.project.path,sequence_name:s.name,sequence_id:s.sequenceID,width:st.videoFrameWidth,height:st.videoFrameHeight,video_tracks:vt});
}catch(e){__error('INSPECT '+e.toString()+' line '+e.line);}
"""


def inspect_active() -> dict:
    if LAB_SESSION is not None:
        return LAB_SESSION.inspect_active()
    return bridge_call("inspect", INSPECT_JSX)


def duplicate_vertical(source: dict, project_copy: Path | None, sequence_name: str, work_dir: Path | None = None) -> dict:
    """Clone a vertical sequence in place, or explicitly save into a new project copy."""
    if LAB_SESSION is not None:
        if project_copy is not None or work_dir is None:
            raise ValueError("Lab duplication requires a receipt directory and never switches projects")
        return LAB_SESSION.duplicate(source, sequence_name, work_dir)
    save_as = ""
    if project_copy is not None:
        if project_copy.resolve() == Path(source["project_path"]).resolve():
            raise ValueError("--project-copy must not name the active project")
        if project_copy.exists():
            raise FileExistsError(f"Refusing to overwrite existing project copy: {project_copy}")
        project_copy.parent.mkdir(parents=True, exist_ok=True)
        save_as = f"if(!app.project.saveAs({jsx_string(project_copy)}))throw new Error('SAVE_AS_FAILED');"
    jsx = f"""
try{{
var sourceID={jsx_string(source['sequence_id'])};
if(app.project.path!={jsx_string(source['project_path'])})throw new Error('PROJECT_CHANGED');
var src=null;for(var i=0;i<app.project.sequences.numSequences;i++){{if(app.project.sequences[i].sequenceID==sourceID){{src=app.project.sequences[i];break;}}}}
if(!src)throw new Error('SOURCE_SEQUENCE_MISSING');
for(var n=0;n<app.project.sequences.numSequences;n++){{if(app.project.sequences[n].name=={jsx_string(sequence_name)})throw new Error('DEST_SEQUENCE_EXISTS');}}
app.project.openSequence(src.sequenceID);
{save_as}
src=app.project.activeSequence;
if(!src.clone())throw new Error('SEQUENCE_CLONE_FAILED');
var dup=app.project.activeSequence;
dup.projectItem.name={jsx_string(sequence_name)};
var st=dup.getSettings();st.videoFrameWidth=1080;st.videoFrameHeight=1920;
if(!dup.setSettings(st))throw new Error('VERTICAL_SETTINGS_FAILED');
app.project.openSequence(dup.sequenceID);app.project.save();
__result({{project_path:app.project.path,sequence_name:dup.name,sequence_id:dup.sequenceID}});
}}catch(e){{__error('DUPLICATE '+e.toString()+' line '+e.line);}}
"""
    return bridge_call("duplicate", jsx)


def source_items(inspection: dict) -> list[dict]:
    items = []
    for track in inspection["video_tracks"]:
        for clip in track["clips"]:
            path = clip.get("media_path") or ""
            if path and Path(path).is_file():
                items.append(clip)
    if not items:
        raise RuntimeError("No source-linked video items were found in the active sequence")
    for i, left in enumerate(items):
        for right in items[i + 1 :]:
            if left["track_index"] == right["track_index"]:
                continue
            overlap = min(left["end"], right["end"]) - max(left["start"], right["start"])
            if overlap > 1 / 12:
                raise RuntimeError(
                    "Overlapping source-linked picture tracks detected. This is a native split-screen "
                    "or composited layout; build/confirm the panel sequences using "
                    "references/native-split-setup.md, then run framing inside each panel sequence."
                )
    items.sort(key=lambda x: (x["start"], x["track_index"], x["item_index"]))
    return items


def rolling_median(values: list[float], radius: int = 2) -> list[float]:
    return [float(np.median(values[max(0, i - radius) : i + radius + 1])) for i in range(len(values))]


def rdp(keys: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(keys) <= 2:
        return keys
    t0, x0, y0 = keys[0]
    t1, x1, y1 = keys[-1]
    worst, worst_i = -1.0, -1
    for i in range(1, len(keys) - 1):
        t, x, y = keys[i]
        u = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
        err = math.hypot(x - (x0 + u * (x1 - x0)), y - (y0 + u * (y1 - y0)))
        if err > worst:
            worst, worst_i = err, i
    if worst <= tolerance:
        return [keys[0], keys[-1]]
    return rdp(keys[: worst_i + 1], tolerance)[:-1] + rdp(keys[worst_i:], tolerance)


def crop_safe_margin(sequence_pixels: int, source_pixels: int, scale_factor: float) -> float:
    return sequence_pixels / (2 * source_pixels * scale_factor)


def crop_safe_x_bounds(sequence_pixels: int, source_pixels: int, scale_factor: float, position_x: float) -> tuple[float, float]:
    """Valid normalized Anchor X range at a fixed native Position and Scale."""
    visible_width = sequence_pixels / (source_pixels * scale_factor)
    return position_x * visible_width, 1.0 - (1.0 - position_x) * visible_width


def same_camera_seam(left: dict, right: dict, frame_seconds: float = 1 / 24) -> bool:
    """A picture cut within the same source/camera and panel, not a layout change."""
    return (
        left.get("camera_id", left["media_path"]) == right.get("camera_id", right["media_path"])
        and left["media_path"] == right["media_path"]
        and left["track_index"] == right["track_index"]
        and abs(left["end"] - right["start"]) <= frame_seconds
        and abs(float(left["speed"]) - float(right["speed"])) <= 0.001
        and float(left["speed"]) > 0
    )


def rendered_subject_x(face_x: float, anchor_x: float, position_x: float, source_width: int, scale: float, sequence_width: int) -> float:
    """Subject X in sequence pixels under Premiere's unrotated native Motion."""
    return position_x * sequence_width + (face_x - anchor_x) * source_width * scale


def reconcile_new_plan_x(items: list[dict], records: list[dict], tracked: list[dict], sequence_width: int, tolerance_pixels: float) -> list[dict]:
    """Hold same-camera crop X at a cut; flag any remaining subject jump."""
    seams = []
    for index in range(1, len(items)):
        left_item, right_item = items[index - 1 : index + 1]
        if not same_camera_seam(left_item, right_item):
            continue
        left, right = records[index - 1 : index + 1]
        left_seen = tracked[index - 1].get("edge_face_seen", [True, True])[1]
        right_seen = tracked[index].get("edge_face_seen", [True, True])[0]
        if left["tracking"]["fallback"] or right["tracking"]["fallback"] or not left_seen or not right_seen:
            seams.append({"left": index - 1, "right": index, "status": "needs_visual_review_no_face"})
            continue
        if (abs(left["scale_percent"] - right["scale_percent"]) > 0.001
                or left["tracking"]["width"] != right["tracking"]["width"]):
            seams.append({"left": index - 1, "right": index, "status": "unresolved_scale_or_source_change"})
            continue
        left_face, right_face = tracked[index - 1]["face_x"][-1], tracked[index]["face_x"][0]
        outgoing, incoming = left["anchor_keys"][-1][1], right["anchor_keys"][0][1]
        scale = right["scale_percent"] / 100
        delta = outgoing - incoming
        rendered_pixels = abs(delta) * right["tracking"]["width"] * scale
        subject_after = abs(rendered_subject_x(left_face, outgoing, 0.5, left["tracking"]["width"], scale, sequence_width)
                            - rendered_subject_x(right_face, incoming + delta, 0.5, right["tracking"]["width"], scale, sequence_width))
        if rendered_pixels <= tolerance_pixels:
            status = "anchor_continuous_subject_shift_render_check_required" if subject_after > 25 else "already_continuous"
            seams.append({"left": index - 1, "right": index, "status": status, "pixel_difference": rendered_pixels, "subject_shift_pixels": subject_after})
            continue
        low, high = crop_safe_x_bounds(sequence_width, right["tracking"]["width"], scale, 0.5)
        proposed = [key[1] + delta for key in right["anchor_keys"]]
        if low > high or any(x < low - 1e-8 or x > high + 1e-8 for x in proposed):
            seams.append({"left": index - 1, "right": index, "status": "unresolved_crop_limit", "pixel_difference": rendered_pixels})
            continue
        for key, x in zip(right["anchor_keys"], proposed):
            key[1] = round(x, 8)
        status = "aligned_anchor_subject_shift_render_check_required" if subject_after > 25 else "aligned_x_render_check_required"
        seams.append({"left": index - 1, "right": index, "status": status, "pixel_difference_before": rendered_pixels, "subject_shift_pixels": subject_after, "delta_x": delta})
    return seams


def detector_for(width: int, height: int):
    detect_w = min(1280, width)
    detect_h = max(1, round(height * detect_w / width))
    detector = cv2.FaceDetectorYN_create(str(MODEL), "", (detect_w, detect_h), 0.30, 0.3, 5000)
    return detector, detect_w, detect_h


def select_face(faces, previous_x: float | None, roi, detect_w: int, detect_h: int, min_height720: float = 15):
    if faces is None:
        return None
    rx0, ry0, rx1, ry1 = roi
    strong, rescue = [], []
    for face in faces:
        x, y, w, h = map(float, face[:4])
        score = float(face[-1])  # YuNet stores confidence after ten landmark coordinates.
        cx, cy = x + w / 2, y + h / 2
        h720 = h * 720 / detect_h
        aspect = h / max(w, 1e-6)
        if not (min_height720 <= h720 <= 400 and aspect < 2.0):
            continue
        candidate = (cx, cy, w, h, score)
        if not (rx0 * detect_w <= cx <= rx1 * detect_w and ry0 * detect_h <= cy <= ry1 * detect_h):
            continue
        if score >= 0.60:
            strong.append(candidate)
        elif score >= 0.45 and previous_x is not None and abs(cx - previous_x) <= 0.08 * detect_w:
            rescue.append(candidate)
    candidates = strong or rescue
    if not candidates:
        return None
    if previous_x is None:
        return max(candidates, key=lambda f: f[2] * f[3] * f[4])
    return min(candidates, key=lambda f: abs(f[0] - previous_x))


def track_item(item: dict, preset: dict, sample_seconds: float, cache_dir: Path | None = None) -> dict:
    if cache_dir is None:
        return _track_item_uncached(item, preset, sample_seconds)
    import sys
    sys.path.insert(0, str(HERE))
    from tracking_cache import get_or_compute
    data, receipt = get_or_compute(item, preset, sample_seconds, cache_dir,
                                  _track_item_uncached, [Path(__file__), MODEL])
    return {**data, 'cache_receipt': receipt}


def _track_item_uncached(item: dict, preset: dict, sample_seconds: float) -> dict:
    path = item["media_path"]
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open source media: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    detector, detect_w, detect_h = detector_for(width, height)
    duration = max(0.0, item["source_out"] - item["source_in"])
    final_rel = max(0.0, duration - 1 / fps)
    rel_times = list(np.arange(0.0, final_rel, sample_seconds))
    if not rel_times or final_rel - rel_times[-1] > 1 / fps:
        rel_times.append(final_rel)
    previous = None
    points = []
    misses = 0
    for rel in rel_times:
        cap.set(cv2.CAP_PROP_POS_MSEC, (item["source_in"] + rel) * 1000)
        ok, frame = cap.read()
        if not ok:
            points.append(None)
            misses += 1
            continue
        small = cv2.resize(frame, (detect_w, detect_h))
        _, faces = detector.detect(small)
        chosen = select_face(faces, previous, preset["roi"], detect_w, detect_h, preset.get("min_face_height720", 15))
        if chosen is None:
            points.append(None)
            misses += 1
        else:
            previous = chosen[0]
            points.append((chosen[0] / detect_w, chosen[1] / detect_h))
    cap.release()
    valid = [point for point in points if point is not None]
    fallback = not valid
    if fallback:
        rx0, ry0, rx1, ry1 = preset["roi"]
        default = ((rx0 + rx1) / 2, preset.get("fallback_y", (ry0 + ry1) / 2))
    else:
        default = (float(np.median([p[0] for p in valid])), float(np.median([p[1] for p in valid])))
    xs, ys, last = [], [], default
    first = valid[0] if valid else default
    for point in points:
        if point is not None:
            last = point
        elif not xs:
            last = first
        xs.append(last[0])
        ys.append(last[1])
    xs = rolling_median(xs)
    ys = rolling_median(ys, radius=2)
    if max(abs(x - float(np.median(xs))) for x in xs) < 8 / max(width, 1):
        xs = [float(np.median(xs))] * len(xs)
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "relative_times": [float(x) for x in rel_times],
        "face_x": xs,
        "face_y": ys,
        "face_y_median": float(np.median(ys)),
        "detections": len(valid),
        "samples": len(points),
        "fallback": fallback,
        "edge_face_seen": [points[0] is not None, points[-1] is not None],
        "miss_rate": misses / max(1, len(points)),
    }


def content_groups(items: list[dict]) -> list[list[int]]:
    def logical_camera_key(item: dict):
        if item.get("camera_id"):
            return ("reviewed-camera", item["camera_id"], item["track_index"])
        # CapCut assemblies arrive as separate files but retain a shared parent
        # identity in names such as "alex clip 6-1" through "alex clip 6-11".
        # Treat those butt-joined sections as one visual run so their Y lock is
        # stable across the edit seams. Other media remains path-identity based.
        match = re.search(r"alex clip\s*(\d+)", Path(item["media_path"]).stem.lower())
        if match:
            return ("alex-clip", int(match.group(1)), item["track_index"])
        return ("media", item["media_path"], item["track_index"])

    groups: list[list[int]] = []
    for i, item in enumerate(items):
        if not groups:
            groups.append([i])
            continue
        prev = items[groups[-1][-1]]
        same_camera = logical_camera_key(item) == logical_camera_key(prev)
        butt = abs(item["start"] - prev["end"]) <= 1 / 12
        if same_camera and butt:
            groups[-1].append(i)
        else:
            groups.append([i])
    return groups


def discrete_y_values(data: dict, item_order: int, allow_y_first_items: int) -> tuple[list[float] | None, float]:
    y_span = float(np.percentile(data["face_y"], 90) - np.percentile(data["face_y"], 10))
    ys = np.asarray(data["face_y"], dtype=float)
    edge = max(2, len(ys) // 5)
    start_y = float(np.median(ys[:edge]))
    end_y = float(np.median(ys[-edge:]))
    enabled = (
        item_order < allow_y_first_items
        and not data["fallback"]
        and data["detections"] >= max(3, data["samples"] // 2)
        and y_span >= 0.07
        and abs(end_y - start_y) >= 0.07
    )
    if not enabled:
        return None, y_span
    midpoint = (start_y + end_y) / 2
    transition = int(np.argmin(np.abs(ys - midpoint)))
    # Two locked plateaus with only a short authored move between them. This is
    # a stand/sit reframe, not continuous vertical face tracking.
    before = max(0, transition - 1)
    after = min(len(ys) - 1, transition + 1)
    result = [start_y] * len(ys)
    for j in range(before, after + 1):
        u = 0.0 if after == before else (j - before) / (after - before)
        result[j] = start_y + u * (end_y - start_y)
    for j in range(after + 1, len(ys)):
        result[j] = end_y
    return result, y_span


def build_plan(
    inspection: dict,
    preset_name: str,
    sample_seconds: float,
    pixel_tolerance: float,
    allow_y_first_items: int = 0,
    preset_after_item: int | None = None,
    after_preset_name: str | None = None,
    fallback_y_first_items: float | None = None,
    cache_dir: Path | None = None,
) -> dict:
    items = source_items(inspection)
    animated = [
        f"T{item['track_index'] + 1}/item{item['item_index']}"
        for item in items
        if item["motion"]["anchor_time_varying"]
        or item["motion"]["position_time_varying"]
        or item["motion"]["scale_time_varying"]
    ]
    if animated:
        raise RuntimeError(
            "Existing native Motion animation was found on source items: "
            + ", ".join(animated)
            + ". Start from the approved pre-reframe sequence; this driver never stacks or replaces "
              "an existing animated framing pass."
        )
    presets = []
    for i in range(len(items)):
        selected = after_preset_name if preset_after_item is not None and i >= preset_after_item else preset_name
        item_preset = dict(PRESETS[selected])
        override = items[i].get('framing_override', {})
        if set(override) - {'zoom', 'eye_y', 'roi', 'fallback_y', 'min_face_height720'}:
            raise ValueError('Unknown shot framing override')
        item_preset.update(override)
        if not 15 <= item_preset.get('min_face_height720', 15) <= 400:
            raise ValueError('Invalid calibrated face-size floor')
        if not 1.0 <= item_preset['zoom'] <= 3.0:
            raise ValueError('Reviewed zoom must be between 1 and 3')
        roi = item_preset['roi']
        if len(roi) != 4 or not (0 <= roi[0] < roi[2] <= 1 and 0 <= roi[1] < roi[3] <= 1):
            raise ValueError('Invalid intended-subject ROI')
        if fallback_y_first_items is not None and i < allow_y_first_items:
            item_preset["fallback_y"] = fallback_y_first_items
        presets.append(item_preset)
    tracked = []
    for number, item in enumerate(items, 1):
        data = track_item(item, presets[number - 1], sample_seconds, cache_dir)
        if any(abs(a-b) > 0.20 for a,b in zip(data['face_x'],data['face_x'][1:])):
            raise RuntimeError('Abrupt subject switch inside a tracking run; review the camera boundary or tighten the intended-subject ROI')
        tracked.append(data)
        print(
            f"[{number:02d}/{len(items):02d}] T{item['track_index'] + 1} item {item['item_index']} "
            f"detections={data['detections']}/{data['samples']}"
            + (" FALLBACK" if data["fallback"] else ""),
            flush=True,
        )
    records = []
    groups = content_groups(items)
    group_for = {index: group_no for group_no, group in enumerate(groups) for index in group}
    group_y = {}
    for group_no, group in enumerate(groups):
        ys = [tracked[i]["face_y_median"] for i in group if not tracked[i]["fallback"]]
        group_y[group_no] = float(np.median(ys)) if ys else float(np.median([tracked[i]["face_y_median"] for i in group]))
    for i, (item, data) in enumerate(zip(items, tracked)):
        preset = presets[i]
        scale_factor = inspection["height"] / data["height"] * preset["zoom"]
        scale_percent = scale_factor * 100
        y_values, y_span = discrete_y_values(data, i, allow_y_first_items)
        y_tracking = y_values is not None
        if y_values is None:
            # Workshop/roundtable items can cut directly between standing and
            # seated postures on the same locked camera. Each allowed item gets
            # its own static eyeline; same-camera grouping must not copy a
            # neighboring seated Y onto a standing shot (or vice versa).
            locked_face_y = data["face_y_median"] if i < allow_y_first_items else group_y[group_for[i]]
            y_values = [locked_face_y] * len(data["relative_times"])
        y_offset = (0.5 - preset["eye_y"]) * inspection["height"] / (data["height"] * scale_factor)
        # Anchor Point must stay inside the source area that can cover the
        # sequence at this scale. A generic 0..1 clamp still permits the crop
        # window to cross a source edge and reveal black.
        x_margin = crop_safe_margin(inspection["width"], data["width"], scale_factor)
        y_margin = crop_safe_margin(inspection["height"], data["height"], scale_factor)
        anchor_xs = [max(x_margin, min(1.0 - x_margin, x)) for x in data["face_x"]]
        anchor_ys = [max(y_margin, min(1.0 - y_margin, face_y + y_offset)) for face_y in y_values]
        dense = [
            [round(t, 6), round(x, 8), round(anchor_y, 8)]
            for t, x, anchor_y in zip(data["relative_times"], anchor_xs, anchor_ys)
        ]
        tolerance_normalized = pixel_tolerance / max(1.0, data["width"] * scale_factor)
        sparse = rdp(dense, tolerance_normalized)
        if len(sparse) == 1:
            sparse.append([round(max(0, item["source_out"] - item["source_in"] - 1 / data["fps"]), 6), sparse[0][1], sparse[0][2]])
        records.append(
            {
                **{key: item[key] for key in ("track_index", "item_index", "name", "media_path", "start", "end", "source_in", "source_out", "speed")},
                "camera_id": item.get("camera_id"),
                "framing_override": item.get("framing_override", {}),
                "baseline_motion": item["motion"],
                "position": [0.5, 0.5],
                "scale_percent": scale_percent,
                "anchor_keys": sparse,
                "tracking": {
                    **{key: data[key] for key in ("detections", "samples", "fallback", "miss_rate", "width", "height", "fps")},
                    "y_mode": "tracked_stand_sit" if y_tracking else "locked",
                    "y_robust_span": y_span,
                },
            }
        )
    seam_report = reconcile_new_plan_x(items, records, tracked, inspection["width"], pixel_tolerance)
    return {
        "schema": "premiere-native-reframe/v1",
        **({"bridge_baseline": inspection["bridge_baseline"]} if "bridge_baseline" in inspection else {}),
        "project_path": inspection["project_path"],
        "sequence_name": inspection["sequence_name"],
        "sequence_id": inspection["sequence_id"],
        "sequence_dimensions": [inspection["width"], inspection["height"]],
        "preset": preset_name,
        "pixel_tolerance": pixel_tolerance,
        "allow_y_first_items": allow_y_first_items,
        "preset_after_item": preset_after_item,
        "after_preset": after_preset_name,
        "fallback_y_first_items": fallback_y_first_items,
        "groups": groups,
        "x_seams": seam_report,
        "records": records,
    }


def source_width(path: str) -> int:
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise RuntimeError(f"Cannot read source dimensions: {path}")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        if width <= 0:
            raise RuntimeError(f"Invalid source width: {path}")
        return width
    finally:
        cap.release()


def boundary_subject_x(item: dict, end: bool, expected_anchor_x: float) -> float | None:
    """Observe the likely intended face on the displayed source-edge frames."""
    cap = cv2.VideoCapture(item["media_path"])
    try:
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width <= 0 or height <= 0:
            return None
        detector, detect_w, detect_h = detector_for(width, height)
        first = float(item["source_in"])
        last = max(first, float(item["source_out"]) - 1 / fps)
        frames = [max(first, last - n / fps) for n in (2, 1, 0)] if end else [min(last, first + n / fps) for n in (0, 1, 2)]
        observations = []
        for source_time in frames:
            cap.set(cv2.CAP_PROP_POS_MSEC, source_time * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            small = cv2.resize(frame, (detect_w, detect_h))
            _, faces = detector.detect(small)
            chosen = select_face(faces, expected_anchor_x * detect_w, (0, 0, 1, 1), detect_w, detect_h)
            if chosen is not None:
                observations.append(chosen[0] / detect_w)
        return float(np.median(observations)) if observations else None
    finally:
        cap.release()


def build_existing_seam_plan(
    inspection: dict, source_widths: dict[str, int] | None = None, tolerance_pixels: float = 1.0,
    boundary_faces: dict[tuple[int, int, str], float | None] | None = None,
) -> dict:
    """Plan an X-only adjustment to *existing* native keys; no Premiere writes."""
    if inspection["width"] <= 0 or inspection["height"] <= 0:
        raise ValueError("A valid active sequence is required")
    items = source_items(inspection)
    widths = dict(source_widths or {})
    faces = dict(boundary_faces or {})
    offsets: dict[int, float] = {}
    seams: list[dict] = []
    for index in range(1, len(items)):
        left, right = items[index - 1 : index + 1]
        if not same_camera_seam(left, right):
            continue
        lm, rm = left["motion"], right["motion"]
        if (lm["position_time_varying"] or rm["position_time_varying"]
                or lm["scale_time_varying"] or rm["scale_time_varying"]
                or abs(float(lm["scale"]) - float(rm["scale"])) > 0.001
                or any(abs(a - b) > 0.00001 for a, b in zip(lm["position"], rm["position"]))):
            seams.append({"left": index - 1, "right": index, "status": "unresolved_layout_or_scale_change"})
            continue
        if not rm["anchor_time_varying"] or not rm["anchor_keys"]:
            seams.append({"left": index - 1, "right": index, "status": "unresolved_no_existing_keys"})
            continue
        if not lm.get("anchor_display_end") or not rm.get("anchor_display_start"):
            seams.append({"left": index - 1, "right": index, "status": "unresolved_missing_display_sample"})
            continue
        path = right["media_path"]
        if path not in widths:
            try:
                widths[path] = source_width(path)
            except RuntimeError:
                seams.append({"left": index - 1, "right": index, "status": "unresolved_source_unreadable"})
                continue
        width = widths[path]
        scale = float(rm["scale"]) / 100
        low, high = crop_safe_x_bounds(inspection["width"], width, scale, float(rm["position"][0]))
        prior_offset = offsets.get(index, 0.0)
        left_anchor = float(lm["anchor_display_end"][0]) + offsets.get(index - 1, 0.0)
        right_anchor = float(rm["anchor_display_start"][0]) + prior_offset
        left_key = (left["track_index"], left["item_index"], "end")
        right_key = (right["track_index"], right["item_index"], "start")
        if left_key not in faces:
            try:
                faces[left_key] = boundary_subject_x(left, True, left_anchor)
            except cv2.error:
                faces[left_key] = None
        if right_key not in faces:
            try:
                faces[right_key] = boundary_subject_x(right, False, right_anchor)
            except cv2.error:
                faces[right_key] = None
        if faces[left_key] is None or faces[right_key] is None:
            seams.append({"left": index - 1, "right": index, "status": "unresolved_no_boundary_face"})
            continue
        desired_delta = left_anchor - right_anchor
        rendered_pixels = abs(desired_delta) * width * scale
        subject_after = abs(rendered_subject_x(faces[left_key], left_anchor, float(lm["position"][0]), width, scale, inspection["width"])
                            - rendered_subject_x(faces[right_key], right_anchor + desired_delta, float(rm["position"][0]), width, scale, inspection["width"]))
        if rendered_pixels <= tolerance_pixels:
            status = "anchor_continuous_subject_shift_render_check_required" if subject_after > 25 else "already_continuous"
            seams.append({"left": index - 1, "right": index, "status": status, "pixel_difference": rendered_pixels, "subject_shift_pixels": subject_after})
            continue
        total_offset = prior_offset + desired_delta
        proposed = [float(key["value"][0]) + total_offset for key in rm["anchor_keys"]]
        if low > high or any(x < low - 1e-8 or x > high + 1e-8 for x in proposed):
            seams.append({"left": index - 1, "right": index, "status": "unresolved_crop_limit", "pixel_difference": rendered_pixels})
            continue
        offsets[index] = total_offset
        status = "aligned_anchor_subject_shift_render_check_required" if subject_after > 25 else "aligned_x_render_check_required"
        seams.append({"left": index - 1, "right": index, "status": status, "pixel_difference_before": rendered_pixels, "subject_shift_pixels": subject_after, "delta_x": desired_delta})
    records = []
    for index, offset in sorted(offsets.items()):
        item = items[index]
        motion = item["motion"]
        records.append({
            **{key: item[key] for key in ("track_index", "item_index", "media_path", "start", "end", "source_in", "source_out", "speed")},
            "baseline_motion": motion,
            "new_anchor_keys": [
                {"ticks": key["ticks"], "value": [round(float(key["value"][0]) + offset, 8), float(key["value"][1])]}
                for key in motion["anchor_keys"]
            ],
            "x_offset": offset,
        })
    return {
        "schema": "premiere-native-x-seam-repair/v1",
        **({"bridge_baseline": inspection["bridge_baseline"]} if "bridge_baseline" in inspection else {}),
        "project_path": inspection["project_path"],
        "sequence_name": inspection["sequence_name"],
        "sequence_id": inspection["sequence_id"],
        "sequence_dimensions": [inspection["width"], inspection["height"]],
        "tolerance_pixels": tolerance_pixels,
        "seams": seams,
        "baseline_items": [
            {**{key: item[key] for key in ("track_index", "item_index", "media_path", "start", "end", "source_in", "source_out", "speed")},
             "motion": item["motion"]}
            for item in items
        ],
        "records": records,
    }


def apply_existing_seam_plan(plan_path: Path, plan: dict) -> dict:
    """Revalidate all targeted items, then change only existing Anchor X values."""
    if LAB_SESSION is not None:
        return LAB_SESSION.repair(plan_path, plan)
    if plan.get("schema") != "premiere-native-x-seam-repair/v1":
        raise ValueError("Not an existing-keyframe seam repair plan")
    if not plan.get("records") or not plan.get("baseline_items"):
        raise ValueError("Repair plan has no checked source items and X-key changes")
    jsx = f"""
try{{
var pf=File({jsx_string(plan_path)});if(!pf.exists)throw new Error('PLAN_MISSING');pf.open('r');var plan=JSON.parse(pf.read());pf.close();
if(app.project.path!=plan.project_path)throw new Error('PROJECT_CHANGED');
if(!app.project.activeSequence||app.project.activeSequence.sequenceID!=plan.sequence_id)throw new Error('ACTIVE_SEQUENCE_CHANGED');
var s=app.project.activeSequence,st=s.getSettings();if(st.videoFrameWidth!=plan.sequence_dimensions[0]||st.videoFrameHeight!=plan.sequence_dimensions[1])throw new Error('SEQUENCE_DIMENSIONS_CHANGED');
function prop(c,n){{for(var i=0;i<c.components.numItems;i++){{var fx=c.components[i];if(fx.displayName=='Motion'){{for(var j=0;j<fx.properties.numItems;j++){{if(fx.properties[j].displayName==n)return fx.properties[j];}}}}}}throw new Error('NO_PROPERTY '+n);}}
function close(a,b,t){{return Math.abs(a-b)<=t;}}
function samePair(a,b,t){{return a&&b&&close(a[0],b[0],t)&&close(a[1],b[1],t);}}
var checked=[],baseline={{}};
for(var i=0;i<plan.baseline_items.length;i++){{
 var r=plan.baseline_items[i],track=s.videoTracks[r.track_index],c=track&&track.clips[r.item_index];if(!c)throw new Error('ITEM_MISSING '+i);
 if(c.projectItem.getMediaPath()!=r.media_path||!close(c.start.seconds,r.start,0.0001)||!close(c.end.seconds,r.end,0.0001)||!close(c.inPoint.seconds,r.source_in,0.0001)||!close(c.outPoint.seconds,r.source_out,0.0001)||!close(c.getSpeed(),r.speed,0.001))throw new Error('EDIT_CHANGED '+i);
 var a=prop(c,'Anchor Point'),p=prop(c,'Position'),sc=prop(c,'Scale'),b=r.motion;
 if(a.isTimeVarying()!=b.anchor_time_varying||p.isTimeVarying()!=b.position_time_varying||sc.isTimeVarying()!=b.scale_time_varying||!samePair(p.getValue(),b.position,0.00001)||!close(sc.getValue(),b.scale,0.001))throw new Error('MOTION_CHANGED '+i);
 var keys=a.isTimeVarying()?a.getKeys():[];if(!keys||keys.length!=b.anchor_keys.length)throw new Error('KEY_COUNT_CHANGED '+i);
 if(!a.isTimeVarying()&&!samePair(a.getValue(),b.anchor,0.0000001))throw new Error('ANCHOR_CHANGED '+i);
 for(var j=0;j<keys.length;j++){{if(String(keys[j].ticks)!=b.anchor_keys[j].ticks||!samePair(a.getValueAtKey(keys[j]),b.anchor_keys[j].value,0.0000001))throw new Error('KEY_CHANGED '+i+'/'+j);}}
 baseline[r.track_index+'/'+r.item_index]={{clip:c,anchor:a,keys:keys,motion:b}};
}}
for(var i=0;i<plan.records.length;i++){{var r=plan.records[i],row=baseline[r.track_index+'/'+r.item_index];if(!row||!row.anchor.isTimeVarying()||row.keys.length!=r.new_anchor_keys.length)throw new Error('TARGET_CHANGED '+i);for(var j=0;j<row.keys.length;j++){{if(String(row.keys[j].ticks)!=r.new_anchor_keys[j].ticks||!close(row.motion.anchor_keys[j].value[1],r.new_anchor_keys[j].value[1],0.0000001))throw new Error('TARGET_KEY_CHANGED '+i+'/'+j);}}checked.push({{clip:row.clip,anchor:row.anchor,keys:row.keys,record:r}});}}
var bad=[];
try{{
 for(var i=0;i<checked.length;i++){{var row=checked[i];for(var j=0;j<row.keys.length;j++){{row.anchor.setValueAtKey(row.keys[j],row.record.new_anchor_keys[j].value,false);}}}}
 for(var i=0;i<checked.length;i++){{var row=checked[i];for(var j=0;j<row.keys.length;j++){{if(!samePair(row.anchor.getValueAtKey(row.keys[j]),row.record.new_anchor_keys[j].value,0.0000001))bad.push(i+'/'+j);}}}}
 if(bad.length)throw new Error('KEY_READBACK_FAILED '+bad.join(','));
 app.project.save();
}}catch(writeError){{for(var i=0;i<checked.length;i++){{var row=checked[i];for(var j=0;j<row.keys.length;j++){{try{{row.anchor.setValueAtKey(row.keys[j],row.record.baseline_motion.anchor_keys[j].value,false);}}catch(_rollbackError){{}}}}}}throw new Error('WRITE_ROLLED_BACK_OR_REQUIRES_REVIEW '+writeError.toString());}}
__result({{project_path:app.project.path,sequence_id:s.sequenceID,changed_items:checked.length,bad_keys:bad,status:'SAVED_EXISTING_X_KEYS_ONLY'}});
}}catch(e){{__error('REPAIR_EXISTING '+e.toString()+' line '+e.line);}}
"""
    return bridge_call("repair_existing_seams", jsx, timeout=120.0)


def apply_plan(plan_path: Path, plan: dict) -> dict:
    if LAB_SESSION is not None:
        return LAB_SESSION.apply(plan_path, plan)
    jsx = f"""
try{{
var pf=File({jsx_string(plan_path)});if(!pf.exists)throw new Error('PLAN_MISSING');pf.open('r');var plan=JSON.parse(pf.read());pf.close();
if(app.project.path!=plan.project_path)throw new Error('PROJECT_CHANGED');
var s=null;for(var q=0;q<app.project.sequences.numSequences;q++){{if(app.project.sequences[q].sequenceID==plan.sequence_id){{s=app.project.sequences[q];break;}}}}if(!s)throw new Error('SEQUENCE_MISSING');
function tm(x){{var t=new Time();t.ticks=String(Math.round(x*{TICKS_PER_SECOND}));return t;}}
function prop(c,n){{for(var i=0;i<c.components.numItems;i++){{var fx=c.components[i];if(fx.displayName=='Motion'){{for(var j=0;j<fx.properties.numItems;j++){{if(fx.properties[j].displayName==n)return fx.properties[j];}}}}}}throw new Error('NO_PROPERTY '+n);}}
function close(a,b,t){{return Math.abs(a-b)<=t;}}
function samePair(a,b,t){{return a&&b&&close(a[0],b[0],t)&&close(a[1],b[1],t);}}
var checked=[];
for(var i=0;i<plan.records.length;i++){{var r=plan.records[i],c=s.videoTracks[r.track_index].clips[r.item_index];if(!c)throw new Error('ITEM_MISSING '+i);if(c.projectItem.getMediaPath()!=r.media_path||!close(c.start.seconds,r.start,0.0001)||!close(c.end.seconds,r.end,0.0001)||!close(c.inPoint.seconds,r.source_in,0.0001)||!close(c.outPoint.seconds,r.source_out,0.0001))throw new Error('EDIT_CHANGED '+i);var a=prop(c,'Anchor Point'),p=prop(c,'Position'),sc=prop(c,'Scale'),b=r.baseline_motion;if(a.isTimeVarying()!=b.anchor_time_varying||p.isTimeVarying()!=b.position_time_varying||sc.isTimeVarying()!=b.scale_time_varying||!samePair(a.getValue(),b.anchor,0.00001)||!samePair(p.getValue(),b.position,0.00001)||!close(sc.getValue(),b.scale,0.001))throw new Error('MOTION_CHANGED '+i);checked.push(i);}}
var result=[];
for(var i=0;i<plan.records.length;i++){{var r=plan.records[i],c=s.videoTracks[r.track_index].clips[r.item_index],a=prop(c,'Anchor Point');prop(c,'Position').setValue(r.position,false);prop(c,'Scale').setValue(r.scale_percent,false);a.setTimeVarying(true);for(var j=0;j<r.anchor_keys.length;j++){{var k=r.anchor_keys[j],t=tm(r.source_in+k[0]);a.addKey(t);a.setValueAtKey(t,[k[1],k[2]],false);a.setInterpolationTypeAtKey(t,0,false);}}result.push({{track:r.track_index,item:r.item_index,keys:a.getKeys().length,scale:prop(c,'Scale').getValue(),position:prop(c,'Position').getValue()}});}}
app.project.openSequence(s.sequenceID);if(plan.records.length){{s.setPlayerPosition(tm(plan.records[0].start+0.5).ticks);}}app.project.save();
__result({{project_path:app.project.path,active_sequence:s.name,sequence_id:s.sequenceID,keyed_items:result.length,records:result,status:'SAVED_NATIVE_MOTION'}});
}}catch(e){{__error('APPLY '+e.toString()+' line '+e.line);}}
"""
    return bridge_call("apply", jsx, timeout=120.0)


def verify(plan: dict) -> dict:
    if LAB_SESSION is not None:
        return LAB_SESSION.verify(plan)
    jsx = f"""
try{{
var id={jsx_string(plan['sequence_id'])},s=null;for(var q=0;q<app.project.sequences.numSequences;q++){{if(app.project.sequences[q].sequenceID==id){{s=app.project.sequences[q];break;}}}}if(!s)throw new Error('SEQUENCE_MISSING');
function prop(c,n){{for(var i=0;i<c.components.numItems;i++){{var fx=c.components[i];if(fx.displayName=='Motion'){{for(var j=0;j<fx.properties.numItems;j++){{if(fx.properties[j].displayName==n)return fx.properties[j];}}}}}}}}
var keyed=0,keys=0,bad=[];for(var i=0;i<{len(plan['records'])};i++){{var r={json.dumps([{'track_index': r['track_index'], 'item_index': r['item_index']} for r in plan['records']])}[i],c=s.videoTracks[r.track_index].clips[r.item_index],a=prop(c,'Anchor Point');if(a&&a.isTimeVarying()){{keyed++;keys+=a.getKeys().length;}}else{{bad.push(i);}}}}
app.project.openSequence(s.sequenceID);app.project.save();var st=s.getSettings();__result({{project_path:app.project.path,active_sequence:s.name,sequence_id:s.sequenceID,width:st.videoFrameWidth,height:st.videoFrameHeight,keyed_items:keyed,total_keys:keys,bad_records:bad}});
}}catch(e){{__error('VERIFY '+e.toString()+' line '+e.line);}}
"""
    return bridge_call("verify", jsx)


def bind_reviewed_shots(inspection: dict, shot_map: dict) -> dict:
    """Bind human-reviewed camera/layout intent to exact native item identities.

    Call after picture-only splits and before face tracking. Embedded panels are
    explicitly excluded from the full-frame planner, then composed natively.
    """
    import copy
    if shot_map.get('schema') != 'premiere-reviewed-shots/v1':
        raise ValueError('Unsupported reviewed shot map')
    if (shot_map.get('project_path'), shot_map.get('sequence_id'), shot_map.get('revision')) != (inspection['project_path'], inspection['sequence_id'], inspection['bridge_baseline']['revision']):
        raise ValueError('Reviewed shot map is stale or targets a different sequence')
    rows = shot_map.get('items', [])
    by_id = {r['node_id']: r for r in rows}
    items = source_items(inspection)
    if len(by_id) != len(rows) or set(by_id) != {c['node_id'] for c in items}:
        raise ValueError('Every picture item requires exactly one reviewed shot decision')
    result = copy.deepcopy(inspection)
    for track in result['video_tracks']:
        kept = []
        for c in track['clips']:
            r = by_id[c['node_id']]
            for field in ('media_path', 'start_ticks', 'end_ticks', 'source_in_ticks', 'source_out_ticks'):
                if r[field] != c[field]:
                    raise ValueError('Reviewed source clock changed')
            if not r.get('camera_id') or r.get('layout') not in ('portrait', 'embedded-panels'):
                raise ValueError('Reviewed camera and supported layout required')
            if r['layout'] == 'portrait':
                c['camera_id'] = r['camera_id']
                c['framing_override'] = r.get('framing_override', {})
                kept.append(c)
        track['clips'] = kept
    return result


def main() -> None:
    global LAB_SESSION
    parser = argparse.ArgumentParser(description="Native Premiere 16:9 to 9:16 item-local reframing")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="alex-stage")
    parser.add_argument("--project-copy", type=Path, help="Optional fresh .prproj destination; default keeps the active project")
    parser.add_argument("--sequence-name", help="Review sequence name; default appends _NATIVE_VERTICAL_REVIEW")
    parser.add_argument("--work-dir", type=Path, help="Plan/report directory; default is beside the active project or explicit copy")
    parser.add_argument("--sample-seconds", type=float, default=0.5)
    parser.add_argument("--pixel-tolerance", type=float, default=8.0)
    parser.add_argument(
        "--allow-y-first-items",
        type=int,
        default=0,
        help="Permit thresholded stand/sit Y tracking only on the first N ordered picture items; all later items remain Y-locked",
    )
    parser.add_argument("--preset-after-item", type=int, help="Use --after-preset from this zero-based ordered picture item onward")
    parser.add_argument("--after-preset", choices=sorted(PRESETS), help="Preset for items at/after --preset-after-item")
    parser.add_argument(
        "--fallback-y-first-items",
        type=float,
        help="Calibrated normalized face-center Y used only when detection fails inside the first --allow-y-first-items items",
    )
    parser.add_argument("--plan-only", action="store_true", help="Inspect and build a plan without duplicating or writing Premiere")
    parser.add_argument("--repair-existing-seams", action="store_true", help="Write an X-only plan for the active keyed sequence; never modifies Premiere")
    parser.add_argument("--apply-repair-plan", type=Path, help="Apply a previously inspected X-only plan after revalidating the active edit")
    parser.add_argument("--seam-tolerance-pixels", type=float, default=1.0, help="Maximum existing-seam X mismatch considered already continuous")
    parser.add_argument("--bridge-profile", type=Path, help="Optional profile override; default Premiere Agent handles guarded reframe and existing-X repair")
    parser.add_argument("--shot-map", type=Path, help="Exact reviewed shot map for an already duplicated/split vertical sequence; use --plan-only")
    args = parser.parse_args()
    if args.shot_map and not args.plan_only:
        parser.error("Reviewed shot maps target an existing native sequence; use --plan-only, inspect, then ReframeSession.apply")
    if args.repair_existing_seams and args.apply_repair_plan:
        parser.error("Choose --repair-existing-seams or --apply-repair-plan, not both")
    if (args.repair_existing_seams or args.apply_repair_plan) and args.project_copy:
        parser.error("Existing-keyframe repair works only in the active weekly project")
    if args.seam_tolerance_pixels < 0:
        parser.error("--seam-tolerance-pixels must be nonnegative")
    if (args.preset_after_item is None) != (args.after_preset is None):
        parser.error("--preset-after-item and --after-preset must be supplied together")
    if args.fallback_y_first_items is not None and not (0.0 <= args.fallback_y_first_items <= 1.0):
        parser.error("--fallback-y-first-items must be between 0 and 1")
    if args.fallback_y_first_items is not None and args.allow_y_first_items <= 0:
        parser.error("--fallback-y-first-items requires --allow-y-first-items")

    if args.project_copy:
        parser.error("Use the current exact project; this route does not switch projects")
    from premiere_reframe_bridge import ReframeSession
    LAB_SESSION = ReframeSession(args.bridge_profile)
    initial = inspect_active()
    source_project = Path(initial["project_path"])
    if args.apply_repair_plan:
        plan_path = args.apply_repair_plan.resolve()
        plan = json.loads(plan_path.read_text())
        result = apply_existing_seam_plan(plan_path, plan)
        if result.get("bad_keys"):
            raise RuntimeError(f"Native X-key readback failed: {result['bad_keys']}")
        print(json.dumps({"applied": result, "unresolved_seams": [s for s in plan["seams"] if s["status"].startswith("unresolved")]}, indent=2))
        return
    if args.repair_existing_seams:
        work_dir = args.work_dir or source_project.parent / "native_reframe"
        work_dir.mkdir(parents=True, exist_ok=True)
        plan = build_existing_seam_plan(initial, tolerance_pixels=args.seam_tolerance_pixels)
        plan_path = work_dir / "existing_x_seam_plan.json"
        if plan_path.exists():
            raise FileExistsError(f"Refusing to overwrite an existing repair plan: {plan_path}")
        plan_path.write_text(json.dumps(plan, indent=2))
        print(json.dumps({"plan": str(plan_path), "changed_items": len(plan["records"]), "seams": plan["seams"]}, indent=2))
        return
    sequence_name = args.sequence_name or f"{initial['sequence_name']}_NATIVE_VERTICAL_REVIEW"
    project_copy = args.project_copy
    work_dir = args.work_dir or (project_copy or source_project).parent / "native_reframe"
    work_dir.mkdir(parents=True, exist_ok=True)

    if LAB_SESSION is not None:
        for name in ('premiere_inspection.json', 'native_motion_plan.json', 'native_motion_plan.bridge-operation.json', 'duplicate.bridge-operation.json'):
            if (work_dir / name).exists():
                raise FileExistsError(f'Reframe work directory already has an attempt: {work_dir / name}; inspect its receipts')
    if args.plan_only:
        inspection = initial
        if inspection["width"] != 1080 or inspection["height"] != 1920:
            inspection = {**inspection, "width": 1080, "height": 1920}
    else:
        duplicate_vertical(initial, project_copy, sequence_name, work_dir)
        inspection = inspect_active()
        if inspection["sequence_name"] != sequence_name or inspection["width"] != 1080 or inspection["height"] != 1920:
            raise RuntimeError("Premiere did not activate the expected 1080x1920 review sequence")

    inspection_path = work_dir / "premiere_inspection.json"
    inspection_path.write_text(json.dumps(inspection, indent=2))
    if args.shot_map:
        inspection = bind_reviewed_shots(inspection, json.loads(args.shot_map.read_text()))
    plan = build_plan(
        inspection,
        args.preset,
        args.sample_seconds,
        args.pixel_tolerance,
        args.allow_y_first_items,
        args.preset_after_item,
        args.after_preset,
        args.fallback_y_first_items,
        cache_dir=work_dir / "tracking-cache",
    )
    plan_path = work_dir / "native_motion_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2))
    fallback_records = [i for i, r in enumerate(plan["records"]) if r["tracking"]["fallback"]]
    print(f"plan={plan_path} records={len(plan['records'])} fallback_records={fallback_records}", flush=True)
    if args.plan_only:
        return
    applied = apply_plan(plan_path, plan)
    verification = verify(plan)
    report = {
        "applied": applied,
        "verification": verification,
        "fallback_records": fallback_records,
    }
    report_path = work_dir / "native_reframe_report.json"
    report_path.write_text(json.dumps(report, indent=2))
    if verification["bad_records"] or verification["keyed_items"] != len(plan["records"]):
        raise RuntimeError(f"Native readback failed: {verification}")
    print(json.dumps({**verification, "report": str(report_path), "fallback_records": fallback_records}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from None
    finally:
        if (LAB_SESSION is not None and not LAB_SESSION.client.unsettled
                and not LAB_SESSION.client.transport.pending):
            LAB_SESSION.close()

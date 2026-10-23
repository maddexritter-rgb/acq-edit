#!/usr/bin/env python3
"""Guarded Premiere MOGRT caption-card assembler.

Default mode is an offline plan with zero Bridge calls. A mutating capability
probe requires --apply --probe and an empty dedicated scratch sequence.
Production assembly is unavailable until full style and saved-readback parity.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path("__ACQ_SKILLS__/edit/scripts")))
from pp_export_clips import es  # type: ignore  # noqa: E402

TICKS = 254016000000
REQUIRED_CONTROLS = {"Word 1", "Word 2", "Word 3", "Word 4", "Y Position"}


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def call(project: Path, sequence: str, sequence_uid: str, body: str, timeout: float = 60):
    if not sequence_uid:
        raise ValueError('Exact sequence UID is required for Bridge calls')
    guard = (
        f"if(app.project.path !== {js(str(project))}) throw new Error('Wrong active project: '+app.project.path);"
        f"if(!app.project.activeSequence || app.project.activeSequence.name !== {js(sequence)}) "
        "throw new Error('Wrong active sequence');"
        f"if(app.project.activeSequence.sequenceID !== {js(sequence_uid)}) throw new Error('Wrong sequence UID');"
    )
    result = es(guard + body, timeout=timeout)
    if result is None:
        raise RuntimeError("Premiere bridge returned no result")
    return result


def inspect_template(project: Path, sequence: str, sequence_uid: str, mogrt: Path, track: int, at: float):
    if not sequence.startswith('_CAPTION_PROBE_'):
        raise ValueError('Probe requires a dedicated _CAPTION_PROBE_ scratch sequence')
    if track < 0 or at < 0:
        raise ValueError('Track and probe time must be nonnegative')
    body = f"""
var seq=app.project.activeSequence;
if({track}>=seq.videoTracks.numTracks) throw new Error('Probe track does not exist');
for(var t=0;t<seq.videoTracks.numTracks;t++) if(seq.videoTracks[t].clips.numItems) throw new Error('Probe requires an empty scratch sequence');
for(var t=0;t<seq.audioTracks.numTracks;t++) if(seq.audioTracks[t].clips.numItems) throw new Error('Probe requires an empty scratch sequence');
var before={{}}; for(var i=0;i<seq.videoTracks[{track}].clips.numItems;i++) before[seq.videoTracks[{track}].clips[i].nodeId]=true;
var item=seq.importMGT({js(str(mogrt))},{js(str(int(at*TICKS)))},{track},0);
if(!item) throw new Error('importMGT failed');
var clip=null; for(var j=0;j<seq.videoTracks[{track}].clips.numItems;j++){{var q=seq.videoTracks[{track}].clips[j];if(!before[q.nodeId]){{clip=q;break;}}}}
if(!clip) throw new Error('Could not resolve imported MOGRT clip');
var props=[];
try {{
 var comp=clip.getMGTComponent();
 if(comp) for(var p=0;p<comp.properties.numItems;p++) props.push({{name:comp.properties[p].displayName,value:comp.properties[p].getValue()}});
}} finally {{ clip.remove(false,false); }}
return {{properties:props,removedProbe:true,saved:false,diagnosticOnly:true}};
"""
    return call(project, sequence, sequence_uid, body)


def assemble(project: Path, sequence: str, mogrt: Path, manifest: dict, track: int,
             allow_degraded: bool):
    raise RuntimeError('Production assembly is not implemented: independent style controls and save/reopen readback must pass first. Use an explicit scratch probe, not a degraded production build.')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--sequence", required=True)
    ap.add_argument("--sequence-uid", help="Exact UID; mandatory for any Bridge mutation")
    ap.add_argument("--mogrt", type=Path, default=SKILL / "assets/spice_base_text.mogrt")
    ap.add_argument("--track", type=int, required=True, help="zero-based empty target video track")
    ap.add_argument("--probe-at", type=float, default=0.0)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--probe", action="store_true", help="Mutating diagnostic in an empty _CAPTION_PROBE_ sequence; requires --apply")
    ap.add_argument("--allow-degraded", action="store_true")
    ap.add_argument("--receipt", type=Path, required=True)
    args = ap.parse_args()
    if args.probe and not args.apply:
        ap.error('--probe requires explicit --apply')
    if args.apply and not args.sequence_uid:
        ap.error('--apply requires --sequence-uid')
    if args.allow_degraded:
        ap.error('--allow-degraded is unavailable: it cannot satisfy native parity')
    data = json.loads(args.manifest.read_text())
    from caption_manifest import validate
    validate(data)
    if not args.apply:
        result = {'mode': 'offline-plan', 'bridge_calls': 0, 'cards': len(data['cards']),
                  'production_ready': False, 'saved': False}
    elif args.probe:
        result = inspect_template(args.project.resolve(), args.sequence, args.sequence_uid, args.mogrt.resolve(), args.track, args.probe_at)
    else:
        result = assemble(args.project, args.sequence, args.mogrt, data, args.track, False)
    names = {p["name"] for p in result.get("properties", [])}
    result["control_names_present"] = REQUIRED_CONTROLS.issubset(names)
    result["parity_capable"] = False  # Names alone never establish style/readback parity.
    result["required_controls"] = sorted(REQUIRED_CONTROLS)
    result["project"] = str(args.project)
    result["sequence"] = args.sequence
    result["sequence_uid"] = args.sequence_uid
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result.get('mode') == 'offline-plan' else 4


if __name__ == "__main__":
    raise SystemExit(main())

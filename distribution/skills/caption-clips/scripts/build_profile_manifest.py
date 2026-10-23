#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from caption_profiles import build_profile_manifest, load_profile, validate_profile_manifest

def main():
    p=argparse.ArgumentParser()
    p.add_argument("words",type=Path);p.add_argument("out",type=Path)
    p.add_argument("--caption-profile",choices=("leila","sharran"),required=True)
    p.add_argument("--plan",type=Path,help="Reviewed semantic-card plan JSON; required for production Leila builds")
    p.add_argument("--fps-num",type=int,default=24000);p.add_argument("--fps-den",type=int,default=1001)
    p.add_argument("--picture-cuts",type=Path,help="JSON array of assembly-frame camera/layout cut boundaries")
    a=p.parse_args(); payload=json.loads(a.words.read_text())
    plan=json.loads(a.plan.read_text()) if a.plan else None
    if isinstance(plan,dict): plan=plan["cards"]
    data=build_profile_manifest(payload["words"],load_profile(a.caption_profile),fps_num=a.fps_num,fps_den=a.fps_den,reviewed_plan=plan,picture_cut_frames=json.loads(a.picture_cuts.read_text()) if a.picture_cuts else ())
    validate_profile_manifest(data);a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(data,indent=2)+"\n")
    print(f"profile manifest: {a.caption_profile} {len(data['cards'])} cards / {len(data['render_segments'])} reveals -> {a.out}")
if __name__=="__main__":main()

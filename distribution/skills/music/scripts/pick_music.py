#!/usr/bin/env python3
"""Canonical clip-to-music compatibility ranker used by /edit."""
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path

ROOT = Path("__ACQ_ASSETS__/content-skill-system/(1) Tik Tok").expanduser()
DEFAULT_REVIEW = Path("~/Documents/Codex/2026-09-14/we/outputs/music-review-room/music_review_decisions.json").expanduser()
PROFILES = {
 "reflective_heavy": dict(valence=-.75,energy=.24,tension=.48,warmth=.45,momentum=.22,dialogue_space=.92,tags=["Emotional","Thought-provoking"]),
 "reflective_hopeful": dict(valence=.35,energy=.34,tension=.18,warmth=.78,momentum=.35,dialogue_space=.90,tags=["Inspirational","Thought-provoking","Chill"]),
 "warm_human": dict(valence=.62,energy=.38,tension=.08,warmth=.92,momentum=.34,dialogue_space=.88,tags=["Chill","Inspirational","Emotional"]),
 "confident_modern": dict(valence=.12,energy=.58,tension=.38,warmth=.38,momentum=.64,dialogue_space=.78,tags=["Engaging","Sigma","Luxury"]),
 "urgent_dark": dict(valence=-.58,energy=.78,tension=.90,warmth=.12,momentum=.82,dialogue_space=.68,tags=["Hard","Suspense","Phonk"]),
 "playful_upbeat": dict(valence=.86,energy=.68,tension=.05,warmth=.64,momentum=.76,dialogue_space=.72,tags=["Engaging","GirlyPop","Chill"]),
 "epic_aspirational": dict(valence=.58,energy=.72,tension=.46,warmth=.52,momentum=.72,dialogue_space=.73,tags=["Inspirational","Hard","Engaging"]),
}
LEXICON = {
 "reflective_heavy":"grief died death alone lonely regret pain lost failure suffer ashamed broke trauma",
 "reflective_hopeful":"learned journey future meaning purpose overcome hope recovery changed lesson progress",
 "warm_human":"family friend love team helped kind grateful relationship together care trust",
 "urgent_dark":"warning danger destroy lose fear enemy war crisis urgent risk trap mistake never must",
 "playful_upbeat":"fun funny laugh easy simple weird dating lifestyle joke hilarious ridiculous",
 "epic_aspirational":"dream win greatness impossible legacy discipline become achieve vision mission",
 "confident_modern":"money million business sales offer profit growth scale rich revenue customer strategy",
}

def classify_text(text):
 tokens=re.findall(r"[a-z0-9']+",text.lower()); scores={k:sum(tokens.count(w) for w in v.split()) for k,v in LEXICON.items()}
 for k in ("reflective_heavy","reflective_hopeful","warm_human","urgent_dark"): scores[k]*=1.25
 winner=max(scores,key=scores.get); return (winner if scores[winner] else "confident_modern"),scores

def make_brief(text,supplied=None):
 profile,evidence=classify_text(text); supplied=supplied or {}; profile=supplied.get("profile",profile)
 if profile not in PROFILES: raise ValueError(f"unknown profile: {profile}")
 brief={**PROFILES[profile]}
 for key in ("valence","energy","tension","warmth","momentum","dialogue_space"):
  if key in supplied:
   floor=-1.0 if key=="valence" else 0.0; brief[key]=max(floor,min(1.0,float(supplied[key])))
 brief.update(profile=profile,arc=supplied.get("arc","steady"),role=supplied.get("role","support-dialogue"),
              tags=list(dict.fromkeys(brief["tags"]+list(supplied.get("tags",[])))),avoid=list(supplied.get("avoid",[])),evidence=evidence)
 return brief

def load_json(value,default):
 try:return json.loads(Path(value).expanduser().read_text())
 except (OSError,json.JSONDecodeError,TypeError):return default

def load_rules(path):
 path=Path(path).expanduser()
 if not path.exists():return []
 return [re.split(r"\t|\s+\|\s+",x,maxsplit=1)[0].strip().lower() for x in path.read_text(errors="replace").splitlines() if x.strip() and not x.lstrip().startswith("#")]

def tag_map():
 rows=load_json(ROOT/"(3) ViralREELS"/"_vibe_tags.json",[])
 return {x["file"]:[t.strip() for t in x.get("vibe","").split(",") if t.strip()] for x in rows}

def transcript_arg(value):
 p=Path(value).expanduser()
 if not p.exists():return value
 raw=p.read_text(errors="replace")
 if p.suffix==".json":return " ".join(str(x.get("word","")) for x in json.loads(raw).get("words",[]))
 return raw

def _norm(value,low,high):return max(0.,min(1.,(float(value)-low)/(high-low)))

def describe(s):
 tempo=float(s.get("tempo") or 96)
 while tempo>150:tempo/=2
 energy=_norm(s.get("energy") or .08,.025,.30); bright=_norm(s.get("brightness") or 1300,650,2800)
 onset=_norm(s.get("onset_density") or 1.2,.55,2.8); perc=_norm(s.get("perc_ratio") or .18,.05,.55); major=s.get("mode")=="major"
 return {"valence":max(-1.,min(1.,(.42 if major else -.28)+.38*bright-.12*energy)),
         "energy":.52*energy+.28*onset+.20*_norm(tempo,70,135),"tension":(.38 if not major else .08)+.32*energy+.20*perc,
         "warmth":.62*(1-bright)+.25*(1-perc)+(.13 if major else 0),"momentum":.42*onset+.34*perc+.24*_norm(tempo,72,138),
         "dialogue_space":1-(.46*onset+.32*perc+.22*bright)}

def compatibility(brief,segment):
 desc=describe(segment); weights=dict(valence=.85,energy=1.25,tension=1.,warmth=.65,momentum=1.15,dialogue_space=1.45)
 return math.sqrt(sum(weights[k]*(desc[k]-brief[k])**2 for k in weights)),desc

def semantic_query(brief,semantic):
 if not semantic:return None
 try:
  import sys
  here=Path(__file__).resolve().parent
  shared=Path("__ACQ_SKILLS__/_shared")
  sys.path[:]=[p for p in sys.path if Path(p or ".").resolve() not in {here,shared}]
  import torch
  from transformers import ClapModel,ClapProcessor
  model_name=semantic.get("model","laion/clap-htsat-unfused"); processor=ClapProcessor.from_pretrained(model_name,local_files_only=True)
  model=ClapModel.from_pretrained(model_name,local_files_only=True).eval()
  positive=", ".join(brief["tags"]); text=f"instrumental background music, {brief['profile'].replace('_',' ')}, {positive}, {brief['role']}, {brief['arc']}, clear space for spoken dialogue"
  with torch.inference_mode():
   vec=model.get_text_features(**processor(text=[text],return_tensors="pt",padding=True)); vec=vec.pooler_output if hasattr(vec,"pooler_output") else vec; vec=vec/vec.norm(dim=-1,keepdim=True)
  return [float(x) for x in vec[0]]
 except Exception as exc:raise RuntimeError(f"semantic music matching unavailable: {exc}") from exc

def rank(index,profile=None,used=(),folders=(),review=None,approved=(),banned=(),duration=0,brief=None,limit=None,semantic=None,query=None):
 brief=brief or make_brief("",{"profile":profile or "confident_modern"}); review=review or {}; tagged=tag_map(); out=[]
 for key,track in index.items():
  path=Path(track.get("path",key)); low=path.name.lower()
  if not path.is_file() or "error" in track or track.get("banned"):continue
  try:rel=str(path.relative_to(ROOT))
  except ValueError:rel=key
  decision=review.get(rel,{})
  if folders and track.get("folder") not in folders:continue
  if decision.get("decision")!="keep":continue
  if any(x in low for x in banned) or any(x in low for x in used):continue
  if duration and float(track.get("duration") or 0)<duration+2:continue
  tags=tagged.get(path.name,[])+list(decision.get("tags") or []); segments=track.get("segments") or [{**track,"start":0.}]
  viable=[s for s in segments if not duration or float(track.get("duration") or 0)-float(s.get("start",0))>=duration] or [{**track,"start":0.}]
  choices=[]
  for segment in viable:
   dist,desc=compatibility(brief,segment); hits=len({x.lower() for x in tags}&{x.lower() for x in brief["tags"]})
   avoid=sum(term.lower() in (" ".join(tags)+" "+str(track.get("vibe",""))+" "+low).lower() for term in brief.get("avoid",[]))
   vec=(semantic or {}).get("embeddings",{}).get(rel); sem=0.
   if vec and query: sem=max(-1.,min(1.,sum(a*b for a,b in zip(vec,query))))
   choices.append((dist-.22*hits+.75*avoid+.90*(1-sem),dist,segment,desc,hits,avoid,sem))
  score,dist,segment,desc,hits,avoid,sem=min(choices,key=lambda x:x[0])
  out.append({"score":round(score,4),"path":str(path),"id":rel,"start":round(float(segment.get("start",0)),2),"folder":track.get("folder"),
              "tags":tags,"vibe":track.get("vibe"),"features":desc,"reasons":{"compatibility_distance":round(dist,4),"tag_hits":hits,
              "avoid_hits":avoid,"semantic_similarity":round(sem,4),"review":decision.get("decision"),"segment_start":round(float(segment.get("start",0)),2)}})
 rows=sorted(out,key=lambda x:(x["score"],x["path"].lower()))
 if limit:
  chosen=[]
  for row in rows:
   if not chosen or all(math.sqrt(sum((row["features"][k]-prior["features"][k])**2 for k in row["features"]))>.10 for prior in chosen):chosen.append(row)
   if len(chosen)==limit:break
  chosen.extend(x for x in rows if x not in chosen and len(chosen)<limit); rows=chosen
 return rows

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("--index",default=str(ROOT/"_music_index.json")); ap.add_argument("--transcript",required=True)
 ap.add_argument("--brief-json"); ap.add_argument("--profile",choices=sorted(PROFILES)); ap.add_argument("--folder",default=""); ap.add_argument("--used",default="")
 ap.add_argument("--duration",type=float,default=0); ap.add_argument("--review-decisions",default=str(DEFAULT_REVIEW)); ap.add_argument("--approved",default=str(ROOT/"_APPROVED.txt"))
 ap.add_argument("--blacklist",default=str(ROOT/"MUSIC_BLACKLIST.txt")); ap.add_argument("--n",type=int,default=5); ap.add_argument("--json",action="store_true"); a=ap.parse_args()
 text=transcript_arg(a.transcript); supplied={}
 if a.brief_json:
  p=Path(a.brief_json).expanduser(); supplied=load_json(p,{}) if p.exists() else json.loads(a.brief_json)
 if a.profile:supplied["profile"]=a.profile
 brief=make_brief(text,supplied); semantic=load_json(ROOT/"_music_semantic_index.json",{})
 if len(semantic.get("embeddings",{}))<1:raise RuntimeError("missing _music_semantic_index.json; refusing acoustic-only fallback")
 query=semantic_query(brief,semantic)
 rows=rank(load_json(a.index,{}),used=[x.strip().lower() for x in a.used.split("|") if x.strip()],
  folders=[x.strip() for x in a.folder.split("|") if x.strip()],review=load_json(a.review_decisions,{}),approved=load_rules(a.approved),banned=load_rules(a.blacklist),duration=a.duration,brief=brief,limit=a.n,semantic=semantic,query=query)
 payload={"schema":"edit.music-selection.v2","brief":brief,"picks":rows,"decision_required":"audition top 3 against actual clip; record winner"}
 if a.json:print(json.dumps(payload,indent=2))
 else:
  print(f"profile={brief['profile']} arc={brief['arc']} role={brief['role']}")
  for row in rows:print(f"  {row['score']:6.3f} start={row['start']:6.1f}s {Path(row['path']).name}\n         compatibility={row['reasons']['compatibility_distance']:.3f} tags={','.join(row['tags']) or '-'}")
 return 0 if rows else 2

if __name__=="__main__":raise SystemExit(main())

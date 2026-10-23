#!/usr/bin/env python3
"""Build CLAP music embeddings for the canonical /edit inventory."""
import argparse, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
SHARED = Path("__ACQ_SKILLS__/_shared")
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() not in {HERE, SHARED}]
import librosa, numpy as np, torch
from transformers import ClapModel, ClapProcessor

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--index"); ap.add_argument("--out"); ap.add_argument("--batch",type=int,default=8); a=ap.parse_args()
 root=Path(a.root).expanduser(); index=Path(a.index).expanduser() if a.index else root/"_music_index.json"; out=Path(a.out).expanduser() if a.out else root/"_music_semantic_index.json"
 tracks=json.loads(index.read_text()); model_name="laion/clap-htsat-unfused"; processor=ClapProcessor.from_pretrained(model_name); model=ClapModel.from_pretrained(model_name).eval()
 rows=[]
 for key,v in tracks.items():
  starts=[float(x.get("start",0)) for x in v.get("segments",[])]; start=starts[1] if len(starts)>1 else 0
  y,_=librosa.load(v["path"],sr=48000,mono=True,offset=start,duration=10); rows.append((key,y))
 result={}
 with torch.inference_mode():
  for pos in range(0,len(rows),a.batch):
   chunk=rows[pos:pos+a.batch]; inputs=processor(audio=[x[1] for x in chunk],sampling_rate=48000,return_tensors="pt",padding=True)
   emb=model.get_audio_features(**inputs); emb=emb.pooler_output if hasattr(emb,"pooler_output") else emb; emb=emb/emb.norm(dim=-1,keepdim=True)
   for (key,_),vec in zip(chunk,emb):result[key]=[round(float(x),7) for x in vec]
   print(f"{min(pos+a.batch,len(rows))}/{len(rows)}",flush=True)
 out.write_text(json.dumps({"model":model_name,"embeddings":result}))
 print(f"wrote {out} with {len(result)} tracks")
if __name__=="__main__":main()

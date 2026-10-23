#!/usr/bin/env python3
"""Dispatch to exactly one engine. Import only the chosen adapter."""
import argparse,importlib,json,sys,fcntl
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import read,inside
p=argparse.ArgumentParser();p.add_argument('action',choices=['doctor','inspect','build','revise','render']);p.add_argument('--backend',choices=['filmcraft','premiere','resolve'],required=True);p.add_argument('--config',required=True);p.add_argument('--project');p.add_argument('--packet');a=p.parse_args()
try:
 config=read(a.config);adapter=importlib.import_module(a.backend).Adapter(config)
 if a.action=='doctor':result=adapter.doctor()
 else:
  project=read(a.project)
  if project['backend']!=a.backend:raise RuntimeError('Backend is fixed within a project')
  packet=read(a.packet);inside(project['root'],a.packet)
  lock=Path(project['root'])/'10_WORK/native.lock'
  with lock.open('a') as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   result=getattr(adapter,a.action)(project,packet)
 print(json.dumps(result,indent=2))
except Exception as e:
 print(json.dumps({'status':'failed','error':str(e),'retrySafe':False}),file=sys.stderr);sys.exit(1)

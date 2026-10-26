#!/usr/bin/env python3
"""Canonical Premiere Agent discovery, diagnostics, scope and guarded execution.

Works in existing chats without a refreshed MCP tool list. Does not fall back to
another connector, start Premiere, switch projects or claim host acceptance.
"""
from pathlib import Path
import argparse,json,os,sys,time,fcntl
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'_shared'))
from premiere_bridge import Profile,PremiereBridge,BridgeError,execute_operation

STAGES={
 'assembly':['lab_import_compiled_assembly','lab_apply_assembly_audio_edges'],
 'reframe':['lab_update_static_panel_geometry','lab_export_reframe_frames','lab_reframe_embedded_panels','lab_split_reframe_shots','lab_duplicate_vertical_sequence','lab_apply_reframe_motion','lab_repair_anchor_x_keys'],
 'captions':['lab_import_prepared_caption_sequence','lab_place_graphic_asset'],
 'music':['lab_prepare_music_source','lab_place_music_item','lab_apply_music_envelope'],
 'export':['export_sequence','export_frame','lab_export_exact_range'],
}

def runtime(profile):return (Path(profile.cwd)/'lab/runtime').resolve()
def read_optional(p):return json.loads(p.read_text()) if p.is_file() else None
def doctor(profile):
 root=runtime(profile);heartbeat=root/'mailbox/heartbeat.json'
 # Installation details only; a fresh heartbeat is not command-response proof.
 heartbeats=list((root/'mailbox').glob('*heartbeat*'))
 return {'profile_mode':profile.mode,'connector':profile.connector,'cwd':profile.cwd,
  'command':profile.command,'executable_exists':Path(profile.command[0]).is_file(),
  'entrypoint_exists':Path(profile.command[1]).is_file(),'runtime':str(root),
  'panel':'Premiere Agent Lab','heartbeat_files':[{'path':str(p),'age_seconds':round(time.time()-p.stat().st_mtime,1)} for p in heartbeats],
  'lease':read_optional(root/'lease.json'),'scope':read_optional(Path(profile.project_authorization)) if profile.project_authorization else None,
  'pending_lock':read_optional(root/'writer.lock'),
  'next':'Use tools/schema to verify discovery without Premiere; use inspect ping and inspect lab_snapshot for live readback. Missing MCP tools in this chat do not imply bridge failure. Do not use the retired MCP Bridge panel.'}

def scope(profile,args):
 if profile.mode!='scoped-edit':raise BridgeError('Scope setup requires the default scoped-edit profile')
 root=runtime(profile)
 project=Path(args.project).resolve(strict=True);write=Path(args.write_root).resolve(strict=True)
 if project.suffix!='.prproj' or not write.is_dir():raise BridgeError('Exact existing project and output directory required')
 inputs=json.loads(Path(args.inputs).read_text())
 if not isinstance(inputs,list) or any(not isinstance(p,str) or not Path(p).is_absolute() for p in inputs):raise BridgeError('Inputs must be a JSON array of exact absolute files, including transitive compiler/media references')
 inputs=sorted(set(str(Path(p).resolve(strict=True)) for p in inputs))
 if any(not Path(p).is_file() for p in inputs):raise BridgeError('Exact input files only; no directory grants')
 with (root/'scope-setup.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  prior=read_optional(root/'lease.json')
  if prior and datetime.fromisoformat(prior['expiresAt']).timestamp()>time.time() and prior.get('owner')!=args.owner:
   raise BridgeError('Another owner has an unexpired lease; coordinate its release, never overwrite it')
  if any((root/name).exists() for name in ['writer.lock','mutation.lock']):raise BridgeError('An unresolved writer lock requires reconciliation')
  client=PremiereBridge(profile)
  try:snapshot=client.inspect('lab_snapshot',{})
  finally:client.close()
  if snapshot['projectPath']!=str(project):raise BridgeError('Requested project is not the currently open project; no project switch performed')
  expires=(datetime.now(timezone.utc)+timedelta(hours=args.hours)).isoformat()
  allowed=sorted({'save_project','set_active_sequence'}|{t for stage in args.stages for t in STAGES[stage]})
  auth={'schema':'premiere-agent/edit-project-authorization-v1','projectPath':str(project),'owner':args.owner,'expiresAt':expires,'tools':allowed,'readPaths':inputs,'writeRoot':str(write),'stages':args.stages}
  lease={'projectPath':str(project),'owner':args.owner,'expiresAt':expires,'productionBridgeStopped':True}
  # Auth is inert until its matching lease is installed; atomic replace each file.
  for p,value in [(Path(profile.project_authorization),auth),(root/'lease.json',lease)]:
   temp=p.with_suffix('.new');temp.write_text(json.dumps(value,indent=2)+'\n');temp.chmod(0o600);temp.replace(p)
  return {'scope':auth,'lease':lease,'snapshot':snapshot,'host_mutations':0}

def release(profile,owner):
 root=runtime(profile)
 with (root/'scope-setup.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  lease=read_optional(root/'lease.json')
  if not lease or lease.get('owner')!=owner:raise BridgeError('Only the recorded owner can release this lease')
  if (root/'writer.lock').exists():raise BridgeError('Writer still active or unresolved; reconcile it before release')
  paths=[root/'lease.json']
  if profile.project_authorization:paths.insert(0,Path(profile.project_authorization))
  for p in paths:
   value=read_optional(p)
   if value and value.get('owner')==owner:
    value['expiresAt']=datetime.now(timezone.utc).isoformat();value['released']=True
    temp=p.with_suffix('.new');temp.write_text(json.dumps(value,indent=2)+'\n');temp.chmod(0o600);temp.replace(p)
  return {'released':True,'owner':owner,'host_mutations':0,'project_left_open':lease['projectPath']}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--profile',type=Path)
 sub=ap.add_subparsers(dest='action',required=True)
 sub.add_parser('doctor');sub.add_parser('mcp');sub.add_parser('tools')
 p=sub.add_parser('release');p.add_argument('--owner',required=True)
 p=sub.add_parser('schema');p.add_argument('tool')
 p=sub.add_parser('search');p.add_argument('query');p.add_argument('--limit',type=int,default=20)
 p=sub.add_parser('inspect');p.add_argument('tool');p.add_argument('--args',type=Path)
 p=sub.add_parser('execute');p.add_argument('--plan',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True)
 p=sub.add_parser('scope');p.add_argument('--project',required=True);p.add_argument('--owner',required=True);p.add_argument('--write-root',required=True);p.add_argument('--inputs',required=True);p.add_argument('--stages',nargs='+',choices=STAGES,required=True);p.add_argument('--hours',type=int,choices=range(1,9),default=4);p.add_argument('--ownership-confirmed',action='store_true',required=True,help='Only after coordinating the single writer and confirming the retired bridge stopped')
 args=ap.parse_args();profile=Profile.load(args.profile)
 if args.action=='mcp':
  os.environ['PREMIERE_AGENT_MODE']=profile.mode
  os.chdir(profile.cwd);os.execv(profile.command[0],profile.command)
 if args.action=='doctor':result=doctor(profile)
 elif args.action=='scope':result=scope(profile,args)
 elif args.action=='release':result=release(profile,args.owner)
 else:
  client=PremiereBridge(profile)
  try:
   if args.action in ('tools','schema'):
    entries=[];params={}
    while True:
     page=client.transport.request('tools/list',params);entries.extend(page['tools'])
     if not page.get('nextCursor'):break
     params={'cursor':page['nextCursor']}
    if args.action=='tools':result={'count':len(entries),'tools':[r['name'] for r in entries]}
    else:
     result=next((r for r in entries if r['name']==args.tool),None)
     if result is None:raise BridgeError('Operation absent from installed connector')
   elif args.action=='search':result=client.inspect('lab_search_capabilities',{'query':args.query,'limit':args.limit,'offset':0})
   elif args.action=='inspect':result=client.inspect(args.tool,json.loads(args.args.read_text()) if args.args else {})
   else:result=execute_operation(client,json.loads(args.plan.read_text()),args.receipt)
  finally:client.close()
 print(json.dumps(result,indent=2))
if __name__=='__main__':
 try:main()
 except Exception as error:print(json.dumps({'status':'ERROR','error':str(error),'replay':False}),file=sys.stderr);sys.exit(1)

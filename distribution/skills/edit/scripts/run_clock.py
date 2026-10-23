#!/usr/bin/env python3
"""Append-only run clock. Init before skill reading; phases cover all wall time."""
import argparse,datetime,json,os,pathlib,subprocess,sys,time,uuid,fcntl

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def append(path,row):
    with open(path,'a') as f:
        fcntl.flock(f,fcntl.LOCK_EX);f.write(json.dumps({'utc':now(),**row})+'\n');f.flush();os.fsync(f.fileno())
def read(path):return [json.loads(s)for s in pathlib.Path(path).read_text().splitlines()]
def summary(path):
    rows=read(path);origin=datetime.datetime.fromisoformat(rows[0]['utc']);stop=next((r for r in reversed(rows)if r['type']=='finish'),{'utc':now()});end=datetime.datetime.fromisoformat(stop['utc']);phases=[]
    switches=[r for r in rows if r['type']in ('init','phase')]
    for i,r in enumerate(switches):
        until=switches[i+1]['utc']if i+1<len(switches)else stop['utc'];phases.append({'name':r.get('phase','intake'),'seconds':(datetime.datetime.fromisoformat(until)-datetime.datetime.fromisoformat(r['utc'])).total_seconds()})
    starts={r['id']:r for r in rows if r['type']=='command_start'};done={r['id']:r for r in rows if r['type']=='command_end'}
    return {'wall_seconds':(end-origin).total_seconds(),'finished':any(r['type']=='finish'for r in rows),'phases':phases,'operations':[{'stage':r['stage'],'seconds':done[k].get('seconds')if k in done else None,'returncode':done[k].get('returncode')if k in done else None,'status':'complete'if k in done else'interrupted_or_running'}for k,r in starts.items()],'cache_state':rows[0].get('cache_state'),'note':'Phases partition wall time including reasoning, waits and retries. Concurrent operations overlap phases; do not sum both. No command arguments or secrets are logged.'}
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--log',required=True);sub=ap.add_subparsers(dest='action',required=True)
    q=sub.add_parser('init');q.add_argument('--cache-state',choices=['cold','warm','mixed','unknown'],default='unknown')
    q=sub.add_parser('phase');q.add_argument('name');q=sub.add_parser('run');q.add_argument('--stage',required=True);q.add_argument('command',nargs=argparse.REMAINDER)
    sub.add_parser('finish');sub.add_parser('report');a=ap.parse_args();p=pathlib.Path(a.log)
    if a.action=='init':
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x')as f:f.write(json.dumps({'type':'init','utc':now(),'phase':'intake_and_skill_reading','cache_state':a.cache_state})+'\n')
        return
    rows=read(p)
    if a.action=='report':print(json.dumps(summary(p),indent=2));return
    if any(r['type']=='finish'for r in rows):raise SystemExit('Run already finished; use a new log for a new run.')
    if a.action=='phase':append(p,{'type':'phase','phase':a.name})
    elif a.action=='finish':append(p,{'type':'finish'});print(json.dumps(summary(p),indent=2))
    else:
        command=a.command[1:]if a.command[:1]==['--']else a.command
        if not command:raise SystemExit('Command required after --')
        key=str(uuid.uuid4());append(p,{'type':'command_start','id':key,'stage':a.stage});t=time.monotonic()
        try:rc=subprocess.run(command).returncode
        except OSError:rc=127
        except KeyboardInterrupt:rc=130
        append(p,{'type':'command_end','id':key,'stage':a.stage,'seconds':time.monotonic()-t,'returncode':rc});raise SystemExit(rc if rc>=0 else 128-rc)
if __name__=='__main__':main()

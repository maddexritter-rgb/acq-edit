"""Filmcraft MCP execution transport; editorial decisions belong to stage skills.

Explicit binary/session paths; one isolated headless process; no uncertain retries.
"""
import argparse
import json
import queue
import subprocess
import threading
import time
from pathlib import Path

class Filmcraft:
    def __init__(self, binary, session, project=None):
        self.folder=Path(session).resolve()
        self.folder.mkdir(parents=True,exist_ok=False)
        self.err=(self.folder/'stderr.log').open('w')
        args=[str(Path(binary).resolve()),'mcp','--data-dir',str(self.folder/'data')]
        if project:args += ['--project',str(Path(project).resolve())]
        self.p=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.err,text=True,bufsize=1)
        self.q=queue.Queue();self.i=0;self.uncertain=False
        def read():
            for line in self.p.stdout:
                try:self.q.put(json.loads(line))
                except ValueError:self.q.put({'invalid':line})
            self.q.put({'eof':True})
        threading.Thread(target=read,daemon=True).start()
        self.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'edit-filmcraft','version':'1'}})
        self.p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');self.p.stdin.flush()
    def request(self, method, params, timeout=180):
        if self.uncertain:raise RuntimeError('Uncertain prior outcome: inspect receipts/project before a new session; no retry')
        self.i+=1;req={'jsonrpc':'2.0','id':self.i,'method':method,'params':params};start=time.monotonic()
        try:
            self.p.stdin.write(json.dumps(req)+'\n');self.p.stdin.flush()
            while True:
                r=self.q.get(timeout=max(.01,timeout-(time.monotonic()-start)))
                if r.get('eof'):raise RuntimeError('Filmcraft process closed')
                if r.get('id')==self.i:break
        except Exception as exc:
            self.uncertain=True;r={'uncertain':str(exc)};raise
        finally:
            with (self.folder/'receipts.jsonl').open('a') as f:f.write(json.dumps({'request':req,'response':locals().get('r'), 'elapsed_s':time.monotonic()-start})+'\n')
        if 'error' in r:raise RuntimeError(r['error'])
        return r
    def tool(self,name,args=None):
        v=self.request('tools/call',{'name':name,'arguments':args or {}})['result']
        if v.get('isError'):raise RuntimeError(v)
        if 'structuredContent' in v:return v['structuredContent']
        for c in v.get('content',[]):
            if c.get('type')=='text':
                try:return json.loads(c['text'])
                except ValueError:return c['text']
        return v
    def run(self,command,params=None):return self.tool('command_run',{'id':command,'params':params or {}})
    def close(self):
        if self.uncertain:raise RuntimeError('Session outcome uncertain; preserve process/receipts for reconciliation')
        if self.p.poll() is None:
            if any(not j.get('finished') for j in self.run('jobs.list')):raise RuntimeError('Active export: wait before closing')
            self.p.stdin.close()
            try:self.p.wait(timeout=10)
            except subprocess.TimeoutExpired:self.p.terminate();self.p.wait(timeout=10)
        self.err.close()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--binary',required=True);ap.add_argument('--session',required=True);ap.add_argument('--project');ap.add_argument('--tool',default='command_list');ap.add_argument('--args',type=Path);a=ap.parse_args()
    c=Filmcraft(a.binary,a.session,a.project)
    try:print(json.dumps(c.tool(a.tool,json.loads(a.args.read_text()) if a.args else {}),indent=2))
    finally:c.close()
if __name__=='__main__':main()

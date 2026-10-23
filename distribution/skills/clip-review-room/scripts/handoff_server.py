"""Autosave review feedback to a local JSON file. No messaging or automation.
The historical script filename handoff_server.py is retained for compatibility.
"""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import argparse,json,os,threading,datetime,urllib.parse,math
LOCK=threading.Lock()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));os.replace(tmp,path)
def snapshot(manifest,reviews,route):
 counts=dict(yes=0,revise=0,no=0,unreviewed=0);clips=[]
 for c in manifest['clips']:
  r=reviews.get(c['id'],{});label={'maybe':'revise',None:'unreviewed'}.get(r.get('decision'),r.get('decision'));counts[label]+=1
  clips.append({**{k:c.get(k) for k in ['id','number','display_title','version','media','native_path','source_url','versions','revision_history']},'decision':label,'notes':r.get('notes',''),'timestamped_notes':r.get('timestamped_notes',[]),'updated_at':r.get('updated_at')})
 return dict(schema_version=1,namespace=manifest['namespace'],saved_at=now(),room_url=route['room_url'],manifest_path=route['manifest'],review_file=route['review_file'],summary=counts,clips=clips,reviews=reviews)
def merge_review(manifest,previous,body):
 if body.get('namespace')!=manifest['namespace'] or not isinstance(body.get('reviews'),dict):raise ValueError('Invalid room data')
 valid={c['id'] for c in manifest['clips']+manifest.get('archived_clips',[])};merged=dict(previous)
 for cid,r in body['reviews'].items():
  if cid not in valid or not isinstance(r,dict):raise ValueError('Unknown clip')
  if r.get('decision') not in [None,'yes','maybe','no'] or not isinstance(r.get('notes',''),str) or len(r.get('notes',''))>20000:raise ValueError('Invalid review')
  notes=r.get('timestamped_notes',[])
  if not isinstance(notes,list):raise ValueError('Invalid time notes')
  for n in notes:
   if not isinstance(n,dict) or not isinstance(n.get('text'),str) or not isinstance(n.get('seconds'),(int,float)) or not math.isfinite(n['seconds']) or n['seconds']<0:raise ValueError('Invalid timestamped note')
  stamp=r.get('updated_at','')
  if not isinstance(stamp,str):raise ValueError('Invalid date')
  if cid not in merged or stamp>=merged[cid].get('updated_at',''):merged[cid]=r
 return merged
class Handler(BaseHTTPRequestHandler):
 def route(self,auth=True):
  name=urllib.parse.urlsplit(self.path).path.strip('/');route=json.loads(CONFIG.read_text())['rooms'].get(name)
  if not route or self.headers.get('Origin')!=route['origin'] or (auth and self.headers.get('X-Review-Token')!=route['token']):raise ValueError('Unauthorized room')
  return route
 def respond(self,data,code=200,origin=None):
  raw=json.dumps(data).encode();self.send_response(code)
  if origin:self.send_header('Access-Control-Allow-Origin',origin)
  self.send_header('Vary','Origin');self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_OPTIONS(self):
  try:r=self.route(False)
  except ValueError:return self.respond({'error':'Forbidden'},403)
  self.send_response(204);self.send_header('Access-Control-Allow-Origin',r['origin']);self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS');self.send_header('Access-Control-Allow-Headers','Content-Type, X-Review-Token');self.end_headers()
 def do_GET(self):
  try:r=self.route()
  except ValueError:return self.respond({'error':'Forbidden'},403)
  p=Path(r['review_file']);self.respond(json.loads(p.read_text()) if p.exists() else {'reviews':{}},origin=r['origin'])
 def do_POST(self):
  try:r=self.route()
  except ValueError:return self.respond({'error':'Forbidden'},403)
  try:
   length=int(self.headers.get('Content-Length',0))
   if not 0<length<2000000 or self.headers.get_content_type()!='application/json':raise ValueError('Invalid payload')
   body=json.loads(self.rfile.read(length));manifest=json.loads(Path(r['manifest']).read_text());path=Path(r['review_file'])
   with LOCK:
    previous=json.loads(path.read_text()).get('reviews',{}) if path.exists() else {}
    reviews=merge_review(manifest,previous,body);data=snapshot(manifest,reviews,r);atomic(path,data)
   self.respond({'saved':True,'saved_at':data['saved_at'],'review_file':str(path)},origin=r['origin'])
  except (ValueError,TypeError,KeyError) as e:self.respond({'error':str(e)},400,r['origin'])
  except OSError:self.respond({'error':'Could not save review file'},500,r['origin'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--port',type=int,default=43128);a=p.parse_args();CONFIG=Path(a.config);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()

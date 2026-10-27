import { createServer,type IncomingMessage,type ServerResponse } from 'node:http';
import { createReadStream } from 'node:fs';
import { pipeline } from 'node:stream';
import { readFile,stat } from 'node:fs/promises';
import path from 'node:path';
import { randomBytes,timingSafeEqual } from 'node:crypto';
import { Store } from './store.js';
import { ROOT,type Config } from './config.js';
import { invariant } from './contracts.js';
import { containedFile } from './files.js';
import { exportState } from './projects.js';
import { workOne } from './worker.js';
import {referenceReview,referenceMedia} from './reference-review.js';
async function body(req:IncomingMessage){let s='';for await(const b of req){s+=b;if(s.length>1_000_000)throw new Error('Request too large')}return JSON.parse(s)}
function json(res:ServerResponse,value:unknown,status=200){res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(value))}
export function serve(store:Store,config:Config,runWorker=true){const token=randomBytes(32).toString('hex');let worker:Promise<unknown>|undefined;let closing=false;const controller=new AbortController();let timer:NodeJS.Timeout|undefined;
 const server=createServer(async(req,res)=>{try{
  const host=req.headers.host||'';invariant(host===`127.0.0.1:${(server.address() as any).port}`,'Invalid host');const origin=`http://${host}`;const url=new URL(req.url||'/',origin);
  res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
  if(req.method==='GET'&&url.pathname==='/session'){invariant(url.searchParams.get('token')===token,'Invalid session token');res.writeHead(303,{'Set-Cookie':`acq_session=${token}; HttpOnly; SameSite=Strict; Path=/`,'Location':'/'});res.end();return}
  const cookie=req.headers.cookie?.split(';').map(x=>x.trim()).find(x=>x.startsWith('acq_session='))?.slice(12)||'';
  invariant(cookie.length===token.length&&timingSafeEqual(Buffer.from(cookie),Buffer.from(token)),'Open the authenticated review URL printed by acq-edit serve');
  if(req.method!=='GET'){invariant(req.headers.origin===origin,'Cross-origin request refused');invariant(req.headers['content-type']?.startsWith('application/json'),'JSON required')}
  if(url.pathname==='/api/projects'&&req.method==='GET'){json(res,store.projects());return}
  let match=url.pathname.match(/^\/api\/projects\/([^/]+)$/);if(match&&req.method==='GET'){json(res,store.snapshot(match[1]!));return}
  match=url.pathname.match(/^\/api\/feedback\/([^/]+)$/);if(match&&req.method==='PUT'){const b=await body(req);const f=store.saveFeedback(match[1]!,b.feedback,b.expectedRevision);await exportState(store,store.clip(store.version(match[1]!).clipId).projectId);json(res,f);return}
  match=url.pathname.match(/^\/api\/projects\/([^/]+)\/revisions$/);if(match&&req.method==='POST'){const b=await body(req);invariant(Array.isArray(b.versionIds),'versionIds required');const j=store.enqueue(match[1]!,b.versionIds);await exportState(store,j.projectId);json(res,j,202);return}
  match=url.pathname.match(/^\/api\/versions\/([^/]+)\/reference$/);if(match&&req.method==='GET'){const v=store.version(match[1]!),p=store.project(store.clip(v.clipId).projectId);json(res,await referenceReview(p,v));return}
  match=url.pathname.match(/^\/api\/projects\/([^/]+)\/export$/);if(match&&req.method==='GET'){res.setHeader('Content-Disposition','attachment; filename="review-feedback.json"');json(res,store.snapshot(match[1]!));return}
  match=url.pathname.match(/^\/(media|reference-media)\/([^/]+)$/);if(match&&req.method==='GET'){
   const isReference=match[1]==='reference-media',v=store.version(match[2]!),p=store.project(store.clip(v.clipId).projectId);const file=isReference?await referenceMedia(p,v):await containedFile(p.root,v.media),size=(await stat(file)).size;res.setHeader('Content-Type',path.extname(file).toLowerCase()==='.webm'?'video/webm':path.extname(file).toLowerCase()==='.mov'?'video/quicktime':'video/mp4');res.setHeader('Accept-Ranges','bytes');
   if(!isReference&&url.searchParams.has('download'))res.setHeader('Content-Disposition',`attachment; filename="clip-${v.clipId.slice(0,8)}-v${v.number}${path.extname(file)}"`);
   // pipeline closes the response on read failures and releases the file on client disconnect.
   // Headers may already be sent, so an interrupted response must not receive a JSON error body.
   const range=req.headers.range;if(range){const m=range.match(/^bytes=(\d*)-(\d*)$/);invariant(m&&(m[1]||m[2]),'Invalid byte range');const start=m[1]?Number(m[1]):Math.max(0,size-Number(m[2])),end=m[1]?(m[2]?Math.min(size-1,Number(m[2])):size-1):size-1;
    if(start>=size||start>end){res.writeHead(416,{'Content-Range':`bytes */${size}`});res.end();return}res.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${size}`,'Content-Length':end-start+1});pipeline(createReadStream(file,{start,end}),res,()=>{});
   }else{res.writeHead(200,{'Content-Length':size});pipeline(createReadStream(file),res,()=>{})}return;
  }
  const assets:Record<string,string>={'/':'index.html','/app.js':'app.js','/activity.js':'activity.js','/reference.js':'reference.js','/style.css':'style.css'};const asset=assets[url.pathname];if(asset&&req.method==='GET'){res.setHeader('Content-Type',asset.endsWith('.html')?'text/html; charset=utf-8':asset.endsWith('.css')?'text/css':'text/javascript');res.end(await readFile(path.join(ROOT,'web',asset)));return}
  json(res,{error:'Not found'},404);
 }catch(e){json(res,{error:(e as Error).message},400)}});
 server.on('listening',()=>{if(runWorker)timer=setInterval(()=>{if(worker||closing)return;worker=workOne(store,config,controller.signal).catch(e=>console.error('Worker:',e.message)).finally(()=>worker=undefined)},1500)});
 server.on('close',()=>{if(timer)clearInterval(timer)});
 const stop=async()=>{
  closing=true;if(timer)clearInterval(timer);controller.abort();
  const closed=new Promise<void>((resolve,reject)=>server.close(e=>e?reject(e):resolve()));
  server.closeIdleConnections();
  await Promise.all([closed,worker]);
 };
 return {server,token,stop};
}

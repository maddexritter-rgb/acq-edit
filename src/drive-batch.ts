import {randomUUID} from 'node:crypto';
import {mkdir,readFile,statfs} from 'node:fs/promises';
import path from 'node:path';
import {Store} from './store.js';
import {type DriveBatch,type DriveFile,now,invariant} from './contracts.js';
import {atomicJson,sha256,containedFile} from './files.js';
import {run} from './process.js';
import {importUrl,recoverIntake,intakeProcessAlive,type IntakeTools} from './intake.js';
import {exportState} from './projects.js';

const folderMime='application/vnd.google-apps.folder',shortcutMime='application/vnd.google-apps.shortcut';
const idPattern=/^[A-Za-z0-9_-]+$/;
interface Manifest {schema:'acq-edit/drive-folder-v1';batchId:string;projectId:string;remote:string;folderId:string;files:DriveFile[];folders:{id:string;name:string;parentId:string}[];excluded:{id:string;name:string;parentId:string;reason:string}[]}
async function record(store:Store,id:string,patch:Partial<DriveBatch>={}){const b=store.updateDriveBatch(id,patch);await atomicJson(path.join(b.directory,'batch.json'),b);await exportState(store,b.projectId);return b}
function children(store:Store,b:DriveBatch){return store.intakes(b.projectId).filter(i=>i.batchId===b.id)}
function terminal(store:Store,b:DriveBatch,allowPending=false){
 invariant(!intakeProcessAlive(b.ownerPid)&&!intakeProcessAlive(b.childPid),'Drive batch owner or child is still live');
 invariant(allowPending||!b.childPending,'Batch query launch outcome is unknown; inspect processes and reconcile');
 for(const i of children(store,b)){invariant(!intakeProcessAlive(i.ownerPid)&&!intakeProcessAlive(i.childPid),'A batch file intake process is still live');invariant(allowPending||!i.childPending,'Batch downloader launch outcome is unknown; inspect processes and reconcile')}
}
async function query(store:Store,b:DriveBatch,parentId:string,tools:IntakeTools){
 tools.signal?.throwIfAborted();store.updateDriveBatch(b.id,{childPending:true});
 try{
  const raw=await (tools.execute||run)('rclone',['backend','query',b.remote+':',`'${parentId}' in parents and trashed = false`],{signal:tools.signal,onSpawn:pid=>{store.updateDriveBatch(b.id,{childPid:pid,childPending:false})}});
  const rows=JSON.parse(raw);invariant(Array.isArray(rows),'Drive folder listing is not an array');return rows;
 }finally{store.updateDriveBatch(b.id,{childPid:null,childPending:false})}
}
async function enumerate(store:Store,b:DriveBatch,tools:IntakeTools):Promise<Manifest>{
 const result:Manifest={schema:'acq-edit/drive-folder-v1',batchId:b.id,projectId:b.projectId,remote:b.remote,folderId:b.folderId,files:[],folders:[],excluded:[]};
 const queue=[{id:b.folderId,names:[] as string[]}],seen=new Set([b.folderId]);
 for(let cursor=0;cursor<queue.length;cursor++){
  const parent=queue[cursor]!;invariant(parent.names.length<=32,'Drive folder nesting exceeds 32 levels');
  const rows=await query(store,b,parent.id,tools);
  for(const row of rows){
   invariant(typeof row.id==='string'&&idPattern.test(row.id)&&!seen.has(row.id),'Drive listing contains a duplicate or invalid ID');seen.add(row.id);
   invariant(seen.size<=10001,'Drive batch exceeds 10000 entries; split the folder explicitly');
   invariant(typeof row.name==='string'&&row.name.length>0&&!row.name.includes('\0')&&typeof row.mimeType==='string'&&Array.isArray(row.parents)&&row.parents.includes(parent.id),'Drive folder entry lacks exact name/type/parent evidence');
   invariant(row.mimeType!==shortcutMime,'Drive shortcuts need an explicit target intake; folder batch does not follow them');
   if(row.mimeType===folderMime){result.folders.push({id:row.id,name:row.name,parentId:parent.id});queue.push({id:row.id,names:[...parent.names,row.name]});continue}
   const media=/^(video|audio)\//.test(row.mimeType)||/\.(mp4|mov|mxf|mkv|webm|avi|mts|m2ts|wav|aif|aiff|flac|mp3|m4a|aac|ogg|opus|braw|r3d)$/i.test(row.name);
   if(!media){result.excluded.push({id:row.id,name:row.name,parentId:parent.id,reason:'Not identified as audio/video media'});continue}
   const bytes=Number(row.size);invariant(Number.isSafeInteger(bytes)&&bytes>0&&typeof row.md5Checksum==='string'&&/^[a-f0-9]{32}$/i.test(row.md5Checksum),'Drive media needs a nonempty binary size and MD5');
   result.files.push({id:row.id,name:row.name,parentId:parent.id,folders:parent.names,bytes,md5:row.md5Checksum.toLowerCase()});
  }
 }
 invariant(result.files.length>0,'Drive folder contains no verifiable audio/video files');return result;
}
async function manifest(b:DriveBatch):Promise<Manifest>{
 invariant(b.manifestPath&&b.manifestSha256,'Drive folder manifest is not sealed');const file=await containedFile(b.directory,b.manifestPath);
 invariant(await sha256(file)===b.manifestSha256,'Frozen Drive folder manifest changed');const m=JSON.parse(await readFile(file,'utf8'));
 invariant(m.schema==='acq-edit/drive-folder-v1'&&m.batchId===b.id&&m.projectId===b.projectId&&m.folderId===b.folderId&&m.remote===b.remote,'Drive manifest identity differs');return m;
}
async function transfer(store:Store,id:string,tools:IntakeTools,retryFailed=false){
 try{
  let b=store.driveBatch(id);await mkdir(b.directory,{recursive:true,mode:0o700});await record(store,id);
  if(!b.manifestPath){const m=await enumerate(store,b,tools),file=path.join(b.directory,'manifest.json');await atomicJson(file,m);b=await record(store,id,{manifestPath:file,manifestSha256:await sha256(file),state:'transferring'})}
  const m=await manifest(b);await record(store,id,{state:'transferring'});
  const remaining=m.files.filter(f=>!children(store,b).some(i=>i.fileId===f.id&&i.state==='ready')).reduce((sum,f)=>sum+f.bytes,0);
  invariant(Number.isSafeInteger(remaining),'Drive batch byte count exceeds supported range');
  const root=store.project(b.projectId).root,fs=tools.freeBytes?null:await statfs(root);const free=tools.freeBytes?await tools.freeBytes(root):fs!.bavail*fs!.bsize;
  invariant(free>remaining*2+1024**3,'Insufficient free space for remaining Drive files, verified copies and reserve');
  for(const file of m.files){
   tools.signal?.throwIfAborted();const prior=children(store,b).find(i=>i.fileId===file.id);
   if(prior&&!(retryFailed&&prior.state==='failed')){await recoverIntake(store,prior.id,tools);continue}
   await importUrl(store,b.projectId,`https://drive.google.com/file/d/${file.id}/view`,'drive',b.remote,tools,{id,expected:file});
  }
  invariant(m.files.every(f=>children(store,b).some(i=>i.fileId===f.id&&i.state==='ready')),'Drive batch source coverage is incomplete');
  return await record(store,id,{state:'ready',ownerPid:null,childPid:null,error:null});
 }catch(e){await record(store,id,{state:'failed',ownerPid:null,error:(e as Error).message});throw new Error(`Drive batch ${id}: ${(e as Error).message}`)}
}
export async function importDriveFolder(store:Store,projectId:string,url:string,remote='drive',tools:IntakeTools={}){
 const u=new URL(url),folderId=u.pathname.match(/^\/drive\/(?:u\/\d+\/)?folders\/([A-Za-z0-9_-]+)\/?$/)?.[1];
 invariant(u.protocol==='https:'&&u.hostname==='drive.google.com'&&!u.username&&!u.password&&!u.port&&folderId,'Use an HTTPS Google Drive folder link');invariant(idPattern.test(remote),'Invalid rclone remote name');
 const id=randomUUID(),b:DriveBatch={id,projectId,url,remote,folderId,directory:path.join(store.project(projectId).root,'10_WORK','drive-batches',id),state:'enumerating',ownerPid:process.pid,childPid:null,createdAt:now(),updatedAt:now(),error:null};
 store.addDriveBatch(b);return transfer(store,id,tools);
}
export async function resumeDriveBatch(store:Store,id:string,tools:IntakeTools={},retryFailed=false){
 const b=store.driveBatch(id);invariant(b.state!=='abandoned','Abandoned batch cannot resume; create a new request');
 if(b.state==='ready'){const m=await manifest(b);for(const f of m.files){const i=children(store,b).find(i=>i.fileId===f.id&&i.state==='ready');invariant(i,'Batch source missing');await recoverIntake(store,i.id,tools)}return b}
 store.transaction(()=>{const current=store.driveBatch(id);terminal(store,current);invariant(!store.jobs(b.projectId).some(j=>['editing','rendering','reconciliation_required'].includes(j.state)),'An editing job owns this project');store.updateDriveBatch(id,{ownerPid:process.pid,error:null,state:current.manifestPath?'transferring':'enumerating'})});
 return transfer(store,id,tools,retryFailed);
}
export async function abandonDriveBatch(store:Store,id:string,evidencePath:string){
 const b=store.driveBatch(id);invariant(!['ready','abandoned'].includes(b.state),'Only an unresolved batch can be abandoned');const evidence=await containedFile(store.project(b.projectId).root,evidencePath),report=JSON.parse(await readFile(evidence,'utf8'));
 invariant(report.batchId===id&&report.noActiveWriter===true&&typeof report.processInspection==='string'&&report.processInspection.trim(),'Evidence must identify the batch and describe observed terminal process state');
 store.transaction(()=>{terminal(store,store.driveBatch(id),true);for(const i of children(store,b))if(i.state!=='ready')store.updateIntake(i.id,{state:'failed',ownerPid:null,childPid:null,childPending:false,error:'Batch abandoned after operator process inspection'});store.updateDriveBatch(id,{state:'abandoned',ownerPid:null,childPid:null,childPending:false,error:'Operator abandoned batch; all files retained'});store.event(b.projectId,{type:'drive-batch.abandoned',batchId:id,evidence})});return record(store,id);
}

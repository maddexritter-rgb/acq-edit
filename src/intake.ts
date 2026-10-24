import {randomUUID,createHash} from 'node:crypto';
import {createReadStream,constants} from 'node:fs';
import {mkdir,copyFile,stat,lstat,statfs,rename,chmod,readdir,readFile,realpath} from 'node:fs/promises';
import path from 'node:path';
import {Store} from './store.js';
import {type Intake,type Source,type DriveFile,now,invariant} from './contracts.js';
import {atomicJson,sha256,safeName,containedFile} from './files.js';
import {run,type RunOptions} from './process.js';
import {exportState} from './projects.js';

export interface IntakeTools {execute?:typeof run;freeBytes?:(folder:string)=>Promise<number>;signal?:AbortSignal}
const reserve=1024**3;
async function available(folder:string,tools:IntakeTools){if(tools.freeBytes)return tools.freeBytes(folder);const fs=await statfs(folder);return fs.bavail*fs.bsize}
async function exists(file:string){try{await lstat(file);return true}catch(e:any){if(e.code==='ENOENT')return false;throw e}}
export function intakeProcessAlive(pid:number|null){if(pid===null)return false;invariant(Number.isSafeInteger(pid)&&pid>0,'Invalid intake process identity');try{process.kill(pid,0);return true}catch(e:any){if(e.code==='ESRCH')return false;throw e}}
async function record(store:Store,id:string,patch:Partial<Intake>={}){const i=store.updateIntake(id,patch);await atomicJson(path.join(i.directory,'intake.json'),i);return i}
async function execute(store:Store,id:string,command:string,args:string[],tools:IntakeTools,options:RunOptions={}){
 store.updateIntake(id,{childPending:true});
 try{return await (tools.execute||run)(command,args,{...options,signal:tools.signal,onSpawn:pid=>{store.updateIntake(id,{childPid:pid,childPending:false})}})}
 finally{store.updateIntake(id,{childPid:null,childPending:false})}
}
async function begin(store:Store,projectId:string,kind:Intake['kind'],input:string,origin:string,extra:Partial<Intake>={}){
 const project=store.project(projectId),id=randomUUID();const directory=path.join(project.root,'10_WORK','intake',id);
 const intake: Intake = {id,projectId,kind,input,origin,directory,state:kind==='local'?'verifying':'downloading',ownerPid:process.pid,childPid:null,createdAt:now(),updatedAt:now(),error:null,...extra};
 store.addIntake(intake);await mkdir(directory,{recursive:true,mode:0o700});await record(store,id);return intake;
}
function parseUrl(url:string,kind:'youtube'|'drive',remote:string){
 const p=new URL(url);invariant(p.protocol==='https:'&&!p.username&&!p.password&&!p.port,'Expected an HTTPS footage URL without embedded credentials');
 if(kind==='youtube'){invariant(['youtube.com','www.youtube.com','youtu.be','m.youtube.com'].includes(p.hostname),'Expected a YouTube HTTPS URL');return {}}
 invariant(p.hostname==='drive.google.com','Expected a Google Drive URL');
 const id=p.pathname.match(/^\/file\/d\/([A-Za-z0-9_-]+)(?:\/|$)/)?.[1]||p.searchParams.get('id');
 invariant(id&&/^[A-Za-z0-9_-]+$/.test(id),'Use a single Drive file link; folders are imported file by file');
 invariant(/^[A-Za-z0-9_-]+$/.test(remote),'Invalid rclone remote name');return {remote,fileId:id};
}
async function downloaded(store:Store,intake:Intake){
 const folder=path.join(intake.directory,'download');let candidate:string;
 if(intake.kind==='youtube'){
  const lines=(await readFile(path.join(intake.directory,'completed-path.txt'),'utf8')).trim().split('\n');invariant(lines.length===1&&lines[0],'Expected one completed YouTube download');candidate=lines[0]!;
 }else{
  const entries=await readdir(folder,{withFileTypes:true});invariant(entries.length===1&&entries[0]!.isFile()&&!/\.(partial|part|tmp)$/i.test(entries[0]!.name),'Drive download is incomplete or contains unexpected files');candidate=path.join(folder,entries[0]!.name);
 }
 invariant((await lstat(candidate)).isFile(),'Downloaded candidate must be a regular file');candidate=await containedFile(folder,candidate);await record(store,intake.id,{candidate,state:'verifying'});return candidate;
}
async function driveProof(store:Store,i:Intake,candidate:string,tools:IntakeTools){
 const name=path.basename(candidate),escaped=name.replaceAll('\\','\\\\').replaceAll("'","\\'");
 const raw=await execute(store,i.id,'rclone',['backend','query',i.remote+':',`name = '${escaped}' and trashed = false`],tools);
 const rows=JSON.parse(raw);invariant(Array.isArray(rows),'Drive metadata result is not an array');const matches=rows.filter((x:any)=>x.id===i.fileId);invariant(matches.length===1,'Cannot verify exact Drive file metadata; no filename-only acceptance');const m=matches[0];
 invariant(typeof m.md5Checksum==='string'&&/^[0-9a-f]{32}$/i.test(m.md5Checksum),'Drive file has no usable MD5; remote verification is unavailable');
 if(i.driveExpected){const expected=i.driveExpected;invariant(m.id===expected.id&&m.name===expected.name&&Number(m.size)===expected.bytes&&m.md5Checksum.toLowerCase()===expected.md5&&Array.isArray(m.parents)&&m.parents.includes(expected.parentId),'Drive file changed from the frozen folder manifest')}
 const size=Number(m.size);invariant(Number.isSafeInteger(size)&&size>0&&size===(await stat(candidate)).size,'Drive file size differs');
 const h=createHash('md5');for await(const chunk of createReadStream(candidate))h.update(chunk);const md5=h.digest('hex');invariant(md5===m.md5Checksum.toLowerCase(),'Drive MD5 differs from downloaded bytes');
 return {kind:'drive-md5',fileId:i.fileId,name:m.name,bytes:size,md5,modifiedTime:m.modifiedTime,checkedAt:now()};
}
async function complete(store:Store,id:string,tools:IntakeTools):Promise<Source>{
 tools.signal?.throwIfAborted();
 let i=store.intake(id);const p=store.project(i.projectId);
 let candidate=i.kind==='local'?await realpath(i.input):await downloaded(store,i);
 const before=await stat(candidate);invariant(before.isFile()&&before.size>0,'Source must be a nonempty regular file');
 const remote=i.kind==='drive'?await driveProof(store,i,candidate,tools):undefined;
 const hash=await sha256(candidate);invariant(!i.expectedSha256||i.expectedSha256===hash,'Intake candidate changed; preserve this attempt and start a new one');
 const extension=path.extname(candidate).toLowerCase();invariant(/^\.[a-z0-9]{1,12}$/.test(extension),'Source needs a normal media filename extension');
 const target=i.target||path.join(p.root,'00_SOURCE',id+'_'+safeName(path.basename(candidate,path.extname(candidate)))+extension);
 invariant(path.dirname(target)===path.join(p.root,'00_SOURCE'),'Intake target is outside the source directory');
 i=await record(store,id,{state:'copying',candidate,target,expectedSha256:hash,bytes:before.size});
 tools.signal?.throwIfAborted();
 const partial=target+'.partial',alreadyLanded=await exists(target);let verifiedFile:string;
 if(alreadyLanded){invariant((await lstat(target)).isFile(),'Landed source must be a regular file');verifiedFile=await containedFile(path.join(p.root,'00_SOURCE'),target)}
 else{
  if(!await exists(partial)){invariant(await available(p.root,tools)>before.size+reserve,'Insufficient free space for source copy plus reserve');await copyFile(candidate,partial,constants.COPYFILE_EXCL)}
  invariant((await lstat(partial)).isFile(),'Partial source is not a regular file');verifiedFile=await containedFile(path.join(p.root,'00_SOURCE'),partial);
 }
 invariant(await sha256(verifiedFile)===hash,'Incomplete or changed source copy; retain partial evidence and start a new attempt');
 const after=await stat(candidate);invariant(before.size===after.size&&before.mtimeMs===after.mtimeMs&&await sha256(candidate)===hash,'Source changed during intake');
 const probe=JSON.parse(await execute(store,id,'ffprobe',['-v','error','-show_format','-show_streams','-of','json',verifiedFile],tools));
 invariant(probe.streams?.some((s:any)=>s.codec_type==='video'||s.codec_type==='audio'),'No audio/video stream');
 const finalRemote=i.kind==='drive'?await driveProof(store,i,candidate,tools):undefined;
 invariant(!remote||(remote.md5===finalRemote?.md5&&remote.bytes===finalRemote.bytes),'Drive source changed during verification');
 tools.signal?.throwIfAborted();
 invariant(await sha256(verifiedFile)===hash,'Source copy changed during media verification');
 const verificationPath=path.join(i.directory,'verification.json');await atomicJson(verificationPath,{schema:'acq-edit/intake-verification-v1',intakeId:id,origin:i.origin,candidate,bytes:before.size,sha256:hash,remote:finalRemote||null,verification:remote?'remote-md5-and-local-sha256':'local-copy-sha256',probed:true,verifiedAt:now(),...(i.batchId?{batchId:i.batchId,folderManifestEntry:i.driveExpected}:{})});
 if(!alreadyLanded){invariant(!await exists(target),'Intake destination appeared during verification');await rename(partial,target)}
 await chmod(target,0o444);const source:Source={id,projectId:i.projectId,path:target,sha256:hash,bytes:before.size,origin:i.origin,probe,intakeId:id,verificationPath,verificationSha256:await sha256(verificationPath)};
 store.finishIntake(id,source);await record(store,id);await exportState(store,i.projectId);return source;
}
async function attempt(store:Store,i:Intake,tools:IntakeTools,download=false){
 try{
  if(download){
   const folder=path.join(i.directory,'download');await mkdir(folder,{mode:0o700});
   const budget=Math.floor((await available(store.project(i.projectId).root,tools)-reserve)/4);invariant(budget>0,'Insufficient free space for download and verified source copy');
   if(i.kind==='youtube')await execute(store,i.id,'yt-dlp',['--ignore-config','--no-playlist','--no-simulate','--restrict-filenames','--no-overwrites','--no-progress','--match-filter','!is_live','--max-filesize',String(budget),'--print-to-file','after_move:filepath',path.join(i.directory,'completed-path.txt'),'-o',path.join(folder,'source.%(ext)s'),'--',i.input],tools,{timeout:4*3600_000});
   else await execute(store,i.id,'rclone',['backend','copyid',i.remote+':',i.fileId!,folder+path.sep,'--checksum','--immutable','--max-transfer',String(budget),'--cutoff-mode','hard'],tools,{timeout:4*3600_000});
   await record(store,i.id,{state:'verifying'});
  }
  return await complete(store,i.id,tools);
 }catch(error){
  if(store.intake(i.id).state!=='ready')await record(store,i.id,{state:'failed',error:(error as Error).message,ownerPid:null,childPid:null});
  await exportState(store,i.projectId);
  throw new Error(`Intake ${i.id}: ${(error as Error).message}`);
 }
}
export async function importLocal(store:Store,projectId:string,file:string,origin='local',tools:IntakeTools={}){
 invariant(file,'Source file required');return attempt(store,await begin(store,projectId,'local',path.resolve(file),origin),tools);
}
export async function importUrl(store:Store,projectId:string,url:string,kind:'youtube'|'drive',remote='drive',tools:IntakeTools={},batch?:{id:string;expected:DriveFile}){
 const extra=parseUrl(url,kind,remote);return attempt(store,await begin(store,projectId,kind,url,kind+':'+url,{...extra,...(batch?{batchId:batch.id,driveExpected:batch.expected}:{})}),tools,true);
}
export async function recoverIntake(store:Store,id:string,tools:IntakeTools={}){
 let i=store.intake(id);
 if(i.state==='ready'){
  const source=store.sources(i.projectId).find(s=>s.id===i.sourceId);invariant(source,'Ready intake has no registered source');invariant(await sha256(source.path)===source.sha256,'Registered source changed');invariant(source.verificationPath&&await sha256(source.verificationPath)===source.verificationSha256,'Verification receipt changed');await record(store,id);await exportState(store,i.projectId);return source;
 }
 store.transaction(()=>{
  i=store.intake(id);invariant(!intakeProcessAlive(i.ownerPid)&&!intakeProcessAlive(i.childPid),'Intake owner or child process is still live; do not replay it');
  invariant(!i.childPending,'Process launch outcome was not recorded; inspect processes and reconcile this intake before retrying');
  invariant(!store.intakes(i.projectId).some(x=>x.id!==id&&!['ready','failed'].includes(x.state)),'Another intake owns the project');
  const batch=store.driveBatches(i.projectId).find(b=>!['ready','abandoned'].includes(b.state));invariant(!batch||batch.id===i.batchId&&batch.ownerPid===process.pid&&batch.state==='transferring','Recover the owning Drive batch first');
  const job=store.jobs(i.projectId).find(j=>['editing','rendering','reconciliation_required'].includes(j.state));invariant(!job,'Recover intake before dispatching another editing job');
  i=store.updateIntake(id,{state:'verifying',ownerPid:process.pid,childPid:null,error:null});
 });
 // Recovery only verifies/copies existing bytes. It never relaunches a downloader.
 return attempt(store,i,tools);
}
export async function abandonIntake(store:Store,id:string,evidencePath:string){
 const i=store.intake(id);invariant(i.state!=='ready','Registered sources cannot be abandoned');
 const evidence=await containedFile(store.project(i.projectId).root,evidencePath);
 const report=JSON.parse(await readFile(evidence,'utf8'));invariant(report.intakeId===id&&typeof report.processInspection==='string'&&report.processInspection.trim()&&report.noActiveWriter===true,'Evidence must identify this intake and describe the operator process inspection');
 store.transaction(()=>{const current=store.intake(id);invariant(current.state!=='ready'&&!intakeProcessAlive(current.ownerPid)&&!intakeProcessAlive(current.childPid),'Intake is registered or a known process is still live');store.updateIntake(id,{state:'failed',ownerPid:null,childPid:null,childPending:false,error:'Operator abandoned this intake after process inspection; see evidence'});store.event(i.projectId,{type:'intake.abandoned',intakeId:id,evidence});});
 await record(store,id);await exportState(store,i.projectId);return store.intake(id);
}

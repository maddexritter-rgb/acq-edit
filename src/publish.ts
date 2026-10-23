import { copyFile,chmod,mkdir,stat } from 'node:fs/promises';
import path from 'node:path';
import { constants } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { Store } from './store.js';
import { type Backend,type Version,invariant,now } from './contracts.js';
import { sha256,containedFile,readJson,atomicJson } from './files.js';
import { run } from './process.js';
import { exportState } from './projects.js';
export interface RenderReceipt {schema:'acq-edit/render-v1';projectId:string;backend:Backend;clipId:string;parentId:string|null;jobId?:string;media:string;nativeProject:string;nativeFingerprint:string;planPath:string;expected:{frames:number;width:number;height:number;fps:string};nativeInspectionPath:string;nativeRendered:true}
export async function publish(store:Store,projectId:string,receiptFile:string):Promise<Version>{
 const p=store.project(projectId);await containedFile(p.root,receiptFile);const r=await readJson<RenderReceipt>(receiptFile);
 invariant(r.schema==='acq-edit/render-v1'&&r.projectId===p.id&&r.backend===p.backend&&r.nativeRendered===true,'Render receipt identity/backend mismatch');
 const jobId=r.jobId||process.env.ACQ_EDIT_JOB_ID;
 if(r.jobId&&process.env.ACQ_EDIT_JOB_ID)invariant(r.jobId===process.env.ACQ_EDIT_JOB_ID,'Receipt belongs to another job');
 store.publicationJob(r.clipId,r.parentId,jobId);
 const c=store.clip(r.clipId);invariant(c.projectId===p.id&&c.currentVersionId===r.parentId,'Stale render receipt');
 for(const f of [r.media,r.nativeProject,r.planPath,r.nativeInspectionPath])await containedFile(p.root,f);
 invariant(await sha256(r.nativeProject)===r.nativeFingerprint,'Native project changed after its receipt');
 const renderedHash=await sha256(r.media);
 const probe=JSON.parse(await run('ffprobe',['-v','error','-count_frames','-show_streams','-of','json',r.media],{timeout:3600_000}));const video=probe.streams.find((s:any)=>s.codec_type==='video');
 invariant(video&&video.width===r.expected.width&&video.height===r.expected.height&&Number(video.nb_read_frames)===r.expected.frames&&video.r_frame_rate===r.expected.fps,'Render frame geometry/rate/count mismatch');
 await run('ffmpeg',['-v','error','-xerror','-i',r.media,'-f','null','-'],{timeout:3600_000});
 const id=randomUUID(),number=store.versions(c.id).length+1;const folder=path.join(p.root,'20_DELIVER',c.id,`v${number}-${id}`);await mkdir(folder,{recursive:true});
 const media=path.join(folder,'clip'+path.extname(r.media));await copyFile(r.media,media,constants.COPYFILE_EXCL);const sum=await sha256(media);invariant(sum===renderedHash&&renderedHash===await sha256(r.media),'Render changed during verification or delivery copy');await chmod(media,0o444);
 const archive:Record<string,string>={};for(const [label,source] of Object.entries({native:r.nativeProject,plan:r.planPath,receipt:receiptFile,inspection:r.nativeInspectionPath})){const target=path.join(folder,label+path.extname(source));await copyFile(source,target,constants.COPYFILE_EXCL);await chmod(target,0o444);archive[label]=target;}
 invariant(await sha256(archive.native!)===r.nativeFingerprint,'Native checkpoint changed during publication');
 const v:Version={id,clipId:c.id,number,media,sha256:sum,nativeProject:r.nativeProject,nativeCheckpoint:archive.native,nativeFingerprint:r.nativeFingerprint,planPath:archive.plan!,receiptPath:archive.receipt!,createdAt:now(),parentId:r.parentId,...(jobId?{jobId}:{})};
 await atomicJson(path.join(folder,'version.json'),v);store.publish(v);await exportState(store,p.id);return v;
}

/** Completion/reconciliation checks the actual immutable bytes, not only database rows. */
export async function verifyPublishedVersions(store:Store,jobId:string,ids:string[]){
 const job=store.job(jobId),p=store.project(job.projectId);
 invariant(Array.isArray(ids)&&ids.length>0,'Published version IDs required');
 for(const id of ids){
  const v=store.version(id);invariant(v.jobId===jobId&&store.clip(v.clipId).projectId===p.id,'Version belongs to another job');
  await containedFile(p.root,v.media);invariant(await sha256(v.media)===v.sha256,'Published media is missing or has changed');
  invariant(v.nativeCheckpoint,'Immutable native checkpoint is missing');await containedFile(p.root,v.nativeCheckpoint);
  invariant(await sha256(v.nativeCheckpoint)===v.nativeFingerprint,'Published native checkpoint changed');
  await containedFile(p.root,v.planPath);await containedFile(p.root,v.receiptPath);
 }
}

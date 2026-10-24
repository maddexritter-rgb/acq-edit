import { copyFile,chmod,mkdir,stat } from 'node:fs/promises';
import path from 'node:path';
import { constants } from 'node:fs';
import { randomUUID } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { Store } from './store.js';
import { type Backend,type Version,type Project,type EditPlan,invariant,now } from './contracts.js';
import { sha256,containedFile,readJson,atomicJson } from './files.js';
import { run } from './process.js';
import { exportState } from './projects.js';
export interface RenderReceipt {schema:'acq-edit/render-v1';projectId:string;backend:Backend;clipId:string;parentId:string|null;jobId?:string;media:string;nativeProject:string;nativeFingerprint:string;planPath:string;expected:{frames:number;width:number;height:number;fps:string};nativeInspectionPath:string;nativeRendered:true;inputMediaVerification?:{phase:'after-render-verification';files:Array<{role:'source'|'graphic';id:string;path:string;expectedSha256:string;actualSha256:string}>};recutVerificationPath?:string;recutVerificationSha256?:string}
export async function verifyRecutReceipt(store:Store,p:Project,r:RenderReceipt){
 const next=await readJson<EditPlan>(await containedFile(p.root,r.planPath));
 invariant(next.projectId===p.id&&next.backend===p.backend&&next.clipId===r.clipId,'Published plan identity/backend mismatch');
 if(!r.parentId)return;
 const parent=store.version(r.parentId),prior=await readJson<EditPlan>(await containedFile(p.root,parent.planPath));
 if(parent.planSha256)invariant(await sha256(parent.planPath)===parent.planSha256,'Published parent plan changed');
 if(isDeepStrictEqual(prior.cuts,next.cuts)&&!r.recutVerificationPath)return;
 invariant(r.recutVerificationPath&&r.recutVerificationSha256,'Changed source cuts require native recut verification and fresh dependent finishing plans');
 invariant(parent.planSha256&&await sha256(parent.planPath)===parent.planSha256,'Parent plan lacks verified publication provenance');
 const file=await containedFile(p.root,r.recutVerificationPath);
 invariant(await sha256(file)===r.recutVerificationSha256,'Recut verification changed');
 const proof=await readJson<any>(file);
 invariant(proof.schema==='acq-edit/recut-execution-v1'&&proof.backend===p.backend&&proof.parentVersionId===parent.id&&proof.parentPreserved===true,'Recut verification identity differs');
 invariant(proof.parentPlanSha256===parent.planSha256&&proof.planSha256===await sha256(r.planPath)&&proof.newNativeSha256===r.nativeFingerprint&&path.resolve(proof.construction.nativeProject)===path.resolve(r.nativeProject),'Recut verification does not describe this parent, plan and native checkpoint');
}
export async function publish(store:Store,projectId:string,receiptFile:string):Promise<Version>{
 store.assertNativeSettled(projectId);
 const p=store.project(projectId);await containedFile(p.root,receiptFile);const receiptHash=await sha256(receiptFile),r=await readJson<RenderReceipt>(receiptFile);
 invariant(r.schema==='acq-edit/render-v1'&&r.projectId===p.id&&r.backend===p.backend&&r.nativeRendered===true,'Render receipt identity/backend mismatch');
 const jobId=r.jobId||process.env.ACQ_EDIT_JOB_ID;
 if(r.jobId&&process.env.ACQ_EDIT_JOB_ID)invariant(r.jobId===process.env.ACQ_EDIT_JOB_ID,'Receipt belongs to another job');
 store.publicationJob(r.clipId,r.parentId,jobId);
 const c=store.clip(r.clipId);invariant(c.projectId===p.id&&c.currentVersionId===r.parentId,'Stale render receipt');
 for(const f of [r.media,r.nativeProject,r.planPath,r.nativeInspectionPath])await containedFile(p.root,f);
 const planHash=await sha256(r.planPath),inspectionHash=await sha256(r.nativeInspectionPath);
 await verifyRecutReceipt(store,p,r);
 invariant(await sha256(r.nativeProject)===r.nativeFingerprint,'Native project changed after its receipt');
 const renderedHash=await sha256(r.media);
 const probe=JSON.parse(await run('ffprobe',['-v','error','-count_frames','-show_streams','-of','json',r.media],{timeout:3600_000}));const video=probe.streams.find((s:any)=>s.codec_type==='video');
 invariant(video&&video.width===r.expected.width&&video.height===r.expected.height&&Number(video.nb_read_frames)===r.expected.frames&&video.r_frame_rate===r.expected.fps,'Render frame geometry/rate/count mismatch');
 await run('ffmpeg',['-v','error','-xerror','-i',r.media,'-f','null','-'],{timeout:3600_000});
 const id=randomUUID(),number=store.versions(c.id).length+1;const folder=path.join(p.root,'20_DELIVER',c.id,`v${number}-${id}`);await mkdir(folder,{recursive:true});
 const media=path.join(folder,'clip'+path.extname(r.media));await copyFile(r.media,media,constants.COPYFILE_EXCL);const sum=await sha256(media);invariant(sum===renderedHash&&renderedHash===await sha256(r.media),'Render changed during verification or delivery copy');await chmod(media,0o444);
 const archive:Record<string,string>={},archiveHashes:Record<string,string>={};for(const [label,source] of Object.entries({native:r.nativeProject,plan:r.planPath,receipt:receiptFile,inspection:r.nativeInspectionPath,...(r.recutVerificationPath?{recut:r.recutVerificationPath}:{})})){const before=await sha256(source),target=path.join(folder,label+path.extname(source));await copyFile(source,target,constants.COPYFILE_EXCL);invariant(await sha256(target)===before&&await sha256(source)===before,'Publication input changed during archival');await chmod(target,0o444);archive[label]=target;archiveHashes[label]=before;}
 invariant(await sha256(archive.native!)===r.nativeFingerprint,'Native checkpoint changed during publication');
 invariant(archiveHashes.plan===planHash&&archiveHashes.inspection===inspectionHash&&archiveHashes.receipt===receiptHash,'Publication evidence changed after verification');
 const v:Version={id,clipId:c.id,number,media,sha256:sum,nativeProject:r.nativeProject,nativeCheckpoint:archive.native,nativeFingerprint:r.nativeFingerprint,planPath:archive.plan!,planSha256:archiveHashes.plan!,inspectionPath:archive.inspection!,inspectionSha256:archiveHashes.inspection!,receiptPath:archive.receipt!,receiptSha256:archiveHashes.receipt!,createdAt:now(),parentId:r.parentId,...(jobId?{jobId}:{})};
 if(archive.recut){invariant(archiveHashes.recut===r.recutVerificationSha256,'Recut verification changed during publication');v.recutVerificationPath=archive.recut;v.recutVerificationSha256=archiveHashes.recut;}
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
  if(v.planSha256)invariant(await sha256(v.planPath)===v.planSha256,'Published plan changed');
  if(v.receiptSha256)invariant(await sha256(v.receiptPath)===v.receiptSha256,'Published receipt changed');
  if(v.inspectionPath&&v.inspectionSha256){await containedFile(p.root,v.inspectionPath);invariant(await sha256(v.inspectionPath)===v.inspectionSha256,'Published native inspection changed');}
  if(v.recutVerificationPath&&v.recutVerificationSha256){await containedFile(p.root,v.recutVerificationPath);invariant(await sha256(v.recutVerificationPath)===v.recutVerificationSha256,'Published recut verification changed');}
 }
}

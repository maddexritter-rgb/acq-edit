import path from 'node:path';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {type Project,type Version,invariant} from './contracts.js';
import {containedFile,sha256} from './files.js';
import {isDeepStrictEqual} from 'node:util';

const digest=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
async function archivedJson(project:Project,file:string,expected:string){
 const resolved=await containedFile(path.join(project.root,'20_DELIVER'),file),bytes=await readFile(resolved);
 invariant(createHash('sha256').update(bytes).digest('hex')===expected,'Archived reference provenance changed');
 return JSON.parse(bytes.toString('utf8'));
}
/** Historical review reads the embedded receipt, never the mutable working recipe. */
async function archivedReference(project:Project,version:Version){
 if(!version.planSha256||!version.receiptSha256)return null;
 const plan=await archivedJson(project,version.planPath,version.planSha256);
 const receipt=await archivedJson(project,version.receiptPath,version.receiptSha256);
 if(plan.referenceStyle===undefined){invariant(receipt.referenceEvidence===undefined,'Unbound archived reference evidence');return null}
 invariant(plan.projectId===project.id&&plan.backend===project.backend&&plan.clipId===version.clipId,'Archived reference plan identity differs');
 invariant(receipt.schema==='acq-edit/render-v1'&&receipt.projectId===project.id&&receipt.backend===project.backend&&receipt.clipId===version.clipId&&receipt.parentId===version.parentId,'Archived reference receipt identity differs');
 const evidence=receipt.referenceEvidence,snapshot=evidence?.snapshot;
 invariant(digest(plan.referenceStyle.sha256)&&isDeepStrictEqual(evidence?.contract,plan.referenceStyle),'Archived reference contract differs');
 invariant(snapshot?.schema==='acq-edit/reference-style-v1'&&snapshot.owner==='watch'&&snapshot.projectId===project.id&&snapshot.backend===project.backend&&snapshot.humanApproved===false&&snapshot.coverageStatus==='reported-by-watch-owner','Archived reference snapshot identity differs');
 invariant(typeof snapshot.source?.path==='string'&&digest(snapshot.source.sha256),'Archived reference source pin missing');
 const recipe=snapshot.recipe;
 invariant(recipe&&recipe.sourceSha256===snapshot.source.sha256&&Number.isFinite(recipe.durationSeconds)&&recipe.durationSeconds>0&&typeof snapshot.hasAudio==='boolean','Invalid archived reference recipe');
 invariant(Array.isArray(recipe.segments)&&Array.isArray(recipe.unsupportedEffects)&&recipe.unsupportedEffects.every((x:unknown)=>typeof x==='string'),'Invalid archived reference observations');
 for(const item of recipe.segments)invariant(item&&typeof item.category==='string'&&typeof item.observation==='string'&&['observed','inferred'].includes(item.basis)&&Number.isFinite(item.start)&&Number.isFinite(item.end)&&item.start>=0&&item.end>item.start&&item.end<=recipe.durationSeconds,'Invalid archived reference observation');
 return {snapshot,contract:plan.referenceStyle};
}
async function sourceFile(project:Project,snapshot:any){
 const file=await containedFile(path.join(project.root,'00_SOURCE'),snapshot.source.path);
 invariant(await sha256(file)===snapshot.source.sha256,'Reference media changed since this version was rendered');
 return file;
}
export async function referenceReview(project:Project,version:Version){
 const reference=await archivedReference(project,version);if(!reference)return null;
 let media:{available:boolean;url?:string;error?:string};
 try{await sourceFile(project,reference.snapshot);media={available:true,url:'/reference-media/'+encodeURIComponent(version.id)}}
 catch(e){const error=e as NodeJS.ErrnoException;media={available:false,error:error.code==='ENOENT'?'The original reference file is missing. Restore it to this project to enable playback.':error.message}}
 return {versionId:version.id,versionNumber:version.number,sourceName:path.basename(reference.snapshot.source.path),snapshotSha256:reference.contract.sha256,sourceSha256:reference.snapshot.source.sha256,coverageStatus:reference.snapshot.coverageStatus,hasAudio:reference.snapshot.hasAudio,recipe:reference.snapshot.recipe,media};
}
export async function referenceMedia(project:Project,version:Version){
 const reference=await archivedReference(project,version);invariant(reference,'No archived reference is attached to this version');
 return sourceFile(project,reference.snapshot);
}

import path from 'node:path';
import {Store} from './store.js';
import {invariant} from './contracts.js';
import {atomicJson,containedFile,readJson,sha256} from './files.js';
import {jobPrompt} from './agents.js';
import {completeJob} from './completion.js';
import {exportState} from './projects.js';

/** Hand the frozen request to the already-running chat; never start another model. */
export async function sessionPacket(store:Store,id:string){
 const job=store.job(id),project=store.project(job.projectId);
 invariant(job.execution==='session','This is a background/legacy job. Preserve it; use its original worker or documented recovery.');
 const folder=path.join(project.root,'10_WORK','jobs',id),packet=path.join(folder,'submission.json');
 await atomicJson(packet,{project,job});await exportState(store,project.id);
 return {job,packet,prompt:jobPrompt(project,job,packet),next:`Continue in this chat. Run acq-edit --engine ${project.backend} session-start ${id} once before editing. Use ACQ_EDIT_JOB_ID=${id} for native, brain and publish commands. Finish with session-complete ${id} ${path.join(folder,'result.json')}. Do not start another Claude/Codex CLI or ask for saved permissions.`};
}

export async function startSession(store:Store,id:string){
 const before=store.job(id);
 invariant(before.execution==='session'&&before.state==='queued','Only a queued current-chat job can start. Inspect active work and follow recovery after interruption; do not claim or replay it again.');
 const job=store.claim(id);
 invariant(job,'Project is reserved, source intake is incomplete, or submitted versions changed. Inspect project state before continuing.');
 try{return {...await sessionPacket(store,id),next:`Job reserved for this chat. Use ACQ_EDIT_JOB_ID=${id} on each native, brain and publish command. Inspect existing native state before work. Do not run session-start again. Write the verified result and run session-complete.`}}
 catch(error){store.setJob(id,'reconciliation_required','Current-chat packet preparation failed; inspect state before retrying.');throw error}
}

export async function completeSession(store:Store,id:string,file:string){
 const job=store.job(id),project=store.project(job.projectId);
 invariant(job.execution==='session'&&['editing','rendering'].includes(job.state),'An active current-chat job is required. Interrupted work must be reconciled.');
 const result=await readJson(await containedFile(project.root,path.resolve(file)));
 const completed=await completeJob(store,id,result);await exportState(store,project.id);return completed;
}

/** Explicit operator checkpoint after a lost chat; never auto-release its reservation. */
export async function interruptSession(store:Store,id:string,file:string){
 const job=store.job(id),project=store.project(job.projectId);
 invariant(job.execution==='session'&&['editing','rendering'].includes(job.state),'Only active current-chat jobs can be checkpointed for recovery');
 const evidence=await containedFile(project.root,path.resolve(file)),report=await readJson<any>(evidence),hash=await sha256(evidence);
 invariant(report.jobId===id&&report.noActiveWriter===true&&typeof report.processInspection==='string'&&report.processInspection.trim()&&typeof report.nativeInspection==='string'&&report.nativeInspection.trim(),'Inspect the stopped chat, processes and native host before requesting recovery');
 store.transaction(()=>{
  invariant(JSON.stringify(store.job(id))===JSON.stringify(job),'Job changed during inspection');
  store.assertNativeSettled(project.id);
  store.setJob(id,'reconciliation_required','Current chat stopped; explicit inspection checkpoint recorded. Reconcile verified evidence before continuing.');
  store.event(project.id,{type:'session.interrupted',jobId:id,evidence,evidenceSha256:hash});
 });
 await exportState(store,project.id);return store.job(id);
}

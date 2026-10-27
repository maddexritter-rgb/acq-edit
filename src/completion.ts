import {Store} from './store.js';
import {invariant} from './contracts.js';
import {containedFile,readJson,sha256} from './files.js';
import {verifyPublishedVersions} from './publish.js';
/** Completion mode is frozen on enqueue. Missing means historical rendered workflow. */
export async function completeJob(store:Store,jobId:string,result:any){
 const job=store.job(jobId),project=store.project(job.projectId);
 invariant(result?.jobId===jobId,'Result belongs to another job');
 if(job.completion!=='editable-project'){
  invariant(Array.isArray(result.versionIds)&&result.versionIds.length>0,'Agent returned no completed versions');
  await verifyPublishedVersions(store,jobId,result.versionIds);return store.finishJob(jobId,result.versionIds);
 }
 invariant(project.backend==='premiere'&&Array.isArray(result.operationIds)&&result.operationIds.length>0&&new Set(result.operationIds).size===result.operationIds.length,'Exact native completion operation IDs required');
 const receipts:any[]=[];
 for(const id of result.operationIds){
  const op=store.nativeOperation(id);
  invariant(op.jobId===jobId&&op.projectId===project.id&&op.action==='complete'&&op.state==='succeeded'&&op.resultPath&&op.resultSha256,'Missing successful native completion evidence');
  const file=await containedFile(project.root,op.resultPath);
  invariant(await sha256(file)===op.resultSha256,'Native completion journal changed');
  const journal=await readJson<any>(file),r=JSON.parse(journal.stdout);
  invariant(journal.operationId===id&&r.schema==='acq-edit/editable-project-v1'&&r.jobId===jobId&&r.projectId===project.id&&store.clip(r.clipId).projectId===project.id&&r.sequenceId,'Native completion identity differs');
  invariant(await sha256(await containedFile(project.root,r.receiptPath))===r.receiptSha256,'Completion receipt changed');
  invariant(Array.isArray(r.artifacts)&&r.artifacts.length>=6,'Incomplete native completion artifacts');
  for(const required of [r.nativeProject,r.planPath,r.inspectionPath])invariant(r.artifacts.some((a:any)=>a.path===required),'Missing saved project, plan or inspection');
  for(const a of r.artifacts)invariant(await sha256(await containedFile(project.root,a.path))===a.sha256,'Native completion evidence is stale: '+a.path);
  invariant(!receipts.some(x=>x.clipId===r.clipId),'Duplicate clip completion');receipts.push(r);
 }
 const completed=store.nativeOperations(project.id).filter(o=>o.jobId===jobId&&o.action==='complete'&&o.state==='succeeded');
 invariant(completed.length===receipts.length,'Result omitted a completed native clip');
 return store.finishEditableJob(jobId,receipts);
}

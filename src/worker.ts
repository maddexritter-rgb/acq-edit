import path from 'node:path';
import { Store } from './store.js';
import { type Config } from './config.js';
import { executeAgent } from './agents.js';
import { invariant } from './contracts.js';
import { readJson } from './files.js';
import { exportState } from './projects.js';
export async function workOne(store:Store,config:Config){const job=store.claim();if(!job)return false;const p=store.project(job.projectId);
 try{
  await exportState(store,p.id);
  await executeAgent(config,p,job,id=>store.setJob(job.id,store.job(job.id).state,null,id));
  const result=await readJson<{jobId:string;versionIds:string[]}>(path.join(p.root,'10_WORK','jobs',job.id,'result.json'));
  invariant(result.jobId===job.id&&Array.isArray(result.versionIds)&&result.versionIds.length>0,'Agent returned no completed versions');
  const versions=result.versionIds.map(id=>store.version(id));invariant(versions.every(v=>store.clip(v.clipId).projectId===p.id&&v.createdAt>=job.createdAt),'Job result contains unrelated/old versions');
  if(job.kind==='revision')invariant(job.snapshot.every(s=>versions.some(v=>v.clipId===s.clipId&&v.parentId===s.version.id)),'Not all selected revisions completed');
  store.setJob(job.id,'ready');
 }catch(e){store.setJob(job.id,'reconciliation_required',(e as Error).message)}
 await exportState(store,p.id);return true;
}

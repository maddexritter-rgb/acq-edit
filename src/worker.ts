import {AgentSetupError} from './agent-readiness.js';
import path from 'node:path';
import { Store } from './store.js';
import { type Config } from './config.js';
import { executeAgent } from './agents.js';
import { invariant } from './contracts.js';
import { readJson } from './files.js';
import { completeJob } from './completion.js';
import { exportState } from './projects.js';
export async function workOne(store:Store,config:Config,signal?:AbortSignal){if(signal?.aborted)return false;const job=store.claim();if(!job)return false;const p=store.project(job.projectId);
 try{
  await exportState(store,p.id);
  await executeAgent(config,p,job,id=>store.setJob(job.id,store.job(job.id).state,null,id),signal);
  const result=await readJson<{jobId:string;versionIds:string[]}>(path.join(p.root,'10_WORK','jobs',job.id,'result.json'));
  await completeJob(store,job.id,result);
 }catch(e){store.setJob(job.id,e instanceof AgentSetupError?'failed':'reconciliation_required',(e as Error).message)}
 await exportState(store,p.id);return true;
}

import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {readdir} from 'node:fs/promises';
import {writeFileSync,renameSync} from 'node:fs';
import {Store} from './store.js';
import {type NativeAction,type NativeOperation,now,invariant} from './contracts.js';
import {type Config,ROOT,HOME,secretEnv} from './config.js';
import {atomicJson,containedFile,readJson,sha256} from './files.js';
import {run} from './process.js';
import {intakeProcessAlive} from './intake.js';
import {exportState} from './projects.js';
import {verifyRuntime} from './runtime.js';

async function record(store:Store,id:string,patch:Partial<NativeOperation>={}){const value=store.updateNativeOperation(id,patch);await atomicJson(path.join(value.directory,'operation.json'),value);await exportState(store,value.projectId);return value}
async function children(operation:NativeOperation,allowUnknown=false){
 let names:string[];try{names=await readdir(path.join(operation.directory,'children'))}catch(e:any){if(e.code==='ENOENT')return;throw e}
 for(const name of names.filter(n=>n.endsWith('.json'))){
  const file=await containedFile(operation.directory,path.join(operation.directory,'children',name));
  const child=await readJson<{operationId:string;pid:number|null;pending:boolean}>(file);
  invariant(child.operationId===operation.id&&typeof child.pending==='boolean','Native child journal identity differs');
  invariant(!intakeProcessAlive(child.pid),'A recorded native editor child is still live');
  invariant(allowUnknown||!child.pending,'Native editor child launch outcome is unknown; inspect before reconciliation');
 }
}
export async function executeNative(store:Store,config:Config,projectId:string,action:NativeAction,packetFile:string,tools:{execute?:typeof run;verifyRuntime?:typeof verifyRuntime;signal?:AbortSignal}={}){
 const project=store.project(projectId),packetPath=await containedFile(project.root,packetFile),id=randomUUID();
 const requested=await readJson<{kind?:string}>(packetPath);
 invariant(action!=='hooks'&&!['text-hook','text-hook-remove'].includes(requested.kind||''),'Opening text hooks have been removed; preserve legacy projects and use their pinned toolkit version');
 const operation:NativeOperation={id,projectId,backend:project.backend,action,jobId:process.env.ACQ_EDIT_JOB_ID||null,packetPath,packetSha256:await sha256(packetPath),directory:path.join(project.root,'10_WORK','native-operations',id),state:'running',ownerPid:process.pid,childPid:null,childPending:false,dispatchPhase:'not-started',createdAt:now(),updatedAt:now(),error:null};
 store.addNativeOperation(operation);
 try{
  await record(store,id);
  if(operation.jobId){
   // A finishing job can render an intermediate, inspect it, then edit again.
   // Keep one job/lock throughout while exposing the current native phase.
   store.setJob(operation.jobId,action==='render'?'rendering':'editing');await exportState(store,projectId);
  }
  await (tools.verifyRuntime||verifyRuntime)(config);
  const env={...process.env,...await secretEnv(),ACQ_EDIT_ROOT:ROOT,ACQ_EDIT_NATIVE_OPERATION_ID:id,ACQ_EDIT_NATIVE_OPERATION_DIR:operation.directory};
  tools.signal?.throwIfAborted();
  // Commit uncertainty before invoking the process runner. A crash in this gap
  // must never be misclassified as proof that no editor command was dispatched.
  await record(store,id,{childPending:true,dispatchPhase:'launching'});
  const result=await (tools.execute||run)(project.backend==='resolve'&&!['compile','captions','hooks','reference'].includes(action)?config.resolvePython!:config.python,[path.join(ROOT,'python','native.py'),action,'--backend',project.backend,'--config',path.join(HOME,'config.json'),'--project',path.join(project.root,'project.json'),'--packet',packetPath],{timeout:4*3600_000,env,signal:tools.signal,onSpawn:pid=>{store.updateNativeOperation(id,{childPid:pid,childPending:false,dispatchPhase:'spawned'})}});
  store.updateNativeOperation(id,{childPid:null,childPending:false,dispatchPhase:'returned'});
  await children(operation);
  invariant(await sha256(packetPath)===operation.packetSha256,'Native packet changed during execution');
  const resultPath=path.join(operation.directory,'result.json');await atomicJson(resultPath,{operationId:id,projectId,backend:project.backend,action,packetSha256:operation.packetSha256,stdout:result});
  await record(store,id,{resultPath,resultSha256:await sha256(resultPath)});
  let value:unknown;
  try{value=JSON.parse(result)}catch{throw new Error('Native command returned invalid JSON; inspect the retained result journal')}
  invariant(value!==null&&typeof value==='object'&&!Array.isArray(value),'Native command must return a JSON object; inspect the retained result journal');
  const prepared=value as Record<string,unknown>;
  if(prepared.status==='validation-failed'){
   invariant(['compile','captions','reference'].includes(action)&&prepared.schema==='acq-edit/preparation-failure-v1'&&prepared.nativeEditorStarted===false&&prepared.action===action&&prepared.projectId===projectId&&prepared.backend===project.backend&&prepared.packetSha256===operation.packetSha256,'Unverified preparation failure; inspect native outcome');
   await record(store,id,{state:'validation_failed',ownerPid:null,error:String(prepared.error)});
   throw new Error('Preparation validation failed: '+String(prepared.error));
  }
  await record(store,id,{state:'succeeded',ownerPid:null});
  return value as Record<string,unknown>;
 }catch(e){if(store.nativeOperation(id).state==='validation_failed')throw e;await record(store,id,{state:'reconciliation_required',ownerPid:null,error:(e as Error).message});throw new Error(`Native operation ${id} requires reconciliation: ${(e as Error).message}`)}
}
async function reconcileNotDispatched(operation:NativeOperation,evidencePath:string,evidenceSha256:string){
 invariant(operation.dispatchPhase==='not-started'&&operation.childPid===null&&!operation.childPending&&!operation.resultPath&&!operation.resultSha256,'No durable proof that this native command was never dispatched; inspect its native outcome');
 let entries:string[]=[];try{entries=await readdir(path.join(operation.directory,'children'))}catch(e:any){if(e.code!=='ENOENT')throw e}
 invariant(entries.length===0,'Native child records contradict the not-dispatched outcome');
 const resultPath=path.join(operation.directory,'reconciliation-attempts',randomUUID()+'-not-dispatched.json');
 await atomicJson(resultPath,{schema:'acq-edit/native-not-dispatched-reconciliation-v1',operationId:operation.id,projectId:operation.projectId,backend:operation.backend,
  originalOperation:operation,evidencePath,evidenceSha256,nativeCommandStarted:false,nativeRequestReplayed:false,verifiedAt:now()});
 return {resultPath,resultSha256:await sha256(resultPath)};
}
async function reconcilePremiere(store:Store,operation:NativeOperation,file:string,evidenceSha256:string,tools:{config?:Config;execute?:typeof run;verifyRuntime?:typeof verifyRuntime}){
 const config=tools.config;invariant(config,'Configured Premiere runtime required for lifecycle recovery');
 const directory=path.join(operation.directory,'reconciliation-attempts');
 let names:string[]=[];try{names=await readdir(directory)}catch(e:any){if(e.code!=='ENOENT')throw e}
 for(const name of names.filter(n=>n.endsWith('.json'))){
  const prior=await readJson<any>(await containedFile(operation.directory,path.join(directory,name)));
  invariant(prior.operationId===operation.id,'Recovery attempt identity differs');
  invariant(!intakeProcessAlive(prior.ownerPid)&&!intakeProcessAlive(prior.childPid),'A previous recovery process is still live');
  invariant(!prior.childPending,'Previous recovery command launch is unknown; inspect its process journal before repair');
 }
 const attemptFile=path.join(directory,randomUUID()+'.json');
 const attempt={operationId:operation.id,evidence:file,evidenceSha256,ownerPid:process.pid as number|null,childPid:null as number|null,childPending:false,state:'preflight',createdAt:now(),updatedAt:now(),error:null as string|null};
 await atomicJson(attemptFile,attempt);
 // onSpawn is synchronous: persist the child before allowing asynchronous command work.
 const persist=()=>{attempt.updatedAt=now();const staged=attemptFile+'.new';writeFileSync(staged,JSON.stringify(attempt,null,2)+'\n',{mode:0o600});renameSync(staged,attemptFile)};
 try{
  await (tools.verifyRuntime||verifyRuntime)(config);
  invariant(await sha256(file)===evidenceSha256,'Recovery evidence changed before dispatch');
  const env:NodeJS.ProcessEnv={...process.env,...await secretEnv(),ACQ_EDIT_ROOT:ROOT};
  delete env.ACQ_EDIT_NATIVE_OPERATION_ID;delete env.ACQ_EDIT_NATIVE_OPERATION_DIR;
  attempt.state='running';attempt.childPending=true;persist();
  let stdout:string;
  try{stdout=await (tools.execute||run)(config.python,[path.join(ROOT,'python/native.py'),'reconcile','--backend','premiere','--config',path.join(HOME,'config.json'),'--project',path.join(store.project(operation.projectId).root,'project.json'),'--packet',file],{timeout:120_000,env,onSpawn:pid=>{attempt.childPid=pid;attempt.childPending=false;persist()}})}
  finally{attempt.childPending=false;if(!intakeProcessAlive(attempt.childPid))attempt.childPid=null;persist()}
  invariant(!intakeProcessAlive(attempt.childPid),'Recovery command is still live');
  const value=JSON.parse(stdout);
  invariant(value.schema==='acq-edit/premiere-lifecycle-recovery-result-v1'&&value.operationId===operation.id&&value.originalWriterLockReleased===true&&value.nativeRequestReplayed===false,'Premiere lifecycle recovery did not prove release of its original lock');
  const resultPath=await containedFile(store.project(operation.projectId).root,value.resultPath);
  invariant(await sha256(resultPath)===value.resultSha256,'Premiere recovery result changed');
  const report=await readJson<any>(resultPath);
  invariant(report.schema==='acq-edit/premiere-project-reconciliation-v1'&&report.operationId===operation.id&&report.projectId===operation.projectId&&report.releaseAuthorized===true&&report.originalWriterLockReleased===true&&report.nativeRequestReplayed===false,'Premiere recovery report identity differs');
  const requestPath=await containedFile(store.project(operation.projectId).root,report.evidencePath),request=await readJson<any>(requestPath);
  invariant(await sha256(requestPath)===report.evidenceSha256&&request.originalEvidencePath===file&&request.originalEvidenceSha256===evidenceSha256,'Premiere recovery report does not bind the submitted evidence');
  invariant(await sha256(file)===evidenceSha256,'Recovery evidence changed during inspection');
  attempt.state='succeeded';return {resultPath,resultSha256:value.resultSha256,attemptFile};
 }catch(e){attempt.state='failed';attempt.error=(e as Error).message;throw e}
 finally{attempt.ownerPid=null;persist()}
}
export async function reconcileNative(store:Store,id:string,evidencePath:string,tools:{config?:Config;execute?:typeof run;verifyRuntime?:typeof verifyRuntime}={}){
 const operation=store.nativeOperation(id);invariant(['running','reconciliation_required'].includes(operation.state),'Native operation is already terminal');
 const file=await containedFile(store.project(operation.projectId).root,evidencePath),evidence=await readJson<any>(file);
 invariant(evidence.operationId===id&&evidence.backend===operation.backend&&evidence.noActiveWriter===true&&typeof evidence.processInspection==='string'&&evidence.processInspection.trim()&&typeof evidence.nativeInspection==='string'&&evidence.nativeInspection.trim(),'Evidence must identify the operation/backend and describe terminal process and native host inspection');
 const evidenceSha256=await sha256(file);
 invariant(!intakeProcessAlive(operation.ownerPid)&&!intakeProcessAlive(operation.childPid),'Native operation owner or command is still live');
 await children(operation,true);
 let premiereRecovery:{resultPath:string;resultSha256:string;attemptFile:string}|undefined;
 let preflightRecovery:{resultPath:string;resultSha256:string}|undefined;
 invariant(evidence.nativeOutcome===undefined||evidence.nativeOutcome==='not-dispatched','Unsupported native recovery outcome');
 if(evidence.nativeOutcome==='not-dispatched'){
  invariant(evidence.premiereLifecycle===undefined,'A command that never started cannot also claim a Premiere lifecycle outcome');
  preflightRecovery=await reconcileNotDispatched(operation,file,evidenceSha256);
 }else if(operation.backend==='premiere'&&operation.action==='open'){
  invariant(evidence.premiereLifecycle&&['unchanged','target-open','artifacts-retained'].includes(evidence.premiereLifecycle.outcome),'Premiere lifecycle recovery requires an explicit observed outcome');
  premiereRecovery=await reconcilePremiere(store,operation,file,evidenceSha256,tools);
 }
 invariant(await sha256(file)===evidenceSha256,'Recovery evidence changed during reconciliation');
 store.transaction(()=>{const current=store.nativeOperation(id);invariant(JSON.stringify(current)===JSON.stringify(operation),'Native operation changed during reconciliation');invariant(!intakeProcessAlive(current.ownerPid)&&!intakeProcessAlive(current.childPid),'Native process is still live');store.updateNativeOperation(id,{state:'reconciled',ownerPid:null,childPid:null,childPending:false,error:'Operator inspected the native outcome; original files and result retained'});store.event(operation.projectId,{type:'native.reconciled',operationId:id,evidence:file,evidenceSha256,...(premiereRecovery?{premiereRecovery}:{}),...(preflightRecovery?{preflightRecovery}:{})})});
 return record(store,id);
}
export async function reconcileJob(store:Store,id:string,outcome:'ready'|'failed',evidencePath:string){
 const job=store.job(id);invariant(job.state==='reconciliation_required','Job does not need reconciliation');store.assertNativeSettled(job.projectId);
 const file=await containedFile(store.project(job.projectId).root,evidencePath),report=await readJson<any>(file);
 invariant(report.jobId===id,'Reconciliation evidence belongs to another job');
 if(outcome==='ready'){
  const {completeJob}=await import('./completion.js');await completeJob(store,id,report);
 }else{
  invariant(report.noActiveWriter===true&&typeof report.processInspection==='string'&&report.processInspection.trim()&&typeof report.nativeInspection==='string'&&report.nativeInspection.trim(),'Failed reconciliation requires terminal process and native host inspection');
  store.transaction(()=>{invariant(store.job(id).state==='reconciliation_required','Job state changed');store.assertNativeSettled(job.projectId);store.setJob(id,'failed','Operator reconciled the native outcome; see evidence.')});
 }
 store.event(job.projectId,{type:'job.reconciled',jobId:id,evidence:file,evidenceSha256:await sha256(file)});await exportState(store,job.projectId);return store.job(id);
}

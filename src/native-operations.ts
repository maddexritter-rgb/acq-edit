import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {readdir} from 'node:fs/promises';
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
 const operation:NativeOperation={id,projectId,backend:project.backend,action,jobId:process.env.ACQ_EDIT_JOB_ID||null,packetPath,packetSha256:await sha256(packetPath),directory:path.join(project.root,'10_WORK','native-operations',id),state:'running',ownerPid:process.pid,childPid:null,childPending:false,createdAt:now(),updatedAt:now(),error:null};
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
  store.updateNativeOperation(id,{childPending:true});
  const result=await (tools.execute||run)(project.backend==='resolve'&&!['compile','captions','hooks'].includes(action)?config.resolvePython!:config.python,[path.join(ROOT,'python','native.py'),action,'--backend',project.backend,'--config',path.join(HOME,'config.json'),'--project',path.join(project.root,'project.json'),'--packet',packetPath],{timeout:4*3600_000,env,signal:tools.signal,onSpawn:pid=>{store.updateNativeOperation(id,{childPid:pid,childPending:false})}});
  store.updateNativeOperation(id,{childPid:null,childPending:false});
  await children(operation);
  invariant(await sha256(packetPath)===operation.packetSha256,'Native packet changed during execution');
  const resultPath=path.join(operation.directory,'result.json');await atomicJson(resultPath,{operationId:id,projectId,backend:project.backend,action,packetSha256:operation.packetSha256,stdout:result});
  await record(store,id,{resultPath,resultSha256:await sha256(resultPath)});
  let value:unknown;
  try{value=JSON.parse(result)}catch{throw new Error('Native command returned invalid JSON; inspect the retained result journal')}
  invariant(value!==null&&typeof value==='object'&&!Array.isArray(value),'Native command must return a JSON object; inspect the retained result journal');
  await record(store,id,{state:'succeeded',ownerPid:null});
  return value as Record<string,unknown>;
 }catch(e){await record(store,id,{state:'reconciliation_required',ownerPid:null,error:(e as Error).message});throw new Error(`Native operation ${id} requires reconciliation: ${(e as Error).message}`)}
}
export async function reconcileNative(store:Store,id:string,evidencePath:string){
 const operation=store.nativeOperation(id);invariant(['running','reconciliation_required'].includes(operation.state),'Native operation is already terminal');
 const file=await containedFile(store.project(operation.projectId).root,evidencePath),evidence=await readJson<any>(file);
 invariant(evidence.operationId===id&&evidence.backend===operation.backend&&evidence.noActiveWriter===true&&typeof evidence.processInspection==='string'&&evidence.processInspection.trim()&&typeof evidence.nativeInspection==='string'&&evidence.nativeInspection.trim(),'Evidence must identify the operation/backend and describe terminal process and native host inspection');
 const evidenceSha256=await sha256(file);
 invariant(!intakeProcessAlive(operation.ownerPid)&&!intakeProcessAlive(operation.childPid),'Native operation owner or command is still live');
 await children(operation,true);
 store.transaction(()=>{const current=store.nativeOperation(id);invariant(JSON.stringify(current)===JSON.stringify(operation),'Native operation changed during reconciliation');invariant(!intakeProcessAlive(current.ownerPid)&&!intakeProcessAlive(current.childPid),'Native process is still live');store.updateNativeOperation(id,{state:'reconciled',ownerPid:null,childPid:null,childPending:false,error:'Operator inspected the native outcome; original files and result retained'});store.event(operation.projectId,{type:'native.reconciled',operationId:id,evidence:file,evidenceSha256})});
 return record(store,id);
}
export async function reconcileJob(store:Store,id:string,outcome:'ready'|'failed',evidencePath:string){
 const job=store.job(id);invariant(job.state==='reconciliation_required','Job does not need reconciliation');store.assertNativeSettled(job.projectId);
 const file=await containedFile(store.project(job.projectId).root,evidencePath),report=await readJson<any>(file);
 invariant(report.jobId===id,'Reconciliation evidence belongs to another job');
 if(outcome==='ready'){
  const {verifyPublishedVersions}=await import('./publish.js');await verifyPublishedVersions(store,id,report.versionIds);store.finishJob(id,report.versionIds);
 }else{
  invariant(report.noActiveWriter===true&&typeof report.processInspection==='string'&&report.processInspection.trim()&&typeof report.nativeInspection==='string'&&report.nativeInspection.trim(),'Failed reconciliation requires terminal process and native host inspection');
  store.transaction(()=>{invariant(store.job(id).state==='reconciliation_required','Job state changed');store.assertNativeSettled(job.projectId);store.setJob(id,'failed','Operator reconciled the native outcome; see evidence.')});
 }
 store.event(job.projectId,{type:'job.reconciled',jobId:id,evidence:file,evidenceSha256:await sha256(file)});await exportState(store,job.projectId);return store.job(id);
}

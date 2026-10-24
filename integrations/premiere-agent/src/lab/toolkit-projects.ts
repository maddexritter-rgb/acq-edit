/** Toolkit-only lifecycle contract. General Lab lifecycle tools remain blocked. */
import {createHash} from 'node:crypto';
import {existsSync,readFileSync,writeFileSync,renameSync,openSync,closeSync,unlinkSync,realpathSync,lstatSync,mkdirSync} from 'node:fs';
import path from 'node:path';
import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {resolveCapabilities} from '../security/capabilities.js';
import {buildToolScript,escapeForExtendScript} from '../bridge/script-builder.js';

const hash=(value:string|Buffer)=>createHash('sha256').update(value).digest('hex');
const digest=(value:unknown)=>hash(JSON.stringify(value));
const need=(ok:unknown,message:string):void=>{if(!ok)throw Error(message)};
export const WORKSPACE_BODY=`
function workspace(){
 if(!app.projects||typeof app.projects.numProjects!=='number')throw Error('PROJECT_COLLECTION_UNAVAILABLE');
 var n=app.projects.numProjects;if(n<0||n>100||n%1)throw Error('PROJECT_COLLECTION_INVALID');
 var rows=[];for(var i=0;i<n;i++){var p=app.projects[i];if(!p)throw Error('PROJECT_COLLECTION_INCOMPLETE');rows.push({path:String(p.path||''),name:String(p.name||'')});}
 return {version:String(app.version),openProjects:rows,activePath:app.project?String(app.project.path||''):null};
}
`;
export const inspectBody=WORKSPACE_BODY+'return __result(workspace());';
export function lifecycleBody(mode:'create'|'open',target:string,expiresAt:string,operationId:string){
 need(/^[A-Za-z0-9_-]{1,80}$/.test(operationId),'TOOLKIT_NATIVE_OPERATION_ID_REQUIRED');
 need(Number.isFinite(Date.parse(expiresAt)),'TOOLKIT_NATIVE_DEADLINE_REQUIRED');
 const q='"'+escapeForExtendScript(target)+'"';
 return WORKSPACE_BODY+`
 if(new Date().getTime()>=${Date.parse(expiresAt)})return __error('TOOLKIT_NATIVE_SCOPE_EXPIRED');
 var before=workspace();
 if(!/^26\\.3\\.0(?:\\D|$)/.test(before.version))return __error('TOOLKIT_HOST_VERSION_MISMATCH');
 if(before.openProjects.length||before.activePath!==null)return __error('TOOLKIT_EMPTY_WORKSPACE_REQUIRED');
 var destination=${q},file=File(destination);
 if(${mode==='create'?'file.exists':'!file.exists'})return __error('TOOLKIT_TARGET_FILE_CHANGED');
 var markerKey='__acqEditProjectLifecycle',oldMarker=$.global[markerKey];
 if(oldMarker&&oldMarker.phase==='running')return __error('TOOLKIT_NATIVE_LIFECYCLE_STILL_RUNNING');
 $.global[markerKey]={operationId:${JSON.stringify(operationId)},phase:'running',startedAt:new Date().getTime()};
 try {
 ${mode==='create'?'app.newProject(destination);':'app.openDocument(destination);'}
 var after=workspace(),project=app.project;
 if(!project||after.openProjects.length!==1||after.activePath!==destination||after.openProjects[0].path!==destination)return __error('TOOLKIT_PROJECT_IDENTITY_UNVERIFIED');
 ${mode==='create'?`if(!project.sequences||project.sequences.numSequences!==0||!project.rootItem||project.rootItem.children.numItems!==0)return __error('TOOLKIT_NEW_PROJECT_NOT_EMPTY');project.save();`:''}
 if(!File(destination).exists)return __error('TOOLKIT_PROJECT_NOT_SAVED');
 return __result({mode:${JSON.stringify(mode)},projectPath:destination,workspace:workspace(),nativeWorkflowQualified:false});
 } finally { $.global[markerKey].phase='returned';$.global[markerKey].finishedAt=new Date().getTime(); }
 `;
}
export type LifecycleRequest={operationId:string;mode:'create'|'open';projectPath:string;expectedWorkspaceRevision:string;expectedNativeSha256?:string};
export class ToolkitProjects {
 constructor(readonly root:string,readonly bridge:BridgeOptions,readonly send:typeof sendCommand=sendCommand,
  readonly hooks:{snapshot?:()=>Promise<any>;now?:()=>number;processAlive?:(pid:number)=>boolean}={}){}
 private now(){return this.hooks.now?.()??Date.now()}
 private alive(pid:number){
  if(!Number.isInteger(pid)||pid<=0)return true;
  if(this.hooks.processAlive)return this.hooks.processAlive(pid);
  try{process.kill(pid,0);return true}catch(error:any){return error.code!=='ESRCH'}
 }
 async inspect(operationId?:string){
  if(operationId)need(/^[A-Za-z0-9_-]{1,80}$/.test(operationId),'TOOLKIT_NATIVE_OPERATION_ID_REQUIRED');
  const body=operationId?WORKSPACE_BODY+"return __result({workspace:workspace(),nativeOperation:typeof $!=='undefined'&&$.global?($.global.__acqEditProjectLifecycle||null):null});":inspectBody;
  const result=await this.send(buildToolScript(body),this.bridge);
  need(result.success,'TOOLKIT_WORKSPACE_INSPECTION_FAILED: '+String(result.error||''));
  const data=result.data as any,state=operationId?data.workspace:data;
  need(state&&Array.isArray(state.openProjects)&&typeof state.version==='string'&&(typeof state.activePath==='string'||state.activePath===null),'TOOLKIT_WORKSPACE_INVALID');
  if(operationId&&data.nativeOperation)need(/^[A-Za-z0-9_-]{1,80}$/.test(data.nativeOperation.operationId)&&['running','returned'].includes(data.nativeOperation.phase),'TOOLKIT_NATIVE_MARKER_INVALID');
  return {state,revision:digest(state),...(operationId?{nativeOperation:data.nativeOperation}: {})};
 }
 private pinnedFile(file:string){
  need(path.isAbsolute(file)&&realpathSync(file)===file&&lstatSync(file).isFile(),'TOOLKIT_REGULAR_FILE_REQUIRED');
  return readFileSync(file);
 }
 private authorize(args:LifecycleRequest){
  const auth=JSON.parse(this.pinnedFile(path.join(this.root,'toolkit-scopes',args.operationId+'.json')).toString());
  need(auth.schema==='acq-edit/premiere-project-scope-v1'&&auth.operationId===args.operationId&&auth.mode===args.mode&&auth.projectPath===args.projectPath&&auth.ownershipConfirmed===true,'TOOLKIT_EXACT_LIFECYCLE_SCOPE_REQUIRED');
  const expiry=Date.parse(auth.expiresAt);
  need(Number.isFinite(expiry)&&expiry>this.now()&&expiry<=this.now()+10*60_000,'TOOLKIT_LIFECYCLE_SCOPE_EXPIRED_OR_TOO_LONG');
  need(path.isAbsolute(auth.projectRoot)&&realpathSync(auth.projectRoot)===auth.projectRoot,'TOOLKIT_PROJECT_ROOT_REQUIRED');
  const manifest=this.pinnedFile(path.join(auth.projectRoot,'project.json'));
  need(hash(manifest)===auth.projectManifestSha256,'TOOLKIT_PROJECT_MANIFEST_CHANGED');
  const project=JSON.parse(manifest.toString());
  need(project.id===auth.projectId&&project.root===auth.projectRoot&&project.backend==='premiere','TOOLKIT_PROJECT_IDENTITY_MISMATCH');
  const target=args.projectPath,work=path.join(auth.projectRoot,'10_WORK');
  need(path.isAbsolute(target)&&target.endsWith('.prproj')&&target.startsWith(work+path.sep)&&path.resolve(target)===target&&realpathSync(path.dirname(target))===path.dirname(target),'TOOLKIT_PROJECT_TARGET_OUTSIDE_WORK');
  need(auth.expectedWorkspaceRevision===args.expectedWorkspaceRevision&&auth.expectedNativeSha256===(args.expectedNativeSha256??null),'TOOLKIT_LIFECYCLE_INPUT_CHANGED');
  if(args.mode==='create')need(!lstatSync(target,{throwIfNoEntry:false})&&!args.expectedNativeSha256,'TOOLKIT_NEW_PROJECT_ALREADY_EXISTS');
  else need(/^[a-f0-9]{64}$/.test(args.expectedNativeSha256||'')&&hash(this.pinnedFile(target))===args.expectedNativeSha256,'TOOLKIT_SAVED_PROJECT_CHANGED');
  const leaseFile=path.join(this.root,'lease.json');
  if(existsSync(leaseFile)){
   const lease=JSON.parse(this.pinnedFile(leaseFile).toString()),expires=Date.parse(lease.expiresAt);
   need(Number.isFinite(expires)&&expires<=this.now(),'TOOLKIT_EXISTING_STAGE_LEASE_REQUIRES_RELEASE');
  }
  return auth;
 }
 async reconcile(args:{operationId:string;evidencePath:string;evidenceSha256:string}){
  need(/^[A-Za-z0-9_-]{1,80}$/.test(args.operationId)&&/^[a-f0-9]{64}$/.test(args.evidenceSha256),'TOOLKIT_RECOVERY_REQUEST_INVALID');
  const capabilities=resolveCapabilities().capabilities;
  need(capabilities.has('edit')&&capabilities.has('filesystem'),'TOOLKIT_LIFECYCLE_AUTHORITY_REQUIRED');
  const file=path.join(this.root,'operations',args.operationId+'.json'),raw=this.pinnedFile(file),row=JSON.parse(raw.toString());
  need(row.schema==='acq-edit/premiere-project-operation-v2'&&row.operationId===args.operationId&&['unknown','running'].includes(row.status)&&row.fingerprint===digest(row.request),'TOOLKIT_UNCERTAIN_LIFECYCLE_REQUIRED');
  const scopeRaw=this.pinnedFile(path.join(this.root,'toolkit-scopes',args.operationId+'.json')),scope=JSON.parse(scopeRaw.toString());
  need(hash(scopeRaw)===row.scopeSha256&&scope.expiresAt===row.scopeExpiresAt&&scope.projectId===row.projectId&&scope.projectPath===row.request.projectPath&&scope.operationId===row.operationId,'TOOLKIT_ORIGINAL_SCOPE_CHANGED');
  need(path.isAbsolute(scope.projectRoot)&&realpathSync(scope.projectRoot)===scope.projectRoot,'TOOLKIT_PROJECT_ROOT_REQUIRED');
  need(args.evidencePath.startsWith(path.join(scope.projectRoot,'10_WORK')+path.sep),'TOOLKIT_RECOVERY_EVIDENCE_OUTSIDE_PROJECT');
  const evidenceRaw=this.pinnedFile(args.evidencePath);need(hash(evidenceRaw)===args.evidenceSha256,'TOOLKIT_RECOVERY_EVIDENCE_CHANGED');
  const evidence=JSON.parse(evidenceRaw.toString()),intent=evidence.premiereLifecycle;
  need(evidence.operationId===args.operationId&&evidence.backend==='premiere'&&evidence.noActiveWriter===true&&typeof evidence.processInspection==='string'&&evidence.processInspection.trim()&&typeof evidence.nativeInspection==='string'&&evidence.nativeInspection.trim(),'TOOLKIT_RECOVERY_PROCESS_AND_HOST_EVIDENCE_REQUIRED');
  need(intent?.schema==='acq-edit/premiere-lifecycle-reconciliation-v1'&&['unchanged','target-open','artifacts-retained'].includes(intent.outcome)&&/^[a-f0-9]{64}$/.test(intent.expectedWorkspaceRevision),'TOOLKIT_RECOVERY_OUTCOME_REQUIRED');
  const reportFile=file+'.reconciliation.json',lock=path.join(this.root,'writer.lock');
  const readReport=()=>{const report=JSON.parse(this.pinnedFile(reportFile).toString());need(report.originalOperationSha256===hash(raw)&&report.evidencePath===args.evidencePath&&report.evidenceSha256===args.evidenceSha256,'TOOLKIT_RECOVERY_REPORT_CONFLICT');return report};
  const ownsLock=()=>{
   if(!existsSync(lock))return false;
   const value=JSON.parse(this.pinnedFile(lock).toString());
   return value.schema==='acq-edit/premiere-lifecycle-lock-v1'&&value.operationId===args.operationId&&value.fingerprint===row.fingerprint&&value.ownerPid===row.ownerPid;
  };
  if(existsSync(reportFile)&&!existsSync(lock))return {...readReport(),originalWriterLockReleased:true};
  need(ownsLock(),'TOOLKIT_ORIGINAL_WRITER_LOCK_REQUIRED');
  const mutex=path.join(this.root,'reconcile.lock'),fd=openSync(mutex,'wx',0o600);
  try{
   need(ownsLock(),'TOOLKIT_ORIGINAL_WRITER_LOCK_CHANGED');
   need(!this.alive(row.ownerPid),'TOOLKIT_ORIGINAL_BRIDGE_STILL_LIVE');
   const expiry=Date.parse(row.scopeExpiresAt);
   need(Number.isFinite(expiry)&&expiry<=this.now(),'TOOLKIT_ORIGINAL_SCOPE_STILL_VALID');
   const first=await this.inspect(args.operationId);
   need(!first.nativeOperation||first.nativeOperation.phase==='returned','TOOLKIT_NATIVE_LIFECYCLE_STILL_RUNNING');
   let report:any;
   if(existsSync(reportFile))report=readReport();
   else{
    need(first.revision===intent.expectedWorkspaceRevision,'TOOLKIT_RECOVERY_WORKSPACE_CHANGED');
    const target=row.request.projectPath;
    let nativeSha256:string|null=null,nativeSnapshot:any=null;
    if(intent.outcome==='unchanged'){
     need(first.revision===row.before.revision,'TOOLKIT_RECOVERY_NOT_UNCHANGED');
     if(row.request.mode==='create')need(!lstatSync(target,{throwIfNoEntry:false}),'TOOLKIT_RECOVERY_CREATED_FILE_EXISTS');
     else{nativeSha256=hash(this.pinnedFile(target));need(nativeSha256===row.request.expectedNativeSha256,'TOOLKIT_RECOVERY_SAVED_BYTES_CHANGED')}
    }else{
     nativeSha256=hash(this.pinnedFile(target));need(nativeSha256===intent.expectedNativeSha256,'TOOLKIT_RECOVERY_TARGET_BYTES_CHANGED');
     if(intent.outcome==='artifacts-retained')need(first.revision===row.before.revision,'TOOLKIT_RECOVERY_EMPTY_WORKSPACE_REQUIRED');
     else{
      need(first.state.openProjects.length===1&&first.state.activePath===target&&first.state.openProjects[0].path===target,'TOOLKIT_RECOVERY_TARGET_NOT_ACTIVE');
      need(this.hooks.snapshot,'TOOLKIT_RECOVERY_FULL_SNAPSHOT_REQUIRED');
      nativeSnapshot=await this.hooks.snapshot!();
      need(nativeSnapshot.projectPath===target&&digest(nativeSnapshot)===intent.expectedNativeRevision,'TOOLKIT_RECOVERY_NATIVE_STATE_CHANGED');
     }
    }
    const second=await this.inspect(args.operationId);
    need(second.revision===first.revision&&digest(second.nativeOperation??null)===digest(first.nativeOperation??null),'TOOLKIT_RECOVERY_NATIVE_ACTIVITY_CHANGED');
    if(nativeSnapshot)need(digest(await this.hooks.snapshot!())===digest(nativeSnapshot),'TOOLKIT_RECOVERY_NATIVE_STATE_CHANGED');
    if(nativeSha256)need(hash(this.pinnedFile(target))===nativeSha256,'TOOLKIT_RECOVERY_TARGET_BYTES_CHANGED');
    else need(!lstatSync(target,{throwIfNoEntry:false}),'TOOLKIT_RECOVERY_TARGET_APPEARED');
    need(hash(this.pinnedFile(file))===hash(raw)&&hash(this.pinnedFile(args.evidencePath))===args.evidenceSha256,'TOOLKIT_RECOVERY_INPUT_CHANGED');
    report={schema:'acq-edit/premiere-project-reconciliation-v1',operationId:row.operationId,projectId:row.projectId,
     outcome:intent.outcome,originalOperationSha256:hash(raw),originalScopeSha256:row.scopeSha256,
     evidencePath:args.evidencePath,evidenceSha256:args.evidenceSha256,workspace:second,nativeSha256,nativeSnapshot,
     inspectedAt:new Date(this.now()).toISOString(),releaseAuthorized:true,nativeRequestReplayed:false,nativeWorkflowQualified:false};
    const staged=reportFile+'.pending';writeFileSync(staged,JSON.stringify(report,null,2),{flag:'wx',mode:0o600});renameSync(staged,reportFile);
   }
   // The report commits first. A restart can finish releasing only this exact old lock.
   need(ownsLock(),'TOOLKIT_ORIGINAL_WRITER_LOCK_CHANGED');unlinkSync(lock);
   return {...report,originalWriterLockReleased:true};
  }finally{closeSync(fd);unlinkSync(mutex)}
 }
 async execute(input:LifecycleRequest){
  const args=JSON.parse(JSON.stringify(input)) as LifecycleRequest;
  const capabilities=resolveCapabilities().capabilities;
  need(capabilities.has('edit')&&capabilities.has('filesystem'),'TOOLKIT_LIFECYCLE_AUTHORITY_REQUIRED');
  need(/^[A-Za-z0-9_-]{1,80}$/.test(args.operationId)&&['create','open'].includes(args.mode)&&/^[a-f0-9]{64}$/.test(args.expectedWorkspaceRevision),'TOOLKIT_LIFECYCLE_REQUEST_INVALID');
  const folder=path.join(this.root,'operations');mkdirSync(folder,{recursive:true,mode:0o700});
  const file=path.join(folder,args.operationId+'.json'),fingerprint=digest(args);
  const prior=()=>{const row=JSON.parse(this.pinnedFile(file).toString());need(row.fingerprint===fingerprint&&row.schema==='acq-edit/premiere-project-operation-v2','OPERATION_ID_CONFLICT');return row};
  if(existsSync(file))return prior();
  need(!existsSync(file+'.staged')&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json'))&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json.claim')),'TOOLKIT_OPERATION_ID_ALREADY_RESERVED');
  const lock=path.join(this.root,'writer.lock'),fd=openSync(lock,'wx',0o600);
  let dispatched=false,settled=false;
  try{
   writeFileSync(fd,JSON.stringify({schema:'acq-edit/premiere-lifecycle-lock-v1',operationId:args.operationId,fingerprint,ownerPid:process.pid}));
   if(existsSync(file))return prior();
   need(!existsSync(file+'.staged')&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json'))&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json.claim')),'TOOLKIT_OPERATION_ID_ALREADY_RESERVED');
   const auth=this.authorize(args),before=await this.inspect();
   need(before.revision===args.expectedWorkspaceRevision,'TOOLKIT_WORKSPACE_CHANGED');
   need(/^26\.3\.0(?:\D|$)/.test(before.state.version),'TOOLKIT_HOST_VERSION_MISMATCH');
   need(before.state.openProjects.length===0&&before.state.activePath===null,'TOOLKIT_EMPTY_WORKSPACE_REQUIRED');
   // Recheck disk/scope after the native read and before writing the dispatch journal.
   this.authorize(args);
   const row:any={schema:'acq-edit/premiere-project-operation-v2',ownerPid:process.pid,scopeSha256:hash(this.pinnedFile(path.join(this.root,'toolkit-scopes',args.operationId+'.json'))),scopeExpiresAt:auth.expiresAt,operationId:args.operationId,fingerprint,tool:'lab_toolkit_project',request:args,projectId:auth.projectId,startedAt:new Date().toISOString(),status:'running',before,ownership:'caller_confirmed_exclusive',nativeWorkflowQualified:false};
   const save=()=>{const staged=file+'.staged';writeFileSync(staged,JSON.stringify(row,null,2),{mode:0o600});renameSync(staged,file)};
   save();dispatched=true;
   try{
    const result=await this.send(buildToolScript(lifecycleBody(args.mode,args.projectPath,auth.expiresAt,args.operationId)),this.bridge);
    row.result=result;
    need(result.success&&(result.data as any)?.projectPath===args.projectPath,'TOOLKIT_PROJECT_OPERATION_UNVERIFIED');
    const after=await this.inspect();
    need(after.state.openProjects.length===1&&after.state.activePath===args.projectPath&&after.state.openProjects[0].path===args.projectPath,'TOOLKIT_PROJECT_READBACK_CHANGED');
    const nativeSha256=hash(this.pinnedFile(args.projectPath));
    need(args.mode==='create'||nativeSha256===args.expectedNativeSha256,'TOOLKIT_OPEN_CHANGED_SAVED_BYTES');
    row.after=after;row.nativeSha256=nativeSha256;row.status='committed_unverified';
   }catch(error){row.status='unknown';row.error=String(error)}
   row.finishedAt=new Date().toISOString();save();settled=row.status!=='unknown';return row;
  }finally{closeSync(fd);if(!dispatched||settled)unlinkSync(lock)}
 }
}

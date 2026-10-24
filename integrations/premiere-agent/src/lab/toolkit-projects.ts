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
export function lifecycleBody(mode:'create'|'open',target:string,expiresAt:string){
 need(Number.isFinite(Date.parse(expiresAt)),'TOOLKIT_NATIVE_DEADLINE_REQUIRED');
 const q='"'+escapeForExtendScript(target)+'"';
 return WORKSPACE_BODY+`
 if(new Date().getTime()>=${Date.parse(expiresAt)})return __error('TOOLKIT_NATIVE_SCOPE_EXPIRED');
 var before=workspace();
 if(!/^26\\.3\\.0(?:\\D|$)/.test(before.version))return __error('TOOLKIT_HOST_VERSION_MISMATCH');
 if(before.openProjects.length||before.activePath!==null)return __error('TOOLKIT_EMPTY_WORKSPACE_REQUIRED');
 var destination=${q},file=File(destination);
 if(${mode==='create'?'file.exists':'!file.exists'})return __error('TOOLKIT_TARGET_FILE_CHANGED');
 ${mode==='create'?'app.newProject(destination);':'app.openDocument(destination);'}
 var after=workspace(),project=app.project;
 if(!project||after.openProjects.length!==1||after.activePath!==destination||after.openProjects[0].path!==destination)return __error('TOOLKIT_PROJECT_IDENTITY_UNVERIFIED');
 ${mode==='create'?`if(!project.sequences||project.sequences.numSequences!==0||!project.rootItem||project.rootItem.children.numItems!==0)return __error('TOOLKIT_NEW_PROJECT_NOT_EMPTY');project.save();`:''}
 if(!File(destination).exists)return __error('TOOLKIT_PROJECT_NOT_SAVED');
 return __result({mode:${JSON.stringify(mode)},projectPath:destination,workspace:workspace(),nativeWorkflowQualified:false});
 `;
}
export type LifecycleRequest={operationId:string;mode:'create'|'open';projectPath:string;expectedWorkspaceRevision:string;expectedNativeSha256?:string};
export class ToolkitProjects {
 constructor(readonly root:string,readonly bridge:BridgeOptions,readonly send:typeof sendCommand=sendCommand){}
 async inspect(){
  const result=await this.send(buildToolScript(inspectBody),this.bridge);
  need(result.success,'TOOLKIT_WORKSPACE_INSPECTION_FAILED: '+String(result.error||''));
  const state=result.data as any;
  need(state&&Array.isArray(state.openProjects)&&typeof state.version==='string'&&(typeof state.activePath==='string'||state.activePath===null),'TOOLKIT_WORKSPACE_INVALID');
  return {state,revision:digest(state)};
 }
 private pinnedFile(file:string){
  need(path.isAbsolute(file)&&realpathSync(file)===file&&lstatSync(file).isFile(),'TOOLKIT_REGULAR_FILE_REQUIRED');
  return readFileSync(file);
 }
 private authorize(args:LifecycleRequest){
  const auth=JSON.parse(this.pinnedFile(path.join(this.root,'toolkit-scopes',args.operationId+'.json')).toString());
  need(auth.schema==='acq-edit/premiere-project-scope-v1'&&auth.operationId===args.operationId&&auth.mode===args.mode&&auth.projectPath===args.projectPath&&auth.ownershipConfirmed===true,'TOOLKIT_EXACT_LIFECYCLE_SCOPE_REQUIRED');
  const expiry=Date.parse(auth.expiresAt);
  need(Number.isFinite(expiry)&&expiry>Date.now()&&expiry<=Date.now()+10*60_000,'TOOLKIT_LIFECYCLE_SCOPE_EXPIRED_OR_TOO_LONG');
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
   need(Number.isFinite(expires)&&expires<=Date.now(),'TOOLKIT_EXISTING_STAGE_LEASE_REQUIRES_RELEASE');
  }
  return auth;
 }
 async execute(input:LifecycleRequest){
  const args=JSON.parse(JSON.stringify(input)) as LifecycleRequest;
  const capabilities=resolveCapabilities().capabilities;
  need(capabilities.has('edit')&&capabilities.has('filesystem'),'TOOLKIT_LIFECYCLE_AUTHORITY_REQUIRED');
  need(/^[A-Za-z0-9_-]{1,80}$/.test(args.operationId)&&['create','open'].includes(args.mode)&&/^[a-f0-9]{64}$/.test(args.expectedWorkspaceRevision),'TOOLKIT_LIFECYCLE_REQUEST_INVALID');
  const folder=path.join(this.root,'operations');mkdirSync(folder,{recursive:true,mode:0o700});
  const file=path.join(folder,args.operationId+'.json'),fingerprint=digest(args);
  const prior=()=>{const row=JSON.parse(this.pinnedFile(file).toString());need(row.fingerprint===fingerprint&&row.schema==='acq-edit/premiere-project-operation-v1','OPERATION_ID_CONFLICT');return row};
  if(existsSync(file))return prior();
  need(!existsSync(file+'.staged')&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json'))&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json.claim')),'TOOLKIT_OPERATION_ID_ALREADY_RESERVED');
  const lock=path.join(this.root,'writer.lock'),fd=openSync(lock,'wx',0o600);
  let dispatched=false,settled=false;
  try{
   if(existsSync(file))return prior();
   need(!existsSync(file+'.staged')&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json'))&&!existsSync(path.join(this.root,'jobs',args.operationId+'.json.claim')),'TOOLKIT_OPERATION_ID_ALREADY_RESERVED');
   const auth=this.authorize(args),before=await this.inspect();
   need(before.revision===args.expectedWorkspaceRevision,'TOOLKIT_WORKSPACE_CHANGED');
   need(/^26\.3\.0(?:\D|$)/.test(before.state.version),'TOOLKIT_HOST_VERSION_MISMATCH');
   need(before.state.openProjects.length===0&&before.state.activePath===null,'TOOLKIT_EMPTY_WORKSPACE_REQUIRED');
   // Recheck disk/scope after the native read and before writing the dispatch journal.
   this.authorize(args);
   const row:any={schema:'acq-edit/premiere-project-operation-v1',operationId:args.operationId,fingerprint,tool:'lab_toolkit_project',request:args,projectId:auth.projectId,startedAt:new Date().toISOString(),status:'running',before,ownership:'caller_confirmed_exclusive',nativeWorkflowQualified:false};
   const save=()=>{const staged=file+'.staged';writeFileSync(staged,JSON.stringify(row,null,2),{mode:0o600});renameSync(staged,file)};
   save();dispatched=true;
   try{
    const result=await this.send(buildToolScript(lifecycleBody(args.mode,args.projectPath,auth.expiresAt)),this.bridge);
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

// Explicit integration tests: compile integrations/premiere-agent first. No licensed host claims.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,realpathSync,mkdirSync,writeFileSync,readFileSync,existsSync,rmSync,symlinkSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {ToolkitProjects,lifecycleBody} from '../integrations/premiere-agent/dist/lab/toolkit-projects.js';
const hash=value=>createHash('sha256').update(value).digest('hex');
function fixture(t,mode='create'){
 const base=realpathSync(mkdtempSync(path.join(tmpdir(),'acq lifecycle ')));t.after(()=>rmSync(base,{recursive:true,force:true}));
 const root=path.join(base,'runtime'),projectRoot=path.join(base,'project');mkdirSync(path.join(root,'toolkit-scopes'),{recursive:true});mkdirSync(path.join(projectRoot,'10_WORK'),{recursive:true});
 const project={id:'project-id',root:projectRoot,backend:'premiere'};writeFileSync(path.join(projectRoot,'project.json'),JSON.stringify(project));
 const target=path.join(projectRoot,'10_WORK','edit.prproj');if(mode==='open')writeFileSync(target,'saved native fixture');
 const state={version:'26.3.0',openProjects:[],activePath:null};
 const args={operationId:'fixture-operation',mode,projectPath:target,expectedWorkspaceRevision:hash(JSON.stringify(state)),...(mode==='open'?{expectedNativeSha256:hash(readFileSync(target))}:{})};
 const auth={schema:'acq-edit/premiere-project-scope-v1',operationId:args.operationId,mode,projectPath:target,ownershipConfirmed:true,
  expiresAt:new Date(Date.now()+300_000).toISOString(),projectId:project.id,projectRoot,projectManifestSha256:hash(readFileSync(path.join(projectRoot,'project.json'))),expectedWorkspaceRevision:args.expectedWorkspaceRevision,expectedNativeSha256:args.expectedNativeSha256??null};
 const scope=path.join(root,'toolkit-scopes',args.operationId+'.json');const scopeWrite=()=>writeFileSync(scope,JSON.stringify(auth));scopeWrite();
 let mutations=0,fail=false;
 const send=async script=>{
  if(script.includes('app.newProject(destination)')||script.includes('app.openDocument(destination)')){
   mutations++;if(fail)return {success:false,error:'Simulated host loss after dispatch'};
   if(mode==='create')writeFileSync(target,'new native fixture');state.openProjects=[{path:target,name:'fixture'}];state.activePath=target;
   return {success:true,data:{projectPath:target}};
  }
  return {success:true,data:structuredClone(state)};
 };
 return {root,projectRoot,target,args,auth,scope,scopeWrite,state,service:new ToolkitProjects(root,{},send),mutations:()=>mutations,fail:()=>fail=true};
}
for(const mode of ['create','open'])test(`${mode} exact scoped target journals once and never replays an ID`,async t=>{
 const f=fixture(t,mode);const before=mode==='open'?readFileSync(f.target):null;
 const result=await f.service.execute(f.args);assert.equal(result.status,'committed_unverified');assert.equal(result.nativeWorkflowQualified,false);
 assert.equal(result.nativeSha256,hash(readFileSync(f.target)));assert.equal(f.mutations(),1);assert.equal(existsSync(path.join(f.root,'writer.lock')),false);
 assert.deepEqual(await f.service.execute(f.args),result);assert.equal(f.mutations(),1);
 if(before)assert.deepEqual(readFileSync(f.target),before);
 await assert.rejects(f.service.execute({...f.args,mode:mode==='open'?'create':'open'}),/CONFLICT/);
});
test('occupied or unsaved workspaces never dispatch and retain unrelated state',async t=>{
 const f=fixture(t);f.state.openProjects=[{path:'/unrelated.prproj',name:'user'}];f.state.activePath='/unrelated.prproj';
 f.args.expectedWorkspaceRevision=hash(JSON.stringify(f.state));f.auth.expectedWorkspaceRevision=f.args.expectedWorkspaceRevision;f.scopeWrite();
 await assert.rejects(f.service.execute(f.args),/EMPTY_WORKSPACE/);assert.equal(f.mutations(),0);assert.equal(existsSync(f.target),false);
 assert.equal(f.state.activePath,'/unrelated.prproj');assert.equal(existsSync(path.join(f.root,'writer.lock')),false);
});
test('unknown host outcomes retain shared writer lock and original journal',async t=>{
 const f=fixture(t);f.fail();const result=await f.service.execute(f.args);
 assert.equal(result.status,'unknown');assert.equal(existsSync(path.join(f.root,'writer.lock')),true);
 assert.deepEqual(await f.service.execute(f.args),result);assert.equal(f.mutations(),1);
 await assert.rejects(f.service.execute({...f.args,operationId:'another-operation'}),/EEXIST/);
});
for(const failure of ['expired','ownership','manifest','target','lease','stale','saved-bytes','symlink'])test(`refuses ${failure} before native mutation`,async t=>{
 const f=fixture(t,failure==='saved-bytes'?'open':'create');
 if(failure==='expired')f.auth.expiresAt=new Date(Date.now()-1000).toISOString();
 if(failure==='ownership')f.auth.ownershipConfirmed=false;
 if(failure==='manifest')writeFileSync(path.join(f.projectRoot,'project.json'),'{}');
 if(failure==='target')writeFileSync(f.target,'user work');
 if(failure==='lease')writeFileSync(path.join(f.root,'lease.json'),JSON.stringify({expiresAt:new Date(Date.now()+100_000).toISOString()}));
 if(failure==='stale')f.state.version='26.3.0 changed';
 if(failure==='saved-bytes')writeFileSync(f.target,'changed saved project');
 if(failure==='symlink')symlinkSync(path.join(f.projectRoot,'missing'),f.target);
 f.scopeWrite();await assert.rejects(f.service.execute(f.args));assert.equal(f.mutations(),0);
});
test('host script rechecks workspace inside the same native dispatch',()=>{
 for(const mode of ['create','open']){
  let calls=0;const app={version:'26.3.0',projects:{numProjects:1,0:{path:'/user.prproj',name:'user'}},project:{path:'/user.prproj'},newProject:()=>calls++,openDocument:()=>calls++};
  const result=vm.runInNewContext(`(function(){${lifecycleBody(mode,'/target.prproj',new Date(Date.now()+300_000).toISOString())}})()`,{app,File:()=>({exists:mode==='open'}),__result:data=>({success:true,data}),__error:error=>({success:false,error})});
  assert.equal(result.success,false);assert.equal(result.error,'TOOLKIT_EMPTY_WORKSPACE_REQUIRED');assert.equal(calls,0);
 }
});
test('host script creates only a new empty native project and saves its own path',()=>{
 const destination='/new "quoted".prproj';let exists=false,saves=0,creates=0;
 const app={version:'26.3.0',project:null,projects:{numProjects:0},newProject(target){assert.equal(target,destination);creates++;this.project={path:target,name:'new',sequences:{numSequences:0},rootItem:{children:{numItems:0}},save(){saves++;exists=true}};this.projects={numProjects:1,0:this.project}}};
 const result=vm.runInNewContext(`(function(){${lifecycleBody('create',destination,new Date(Date.now()+300_000).toISOString())}})()`,{app,File:()=>({exists}),__result:data=>({success:true,data}),__error:error=>({success:false,error})});
 assert.equal(result.success,true);assert.equal(creates,1);assert.equal(saves,1);assert.equal(result.data.projectPath,destination);assert.equal(result.data.nativeWorkflowQualified,false);
});

test('delayed native dispatch expires before opening or creating a project',()=>{
 const result=vm.runInNewContext(`(function(){${lifecycleBody('create','/target.prproj',new Date(Date.now()-1).toISOString())}})()`,{__error:error=>({success:false,error})});
 assert.equal(result.error,'TOOLKIT_NATIVE_SCOPE_EXPIRED');
});

test('inspect-only authority cannot invoke the dedicated lifecycle endpoint',async t=>{
 const f=fixture(t),prior=process.env.PREMIERE_MCP_CAPABILITIES;
 process.env.PREMIERE_MCP_CAPABILITIES='inspect';
 try{await assert.rejects(f.service.execute(f.args),/AUTHORITY_REQUIRED/);assert.equal(f.mutations(),0)}
 finally{if(prior===undefined)delete process.env.PREMIERE_MCP_CAPABILITIES;else process.env.PREMIERE_MCP_CAPABILITIES=prior}
});

test('a staged receipt or existing Lab job reserves the lifecycle operation ID',async t=>{
 const f=fixture(t);mkdirSync(path.join(f.root,'jobs'));writeFileSync(path.join(f.root,'jobs',f.args.operationId+'.json.claim'),'reserved');
 await assert.rejects(f.service.execute(f.args),/ALREADY_RESERVED/);assert.equal(f.mutations(),0);
});

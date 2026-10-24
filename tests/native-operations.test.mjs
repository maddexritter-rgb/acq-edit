import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,realpath} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../dist/store.js';
import {executeNative as nativeCommand,reconcileNative,reconcileJob} from '../dist/native-operations.js';
import {sha256} from '../dist/files.js';
import {publish} from '../dist/publish.js';
const executeNative=(store,config,projectId,action,packet,tools={})=>nativeCommand(store,config,projectId,action,packet,{verifyRuntime:async()=>({ready:true}),...tools});
async function fixture(t,backend='filmcraft'){
 const root=await realpath(await mkdtemp(path.join(os.tmpdir(),'acq-native-')));await mkdir(path.join(root,'10_WORK'));
 const store=new Store(path.join(root,'state.sqlite'));store.addProject({id:'p',root,title:'Native recovery fixture',backend,agent:'codex',createdAt:''});
 const packet=path.join(root,'10_WORK/packet.json');await writeFile(packet,'{}');
 t.after(async()=>{delete process.env.ACQ_EDIT_JOB_ID;store.close();await rm(root,{recursive:true,force:true})});
 return {root,store,packet,config:{python:process.execPath,backend},evidence:async(id,extra={})=>{const file=path.join(root,'10_WORK',id+'-evidence.json');await writeFile(file,JSON.stringify({operationId:id,backend,noActiveWriter:true,processInspection:'Controlled test observed terminal process',nativeInspection:'Controlled fixture has no native host writer',...extra}));return file}};
}
test('native success records exact packet, command identity and immutable result before releasing project',async t=>{
 const f=await fixture(t);const result=await executeNative(f.store,f.config,'p','inspect',f.packet,{execute:async(cmd,args,options)=>{
  options.onSpawn(2147483647);assert.equal(f.store.nativeOperations('p')[0].childPid,2147483647);assert(options.env.ACQ_EDIT_NATIVE_OPERATION_ID);assert.equal(f.store.claim(),undefined);return '{"native":true}';
 }});
 assert.deepEqual(result,{native:true});const op=f.store.nativeOperations('p')[0];assert.equal(op.state,'succeeded');assert.equal(op.ownerPid,null);assert.equal(op.packetSha256,await sha256(f.packet));assert.equal(op.resultSha256,await sha256(op.resultPath));const journal=JSON.parse(await readFile(op.resultPath));assert.equal(journal.operationId,op.id);assert.equal(journal.stdout,'{"native":true}');f.store.assertNativeSettled('p');
});
test('intermediate renders return to editing without releasing the owning job',async t=>{
 const f=await fixture(t),job=f.store.enqueueBuild('p','Replace hook after changing captions');f.store.claim();process.env.ACQ_EDIT_JOB_ID=job.id;
 const next=f.store.enqueueBuild('p','Later work');
 for(const [action,state] of [['render','rendering'],['inspect','editing'],['revise','editing'],['hooks','editing'],['render','rendering']]){
  await executeNative(f.store,f.config,'p',action,f.packet,{execute:async(c,a,o)=>{
   o.onSpawn(2147483647);assert.equal(f.store.job(job.id).state,state);assert.equal(f.store.claim(),undefined);return '{}';
  }});
  assert.equal(f.store.job(next.id).state,'queued');assert.equal(f.store.job(job.id).state,state);
 }
 assert.equal(f.store.nativeOperations('p').length,5);assert.ok(f.store.nativeOperations('p').every(op=>op.jobId===job.id&&op.state==='succeeded'));
});
test('malformed or non-object native responses retain evidence and require reconciliation',async t=>{
 for(const stdout of ['progress\n{"native":true}', 'null', '[]', '"double encoded"', 'true']){
  await t.test(stdout,async t=>{
   const f=await fixture(t);
   await assert.rejects(executeNative(f.store,f.config,'p','inspect',f.packet,{execute:async(c,a,o)=>{o.onSpawn(2147483647);return stdout}}),/requires reconciliation.*JSON/);
   const op=f.store.nativeOperations('p')[0];assert.equal(op.state,'reconciliation_required');assert.equal(op.ownerPid,null);assert.equal(op.childPid,null);
   assert.equal(JSON.parse(await readFile(op.resultPath)).stdout,stdout);assert.equal(op.resultSha256,await sha256(op.resultPath));
   assert.throws(()=>f.store.assertNativeSettled('p'),/Native operation/);
  });
 }
});
test('failed native operation blocks queue, re-entry and job reconciliation until inspected',async t=>{
 const f=await fixture(t);const first=f.store.enqueueBuild('p','First');f.store.claim();process.env.ACQ_EDIT_JOB_ID=first.id;
 await assert.rejects(executeNative(f.store,f.config,'p','render',f.packet,{execute:async(c,a,o)=>{o.onSpawn(2147483647);throw Error('interrupted native render')}}),/requires reconciliation/);
 delete process.env.ACQ_EDIT_JOB_ID;const op=f.store.nativeOperations('p')[0];f.store.setJob(first.id,'reconciliation_required');const queued=f.store.enqueueBuild('p','Second');assert.equal(f.store.claim(),undefined);
 await assert.rejects(publish(f.store,'p',f.packet),/Native operation/);assert.throws(()=>f.store.finishJob(first.id,[]),/Native operation/);
 await assert.rejects(executeNative(f.store,f.config,'p','build',f.packet),/Native operation/);
 const report=await f.evidence(op.id,{jobId:first.id});await assert.rejects(reconcileJob(f.store,first.id,'failed',report),/Native operation/);
 await reconcileNative(f.store,op.id,report);assert.equal(f.store.nativeOperation(op.id).state,'reconciled');await reconcileJob(f.store,first.id,'failed',report);assert.equal(f.store.claim().id,queued.id);
});
test('live command or FilmCraft child refuses reconciliation even with an operator assertion',async t=>{
 const f=await fixture(t);await assert.rejects(executeNative(f.store,f.config,'p','render',f.packet,{execute:async(c,a,o)=>{o.onSpawn(process.pid);throw Error('test interruption')}}));
 const op=f.store.nativeOperations('p')[0],report=await f.evidence(op.id);await assert.rejects(reconcileNative(f.store,op.id,report),/still live/);
 f.store.updateNativeOperation(op.id,{childPid:null});await mkdir(path.join(op.directory,'children'));const child=path.join(op.directory,'children/engine.json');await writeFile(child,JSON.stringify({operationId:op.id,pid:process.pid,pending:false}));
 await assert.rejects(reconcileNative(f.store,op.id,report),/editor child is still live/);assert.equal(f.store.nativeOperation(op.id).state,'reconciliation_required');
});
test('unknown child launch and changed packet never produce successful operations',async t=>{
 const f=await fixture(t);await assert.rejects(executeNative(f.store,f.config,'p','build',f.packet,{execute:async(c,a,o)=>{o.onSpawn(2147483647);await mkdir(path.join(o.env.ACQ_EDIT_NATIVE_OPERATION_DIR,'children'));await writeFile(path.join(o.env.ACQ_EDIT_NATIVE_OPERATION_DIR,'children/unknown.json'),JSON.stringify({operationId:o.env.ACQ_EDIT_NATIVE_OPERATION_ID,pid:null,pending:true}));return '{}'}}),/launch outcome is unknown/);
 const op=f.store.nativeOperations('p')[0];await reconcileNative(f.store,op.id,await f.evidence(op.id));
 await assert.rejects(executeNative(f.store,f.config,'p','compile',f.packet,{execute:async(c,a,o)=>{o.onSpawn(2147483647);await writeFile(f.packet,'{"changed":true}');return '{}'}}),/packet changed/);
 assert.equal(f.store.nativeOperations('p')[0].state,'reconciliation_required');
});
test('unrelated native commands cannot enter an active job and arbitrary files cannot clear failed jobs',async t=>{
 const f=await fixture(t);const job=f.store.enqueueBuild('p','Owned edit');f.store.claim();
 await assert.rejects(executeNative(f.store,f.config,'p','build',f.packet),/editing job owns/);assert.equal(f.store.nativeOperations('p').length,0);
 f.store.setJob(job.id,'reconciliation_required');await assert.rejects(reconcileJob(f.store,job.id,'failed',f.packet),/another job/);
 await writeFile(f.packet,JSON.stringify({jobId:job.id}));await assert.rejects(reconcileJob(f.store,job.id,'failed',f.packet),/terminal process/);assert.equal(f.store.job(job.id).state,'reconciliation_required');
});

test('stale runtime is refused before spawning a native process',async t=>{
 const f=await fixture(t);let spawned=false;
 await assert.rejects(executeNative(f.store,f.config,'p','build',f.packet,{verifyRuntime:async()=>{throw Error('stale installed runtime')},execute:async()=>{spawned=true;return '{}'}}),/stale installed runtime/);
 assert.equal(spawned,false);const op=f.store.nativeOperations('p')[0];assert.equal(op.state,'reconciliation_required');assert.equal(op.childPid,null);assert.equal(op.childPending,false);assert.equal(op.resultPath,undefined);
});

async function premiereRecoveryFixture(t){
 const f=await fixture(t,'premiere');
 await assert.rejects(executeNative(f.store,f.config,'p','open',f.packet,{execute:async(c,a,o)=>{o.onSpawn(2147483647);throw Error('lost lifecycle response')}}));
 const op=f.store.nativeOperations('p')[0],file=await f.evidence(op.id,{premiereLifecycle:{outcome:'unchanged'}});
 const execute=async(c,args,options)=>{
  assert.equal(args[1],'reconcile');assert.equal(args[3],'premiere');assert.equal(args.at(-1),file);
  assert.equal(options.env.ACQ_EDIT_NATIVE_OPERATION_ID,undefined);options.onSpawn(2147483647);
  assert.equal(f.store.nativeOperation(op.id).state,'reconciliation_required');
  const request=path.join(f.root,'10_WORK/derived.json'),report=path.join(f.root,'10_WORK/reconciled.json');
  await writeFile(request,JSON.stringify({originalEvidencePath:file,originalEvidenceSha256:await sha256(file)}));
  await writeFile(report,JSON.stringify({schema:'acq-edit/premiere-project-reconciliation-v1',operationId:op.id,projectId:'p',releaseAuthorized:true,originalWriterLockReleased:true,nativeRequestReplayed:false,evidencePath:request,evidenceSha256:await sha256(request)}));
  return JSON.stringify({schema:'acq-edit/premiere-lifecycle-recovery-result-v1',operationId:op.id,resultPath:report,resultSha256:await sha256(report),originalWriterLockReleased:true,nativeRequestReplayed:false});
 };
 return {...f,op,file,tools:{config:f.config,verifyRuntime:async()=>({ready:true}),execute}};
}
test('Premiere lifecycle reconciliation requires verified lock release and preserves original records',async t=>{
 const f=await premiereRecoveryFixture(t),packet=await readFile(f.packet),original=await readFile(path.join(f.op.directory,'operation.json'));
 const result=await reconcileNative(f.store,f.op.id,f.file,f.tools);
 assert.equal(result.state,'reconciled');assert.deepEqual(await readFile(f.packet),packet);
 const {readdir}=await import('node:fs/promises'),dir=path.join(f.op.directory,'reconciliation-attempts');
 const attempts=await readdir(dir);assert.equal(attempts.length,1);
 const attempt=JSON.parse(await readFile(path.join(dir,attempts[0])));assert.equal(attempt.state,'succeeded');assert.equal(attempt.ownerPid,null);assert.equal(attempt.childPid,null);assert.equal(attempt.childPending,false);
 assert.equal(JSON.parse(original).error,'lost lifecycle response');assert.equal(result.packetSha256,f.op.packetSha256);
});
test('Premiere lifecycle cannot be cleared using generic text evidence or a stale installation',async t=>{
 const f=await premiereRecoveryFixture(t);let invoked=false;
 await assert.rejects(reconcileNative(f.store,f.op.id,await f.evidence(f.op.id)),/explicit observed outcome/);
 f.file=await f.evidence(f.op.id,{premiereLifecycle:{outcome:'unchanged'}});
 await assert.rejects(reconcileNative(f.store,f.op.id,f.file,{...f.tools,verifyRuntime:async()=>{throw Error('stale runtime')},execute:async()=>{invoked=true;return '{}'}}),/stale runtime/);
 assert.equal(invoked,false);assert.equal(f.store.nativeOperation(f.op.id).state,'reconciliation_required');
});
test('failed recovery remains reserved and can resume without replaying the original operation',async t=>{
 const f=await premiereRecoveryFixture(t);
 await assert.rejects(reconcileNative(f.store,f.op.id,f.file,{...f.tools,execute:async(c,a,o)=>{o.onSpawn(2147483647);throw Error('native inspection unavailable')}}),/inspection unavailable/);
 assert.equal(f.store.nativeOperation(f.op.id).state,'reconciliation_required');
 assert.equal((await reconcileNative(f.store,f.op.id,f.file,f.tools)).state,'reconciled');
});
test('live or uncertain prior recovery subprocess prevents another recovery dispatch',async t=>{
 const f=await premiereRecoveryFixture(t),dir=path.join(f.op.directory,'reconciliation-attempts');await mkdir(dir);
 const journal=path.join(dir,'prior.json');let invoked=false;
 for(const prior of [{ownerPid:process.pid,childPid:null,childPending:false},{ownerPid:null,childPid:process.pid,childPending:false},{ownerPid:null,childPid:null,childPending:true}]){
  await writeFile(journal,JSON.stringify({operationId:f.op.id,...prior}));
  await assert.rejects(reconcileNative(f.store,f.op.id,f.file,{...f.tools,execute:async()=>{invoked=true;return '{}'}}),/still live|launch is unknown/);
 }
 assert.equal(invoked,false);assert.equal(f.store.nativeOperation(f.op.id).state,'reconciliation_required');
});
for(const corruption of ['unreleased','replayed','report-changed','unbound','evidence-changed'])test(`Premiere recovery rejects ${corruption} without settling the outer operation`,async t=>{
 const f=await premiereRecoveryFixture(t);
 const execute=async(...args)=>{
  const value=JSON.parse(await f.tools.execute(...args));
  if(corruption==='unreleased')value.originalWriterLockReleased=false;
  if(corruption==='replayed')value.nativeRequestReplayed=true;
  if(corruption==='report-changed')await writeFile(value.resultPath,'{}');
  if(corruption==='unbound')await writeFile(path.join(f.root,'10_WORK/derived.json'),'{}');
  if(corruption==='evidence-changed')await writeFile(f.file,'{}');
  return JSON.stringify(value);
 };
 await assert.rejects(reconcileNative(f.store,f.op.id,f.file,{...f.tools,execute}));
 assert.equal(f.store.nativeOperation(f.op.id).state,'reconciliation_required');
});

for(const backend of ['filmcraft','premiere','resolve'])test(`${backend} preflight failure can be reconciled without an installed engine or native dispatch`,async t=>{
 const f=await fixture(t,backend);let calls=0;
 await assert.rejects(executeNative(f.store,f.config,'p','open',f.packet,{verifyRuntime:async()=>{throw Error('installation unavailable')},execute:async()=>{calls++;return '{}'}}),/installation unavailable/);
 const op=f.store.nativeOperations('p')[0],packet=await readFile(f.packet),file=await f.evidence(op.id,{nativeOutcome:'not-dispatched'});
 assert.equal(op.dispatchPhase,'not-started');assert.equal(JSON.parse(await readFile(path.join(op.directory,'operation.json'))).dispatchPhase,'not-started');
 const recovered=await reconcileNative(f.store,op.id,file,{execute:async()=>{calls++;throw Error('must not contact host')}});
 assert.equal(recovered.state,'reconciled');assert.equal(calls,0);assert.deepEqual(await readFile(f.packet),packet);
 const {readdir}=await import('node:fs/promises'),dir=path.join(op.directory,'reconciliation-attempts');
 const files=await readdir(dir);assert.equal(files.length,1);
 const proof=JSON.parse(await readFile(path.join(dir,files[0])));
 assert.deepEqual(proof.originalOperation,op);assert.equal(proof.nativeCommandStarted,false);assert.equal(proof.nativeRequestReplayed,false);
 assert.equal(proof.evidenceSha256,await sha256(file));f.store.assertNativeSettled('p');
});
for(const phase of ['launching','spawned','returned'])test(`a ${phase} command cannot use not-dispatched recovery even with cleared PIDs`,async t=>{
 const f=await fixture(t,'premiere');
 const execute=async(c,a,o)=>{assert.equal(f.store.nativeOperations('p')[0].dispatchPhase,'launching');
  const disk=JSON.parse(await readFile(path.join(o.env.ACQ_EDIT_NATIVE_OPERATION_DIR,'operation.json')));assert.equal(disk.dispatchPhase,'launching');assert.equal(disk.childPending,true);
  if(phase==='launching')throw Error('uncertain launch');
  o.onSpawn(2147483647);assert.equal(f.store.nativeOperations('p')[0].dispatchPhase,'spawned');
  if(phase==='spawned')throw Error('lost command');return 'invalid-json';
 };
 await assert.rejects(executeNative(f.store,f.config,'p','open',f.packet,{execute}));
 const op=f.store.nativeOperations('p')[0];assert.equal(op.dispatchPhase,phase);
 f.store.updateNativeOperation(op.id,{childPid:null,childPending:false});
 await assert.rejects(reconcileNative(f.store,op.id,await f.evidence(op.id,{nativeOutcome:'not-dispatched'})),/No durable proof/);
 assert.equal(f.store.nativeOperation(op.id).state,'reconciliation_required');
});
for(const contradiction of ['legacy','pending','child','result','child-journal','two-outcomes'])test(`not-dispatched recovery refuses ${contradiction} evidence`,async t=>{
 const f=await fixture(t,'premiere');await assert.rejects(executeNative(f.store,f.config,'p','open',f.packet,{verifyRuntime:async()=>{throw Error('test setup failure')}}));
 const op=f.store.nativeOperations('p')[0];
 if(contradiction==='legacy')f.store.updateNativeOperation(op.id,{dispatchPhase:undefined});
 if(contradiction==='pending')f.store.updateNativeOperation(op.id,{childPending:true});
 if(contradiction==='child')f.store.updateNativeOperation(op.id,{childPid:2147483647});
 if(contradiction==='result')f.store.updateNativeOperation(op.id,{resultPath:path.join(op.directory,'result.json')});
 if(contradiction==='child-journal'){await mkdir(path.join(op.directory,'children'));await writeFile(path.join(op.directory,'children/engine.json'),JSON.stringify({operationId:op.id,pid:null,pending:false}))}
 const file=await f.evidence(op.id,{nativeOutcome:'not-dispatched',...(contradiction==='two-outcomes'?{premiereLifecycle:{outcome:'unchanged'}}:{})});
 await assert.rejects(reconcileNative(f.store,op.id,file),/No durable proof|child records contradict|cannot also claim/);
 assert.equal(f.store.nativeOperation(op.id).state,'reconciliation_required');
});
test('already cancelled native request keeps explicit not-started state',async t=>{
 const f=await fixture(t,'premiere'),controller=new AbortController();controller.abort();let calls=0;
 await assert.rejects(executeNative(f.store,f.config,'p','open',f.packet,{signal:controller.signal,execute:async()=>{calls++;return '{}'}}));
 const op=f.store.nativeOperations('p')[0];assert.equal(op.dispatchPhase,'not-started');assert.equal(calls,0);
 await reconcileNative(f.store,op.id,await f.evidence(op.id,{nativeOutcome:'not-dispatched'}));
});
test('killed preflight owner is recoverable after restart without ever launching an editor command',{timeout:10000},async t=>{
 const {spawn}=await import('node:child_process'),{once}=await import('node:events'),{access,readdir}=await import('node:fs/promises');
 const f=await fixture(t,'premiere'),marker=path.join(f.root,'unexpected-native-call');
 const code=`import {Store} from ${JSON.stringify(new URL('../dist/store.js',import.meta.url).href)};
 import {executeNative} from ${JSON.stringify(new URL('../dist/native-operations.js',import.meta.url).href)};
 import {writeFile} from 'node:fs/promises';
 const store=new Store(${JSON.stringify(path.join(f.root,'state.sqlite'))});
 await executeNative(store,${JSON.stringify(f.config)},'p','open',${JSON.stringify(f.packet)},{
 verifyRuntime:async()=>{process.stdout.write('preflight-ready\\n');await new Promise(resolve=>setTimeout(resolve,60000));throw Error('test deadline')},
 execute:async()=>{await writeFile(${JSON.stringify(marker)},'unexpected');return '{}'}});`;
 const child=spawn(process.execPath,['--input-type=module','-e',code],{stdio:['ignore','pipe','pipe']});
 const closed=once(child,'close');let stderr='';child.stderr.on('data',b=>stderr+=b);
 t.after(async()=>{if(child.exitCode===null&&child.signalCode===null)child.kill('SIGKILL');await closed});
 const first=await Promise.race([once(child.stdout,'data').then(([data])=>String(data)),closed.then(()=>{throw Error('preflight owner exited before readiness: '+stderr)})]);
 assert.equal(first,'preflight-ready\n');const op=f.store.nativeOperations('p')[0];assert.equal(op.ownerPid,child.pid);assert.equal(op.dispatchPhase,'not-started');
 const file=await f.evidence(op.id,{nativeOutcome:'not-dispatched'});
 await assert.rejects(reconcileNative(f.store,op.id,file),/still live/);
 child.kill('SIGKILL');await closed;assert.throws(()=>process.kill(op.ownerPid,0),{code:'ESRCH'});
 const restarted=new Store(path.join(f.root,'state.sqlite'));
 try{assert.equal((await reconcileNative(restarted,op.id,file)).state,'reconciled')}finally{restarted.close()}
 await assert.rejects(access(marker),{code:'ENOENT'});
 const proofs=await readdir(path.join(op.directory,'reconciliation-attempts'));assert.equal(proofs.length,1);
 assert.equal(JSON.parse(await readFile(path.join(op.directory,'reconciliation-attempts',proofs[0]))).originalOperation.state,'running');
});

test('reference preparation uses shared Python for every selected engine',async t=>{
 for(const backend of ['resolve','premiere','filmcraft'])await t.test(backend,async t=>{
  const f=await fixture(t,backend);f.config.resolvePython='/unused/resolve-python';
  await executeNative(f.store,f.config,'p','reference',f.packet,{execute:async(cmd,args,options)=>{
   assert.equal(cmd,f.config.python);assert.equal(args[1],'reference');assert.equal(args[3],backend);options.onSpawn(2147483647);return '{"humanApproved":false}';
  }});
  assert.equal(f.store.nativeOperations('p')[0].state,'succeeded');
 });
});

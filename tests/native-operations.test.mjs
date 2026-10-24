import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../dist/store.js';
import {executeNative,reconcileNative,reconcileJob} from '../dist/native-operations.js';
import {sha256} from '../dist/files.js';
import {publish} from '../dist/publish.js';
async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-native-'));await mkdir(path.join(root,'10_WORK'));
 const store=new Store(path.join(root,'state.sqlite'));store.addProject({id:'p',root,title:'Native recovery fixture',backend:'filmcraft',agent:'codex',createdAt:''});
 const packet=path.join(root,'10_WORK/packet.json');await writeFile(packet,'{}');
 t.after(async()=>{delete process.env.ACQ_EDIT_JOB_ID;store.close();await rm(root,{recursive:true,force:true})});
 return {root,store,packet,config:{python:process.execPath,backend:'filmcraft'},evidence:async(id,extra={})=>{const file=path.join(root,'10_WORK',id+'-evidence.json');await writeFile(file,JSON.stringify({operationId:id,backend:'filmcraft',noActiveWriter:true,processInspection:'Controlled test observed terminal process',nativeInspection:'Controlled fixture has no native host writer',...extra}));return file}};
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

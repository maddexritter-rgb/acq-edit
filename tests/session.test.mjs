import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {Store} from '../dist/store.js';
import {startSession,sessionPacket,completeSession,interruptSession} from '../dist/session.js';
import {serve} from '../dist/server.js';
import {sessionRequest,jobPresentation} from '../web/activity.js';
const execute=promisify(execFile);
async function fixture(t,backend='filmcraft'){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-session-')),s=new Store(path.join(root,'state.sqlite'));
 await mkdir(path.join(root,'10_WORK'));
 const p={id:'p',title:'Session fixture',root,backend,agent:'claude',createdAt:''};s.addProject(p);
 t.after(async()=>{s.close();await rm(root,{recursive:true,force:true})});return {root,s,p};
}
test('current-chat jobs cannot be claimed or recovered by a background worker',async t=>{
 const {s}=await fixture(t),j=s.enqueueBuild('p','Caption this',undefined,'session');
 assert.equal(s.claim(),undefined);const packet=await sessionPacket(s,j.id);
 assert.equal(packet.job.state,'queued');assert.match(packet.next,/Do not start another/);
 await startSession(s,j.id);assert.equal(s.job(j.id).state,'editing');
 s.recover(true);assert.equal(s.job(j.id).state,'editing');
 await assert.rejects(startSession(s,j.id),/Only a queued/);
 const next=s.enqueueBuild('p','Another',undefined,'session');await assert.rejects(startSession(s,next.id),/reserved/);
 assert.equal(s.job(next.id).state,'queued');
 // Explicit recovery still leaves interrupted work reserved; no automatic replay.
 s.recover();assert.equal(s.job(j.id).state,'reconciliation_required');assert.equal(s.claim(next.id),undefined);
});
test('legacy jobs keep their mode and cannot be claimed as current-chat requests',async t=>{
 const {s}=await fixture(t),j=s.enqueueBuild('p','Historical');delete j.execution;
 s.db.prepare('UPDATE jobs SET data=? WHERE id=?').run(JSON.stringify(j),j.id);
 assert.equal(s.claim(j.id),undefined);await assert.rejects(sessionPacket(s,j.id),/background\/legacy/);
 assert.equal(s.claim().id,j.id);s.recover(true);assert.equal(s.job(j.id).state,'reconciliation_required');
});
test('default build succeeds with a missing CLI and returns a usable session packet',async t=>{
 for(const backend of ['filmcraft','premiere']){
 const {root,s}=await fixture(t,backend);
 await writeFile(path.join(root,'config.json'),JSON.stringify({backend,agent:'claude',agentCommand:path.join(root,'missing-claude'),python:'/missing/python',storageRoot:root,port:4317}));
 const env={...process.env,ACQ_EDIT_HOME:root};
 const run=async(...args)=>JSON.parse((await execute(process.execPath,[path.resolve('dist/cli.js'),...args],{env})).stdout);
 const packet=await run('build','p','Build this clip');assert.equal(packet.job.execution,'session');assert.equal(packet.job.state,'queued');
 assert.equal(packet.job.completion,backend==='premiere'?'editable-project':'rendered-review');
 assert.equal(JSON.parse(await readFile(packet.packet)).job.id,packet.job.id);
 await run('session-start',packet.job.id);assert.equal(s.job(packet.job.id).state,'editing');
 await assert.rejects(run('build','p','--background','Another clip'),/CLI/);
 assert.equal(s.jobs('p').length,1);
 }
});
test('current-chat completion rejects forged or empty results and preserves reservation',async t=>{
 for(const backend of ['filmcraft','premiere']){
 const {s,root}=await fixture(t,backend),j=s.enqueueBuild('p','Build',undefined,'session');await startSession(s,j.id);
 const result=path.join(root,'10_WORK','result.json');await writeFile(result,JSON.stringify({jobId:j.id,versionIds:[],operationIds:['pretend']}));
 await assert.rejects(completeSession(s,j.id,result));assert.equal(s.job(j.id).state,'editing');
 await writeFile(result,JSON.stringify({jobId:'different',versionIds:['fake']}));await assert.rejects(completeSession(s,j.id,result),/another job/);
 }
});
test('default room captures exact revision notes without dispatch, including duplicates and late notes',async t=>{
 const {s,root,p}=await fixture(t);s.addClip({id:'c',projectId:'p',number:1,title:'Clip',currentVersionId:null});s.publish({id:'v',clipId:'c',number:1,parentId:null,media:path.join(root,'fake.mp4'),createdAt:''});
 let dispatched=0;const room=serve(s,{},undefined,async()=>{dispatched++;return false});
 await new Promise(r=>room.server.listen(0,'127.0.0.1',r));
 try{
 const base=`http://127.0.0.1:${room.server.address().port}`,login=await fetch(base+'/session?token='+room.token,{redirect:'manual'}),cookie=login.headers.get('set-cookie').split(';')[0];
 const caps=await (await fetch(base+'/api/capabilities',{headers:{cookie}})).json();assert.equal(caps.mode,'session');assert.equal(caps.revisionProcessing,true);
 s.saveFeedback('v',{notes:'Only restyle captions',comments:[],decision:'revise'},0);
 const request=async()=>{const r=await fetch(base+'/api/projects/p/revisions',{method:'POST',headers:{cookie,Origin:base,'Content-Type':'application/json'},body:JSON.stringify({versionIds:['v']})});assert.equal(r.status,202);return r.json()};
 const j=await request(),duplicate=await request();assert.equal(j.id,duplicate.id);assert.equal(j.execution,'session');
 s.saveFeedback('v',{notes:'Later music note',comments:[],decision:'revise'},1);
 assert.equal(s.job(j.id).snapshot[0].feedback.notes,'Only restyle captions');
 assert.match(jobPresentation(j).label,/chat/);assert.match(sessionRequest(j,p),new RegExp(j.id));
 await new Promise(r=>setTimeout(r,1650));assert.equal(dispatched,0);assert.equal(s.claim(),undefined);
 await startSession(s,j.id);await room.stop();assert.equal(s.job(j.id).state,'editing');assert.equal(s.feedback('v').notes,'Later music note');
 }finally{if(room.server.listening)await room.stop()}
});

test('interrupted chats have an explicit evidence-backed recovery path without releasing uncertain work',async t=>{
 const {s,root}=await fixture(t),j=s.enqueueBuild('p','Edit',undefined,'session');await startSession(s,j.id);
 const file=path.join(root,'10_WORK','inspection.json');await writeFile(file,JSON.stringify({jobId:j.id}));
 await assert.rejects(interruptSession(s,j.id,file),/Inspect/);assert.equal(s.job(j.id).state,'editing');
 const evidence={jobId:j.id,noActiveWriter:true,processInspection:'Fixture chat stopped; no command process',nativeInspection:'Fixture has no host work'};await writeFile(file,JSON.stringify(evidence));
 await interruptSession(s,j.id,file);assert.equal(s.job(j.id).state,'reconciliation_required');
 const next=s.enqueueBuild('p','Next',undefined,'session');assert.equal(s.claim(next.id),undefined);
 const {reconcileJob}=await import('../dist/native-operations.js');await reconcileJob(s,j.id,'failed',file);assert.equal(s.claim(next.id).id,next.id);
});

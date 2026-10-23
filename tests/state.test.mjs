import test from 'node:test';import assert from 'node:assert/strict';import {mkdtempSync,rmSync} from 'node:fs';import os from 'node:os';import path from 'node:path';import {Store} from '../dist/store.js';import {routeRevision} from '../dist/contracts.js';
function fixture(t){const root=mkdtempSync(path.join(os.tmpdir(),'acq-state-'));const s=new Store(path.join(root,'state.sqlite'));t.after(()=>{s.close();rmSync(root,{recursive:true,force:true})});s.addProject({id:'p',title:'Test',root,backend:'resolve',agent:'codex',createdAt:'2026-01-01'});s.addClip({id:'c',projectId:'p',number:1,title:'A complete thought',currentVersionId:null});s.publish(version('v1',1,null));return s}
function version(id,number,parentId){return{id,clipId:'c',number,parentId,media:'/media/'+id+'.mp4',sha256:id,nativeProject:'project.drp',nativeFingerprint:'abc',planPath:'plan.json',receiptPath:'receipt.json',createdAt:new Date().toISOString()}}
function notes(s,text='Make captions larger'){return s.saveFeedback('v1',{decision:'revise',notes:text,comments:[{id:'comment',seconds:1.25,text:'Here'}]},s.feedback('v1').revision)}
test('duplicate submissions use same durable snapshot and preserve later notes',t=>{const s=fixture(t);notes(s);const a=s.enqueue('p',['v1']),b=s.enqueue('p',['v1']);assert.equal(a.id,b.id);notes(s,'Keep this for next time');assert.equal(s.job(a.id).snapshot[0].feedback.notes,'Make captions larger');assert.equal(s.feedback('v1').notes,'Keep this for next time');assert.notEqual(s.enqueue('p',['v1']).id,a.id)});
test('optimistic feedback writes refuse stale tabs',t=>{const s=fixture(t);notes(s);assert.throws(()=>s.saveFeedback('v1',{decision:'no',notes:'old',comments:[]},0),/another window/);assert.equal(s.feedback('v1').decision,'revise')});
test('project mutations serialize and interrupted work blocks new work',t=>{const s=fixture(t);notes(s);const a=s.enqueue('p',['v1']);notes(s,'Second');s.enqueue('p',['v1']);assert.equal(s.claim().id,a.id);assert.equal(s.claim(),undefined);s.recover();assert.equal(s.job(a.id).state,'reconciliation_required');assert.equal(s.claim(),undefined)});
test('new versions reset decision and old timecodes remain bound to old media',t=>{const s=fixture(t);notes(s);s.publish(version('v2',2,'v1'));assert.equal(s.feedback('v2').decision,null);assert.equal(s.feedback('v2').comments.length,0);assert.equal(s.feedback('v1').comments[0].seconds,1.25);assert.equal(s.version('v1').media,'/media/v1.mp4');assert.throws(()=>s.enqueue('p',['v1']),/current version/)});
test('queued stale revision cannot overwrite newer clip',t=>{const s=fixture(t);notes(s);const j=s.enqueue('p',['v1']);s.publish(version('v2',2,'v1'));assert.equal(s.claim(),undefined);assert.equal(s.job(j.id).state,'failed')});
test('cross-project submissions and duplicate media paths are rejected',t=>{const s=fixture(t);s.addProject({id:'other',title:'Other',root:'/other',backend:'filmcraft',agent:'claude',createdAt:''});notes(s);assert.throws(()=>s.enqueue('other',['v1']),/current version/);assert.throws(()=>s.publish({...version('v2',2,'v1'),media:'/media/v1.mp4'}),/Immutable media/)});
test('caption changes do not route to assembly, recuts do',()=>{assert.deepEqual(routeRevision('Make the caption font larger'),['edit','caption-clips']);assert.ok(routeRevision('Remove this sentence').includes('assembly-design'));assert.ok(routeRevision('Remove this sentence').includes('caption-clips'))});

test('late feedback survives publication, stays bound to V1, and is consumed only by its next published job',t=>{
 const s=fixture(t);notes(s);const first=s.enqueue('p',['v1']);s.claim();
 s.saveFeedback('v1',{decision:'yes',notes:'Make captions larger, and remove the final filler.',comments:[{id:'comment',seconds:1.25,text:'Here'},{id:'late',seconds:1.8,text:'Remove this word, on V1'}]},s.feedback('v1').revision);
 assert.throws(()=>s.publish(version('v2',2,'v1')),/exact job ID/);
 s.publish({...version('v2',2,'v1'),jobId:first.id});s.finishJob(first.id,['v2']);
 const deferred=s.pendingFeedback('c');assert.equal(deferred.length,1);assert.equal(deferred[0].sourceVersion.id,'v1');assert.equal(deferred[0].latest.comments[1].seconds,1.8);
 assert.equal(s.feedback('v2').notes,'');assert.equal(s.feedback('v2').decision,null);
 const second=s.enqueue('p',['v2']);assert.equal(second.snapshot[0].deferred[0].id,deferred[0].id);assert.ok(second.snapshot[0].owners.includes('assembly-design'));
 assert.equal(s.enqueue('p',['v2']).id,second.id);s.claim();s.recover();assert.equal(s.pendingFeedback('c').length,1);
 s.publish({...version('v3',3,'v2'),jobId:second.id});s.finishJob(second.id,['v3']);assert.equal(s.pendingFeedback('c').length,0);
 assert.equal(s.job(second.id).snapshot[0].deferred[0].sourceVersion.media,'/media/v1.mp4');
 assert.equal(s.feedback('v1').comments[1].text,'Remove this word, on V1');
});

test('edited and withdrawn submitted notes remain explicit, but decision-only changes do not create a revision',t=>{
 const s=fixture(t);notes(s);const first=s.enqueue('p',['v1']);s.claim();
 s.saveFeedback('v1',{decision:'no',notes:'',comments:[]},s.feedback('v1').revision);
 s.publish({...version('v2',2,'v1'),jobId:first.id});s.finishJob(first.id,['v2']);
 const d=s.pendingFeedback('c')[0];assert.equal(d.submitted.notes,'Make captions larger');assert.equal(d.latest.notes,'');assert.equal(d.submitted.comments.length,1);assert.equal(d.latest.comments.length,0);
 const second=s.enqueue('p',['v2']);s.claim();s.saveFeedback('v2',{decision:'yes',notes:'',comments:[]},0);
 s.publish({...version('v3',3,'v2'),jobId:second.id});s.finishJob(second.id,['v3']);assert.equal(s.pendingFeedback('c').length,0);assert.equal(s.feedback('v3').decision,null);
});

test('a new version and completion cannot be attributed to an unrelated job',t=>{
 const s=fixture(t);notes(s);const first=s.enqueue('p',['v1']);s.claim();
 assert.throws(()=>s.publish({...version('v2',2,'v1'),jobId:'other'}),/exact job ID/);
 assert.throws(()=>s.finishJob(first.id,['v1']),/another job/);
 s.publish({...version('v2',2,'v1'),jobId:first.id});
 assert.throws(()=>s.publish({...version('v3',3,'v2'),jobId:first.id}),/already published/);
 assert.throws(()=>s.finishJob(first.id,['v2','v2']),/distinct/);
 s.finishJob(first.id,['v2']);assert.equal(s.job(first.id).state,'ready');
});

test('partial batch publication preserves unconsumed feedback and cannot mark the whole job ready',t=>{
 const s=fixture(t);s.addClip({id:'other',projectId:'p',number:2,title:'Another clip',currentVersionId:null});s.publish({...version('other-v1',1,null),clipId:'other'});
 notes(s);s.saveFeedback('other-v1',{decision:'revise',notes:'Adjust captions',comments:[]},0);
 const job=s.enqueue('p',['v1','other-v1']);s.claim();notes(s,'Late note');
 s.publish({...version('v2',2,'v1'),jobId:job.id});assert.throws(()=>s.finishJob(job.id,['v2']),/Not all/);
 s.recover();assert.equal(s.pendingFeedback('c')[0].latest.notes,'Late note');assert.equal(s.clip('other').currentVersionId,'other-v1');
 s.publish({...version('other-v2',2,'other-v1'),clipId:'other',jobId:job.id});s.finishJob(job.id,['v2','other-v2']);
 assert.equal(s.pendingFeedback('c').length,1);
});

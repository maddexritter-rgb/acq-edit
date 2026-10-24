import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../dist/store.js';
import {sha256} from '../dist/files.js';
import {verifyPublishedVersions} from '../dist/publish.js';

test('completion verifies job ownership and archived bytes even when the live native project changes',async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-publish-'));
 const s=new Store(path.join(root,'state.sqlite'));
 t.after(async()=>{s.close();await rm(root,{recursive:true,force:true})});
 s.addProject({id:'p',title:'Integrity fixture',root,backend:'resolve',agent:'codex',createdAt:''});
 s.addClip({id:'c',projectId:'p',number:1,title:'Fixture',currentVersionId:null});
 const files=Object.fromEntries(['media','native','live','plan','receipt','inspection'].map(k=>[k,path.join(root,k)]));
 for(const [k,f] of Object.entries(files))await writeFile(f,k);
 const base={clipId:'c',media:files.media,sha256:await sha256(files.media),nativeProject:files.live,nativeCheckpoint:files.native,nativeFingerprint:await sha256(files.native),planPath:files.plan,planSha256:await sha256(files.plan),receiptPath:files.receipt,receiptSha256:await sha256(files.receipt),inspectionPath:files.inspection,inspectionSha256:await sha256(files.inspection),createdAt:''};
 s.publish({...base,id:'v1',number:1,parentId:null});
 s.saveFeedback('v1',{decision:'revise',notes:'Change caption color',comments:[]},0);
 const j=s.enqueue('p',['v1']);s.claim();
 const nextMedia=path.join(root,'media-v2');await writeFile(nextMedia,'media');
 s.publish({...base,id:'v2',number:2,parentId:'v1',jobId:j.id,media:nextMedia});
 await writeFile(files.live,'Intervening manual edits');
 await verifyPublishedVersions(s,j.id,['v2']);
 await assert.rejects(verifyPublishedVersions(s,j.id,['v1']),/another job/);
 for(const key of ['plan','receipt','inspection']){
  await writeFile(files[key],'changed');
  await assert.rejects(verifyPublishedVersions(s,j.id,['v2']),/Published .*changed/);
  await writeFile(files[key],key);
 }
 await writeFile(nextMedia,'damaged');
 await assert.rejects(verifyPublishedVersions(s,j.id,['v2']),/media.*changed/);
 await writeFile(nextMedia,'media');await writeFile(files.native,'changed checkpoint');
 await assert.rejects(verifyPublishedVersions(s,j.id,['v2']),/checkpoint changed/);
 await writeFile(files.native,'native');await rm(files.plan);
 await assert.rejects(verifyPublishedVersions(s,j.id,['v2']));
 assert.equal(s.job(j.id).state,'editing');
});

test('changed cuts cannot publish without an exact native recut proof',async t=>{
 const {verifyRecutReceipt}=await import('../dist/publish.js');
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-recut-publication-'));const s=new Store(path.join(root,'state.sqlite'));
 t.after(async()=>{s.close();await rm(root,{recursive:true,force:true})});
 const p={id:'p',title:'Fixture',root,backend:'filmcraft',agent:'codex',createdAt:''};s.addProject(p);s.addClip({id:'c',projectId:'p',number:1,title:'Clip',currentVersionId:null});
 const prior=path.join(root,'prior.json'),next=path.join(root,'next.json'),proofFile=path.join(root,'recut.json');
 const plan={projectId:'p',backend:'filmcraft',clipId:'c',cuts:[{id:'a',frames:50}]};await writeFile(prior,JSON.stringify(plan));await writeFile(next,JSON.stringify({...plan,cuts:[{id:'b',frames:25}]}));
 const version={id:'v1',clipId:'c',number:1,parentId:null,media:path.join(root,'old.mp4'),planPath:prior,planSha256:await sha256(prior),createdAt:''};s.publish(version);
 const receipt={projectId:'p',backend:'filmcraft',clipId:'c',parentId:'v1',planPath:next,nativeProject:path.join(root,'new.fcproj'),nativeFingerprint:'new-native-hash'};
 await assert.rejects(verifyRecutReceipt(s,p,receipt),/Changed source cuts/);
 const proof={schema:'acq-edit/recut-execution-v1',backend:'filmcraft',parentVersionId:'v1',parentPreserved:true,parentPlanSha256:version.planSha256,planSha256:await sha256(next),newNativeSha256:receipt.nativeFingerprint,construction:{nativeProject:receipt.nativeProject}};
 await writeFile(proofFile,JSON.stringify(proof));receipt.recutVerificationPath=proofFile;receipt.recutVerificationSha256=await sha256(proofFile);
 await verifyRecutReceipt(s,p,receipt);
 await writeFile(proofFile,JSON.stringify({...proof,parentVersionId:'different'}));receipt.recutVerificationSha256=await sha256(proofFile);
 await assert.rejects(verifyRecutReceipt(s,p,receipt),/identity differs/);
 await writeFile(proofFile,JSON.stringify({...proof,planSha256:'stale'}));receipt.recutVerificationSha256=await sha256(proofFile);
 await assert.rejects(verifyRecutReceipt(s,p,receipt),/does not describe/);
});

test('native resume metadata rejects unrelated inspections, engines and stale startup overrides',async()=>{
 const {verifyNativeReopen}=await import('../dist/publish.js');
 const p={id:'p',backend:'resolve'},state={project:'ACQ_p',timeline:'timeline-id'},digest='a'.repeat(64);
 const value={nativeProjectId:'native-id',database:{DbType:'Disk',DbName:'Test'},timelineId:'timeline-id',expectedFingerprint:'b'.repeat(64),inspectionSha256:digest};
 assert.deepEqual(verifyNativeReopen(p,value,state,digest),value);
 assert.equal(verifyNativeReopen(p,undefined,null,digest),undefined);
 for(const bad of [null,[],{...value,emptyWorkspace:{}},{...value,timelineId:'another'},{...value,inspectionSha256:'wrong'},{...value,expectedFingerprint:'bad'},{...value,database:{DbName:'Test'}}])assert.throws(()=>verifyNativeReopen(p,bad,state,digest),/Native reopen|native reopen|Unexpected/);
 assert.throws(()=>verifyNativeReopen({...p,backend:'filmcraft'},value,state,digest),/requires Resolve/);
 assert.throws(()=>verifyNativeReopen(p,value,{...state,project:'ACQ_other'},digest),/differs/);
});

for(const backend of ['resolve','premiere'])test(`${backend} resume target survives database restart and frozen revision submission`,async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-resume-')),database=path.join(root,'state.sqlite');let s=new Store(database);
 t.after(async()=>{s.close();await rm(root,{recursive:true,force:true})});
 const p={id:'p',title:'Resume fixture',root,backend,agent:'codex',createdAt:''};s.addProject(p);s.addClip({id:'c',projectId:'p',number:1,title:'Clip',currentVersionId:null});
 const files=Object.fromEntries(['media','native','plan','receipt','inspection'].map(k=>[k,path.join(root,k==='native'?'native.prproj':k)]));
 for(const k of ['media','native','plan'])await writeFile(files[k],k);
 await writeFile(files.inspection,JSON.stringify(backend==='resolve'?{project:'ACQ_p',timeline:'timeline-id'}:{snapshot:{projectPath:files.native,sequenceId:'sequence-id'},nativeSha256:await sha256(files.native),nativeStateFingerprint:'b'.repeat(64)}));
 const target=backend==='premiere'?{schema:'acq-edit/premiere-reopen-v1',nativeProject:files.native,nativeSha256:await sha256(files.native),expectedFingerprint:'b'.repeat(64),sequenceId:'sequence-id',inspectionSha256:await sha256(files.inspection)}:{nativeProjectId:'native-id',database:{DbType:'Disk',DbName:'Test'},timelineId:'timeline-id',expectedFingerprint:'b'.repeat(64),inspectionSha256:await sha256(files.inspection)};
 await writeFile(files.receipt,JSON.stringify({nativeReopen:target}));
 const j=s.enqueueBuild('p','Build fixture');s.claim();
 const v={id:'v1',clipId:'c',number:1,parentId:null,jobId:j.id,createdAt:'',media:files.media,sha256:await sha256(files.media),nativeProject:files.native,nativeCheckpoint:files.native,nativeFingerprint:await sha256(files.native),planPath:files.plan,planSha256:await sha256(files.plan),inspectionPath:files.inspection,inspectionSha256:await sha256(files.inspection),receiptPath:files.receipt,receiptSha256:await sha256(files.receipt),nativeReopen:target};
 s.publish(v);await verifyPublishedVersions(s,j.id,['v1']);s.finishJob(j.id,['v1']);s.close();s=new Store(database);
 s.saveFeedback('v1',{decision:'revise',notes:'Change caption',comments:[]},0);const next=s.enqueue('p',['v1']);
 assert.deepEqual(next.snapshot[0].version.nativeReopen,target);
 const changed={...v,nativeReopen:{...target,expectedFingerprint:'c'.repeat(64)}};
 s.db.prepare('UPDATE versions SET data=? WHERE id=?').run(JSON.stringify(changed),'v1');
 await assert.rejects(verifyPublishedVersions(s,j.id,['v1']),/reopen metadata changed/);
 assert.deepEqual(s.job(next.id).snapshot[0].version.nativeReopen,target);
});

 test('Premiere reopen metadata binds saved bytes, native path, sequence and full inspection fingerprint',async()=>{
 const {verifyNativeReopen}=await import('../dist/publish.js');
 const p={id:'p',root:'/toolkit/project',backend:'premiere'},digest='a'.repeat(64),native='/toolkit/project/10_WORK/edit.prproj';
 const value={schema:'acq-edit/premiere-reopen-v1',nativeProject:native,nativeSha256:'b'.repeat(64),expectedFingerprint:'c'.repeat(64),sequenceId:'sequence',inspectionSha256:digest};
 const state={snapshot:{projectPath:native,sequenceId:'sequence'},nativeSha256:value.nativeSha256,nativeStateFingerprint:value.expectedFingerprint};
 assert.deepEqual(verifyNativeReopen(p,value,state,digest),value);
 for(const changed of [null,[],{...value,ownershipConfirmed:true},{...value,nativeProject:'/other/edit.prproj'},{...value,nativeSha256:'d'.repeat(64)},{...value,expectedFingerprint:'d'.repeat(64)},{...value,sequenceId:'other'},{...value,inspectionSha256:'d'.repeat(64)}])assert.throws(()=>verifyNativeReopen(p,changed,state,digest),/Native reopen|native reopen/);
 });

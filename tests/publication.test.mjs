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

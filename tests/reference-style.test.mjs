import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,symlink} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {sha256} from '../dist/files.js';
import {verifyReferenceReceipt} from '../dist/reference-style.js';
async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-reference-'));t.after(()=>rm(root,{recursive:true,force:true}));
 await mkdir(path.join(root,'00_SOURCE'));await mkdir(path.join(root,'10_WORK'));
 const source=path.join(root,'00_SOURCE/ref.mp4'),report=path.join(root,'10_WORK/watch.txt'),origin=path.join(root,'10_WORK/recipe.json'),file=path.join(root,'10_WORK/frozen.json');
 await writeFile(source,'synthetic source');await writeFile(report,'synthetic report; not viewing proof');await writeFile(origin,'{"revision":1}');
 const project={id:'p',root,backend:'resolve'};
 const snapshot={schema:'acq-edit/reference-style-v1',owner:'watch',projectId:'p',backend:'resolve',humanApproved:false,coverageStatus:'reported-by-watch-owner',source:{path:source,sha256:await sha256(source)},recipeOrigin:{path:origin,sha256:await sha256(origin)},recipe:{revision:1},evidenceFiles:[{id:'report',path:report,sha256:await sha256(report)}]};
 const bind=async()=>{await writeFile(file,JSON.stringify(snapshot));const contract={path:file,sha256:await sha256(file)};return {plan:{referenceStyle:contract},evidence:{contract,snapshot:structuredClone(snapshot)}}};
 return {project,snapshot,source,report,origin,file,bind,...await bind()};
}
test('publication binds frozen recipe and ignores later working recipe changes',async t=>{
 const f=await fixture(t);await verifyReferenceReceipt(f.project,f.plan,f.evidence);
 await writeFile(f.origin,'{"revision":2}');await verifyReferenceReceipt(f.project,f.plan,f.evidence);assert.equal(f.evidence.snapshot.recipe.revision,1);
});
test('publication rejects changed reference source, evidence and snapshot',async t=>{
 const f=await fixture(t);
 for(const file of [f.source,f.report,f.file]){const bytes=await readFile(file);await writeFile(file,'changed');await assert.rejects(verifyReferenceReceipt(f.project,f.plan,f.evidence),/changed/);await writeFile(file,bytes)}
});
test('publication rejects mismatched or unbound receipts and false approval identity',async t=>{
 const f=await fixture(t);await verifyReferenceReceipt(f.project,{},undefined);
 await assert.rejects(verifyReferenceReceipt(f.project,{},f.evidence),/no bound/);
 for(const evidence of [undefined,{...f.evidence,contract:{...f.evidence.contract,sha256:'a'.repeat(64)}},{...f.evidence,snapshot:{...f.snapshot,recipe:{revision:2}}}])await assert.rejects(verifyReferenceReceipt(f.project,f.plan,evidence),/differs/);
 for(const change of [{humanApproved:true},{backend:'premiere'},{projectId:'other'},{coverageStatus:'human-approved'}]){
  const original=structuredClone(f.snapshot);Object.assign(f.snapshot,change);const bound=await f.bind();await assert.rejects(verifyReferenceReceipt(f.project,bound.plan,bound.evidence),/identity or approval/);Object.assign(f.snapshot,original);
 }
});
test('reference paths must remain within their project folders after symlink resolution',async t=>{
 const f=await fixture(t),link=path.join(f.project.root,'10_WORK/ref-link');await symlink(f.source,link);f.snapshot.evidenceFiles[0]={id:'outside-evidence-folder',path:link,sha256:await sha256(f.source)};const bound=await f.bind();await assert.rejects(verifyReferenceReceipt(f.project,bound.plan,bound.evidence),/outside project/);
});

test('publication archives the exact frozen recipe and later working changes leave it intact',async t=>{
 const {Store}=await import('../dist/store.js'),{publish}=await import('../dist/publish.js'),{run}=await import('../dist/process.js');
 const f=await fixture(t),store=new Store(path.join(f.project.root,'state.sqlite'));t.after(()=>store.close());
 store.addProject({...f.project,title:'Synthetic publication fixture',agent:'codex',createdAt:''});store.addClip({id:'c',projectId:'p',number:1,title:'Synthetic fixture',currentVersionId:null});
 const work=path.join(f.project.root,'10_WORK'),media=path.join(work,'render.mp4'),native=path.join(work,'native.fixture'),inspection=path.join(work,'inspection.json'),plan=path.join(work,'plan.json'),receipt=path.join(work,'receipt.json');
 await run('ffmpeg',['-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=25:duration=0.08','-c:v','libx264','-pix_fmt','yuv420p',media]);
 await writeFile(native,'Synthetic native stand-in; this test does not qualify an editor');await writeFile(inspection,'{}');await writeFile(plan,JSON.stringify({...f.plan,projectId:'p',backend:'resolve',clipId:'c'}));
 await writeFile(receipt,JSON.stringify({schema:'acq-edit/render-v1',projectId:'p',backend:'resolve',clipId:'c',parentId:null,media,nativeProject:native,nativeFingerprint:await sha256(native),nativeInspectionPath:inspection,planPath:plan,nativeRendered:true,expected:{width:160,height:90,frames:2,fps:'25/1'},referenceEvidence:f.evidence}));
 const originalReceipt=JSON.parse(await readFile(receipt));
 await writeFile(receipt,JSON.stringify({...originalReceipt,expected:{...originalReceipt.expected,frames:3}}));
 await assert.rejects(publish(store,'p',receipt),/decoded frame count mismatch/);
 await writeFile(receipt,JSON.stringify(originalReceipt));
 const version=await publish(store,'p',receipt),before=await readFile(version.receiptPath);
 assert.deepEqual(JSON.parse(before).referenceEvidence,f.evidence);assert.equal(store.feedback(version.id).decision,null);
 await writeFile(f.origin,'{"revision":2}');await writeFile(f.file,'{"new":"working file must not rewrite archived receipt"}');
 assert.deepEqual(await readFile(version.receiptPath),before);assert.equal(await sha256(version.receiptPath),version.receiptSha256);
});

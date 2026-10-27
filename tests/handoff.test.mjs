import test from 'node:test';import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';import path from 'node:path';import os from 'node:os';
import {Store} from '../dist/store.js';import {sha256} from '../dist/files.js';import {prepareHandoff,importHandoff} from '../dist/handoff.js';
async function fixture(t,backend){
 const base=await mkdtemp(path.join(os.tmpdir(),'acq-handoff-')),root=path.join(base,'original');for(const d of ['00_SOURCE','10_WORK','20_DELIVER'])await mkdir(path.join(root,d),{recursive:true});
 const s=new Store(path.join(base,'source.sqlite')),dest=new Store(path.join(base,'dest.sqlite'));t.after(async()=>{s.close();dest.close();await rm(base,{recursive:true,force:true})});
 const p={id:'p',root,title:'Synthetic source',backend,agent:'codex',createdAt:''};s.addProject(p);await writeFile(path.join(root,'project.json'),JSON.stringify(p));s.addClip({id:'c',projectId:'p',number:1,title:'Synthetic',currentVersionId:null});
 const media=path.join(root,'00_SOURCE/raw.mov');await writeFile(media,'source bytes, never a finished render');const source={id:'s',projectId:'p',path:media,sha256:await sha256(media),bytes:42,origin:'fixture',probe:{}};s.addSource(source);
 const evidence=path.join(root,'10_WORK/evidence.json');await writeFile(evidence,'{}');const sum=await sha256(evidence);
 const plan={schema:'acq-edit/plan-v1',projectId:'p',backend,clipId:'c',title:'Synthetic',fps:{numerator:30,denominator:1},width:1080,height:1920,sampleRate:48000,brain:{receiptPath:evidence,sha256:sum},editorial:{selectionPath:evidence,sha256:sum,reviewed:true},sources:[source],cuts:[{id:'cut',sourceId:'s',sourceInFrame:2,frames:30,recordFrame:0,audioInSample:3200,audioSamples:48000,wordIds:['1'],boundaryEvidence:'fixture'}],captions:[{startFrame:0,endFrame:30,text:'Kept words',style:{face:'Fixture'}}],graphics:[],framing:{},audio:{gainDb:0}};
 const file=path.join(root,'10_WORK/plan.json');await writeFile(file,JSON.stringify(plan));const destination=backend==='filmcraft'?'premiere':'filmcraft';
 return {base,root,s,dest,plan,file,source,request:{planPath:file,destination},config:{backend,agent:'codex',storageRoot:base},destination};
}
for(const backend of ['filmcraft','premiere'])test(`${backend} handoff preserves exact decisions/sources and reserves one linked destination`,async t=>{
 const f=await fixture(t,backend),before=await readFile(f.file,'utf8');const out=await prepareHandoff(f.s,f.config,'p',f.request);assert.equal(out.state,'prepared');
 const calls=[];const intake=async(store,pid,file)=>{calls.push(file);const source={...f.source,id:'new-source',projectId:pid};store.addSource(source);return source};
 const imported=await importHandoff(f.dest,{...f.config,backend:f.destination},out.checkpoint,{intake});assert.equal(imported.state,'reconstruction-queued');
 const checkpoint=JSON.parse(await readFile(imported.checkpoint));for(const key of ['cuts','captions','framing','audio'])assert.deepEqual(checkpoint.plan[key],f.plan[key]);
 assert.equal(f.dest.project(imported.projectId).backend,f.destination);assert.equal(f.s.project('p').backend,backend);assert.equal(await readFile(f.file,'utf8'),before);assert.deepEqual(calls,[f.source.path]);
 const duplicate=await importHandoff(f.dest,{...f.config,backend:f.destination},out.checkpoint,{intake});assert.equal(duplicate.projectId,imported.projectId);assert.equal(f.dest.projects().length,1);assert.equal(calls.length,1);
});
for(const backend of ['filmcraft','premiere'])test(`${backend} mid-render handoff waits and unsupported effects pause`,async t=>{
 const f=await fixture(t,backend),j=f.s.enqueueBuild('p','render');f.s.claim();f.s.setJob(j.id,'rendering');
 assert.equal((await prepareHandoff(f.s,f.config,'p',f.request)).state,'waiting-for-safe-checkpoint');assert.equal(f.s.job(j.id).state,'rendering');
 f.s.setJob(j.id,'failed','Fixture settled');f.plan.graphics=[{path:f.source.path,startFrame:0,frames:30,sha256:f.source.sha256}];await writeFile(f.file,JSON.stringify(f.plan));
 const blocked=await prepareHandoff(f.s,f.config,'p',f.request);assert.equal(blocked.state,'needs-editor-choice');assert.match(blocked.reason,/no flattening/);assert.equal(f.dest.projects().length,0);
});
test('constructed native state without a completed checkpoint pauses instead of dropping edits',async t=>{
 const f=await fixture(t,'premiere');f.s.addNativeOperation({id:'op',projectId:'p',backend:'premiere',action:'build',state:'running',jobId:null,createdAt:'',updatedAt:''});f.s.updateNativeOperation('op',{state:'succeeded'});
 const result=await prepareHandoff(f.s,f.config,'p',f.request);assert.equal(result.state,'needs-editor-choice');assert.match(result.reason,/no completed checkpoint/);
});
for(const backend of ['filmcraft','premiere'])test(`${backend} post-construction handoff checks intervening native edits`,async t=>{
 const f=await fixture(t,backend);f.s.publish({id:'v',clipId:'c',number:1,parentId:null,media:path.join(f.root,'unused.mp4'),nativeProject:path.join(f.root,'10_WORK/native'),planSha256:await sha256(f.file),nativeReopen:{expectedFingerprint:'checkpoint'},createdAt:''});
 const changed=await prepareHandoff(f.s,f.config,'p',f.request,{inspect:async()=>({fingerprint:'manual-edit'})});assert.equal(changed.state,'needs-editor-choice');assert.match(changed.reason,/Intervening/);
 const same=await prepareHandoff(f.s,f.config,'p',f.request,{inspect:async()=>({fingerprint:'checkpoint'})});assert.equal(same.state,'prepared');
});

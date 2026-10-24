import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm,symlink} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {sha256} from '../dist/files.js';
import {referenceReview,referenceMedia} from '../dist/reference-review.js';
import {Store} from '../dist/store.js';
import {serve} from '../dist/server.js';
async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-reference-review-'));for(const folder of ['00_SOURCE','10_WORK','20_DELIVER'])await mkdir(path.join(root,folder));
 const store=new Store(path.join(root,'state.sqlite'));t.after(async()=>{store.close();await rm(root,{recursive:true,force:true})});
 const project={id:'p',title:'Synthetic reference review',root,backend:'resolve',agent:'codex',createdAt:''};store.addProject(project);store.addClip({id:'c',projectId:'p',title:'Synthetic clip',number:1,currentVersionId:null});
 const versions=[];
 for(const number of [1,2]){
  const id='v'+number,folder=path.join(root,'20_DELIVER',id);await mkdir(folder);const source=path.join(root,'00_SOURCE',id+'.mp4');await writeFile(source,number===1?'0123456789':'abcdefghij');
  const snapshot={schema:'acq-edit/reference-style-v1',owner:'watch',projectId:'p',backend:'resolve',humanApproved:false,coverageStatus:'reported-by-watch-owner',hasAudio:false,source:{path:source,sha256:await sha256(source)},recipe:{sourceSha256:await sha256(source),durationSeconds:6,coverage:{fullVideoViewed:true,audioListened:false,audioAbsent:true,evidence:['synthetic'],denseIntervals:[]},segments:[{start:1,end:2,category:'motion',basis:'observed',observation:'Synthetic recipe '+number,evidence:['synthetic']}],unsupportedEffects:['Synthetic limitation '+number]}};
  const working=path.join(root,'10_WORK','frozen-'+id+'.json');await writeFile(working,JSON.stringify(snapshot));const contract={path:working,sha256:await sha256(working)};
  const planPath=path.join(folder,'plan.json'),receiptPath=path.join(folder,'receipt.json'),parentId=number===1?null:'v1';await writeFile(planPath,JSON.stringify({projectId:'p',backend:'resolve',clipId:'c',referenceStyle:contract}));await writeFile(receiptPath,JSON.stringify({schema:'acq-edit/render-v1',projectId:'p',backend:'resolve',clipId:'c',parentId,referenceEvidence:{contract,snapshot}}));
  const version={id,clipId:'c',number,parentId,planPath,planSha256:await sha256(planPath),receiptPath,receiptSha256:await sha256(receiptPath),media:path.join(folder,'clip.mp4'),createdAt:''};store.publish(version);versions.push({version,source,working,snapshot});
 }
 return {root,store,project,versions};
}
test('historical reference notes and source stay bound to the selected version, independently of working files',async t=>{
 const f=await fixture(t);for(const entry of f.versions){await rm(entry.working);const view=await referenceReview(f.project,entry.version);assert.equal(view.versionId,entry.version.id);assert.equal(view.recipe.segments[0].observation,'Synthetic recipe '+entry.version.number);assert.equal(view.media.url,'/reference-media/'+entry.version.id);assert.equal(await referenceMedia(f.project,entry.version),await import('node:fs/promises').then(m=>m.realpath(entry.source)))}
 assert.equal(f.store.feedback('v1').decision,null);assert.equal(f.store.feedback('v2').decision,null);
});
test('missing or changed source preserves readable notes but refuses reference playback',async t=>{
 const f=await fixture(t);for(const [index,entry] of f.versions.entries()){
  if(index)await rm(entry.source);else await writeFile(entry.source,'changed');
  const view=await referenceReview(f.project,entry.version);assert.equal(view.media.available,false);assert.equal(view.media.url,undefined);assert(view.media.error);if(index)assert.match(view.media.error,/original reference file is missing/);assert.equal(view.recipe.segments[0].observation,'Synthetic recipe '+entry.version.number);await assert.rejects(referenceMedia(f.project,entry.version));
 }
});
test('changed archived receipts, plans and escaped source paths are refused',async t=>{
 const f=await fixture(t),entry=f.versions[0];
 for(const file of [entry.version.planPath,entry.version.receiptPath]){const bytes=await readFile(file);await writeFile(file,'{}');await assert.rejects(referenceReview(f.project,entry.version),/provenance changed/);await writeFile(file,bytes)}
 const outside=path.join(f.root,'10_WORK/outside.mp4');await writeFile(outside,await readFile(entry.source));await rm(entry.source);await symlink(outside,entry.source);await assert.rejects(referenceMedia(f.project,entry.version),/outside project/);
});
test('legacy versions without verified archives expose no inferred reference',async t=>{
 const f=await fixture(t);assert.equal(await referenceReview(f.project,{...f.versions[0].version,receiptSha256:undefined}),null);await assert.rejects(referenceMedia(f.project,{...f.versions[0].version,receiptSha256:undefined}),/No archived reference/);
});
test('authenticated reference endpoints serve each version and ranges without changing feedback',async t=>{
 const f=await fixture(t),room=serve(f.store,{},false);await new Promise(resolve=>room.server.listen(0,'127.0.0.1',resolve));t.after(()=>room.stop());const base='http://127.0.0.1:'+room.server.address().port;
 assert.equal((await fetch(base+'/reference-media/v1')).status,400);const login=await fetch(base+'/session?token='+room.token,{redirect:'manual'}),cookie=login.headers.get('set-cookie').split(';')[0];
 for(const [id,expected] of [['v1','234'],['v2','cde']]){const response=await fetch(base+'/api/versions/'+id+'/reference',{headers:{cookie}});assert.equal(response.status,200);assert.equal((await response.json()).versionId,id);const media=await fetch(base+'/reference-media/'+id,{headers:{cookie,range:'bytes=2-4'}});assert.equal(media.status,206);assert.equal(await media.text(),expected)}
 assert.equal((await fetch(base+'/reference.js',{headers:{cookie}})).status,200);
 await writeFile(f.versions[0].source,'changed');assert.equal((await fetch(base+'/reference-media/v1',{headers:{cookie}})).status,400);assert.equal((await (await fetch(base+'/api/versions/v1/reference',{headers:{cookie}})).json()).media.available,false);
 assert.equal(f.store.jobs('p').length,0);assert.equal(f.store.feedback('v1').revision,0);assert.equal(f.store.feedback('v2').revision,0);
});

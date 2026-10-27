import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {Store} from '../dist/store.js';
import {completeJob} from '../dist/completion.js';
import {sha256} from '../dist/files.js';
import {jobPrompt} from '../dist/agents.js';
async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-complete-'));await mkdir(path.join(root,'10_WORK'));const s=new Store(path.join(root,'db'));
 const p={id:'p',root,title:'Synthetic',backend:'premiere',agent:'codex',createdAt:''};s.addProject(p);s.addClip({id:'c',projectId:'p',number:1,title:'Clip',currentVersionId:null});
 t.after(async()=>{delete process.env.ACQ_EDIT_JOB_ID;s.close();await rm(root,{recursive:true,force:true})});
 const j=s.enqueueBuild('p','Build editable');s.claim();process.env.ACQ_EDIT_JOB_ID=j.id;
 const artifacts=[];for(const name of ['native.prproj','plan.json','inspection.json','reopen.json','captions.json','audio.json']){const file=path.join(root,name);await writeFile(file,'synthetic '+name);artifacts.push({path:file,sha256:await sha256(file)})}
 const receipt={schema:'acq-edit/editable-project-v1',jobId:j.id,projectId:'p',clipId:'c',sequenceId:'sequence',nativeProject:artifacts[0].path,planPath:artifacts[1].path,inspectionPath:artifacts[2].path,artifacts};
 const receiptPath=path.join(root,'receipt.json');await writeFile(receiptPath,JSON.stringify(receipt));
 const result={...receipt,receiptPath,receiptSha256:await sha256(receiptPath)},journal=path.join(root,'native-result.json');await writeFile(journal,JSON.stringify({operationId:'op',stdout:JSON.stringify(result)}));
 s.addNativeOperation({id:'op',projectId:'p',jobId:j.id,backend:'premiere',action:'complete',state:'running',directory:root,packetPath:artifacts[1].path,packetSha256:artifacts[1].sha256,ownerPid:null,childPid:null,childPending:false,createdAt:'',updatedAt:'',error:null});s.updateNativeOperation('op',{state:'succeeded',resultPath:journal,resultSha256:await sha256(journal)});
 return {s,p,j,artifacts,result:{jobId:j.id,operationIds:['op']}};
}
test('new Premiere job completes with native evidence and no video or review version',async t=>{
 const f=await fixture(t);assert.equal(f.j.completion,'editable-project');await completeJob(f.s,f.j.id,f.result);assert.equal(f.s.job(f.j.id).state,'ready');assert.equal(f.s.versions('c').length,0);assert.equal(f.s.job(f.j.id).nativeCompletions.length,1);
 assert.match(jobPrompt(f.p,f.j,'packet'),/Do not export an MP4, launch the review room or upload/);
 assert.equal(f.s.enqueueBuild('p','Export explicitly','rendered-review').completion,'rendered-review');
});
test('native completion refuses missing, changed and duplicate evidence',async t=>{
 const f=await fixture(t);
 await assert.rejects(completeJob(f.s,f.j.id,{jobId:f.j.id,versionIds:['pretend-mp4']}),/operation IDs/);
 await assert.rejects(completeJob(f.s,f.j.id,{jobId:f.j.id,operationIds:['op','op']}),/operation IDs/);
 await writeFile(f.artifacts[0].path,'manual saved edit');await assert.rejects(completeJob(f.s,f.j.id,f.result),/stale/);assert.equal(f.s.job(f.j.id).state,'editing');
});
test('historical Premiere jobs retain rendered completion after upgrade',async t=>{
 const f=await fixture(t);const legacy={...f.j};delete legacy.completion;f.s.db.prepare('UPDATE jobs SET data=? WHERE id=?').run(JSON.stringify(legacy),f.j.id);
 await assert.rejects(completeJob(f.s,f.j.id,f.result),/completed versions/);
 assert.match(jobPrompt(f.p,legacy,'packet'),/native render inspection/);
});

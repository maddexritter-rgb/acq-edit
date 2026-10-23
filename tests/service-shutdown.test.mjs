import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,mkdir} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

test('service shutdown waits for its agent, reconciles the job, and exports durable state',async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-shutdown-'));
 process.env.ACQ_EDIT_HOME=path.join(root,'config');process.env.SCENARIO='hang';process.env.PID_FILE=path.join(root,'pid');
 const {Store}=await import('../dist/store.js'),{serve}=await import('../dist/server.js');
 const s=new Store(path.join(root,'state.sqlite'));
 const projectRoot=path.join(root,'project');await mkdir(projectRoot);
 s.addProject({id:'p',title:'Shutdown fixture',root:projectRoot,backend:'filmcraft',agent:'codex',createdAt:''});
 const job=s.enqueueBuild('p','Fixture only');
 const room=serve(s,{storageRoot:root,backend:'filmcraft',agent:'codex',python:'python3',port:0,agentCommand:fileURLToPath(new URL('./fixtures/agent-process.mjs',import.meta.url))});
 t.after(async()=>{if(room.server.listening)await room.stop();s.close();await rm(root,{recursive:true,force:true})});
 await new Promise(r=>room.server.listen(0,'127.0.0.1',r));
 let pid;
 for(let n=0;n<250;n++){try{pid=Number(await readFile(process.env.PID_FILE,'utf8'));break}catch{await new Promise(r=>setTimeout(r,10))}}
 assert.ok(pid,'worker spawned a live agent');assert.equal(s.job(job.id).state,'editing');
 await room.stop();
 assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});
 assert.equal(s.job(job.id).state,'reconciliation_required');assert.match(s.job(job.id).error,/shutdown/);
 assert.equal(room.server.listening,false);
 const exported=JSON.parse(await readFile(path.join(projectRoot,'10_WORK','review-feedback.json'),'utf8'));
 assert.equal(exported.jobs[0].state,'reconciliation_required');
});

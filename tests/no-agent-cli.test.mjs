import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readdir} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {serve} from '../dist/server.js';
const exec=promisify(execFile);
const retired=[['worker'],['agent-check','old-job','--smoke'],['doctor','--background'],['serve','--worker'],['build','old-project','--export','--background','Make a clip']];
test('retired agent entrypoints refuse before configuration, job claims or runtime installation',async t=>{
 const home=await mkdtemp(path.join(os.tmpdir(),'acq-no-agent-'));
 t.after(()=>rm(home,{recursive:true,force:true}));
 for(const args of retired){
  for(const [binary,prefix] of [[process.execPath,[path.resolve('dist/cli.js')]],['python3',[path.resolve('scripts/acq_edit.py')]],['python3',[path.resolve('scripts/acq_edit.py'),'--engine','premiere']]]){
   await assert.rejects(exec(binary,[...prefix,...args],{env:{...process.env,HOME:home,ACQ_EDIT_HOME:path.join(home,'config')}}),error=>{
    assert.match(error.stderr,/Separate agent CLI execution has been removed/);
    assert.match(error.stderr,/existing chat/);
    return true;
   });
   assert.deepEqual(await readdir(home),[],'No runtime, credentials or job state may be created');
  }
 }
});
test('help no longer advertises nested agent setup or execution',async()=>{
 const {stdout}=await exec(process.execPath,[path.resolve('dist/cli.js'),'--help']);
 assert.doesNotMatch(stdout,/agent-check|--background|--worker|\nworker\n/);
 assert.match(stdout,/session-start/);
});
test('review server rejects the retired worker mode before opening a server',()=>{
 let executed=false;
 assert.throws(()=>serve({}, {},true,async()=>{executed=true}),/Separate agent CLI execution has been removed/);
 assert.equal(executed,false);
});

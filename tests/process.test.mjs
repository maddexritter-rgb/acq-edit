import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {run} from '../dist/process.js';
test('native process runner captures success and nonzero diagnostics',async()=>{
 assert.equal(await run(process.execPath,['-e',"process.stdout.write('ok')"]),'ok');
 await assert.rejects(run(process.execPath,['-e',"console.error('native failure');process.exit(2)"]),/exited 2: native failure/);
});
test('native runner waits for kill escalation after a ready child ignores termination',async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-process-ready-'));t.after(()=>rm(root,{recursive:true,force:true}));
 const ready=path.join(root,'ready'),controller=new AbortController();let pid;
 const pending=run(process.execPath,['-e',"process.on('SIGTERM',()=>{});require('fs').writeFileSync(process.argv[1],'ready');setInterval(()=>{},1000)",ready],{timeout:10000,signal:controller.signal,shutdownGraceMs:100,onSpawn:value=>pid=value});
 const rejected=assert.rejects(pending,/interrupted/);
 try{
  const deadline=Date.now()+8000;
  while(await readFile(ready,'utf8').catch(e=>{if(e.code==='ENOENT')return '';throw e})!=='ready'){
   assert(Date.now()<deadline,'child installed its termination handler');await delay(10);
  }
  const started=Date.now();controller.abort();await rejected;
  assert.ok(Date.now()-started>=90,'waited for kill escalation after the child was ready');
  assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});
 }finally{controller.abort();await rejected}
});
test('native timeout does not release a live owned process',async()=>{
 let pid;
 await assert.rejects(run(process.execPath,['-e','setInterval(()=>{},1000)'],{timeout:150,shutdownGraceMs:100,onSpawn:value=>pid=value}),/timed out/);
 assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});
});
test('native runner bounds output and handles spawn failure',async()=>{
 await assert.rejects(run(process.execPath,['-e',"process.stdout.write('x'.repeat(10000));setInterval(()=>{},1000)"],{outputLimit:1000,shutdownGraceMs:50}),/output limit/);
 await assert.rejects(run('/missing-acq-executable',[]),/ENOENT/);
});
test('owned child identity is recorded and persistence failure stops it before returning',async()=>{
 let pid;
 await assert.rejects(run(process.execPath,['-e','setInterval(()=>{},1000)'],{onSpawn:value=>{pid=value;throw Error('identity write failed')},shutdownGraceMs:50}),/identity write failed/);
 assert(Number.isSafeInteger(pid));assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});
});

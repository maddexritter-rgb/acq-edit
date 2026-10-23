import test from 'node:test';
import assert from 'node:assert/strict';
import {run} from '../dist/process.js';
test('native process runner captures success and nonzero diagnostics',async()=>{
 assert.equal(await run(process.execPath,['-e',"process.stdout.write('ok')"]),'ok');
 await assert.rejects(run(process.execPath,['-e',"console.error('native failure');process.exit(2)"]),/exited 2: native failure/);
});
test('native runner kills an uncooperative operation before timeout rejection',async()=>{
 const started=Date.now();
 await assert.rejects(run(process.execPath,['-e',"process.on('SIGTERM',()=>{});setInterval(()=>{},1000)"],{timeout:150,shutdownGraceMs:100}),/timed out/);
 assert.ok(Date.now()-started>=240,'waited for kill escalation, not only initial timeout');
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

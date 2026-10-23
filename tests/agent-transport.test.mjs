import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {runAgentTransport} from '../dist/agent-transport.js';
const script=fileURLToPath(new URL('./fixtures/agent-process.mjs',import.meta.url));
function opts(scenario,extra={}){return{agent:scenario.startsWith('claude')?'claude':'codex',command:process.execPath,args:[script],cwd:os.tmpdir(),env:{...process.env,SCENARIO:scenario},prompt:'Fixture only',writableRoots:[],onSession:()=>{},onLine:async()=>{},timeoutMs:2000,shutdownGraceMs:50,...extra}}
for(const scenario of ['success','early','claude-success'])test(`agent transport verifies ${scenario} completion and flushes logs`,async()=>{
 const logs=[],sessions=[];await runAgentTransport(opts(scenario,{onSession:id=>sessions.push(id),onLine:async line=>{await new Promise(r=>setTimeout(r,5));logs.push(line)}}));
 assert.ok(logs.some(l=>l.includes(scenario==='claude-success'?'"result"':'turn/completed')));assert.ok(sessions.length);
});
for(const [scenario,message] of [['claude-missing','without a completion result'],['claude-error','Fixture failure'],['claude-credit','Credit balance is too low'],['claude-malformed','Invalid agent event'],['disconnect','disconnected'],['turn-failed','turn failed'],['approval','interactive input'],['wrong-turn','deadline exceeded']])test(`agent transport rejects ${scenario}`,async()=>{
 await assert.rejects(runAgentTransport(opts(scenario,{timeoutMs:scenario==='wrong-turn'?150:2000})),new RegExp(message));
});
test('resuming Codex requires the exact requested session',async()=>{await assert.rejects(runAgentTransport(opts('wrong-session',{session:'requested'})),/different or missing session/)});
test('log failure stops execution instead of reporting completion',async()=>{await assert.rejects(runAgentTransport(opts('claude-log-failure',{onLine:async()=>{throw Error('disk full')}})),/disk full/)});
test('abort waits for termination of an uncooperative owned process',async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-agent-'));t.after(()=>rm(root,{recursive:true,force:true}));const pidFile=path.join(root,'pid');
 const controller=new AbortController();const promise=runAgentTransport(opts('hang',{signal:controller.signal,env:{...process.env,SCENARIO:'hang',PID_FILE:pidFile}}));
 const rejected=assert.rejects(promise,/interrupted/);let pid;
 for(let n=0;n<50;n++){try{pid=Number(await readFile(pidFile,'utf8'));break}catch{await new Promise(r=>setTimeout(r,10))}}
 assert.ok(pid);controller.abort();await rejected;assert.throws(()=>process.kill(pid,0),{code:'ESRCH'});
});

test('Claude resume requires the exact session',async()=>{await assert.rejects(runAgentTransport(opts('claude-success',{session:'different'})),/different session/)});

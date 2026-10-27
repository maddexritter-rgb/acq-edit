import test from 'node:test';
import assert from 'node:assert/strict';
import {agentReadiness} from '../dist/agent-readiness.js';
const config={agent:'claude',agentCommand:'/selected/claude'};
const stub=(version='2.1.312',auth={loggedIn:true,email:'private-account'})=>async(c,a)=>a[0]==='--version'?`${version} (Claude Code)`:JSON.stringify(auth);
test('Claude readiness checks selected executable without returning account data',async()=>{
 const calls=[];const r=await agentReadiness(config,'claude',async(c,a,o)=>{calls.push([c,a,o]);return stub()(c,a)}, {},'/project');
 assert(r.ready);assert(!JSON.stringify(r).includes('private-account'));assert(calls.every(x=>x[0]==='/selected/claude'&&x[2].cwd==='/project'));
 assert.deepEqual(calls[1][1],['auth','status']);
});
test('old, missing, malformed and signed-out CLI cannot pass readiness',async()=>{
 for(const exec of [stub('2.1.195'),stub('2.1.312',{loggedIn:false}),async()=>{throw Error('private token')},stub('garbage'),async(c,a)=>a[0]==='--version'?'2.1.312':'not JSON']){
  const r=await agentReadiness(config,'claude',exec);assert(!r.ready);assert(!JSON.stringify(r).includes('private token'));
 }
});
test('minimum version is only a baseline, not model or permission qualification',async()=>{
 for(const v of ['2.1.251','2.2.0','3.0.0']){const r=await agentReadiness(config,'claude',stub(v));assert(r.ready);assert(r.unverified.length);}
});

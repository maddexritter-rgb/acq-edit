import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,writeFile} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {smokeAgent} from '../dist/agent-smoke.js';
const ready=async()=>({ready:true,agent:'claude',version:'2.1.312',authenticated:true,problems:[],unverified:[],qualification:'fixture'});
for(const kind of ['success','denied','missing-proof','no-tools','throw'])test(`project smoke verifies ${kind} with no permission changes`,async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-smoke-'));t.after(()=>rm(root,{recursive:true,force:true}));
 const result=await smokeAgent({agent:'claude',python:'/fixture/python'},{id:'p',agent:'claude',root},async o=>{
  assert.equal(o.cwd,root);assert(!o.args.some(x=>/allowedTools|skip-permissions/.test(x)));assert.equal(o.env.ASSEMBLYAI_API_KEY,undefined);
  if(kind==='throw')throw Error('private-key');
  const commands=JSON.parse(o.prompt.match(/Bash commands: (\[.*?\])\./)[1]);
  if(kind!=='no-tools')for(const [i,command] of commands.entries()){
   await o.onLine(JSON.stringify({message:{content:[{type:'tool_use',id:String(i),name:'Bash',input:{command}}]}}));
   await o.onLine(JSON.stringify({message:{content:[{type:'tool_result',tool_use_id:String(i),is_error:kind==='denied'}]}}));
  }
  if(kind!=='missing-proof'){const match=o.prompt.match(/create (.+) containing exactly ([\w-]+)/);await writeFile(match[1],match[2]);}
 },ready);
 assert.equal(result.ready,kind==='success');assert(!JSON.stringify(result).includes('private-key'));
});

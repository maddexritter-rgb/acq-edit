import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readdir,readFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {doctor} from '../dist/doctor.js';
const config=backend=>({backend,agent:'codex',python:'/fixture/python',resolvePython:'/fixture/ResolvePython',filmcraft:'/fixture/filmcraft',premiereProfile:'/fixture/profile.json',storageRoot:'/fixture/projects',port:4317});
function harness(backend,overrides={}){
 const calls=[];
 const execute=async(command,args,options)=>{
  calls.push({command,args,options});
  if(args.includes('--version')||args.includes('-version'))return 'Fixture 1.0\n';
  if(args[0].endsWith('materialize.py'))return JSON.stringify({ready:true,verifiedFiles:683,routedEntrypoints:38});
  if(args[0].endsWith('check_youtube.py'))return JSON.stringify({ready:true});
  if(args[0].endsWith('check_framing_dependencies.py'))return JSON.stringify({ready:true});
  if(args[0].endsWith('asset_bundle.py'))return JSON.stringify({ready:true,version:'fixture'});
  if(args[0].endsWith('brain_receipts.py'))return JSON.stringify({ready:true,remoteAccess:'not-checked'});
  if(args[0].endsWith('native.py'))return JSON.stringify(backend==='filmcraft'?{backend,binaryPresent:true}:backend==='resolve'?{backend,studio:true,connected:true}:{backend,ready:true});
  if(command==='/fixture/filmcraft'&&args[0]==='--help')return 'FilmCraft help';
  throw Error('Unexpected command');
 };
 return {calls,base:execute,tools:{execute,platform:'darwin',node:'v24.1.0',env:{},secrets:async()=>({ASSEMBLYAI_API_KEY:'fixture-aai',GEMINI_API_KEY:'fixture-gemini'}),storage:async()=>{},...overrides}};
}
test('doctor checks only the selected engine and distinguishes local readiness from acceptance',async()=>{
 for(const backend of ['filmcraft','resolve','premiere']){
  const h=harness(backend),report=await doctor(config(backend),h.tools);
  assert.equal(report.readiness.ready,true);assert.equal(report.brain.remoteAccess,'not-checked');assert(report.readiness.unverified.some(x=>x.includes('authentication')));
  const native=h.calls.filter(c=>c.args[0].endsWith('native.py'));assert.equal(native.length,1);assert(native[0].args.includes(backend));assert.equal(native[0].command,backend==='resolve'?'/fixture/ResolvePython':'/fixture/python');
  assert.equal(h.calls.some(c=>c.command==='/fixture/filmcraft'),backend==='filmcraft');
  assert(h.calls.every(c=>c.options.env.PYTHONDONTWRITEBYTECODE==='1'));
  assert(!JSON.stringify(report).includes('fixture-aai'));assert(!JSON.stringify(report).includes('fixture-gemini'));
 }
});
test('optional URL tools do not block local editing',async()=>{
 const h=harness('resolve');h.tools.execute=async(command,...rest)=>{if([path.resolve('.local/venv/bin/yt-dlp'),'rclone'].includes(command))throw Error('absent');return h.base(command,...rest)};
 const report=await doctor(config('resolve'),h.tools);assert.equal(report.readiness.ready,true);assert.deepEqual(report.readiness.optional.map(x=>x.check),['youtube','drive']);
});
test('doctor reports all missing prerequisites without launching native or brain code from a bad runtime',async()=>{
 const h=harness('resolve',{platform:'linux',node:'v22.0.0',secrets:async()=>({}),storage:async()=>{throw Error('unmounted')}});
 h.tools.execute=async(command,args,options)=>{if(command==='ffmpeg'||args[0].endsWith('materialize.py'))throw Error('private diagnostic fixture-secret');return h.base(command,args,options)};
 const report=await doctor(config('resolve'),h.tools),ids=report.readiness.blocking.map(x=>x.check);
 for(const id of ['platform','node','storage','ffmpeg','assemblyAI','gemini','skills','brain','native'])assert(ids.includes(id),id);
 assert.equal(report.readiness.ready,false);assert(!h.calls.some(c=>/native.py|brain_receipts.py/.test(c.args[0])));assert(!JSON.stringify(report).includes('fixture-secret'));
});
test('unreadable credentials, invalid brain and disconnected native checks are actionable',async()=>{
 const h=harness('premiere',{secrets:async()=>{throw Error('private invalid credential value')}});
 h.tools.execute=async(command,args,options)=>args[0].endsWith('native.py')?JSON.stringify({backend:'premiere',ready:false,connectionError:'private connector token'}):h.base(command,args,options);
 const report=await doctor(config('premiere'),h.tools);assert.equal(report.readiness.ready,false);
 for(const id of ['credentials-file','brain','native'])assert(report.readiness.blocking.some(x=>x.check===id&&x.repair));
 assert(!JSON.stringify(report).includes('private invalid credential value'));assert(!JSON.stringify(report).includes('private connector token'));
});
test('brain readiness and a present but unusable FilmCraft executable cannot pass',async()=>{
 const h=harness('filmcraft');h.tools.execute=async(command,args,options)=>{
  if(args[0].endsWith('brain_receipts.py'))return JSON.stringify({ready:false});
  if(command==='/fixture/filmcraft')throw Error('not executable');
  return h.base(command,args,options);
 };
 const report=await doctor(config('filmcraft'),h.tools);assert.equal(report.readiness.ready,false);assert.equal(report.native.checked,true);
 assert.deepEqual(report.readiness.blocking.map(x=>x.check),['brain','native']);
});
test('real doctor CLI returns nonzero with JSON and creates no state database or configuration writes',async t=>{
 const base=await mkdtemp(path.join(os.tmpdir(),'acq-doctor-'));t.after(()=>rm(base,{recursive:true,force:true}));
 const home=path.join(base,'home');await mkdir(home);const c={...config('resolve'),python:path.join(base,'missing-python'),agentCommand:path.join(base,'missing-agent'),storageRoot:base};
 const file=path.join(home,'config.json'),content=JSON.stringify(c);await writeFile(file,content);
 const env={...process.env,ACQ_EDIT_HOME:home,ASSEMBLYAI_API_KEY:'',GEMINI_API_KEY:'',EDITORIAL_BRAIN_READ_KEY:''};
 let result;try{await promisify(execFile)(process.execPath,['dist/cli.js','doctor'],{cwd:path.resolve('.'),env});assert.fail('Expected nonzero readiness exit')}catch(error){result=error}
 assert.equal(result.code,1);const report=JSON.parse(result.stdout);assert.equal(report.readiness.ready,false);assert.equal(report.native.checked,false);
 assert.deepEqual(await readdir(home),['config.json']);assert.equal(await readFile(file,'utf8'),content);
});
test('doctor before setup gives a repair without creating its configuration folder',async t=>{
 const base=await mkdtemp(path.join(os.tmpdir(),'acq-doctor-unconfigured-'));t.after(()=>rm(base,{recursive:true,force:true}));
 const home=path.join(base,'not-created');
 await assert.rejects(promisify(execFile)(process.execPath,['dist/cli.js','doctor'],{cwd:path.resolve('.'),env:{...process.env,ACQ_EDIT_HOME:home}}),error=>{
  assert.equal(error.code,1);const report=JSON.parse(error.stdout);assert.equal(report.readiness.blocking[0].check,'configuration');assert.match(report.readiness.blocking[0].repair,/setup/);return true;
 });
 assert.deepEqual(await readdir(base),[]);
});

test('missing framing runtime blocks readiness without leaking child diagnostics',async()=>{
 const h=harness('filmcraft');
 h.tools.execute=async(command,args,options)=>{
  if(args[0].endsWith('check_youtube.py'))return JSON.stringify({ready:true});
  if(args[0].endsWith('check_framing_dependencies.py'))throw Error('private diagnostic fixture-secret');
  return h.base(command,args,options);
 };
 const report=await doctor(config('filmcraft'),h.tools);
 assert.equal(report.readiness.ready,false);
 assert(report.readiness.blocking.some(x=>x.check==='framing'));
 assert(!JSON.stringify(report).includes('fixture-secret'));
});

test('normal doctor never probes a missing or signed-out agent; background diagnostics are explicit',async()=>{
 const h=harness('filmcraft'),c={...config('filmcraft'),agent:'claude',agentCommand:'/missing/claude'};
 h.tools.execute=async(command,...rest)=>{if(command===c.agentCommand)throw Error('not installed');return h.base(command,...rest)};
 const normal=await doctor(c,h.tools);assert.equal(normal.readiness.ready,true);assert.equal(normal.dependencies.agent,undefined);assert.equal(normal.agentReadiness,undefined);
 const background=await doctor(c,{...h.tools,background:true});assert.equal(background.readiness.ready,false);assert(background.readiness.blocking.some(x=>x.check==='agent'));
 assert(!h.calls.some(x=>x.command===c.agentCommand));
});

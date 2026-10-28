import test from 'node:test';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,readdir,stat,symlink,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {readSetup,collectSetup,saveSetup} from '../dist/setup.js';
import {agentExecutable} from '../dist/config.js';
import {Store} from '../dist/store.js';
import {serviceLock} from '../dist/lock.js';
async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-setup-'));t.after(()=>rm(root,{recursive:true,force:true}));
 return {root,home:path.join(root,'home'),toolkit:path.join(root,'checkout with spaces'),userHome:path.join(root,'user')};
}
const initial=f=>({backend:'filmcraft',agent:'codex',storageRoot:path.join(f.root,'stored projects'),python:path.join(f.root,'shared python'),port:17891,filmcraft:path.join(f.root,'custom-filmcraft'),premiereProfile:path.join(f.root,'other-profile.json'),brainConfig:path.join(f.root,'brain'),agentTimeoutMs:123456,customProfile:{keep:true}});
async function existing(f,c){await mkdir(f.home,{recursive:true});const text=JSON.stringify(c,null,4)+'\n';await writeFile(path.join(f.home,'config.json'),text,{mode:0o600});return text;}
test('fresh setup defaults to the chosen integration and expands user paths without installing anything',async t=>{
 for(const backend of ['filmcraft','resolve','premiere']){
  const f=await fixture(t),prompts=[];
  const c=await collectSetup(await readSetup(f.home),[backend,'codex'],async prompt=>{prompts.push(prompt);return prompt.startsWith('Project storage')?'~/footage projects':''},f.toolkit,f.userHome);
  assert.equal(c.storageRoot,path.join(f.userHome,'footage projects'));assert.equal(c.python,path.join(f.toolkit,'.local/venv/bin/python'));
  assert.equal(c.backend,backend);assert.equal(c.port,4317);assert.equal(c.agentCommands,undefined);
  if(backend==='filmcraft')assert.equal(c.filmcraft,path.join(f.toolkit,'.local/filmcraft/target/release/filmcraft-cli'));
  if(backend==='premiere')assert.equal(c.premiereProfile,path.join(f.toolkit,'.local/premiere-profile.json'));
  assert.equal(prompts.filter(p=>/FilmCraft CLI|Toolkit Premiere|Resolve Python/.test(p)).length,1);
  const result=await saveSetup(f.home,{text:null,config:null},c);assert(result.changed);assert.equal(result.backup,null);
  assert.equal((await stat(path.join(f.home,'config.json'))).mode&0o777,0o600);assert.deepEqual(await readdir(f.home),['config.json']);
  await assert.rejects(stat(f.toolkit),{code:'ENOENT'});
 }
});
test('blank rerun preserves settings, unknown fields and credentials without rewriting the file',async t=>{
 const f=await fixture(t),c=initial(f),text=await existing(f,c);const credential=path.join(f.home,'credentials.json');await writeFile(credential,'{"fixture":"keep"}');
 const file=path.join(f.home,'config.json'),before=await stat(file),snapshot=await readSetup(f.home);
 const result=await collectSetup(snapshot,[],async()=>'',f.toolkit,f.userHome);assert.deepEqual(result,c);
 assert.deepEqual(await saveSetup(f.home,snapshot,result),{changed:false,backup:null});assert.equal(await readFile(file,'utf8'),text);assert.equal((await stat(file)).mtimeMs,before.mtimeMs);assert.equal(await readFile(credential,'utf8'),'{"fixture":"keep"}');
 assert.deepEqual((await readdir(f.home)).sort(),['config.json','credentials.json']);
});
test('changing defaults preserves engine paths, custom agent routing and exact prior configuration',async t=>{
 const f=await fixture(t),old={...initial(f),agentCommand:'/custom/codex'},text=await existing(f,old),snapshot=await readSetup(f.home);
 const next=await collectSetup(snapshot,['resolve','claude'],async()=>'',f.toolkit,f.userHome);
 assert.equal(next.filmcraft,old.filmcraft);assert.equal(next.premiereProfile,old.premiereProfile);assert.equal(next.agentTimeoutMs,old.agentTimeoutMs);assert.equal(next.port,old.port);assert.deepEqual(next.customProfile,old.customProfile);
 assert.equal(agentExecutable(next,'codex'),'/custom/codex');assert.equal(agentExecutable(next,'claude'),'claude');assert.equal(next.agentCommand,undefined);
 const saved=await saveSetup(f.home,snapshot,next);assert.equal(await readFile(saved.backup,'utf8'),text);assert.equal((await stat(saved.backup)).mode&0o777,0o600);
 assert.equal((await readSetup(f.home)).config.backend,'resolve');
 // Defaults cannot rewrite the identity of a stored project.
 const store=new Store(path.join(f.home,'state.sqlite'));const p={id:'old',root:f.root,title:'Existing',backend:'filmcraft',agent:'codex',createdAt:''};store.addProject(p);store.close();
 const current=await readSetup(f.home);await saveSetup(f.home,current,{...next,port:17901});const reopened=new Store(path.join(f.home,'state.sqlite'));assert.deepEqual(reopened.project('old'),p);reopened.close();
});
test('normal setup preserves optional agent commands without asking for a second CLI',async t=>{
 const f=await fixture(t),old={...initial(f),agentCommand:'/custom/codex',agentCommands:{claude:'/custom/claude'}};await existing(f,old);
 assert.equal(agentExecutable(old,'claude'),'/custom/claude');assert.equal(agentExecutable({...old,agentCommands:undefined},'claude'),'claude');
 const c=await collectSetup(await readSetup(f.home),['resolve','claude'],async q=>{assert(!q.startsWith('Agent executable'));return ''},f.toolkit,f.userHome);
 assert.equal(agentExecutable(c,'codex'),'/custom/codex');assert.equal(agentExecutable(c,'claude'),'/custom/claude');
});
test('cancelled prompts, malformed configuration and symlinks preserve existing files',async t=>{
 const f=await fixture(t);let questions=0;
 await assert.rejects(collectSetup({text:null,config:null},['resolve','codex'],async()=>{if(++questions===2)throw Error('cancelled');return ''},f.toolkit,f.userHome),/cancelled/);assert.deepEqual(await readdir(f.root),[]);
 await mkdir(f.home);const file=path.join(f.home,'config.json');await writeFile(file,'{broken');await assert.rejects(readSetup(f.home),/invalid JSON/);assert.equal(await readFile(file,'utf8'),'{broken');
 const other=path.join(f.root,'symlink-home');await mkdir(other);await symlink(file,path.join(other,'config.json'));await assert.rejects(readSetup(other),/regular file/);assert.equal(await readFile(file,'utf8'),'{broken');
});
test('concurrent configuration changes and an active service refuse setup without backups or overwritten values',async t=>{
 const f=await fixture(t),c=initial(f);await existing(f,c);const old=await readSetup(f.home),changed={...c,port:17902};await writeFile(path.join(f.home,'config.json'),JSON.stringify(changed));
 await assert.rejects(saveSetup(f.home,old,{...c,port:17903}),/changed while setup/);assert.deepEqual((await readSetup(f.home)).config,changed);assert.deepEqual(await readdir(f.home),['config.json']);
 const release=await serviceLock(f.home);try{await assert.rejects(saveSetup(f.home,await readSetup(f.home),c),/service is already running/)}finally{await release()}
 assert.deepEqual((await readSetup(f.home)).config,changed);assert.deepEqual(await readdir(f.home),['config.json']);
});
test('unsettled native operations and editing jobs must be reconciled before setup changes',async t=>{
 const f=await fixture(t),c=initial(f),text=await existing(f,c);const store=new Store(path.join(f.home,'state.sqlite'));store.addProject({id:'p',root:f.root,title:'Fixture',backend:'filmcraft',agent:'codex',createdAt:''});
 const job=store.enqueueBuild('p','fixture');store.claim();
 await assert.rejects(saveSetup(f.home,await readSetup(f.home),{...c,port:17903}),/Editing jobs/);assert.equal(await readFile(path.join(f.home,'config.json'),'utf8'),text);store.setJob(job.id,'failed');
 store.db.prepare('INSERT INTO native_operations VALUES (?,?,?,?)').run('op','p','reconciliation_required','{}');
 await assert.rejects(saveSetup(f.home,await readSetup(f.home),{...c,port:17903}),/Native operations/);assert.equal(await readFile(path.join(f.home,'config.json'),'utf8'),text);store.close();
});

test('EOF during real setup exits unsuccessfully without saving partial answers',async t=>{
 const f=await fixture(t),text=await existing(f,initial(f));
 const child=spawn(process.execPath,['dist/cli.js','setup','resolve','codex'],{cwd:path.resolve('.'),env:{...process.env,ACQ_EDIT_HOME:f.home},stdio:['pipe','pipe','pipe']});let stderr='';
 const timer=setTimeout(()=>child.kill('SIGTERM'),5000);t.after(()=>clearTimeout(timer));
 child.stdout.once('data',()=>child.stdin.end());child.stderr.on('data',b=>stderr+=b);
 const code=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',resolve)});
 assert.equal(code,1,stderr);assert.match(stderr,/aborted|cancelled/);assert.equal(await readFile(path.join(f.home,'config.json'),'utf8'),text);assert.deepEqual(await readdir(f.home),['config.json']);
});

test('noninteractive setup uses gathered choices and preserves previous project storage',async()=>{
 const {collectNoninteractiveSetup}=await import('../dist/setup.js');
 const before={backend:'premiere',agent:'codex',python:'/prior/.local/venv/bin/python',premiereProfile:'/prior/.local/premiere-profile.json',storageRoot:'/projects',port:4317};
 const old=process.env.ACQ_EDIT_PREVIOUS_RUNTIME;process.env.ACQ_EDIT_PREVIOUS_RUNTIME='/prior';
 try{
  const c=await collectNoninteractiveSetup({text:JSON.stringify(before),config:before},['premiere','claude','--non-interactive'],'/new','/user');
  assert.equal(c.storageRoot,'/projects');assert.equal(c.python,'/new/.local/venv/bin/python');assert.equal(c.premiereProfile,'/new/.local/premiere-profile.json');assert.equal(c.agent,'claude');assert.equal(before.python,'/prior/.local/venv/bin/python');
  await assert.rejects(collectNoninteractiveSetup({text:null,config:null},['premiere','--non-interactive'],'/new'),/backend and agent/);
 }finally{if(old===undefined)delete process.env.ACQ_EDIT_PREVIOUS_RUNTIME;else process.env.ACQ_EDIT_PREVIOUS_RUNTIME=old;}
});

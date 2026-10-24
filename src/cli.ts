#!/usr/bin/env node
import {doctor} from './doctor.js';
import {executeNative,reconcileNative,reconcileJob} from './native-operations.js';
import {importDriveFolder,resumeDriveBatch,abandonDriveBatch} from './drive-batch.js';
import path from 'node:path';
import os from 'node:os';
import { createInterface } from 'node:readline/promises';
import { mkdir,writeFile,access } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { Store } from './store.js';
import { config,saveConfig,HOME,ROOT,secretEnv,type Config } from './config.js';
import { backend,invariant,type NativeAction } from './contracts.js';
import { createProject,importLocal,importUrl,exportState } from './projects.js';
import { atomicJson,readJson,containedFile } from './files.js';
import { serve } from './server.js';
import { publish } from './publish.js';
import { run } from './process.js';
import {recoverIntake,abandonIntake,type IntakeTools} from './intake.js';
import { serviceLock } from './lock.js';
import { workOne } from './worker.js';
const [command,...args]=process.argv.slice(2);const output=(x:unknown)=>console.log(JSON.stringify(x,null,2));
async function interruptibleCommand(work:(tools:IntakeTools)=>Promise<unknown>){const controller=new AbortController();const stop=()=>controller.abort();process.on('SIGINT',stop);process.on('SIGTERM',stop);try{output(await work({signal:controller.signal}))}finally{process.off('SIGINT',stop);process.off('SIGTERM',stop)}}
async function main(){
 if(command==='setup'){
  const rl=createInterface({input:process.stdin,output:process.stdout});try{
   const engine=backend(args[0]||await rl.question('Backend (filmcraft / premiere / resolve): '));
   const agent=args[1]||await rl.question('Agent (codex / claude): ');invariant(agent==='codex'||agent==='claude','Choose codex or claude');
   const storageRoot=path.resolve(await rl.question(`Project storage root [${path.join(os.homedir(),'Movies','ACQ Edit')}]: `)||path.join(os.homedir(),'Movies','ACQ Edit'));
   const c:Config={backend:engine,agent,storageRoot,python:path.join(ROOT,'.local','venv','bin','python'),port:4317};
   if(engine==='filmcraft')c.filmcraft=await rl.question('FilmCraft CLI absolute path (or run scripts/install_engine.py filmcraft first): ');
   if(engine==='premiere')c.premiereProfile=await rl.question('Toolkit Premiere Agent profile absolute path: ');
   if(engine==='resolve')c.resolvePython='/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython';
   c.brainConfig=await rl.question('Editorial brain configuration directory (context.json + restricted read_token): ');
   await mkdir(storageRoot,{recursive:true});await saveConfig(c);
   console.log('Configuration saved. Run credentials to enter API keys privately, then doctor. No global skills or editor settings were changed.');
  }finally{rl.close()}return;
 }
 if(command==='credentials'){const {spawn}=await import('node:child_process');await new Promise<void>((resolve,reject)=>{const child=spawn('python3',[path.join(ROOT,'scripts','credentials.py'),HOME],{stdio:'inherit'});child.on('error',reject);child.on('close',code=>code===0?resolve():reject(new Error('Credential entry failed')))});return}
 if(command==='help'||!command){console.log(`ACQ Edit\nsetup [backend] [agent]\ncredentials\ndoctor\nproject <title>\nprojects\nopen <project-id>\nsource <project-id> <file>\nyoutube <project-id> <url>\ndrive <project-id> <url> [rclone-remote]\ndrive-folder <project-id> <folder-url> [rclone-remote]\ndrive-batches <project-id>\ndrive-resume <batch-id> [--retry-failed]\ndrive-abandon <batch-id> <evidence.json>\nnative-operations <project-id>\nnative-reconcile <operation-id> <evidence.json>\nintakes <project-id>\nintake-abandon <intake-id> <evidence.json>\nintake-recover <intake-id>\nbrain <project-id> <request.json>\nbuild <project-id> <request>\nclip <project-id> <title>\npublish <project-id> <render-receipt.json>\nserve [--no-worker]\nworker\nreconcile <job-id> <ready|failed> <evidence-path>\nnative <project-id> <compile|captions|hooks|reference|inspect|open|build|revise|render> <packet.json>\n`);return}
 if(command==='doctor'){
  try{const checks=await doctor(await config());output(checks);if(!checks.readiness.ready)process.exitCode=1;}
  catch{output({readiness:{ready:false,blocking:[{check:'configuration',repair:'Run setup to create a valid readable toolkit configuration, then rerun doctor.'}],optional:[],qualification:'Local prerequisite checks only; configuration could not be inspected.'}});process.exitCode=1;}
  return;
 }
 const c=await config();const store=new Store(path.join(HOME,'state.sqlite'));
 if(command==='serve'){
  const release=await serviceLock(HOME);store.recover();const room=serve(store,c,!args.includes('--no-worker'));room.server.listen(c.port,'127.0.0.1',()=>console.log(`Review room: http://127.0.0.1:${c.port}/session?token=${room.token}`));
  let stopping=false;const stop=()=>{if(stopping)return;stopping=true;void room.stop().then(()=>{store.close();return release()}).then(()=>process.exit(0)).catch(e=>{console.error(e.message);process.exitCode=1})};room.server.on('error',e=>{console.error(e.message);void release().finally(()=>process.exit(1))});process.on('SIGINT',stop);process.on('SIGTERM',stop);return;
 }
 if(command==='worker'){
  const release=await serviceLock(HOME),controller=new AbortController();
  const stop=()=>controller.abort();process.on('SIGINT',stop);process.on('SIGTERM',stop);
  try{store.recover();output({worked:await workOne(store,c,controller.signal)})}
  finally{process.off('SIGINT',stop);process.off('SIGTERM',stop);store.close();await release()}
  return;
 }
 try{
 switch(command){
 case 'project':invariant(args[0],'Project title required');output(await createProject(store,c.storageRoot,args.join(' '),c.backend,c.agent));break;
 case 'projects':output(store.projects());break;
 case 'open':output(await exportState(store,args[0]!));console.log('Run acq-edit serve to reopen the review room.');break;
 case 'brain':{
  const p=store.project(args[0]!);invariant(args[1],'Brain request JSON required');const request=await containedFile(p.root,path.resolve(args[1]!));
  const jobId=process.env.ACQ_EDIT_JOB_ID;if(jobId){const j=store.job(jobId);invariant(j.projectId===p.id&&['editing','rendering'].includes(j.state),'Brain request belongs to another or inactive job');}
  const result=JSON.parse(await run(c.python,[path.join(ROOT,'python','brain_receipts.py'),'--project',path.join(p.root,'project.json'),'--config',path.join(HOME,'config.json'),'--request',request],{timeout:60000,env:{...process.env,...await secretEnv()}}));
  store.event(p.id,{type:'brain.retrieved',...(jobId?{jobId}:{}),receiptPath:result.receiptPath,sha256:result.sha256,responseSha256:result.responseSha256,versionsPath:result.versionsPath,versionsSha256:result.versionsSha256});await exportState(store,p.id);output(result);break;
 }
 case 'drive-folder':await interruptibleCommand(tools=>importDriveFolder(store,args[0]!,args[1]!,args[2],tools));break;
 case 'drive-batches':output(store.driveBatches(args[0]!));break;
 case 'drive-resume':invariant(!args[1]||args[1]==='--retry-failed','Use --retry-failed to start new attempts for terminal failed files');await interruptibleCommand(tools=>resumeDriveBatch(store,args[0]!,tools,args[1]==='--retry-failed'));break;
 case 'drive-abandon':invariant(args[1],'Process-inspection evidence path required');output(await abandonDriveBatch(store,args[0]!,path.resolve(args[1])));break;
 case 'intakes':output(store.intakes(args[0]!));break;
 case 'intake-abandon':invariant(args[1],'Process-inspection evidence path required');output(await abandonIntake(store,args[0]!,path.resolve(args[1])));break;
 case 'intake-recover':await interruptibleCommand(tools=>recoverIntake(store,args[0]!,tools));break;
 case 'source':await interruptibleCommand(tools=>importLocal(store,args[0]!,args[1]!,'local',tools));break;
 case 'youtube':case 'drive':await interruptibleCommand(tools=>importUrl(store,args[0]!,args[1]!,command,args[2],tools));break;
 case 'build':output(store.enqueueBuild(args[0]!,args.slice(1).join(' ')));break;
 case 'clip':{store.project(args[0]!);const clip={id:randomUUID(),projectId:args[0]!,number:store.clips(args[0]!).length+1,title:args.slice(1).join(' '),currentVersionId:null};invariant(clip.title,'Title required');store.addClip(clip);output(clip);break}
 case 'publish':output(await publish(store,args[0]!,path.resolve(args[1]!)));break;
 case 'reconcile':invariant(args[1]==='failed'||args[1]==='ready','Choose ready or failed after native inspection');invariant(args[2],'Evidence path required');output(await reconcileJob(store,args[0]!,args[1],path.resolve(args[2]!)));break;
 case 'native-operations':output(store.nativeOperations(args[0]!));break;
 case 'native-reconcile':invariant(args[1],'Process and native inspection evidence required');output(await reconcileNative(store,args[0]!,path.resolve(args[1]!),{config:c}));break;
 case 'native':invariant(['compile','captions','hooks','reference','inspect','open','build','revise','render'].includes(args[1]!),'Unknown native operation');invariant(args[2],'Native packet required');await interruptibleCommand(tools=>executeNative(store,c,args[0]!,args[1] as NativeAction,path.resolve(args[2]!),tools));break;
 default:throw Error('Unknown command. Run acq-edit help');
 }
 }finally{store.close()}
}
main().catch(e=>{console.error('ACQ Edit:',e.message);process.exitCode=1});

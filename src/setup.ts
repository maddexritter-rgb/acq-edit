import os from 'node:os';
import path from 'node:path';
import {mkdir,readFile,writeFile,lstat,chmod} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {type Config} from './config.js';
import {backend,invariant} from './contracts.js';
import {atomicJson} from './files.js';
import {serviceLock} from './lock.js';

type Question=(prompt:string)=>Promise<string>;
export interface SetupSnapshot {text:string|null;config:Config|null}
export async function readSetup(home:string):Promise<SetupSnapshot>{
 const file=path.join(home,'config.json');
 try{
  invariant((await lstat(file)).isFile(),'Configuration must be a regular file; preserve and inspect it before setup.');
  const text=await readFile(file,'utf8');let config:Config;
  try{config=JSON.parse(text)}catch{throw new Error('Existing configuration is invalid JSON. Preserve and repair it before running setup.');}
  invariant(config&&typeof config==='object'&&!Array.isArray(config),'Existing configuration must be a JSON object; preserve it before repair.');
  return {text,config};
 }catch(error:any){if(error.code==='ENOENT')return {text:null,config:null};throw error}
}
function absolute(value:string,home:string){
 const expanded=value==='~'?home:value.startsWith('~/')?path.join(home,value.slice(2)):value;
 return path.resolve(expanded);
}
export async function collectSetup(snapshot:SetupSnapshot,args:string[],question:Question,root:string,userHome=os.homedir()):Promise<Config>{
 invariant(args.length<=2,'Use setup [backend] [agent]');
 const previous=snapshot.config;
 async function ask(label:string,fallback?:string){return (await question(`${label}${fallback?` [${fallback}]`:''}: `)).trim()||fallback||'';}
 const engine=backend(args[0]||await ask('Default backend for new projects (filmcraft / premiere / resolve)',previous?.backend));
 const agent=args[1]||await ask('Default agent for new projects (codex / claude)',previous?.agent);invariant(agent==='codex'||agent==='claude','Choose codex or claude');
 const storageRoot=absolute(await ask('Project storage root',previous?.storageRoot||path.join(userHome,'Movies','ACQ Edit')),userHome);
 const python=absolute(await ask('Shared Python executable',previous?.python||path.join(root,'.local/venv/bin/python')),userHome);
 const c:Config={...previous,backend:engine,agent,storageRoot,python,port:previous?.port??4317};
 // Retain the old agent's custom executable when choosing a different default.
 const commands={...previous?.agentCommands};
 if(previous?.agentCommand&&previous.agent)commands[previous.agent]=previous.agentCommand;
 // Preserve optional worker configuration without prompting normal chat users for a CLI.
 const command=commands[agent]||agent;
 if(command==='-'||command===agent)delete commands[agent];else commands[agent]=command.startsWith('~')?absolute(command,userHome):command;
 delete c.agentCommand;
 if(Object.keys(commands).length)c.agentCommands=commands;else delete c.agentCommands;
 if(engine==='filmcraft')c.filmcraft=absolute(await ask('FilmCraft CLI executable',previous?.filmcraft||path.join(root,'.local/filmcraft/target/release/filmcraft-cli')),userHome);
 if(engine==='premiere')c.premiereProfile=absolute(await ask('Toolkit Premiere Agent profile',previous?.premiereProfile||path.join(root,'.local/premiere-profile.json')),userHome);
 if(engine==='resolve')c.resolvePython=absolute(await ask('Resolve Python executable',previous?.resolvePython||'/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython'),userHome);
 const brain=await ask('Editorial brain configuration directory (blank keeps current; - leaves unconfigured)',previous?.brainConfig||process.env.ACQ_EDIT_TEAM_BRAIN_DIR);
 if(brain&&brain!=='-')c.brainConfig=absolute(brain,userHome);else delete c.brainConfig;
 invariant(Number.isInteger(c.port)&&c.port>0&&c.port<=65535,'Existing port is invalid; repair the configuration before saving.');
 return c;
}
function assertStateIdle(file:string){
 const db=new DatabaseSync(file,{readOnly:true});
 try{
  for(const [table,condition,label] of [
   ['jobs',"state IN ('editing','rendering','reconciliation_required')",'Editing jobs'],
   ['native_operations',"state IN ('running','reconciliation_required')",'Native operations'],
   ['intakes',"state NOT IN ('ready','failed')",'Source transfers'],
   ['drive_batches',"state NOT IN ('ready','abandoned')",'Drive batches'],
  ]){
   // Older stores may not have every journal. Do not create or migrate tables.
   if(!db.prepare('SELECT name FROM sqlite_master WHERE type=? AND name=?').get('table',table!))continue;
   invariant(!db.prepare(`SELECT id FROM ${table} WHERE ${condition} LIMIT 1`).get(),`${label} are active or need reconciliation. Finish or reconcile them before changing setup.`);
  }
 }finally{db.close()}
}
export async function saveSetup(home:string,snapshot:SetupSnapshot,c:Config){
 await mkdir(home,{recursive:true,mode:0o700});
 // Use the service reservation so a running room/worker or another setup cannot
 // apply competing changes. No job or native outcome is cleared by setup.
 const release=await serviceLock(home);
 try{
  const current=await readSetup(home);invariant(current.text===snapshot.text,'Configuration changed while setup was open. Rerun setup with the current values; nothing was overwritten.');
  const database=path.join(home,'state.sqlite');
  try{await lstat(database);assertStateIdle(database)}catch(error:any){if(error.code!=='ENOENT')throw error}
  if(snapshot.text!==null&&JSON.stringify(snapshot.config)===JSON.stringify(c))return {changed:false,backup:null};
  await mkdir(c.storageRoot,{recursive:true});
  let backup:string|null=null;
  if(snapshot.text!==null){
   const directory=path.join(home,'config-history');await mkdir(directory,{recursive:true,mode:0o700});
   backup=path.join(directory,new Date().toISOString().replaceAll(':','-')+'-'+randomUUID()+'.json');
   await writeFile(backup,snapshot.text,{flag:'wx',mode:0o600});
  }
  const file=path.join(home,'config.json');await atomicJson(file,c);await chmod(file,0o600);
  return {changed:true,backup};
 }finally{await release()}
}

/** Agent setup uses the same validation/save path without depending on terminal stdin. */
export async function collectNoninteractiveSetup(snapshot:SetupSnapshot,args:string[],root:string,userHome=os.homedir()){
 const positional:string[]=[],options=new Map<string,string>();
 for(let i=0;i<args.length;i++){
  const arg=args[i]!;if(arg==='--non-interactive')continue;
  if(arg==='--storage-root'){invariant(args[i+1]&&!args[i+1]!.startsWith('--'),'--storage-root requires a path');options.set(arg,args[++i]!);}
  else {invariant(!arg.startsWith('--'),'Unknown setup option');positional.push(arg);}
 }
 invariant(positional.length===2,'Noninteractive setup requires backend and agent');
 const previous=process.env.ACQ_EDIT_PREVIOUS_RUNTIME;
 // Only migrate paths owned by the prior registered runtime. Preserve custom paths.
 const updated=snapshot.config?{...snapshot.config}:null;
 if(previous&&updated){for(const key of ['python','filmcraft','premiereProfile','brainConfig'] as const){
  const value=updated[key];if(value&&path.isAbsolute(previous)&&value.startsWith(previous+path.sep))updated[key]=path.join(root,path.relative(previous,value));
 }}
 return collectSetup({...snapshot,config:updated},positional,async prompt=>prompt.startsWith('Project storage root')?options.get('--storage-root')||'':'',root,userHome);
}

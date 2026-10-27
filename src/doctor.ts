import path from 'node:path';
import {access,stat,constants} from 'node:fs/promises';
import {type Config,ROOT,HOME,secretEnv,agentExecutable} from './config.js';
import {run} from './process.js';
import {invariant} from './contracts.js';

interface Issue {check:string;repair:string}
interface DoctorTools {
 execute?:typeof run; secrets?:typeof secretEnv; storage?:(folder:string)=>Promise<void>;
 platform?:string; node?:string; env?:NodeJS.ProcessEnv;
}
async function checkStorage(folder:string){
 invariant(path.isAbsolute(folder),'Storage root must be absolute');
 invariant((await stat(folder)).isDirectory(),'Storage root is not a directory');
 await access(folder,constants.R_OK|constants.W_OK|constants.X_OK);
}
/** No database, configuration writes, agent session or remote brain request. */
export async function doctor(c:Config,tools:DoctorTools={}){
 invariant(['filmcraft','premiere','resolve'].includes(c.backend)&&['codex','claude'].includes(c.agent)&&typeof c.python==='string'&&typeof c.storageRoot==='string','Run setup with valid backend, agent, Python and storage choices');
 const execute=tools.execute||run,env:NodeJS.ProcessEnv={...(tools.env||process.env),PYTHONDONTWRITEBYTECODE:'1'};
 const blocking:Issue[]=[],optional:Issue[]=[];
 const checks:Record<string,any>={node:tools.node||process.version,platform:tools.platform||process.platform,backend:c.backend,agent:c.agent};
 const issue=(check:string,repair:string,required=true)=>(required?blocking:optional).push({check,repair});
 if(checks.platform!=='darwin')issue('platform','Use a Mac for the supported editing toolkit.');
 if(!(Number(checks.node.replace(/^v/,'').split('.')[0])>=24))issue('node','Install Node.js 24 or newer, then run npm ci and npm run build.');
 const entries=[
  {id:'ffmpeg',binary:'ffmpeg',args:['-version'],required:true,repair:'Install FFmpeg and make ffmpeg available on PATH.'},
  {id:'ffprobe',binary:'ffprobe',args:['-version'],required:true,repair:'Install FFmpeg and make ffprobe available on PATH.'},
  {id:'youtube',binary:path.join(ROOT,'.local/venv/bin/yt-dlp'),args:['--version'],required:false,repair:'Install yt-dlp before importing YouTube footage.'},
  {id:'drive',binary:'rclone',args:['--version'],required:false,repair:'Install rclone and configure your Drive remote before importing Drive footage.'},
  {id:'python',binary:c.python,args:['--version'],required:true,repair:'Run scripts/install_shared.sh, then select its Python environment in setup.'},
  {id:'agent',binary:agentExecutable(c,c.agent),args:['--version'],required:true,repair:'Install the selected agent CLI and sign in; check agentCommands (or the legacy agentCommand) if customized.'},
 ];
 const availability=await Promise.all(entries.map(async item=>{
  try{return {available:true,version:(await execute(item.binary,item.args,{env,timeout:15000,outputLimit:64000})).split('\n')[0]}}
  catch{return {available:false}}
 }));
 checks.dependencies={};
 for(const [i,item] of entries.entries()){
  checks.dependencies[item.id]=availability[i];checks[item.binary]=availability[i];
  if(!availability[i]?.available)issue(item.id,item.repair,item.required);
 }
 try{await (tools.storage||checkStorage)(c.storageRoot);checks.storage={ready:true}}
 catch{checks.storage={ready:false};issue('storage','Mount or choose an existing writable project storage directory, then rerun setup.');}
 let secrets:Record<string,string>={},secretsValid=true;
 try{secrets=await (tools.secrets||secretEnv)()}
 catch{secretsValid=false;issue('credentials-file','Repair your private credentials file ownership, mode 0600 and JSON format, or rerun credentials.');}
 const secretValues={...env,...secrets};
 checks.credentials={assemblyAI:!!secretValues.ASSEMBLYAI_API_KEY?.trim(),gemini:!!secretValues.GEMINI_API_KEY?.trim(),fileReadable:secretsValid};
 if(!checks.credentials.assemblyAI)issue('assemblyAI','Run credentials to supply your own AssemblyAI API key.');
 if(!checks.credentials.gemini)issue('gemini','Run credentials to supply your own Gemini API key.');
 // Keep raw child failures private: an invalid configuration can echo secret content.
 checks.skills={ready:false};
 checks.framing={ready:false};
 if(checks.dependencies.python.available){
  try{checks.framing=JSON.parse(await execute(c.python,[path.join(ROOT,'python/check_framing_dependencies.py')],{env,timeout:15000}));}catch{/* preserve bounded dependency diagnostics */}
 }
 if(c.backend==='premiere'&&checks.dependencies.python.available){
  try{checks.compatibility=JSON.parse(await execute(c.python,[path.join(ROOT,'python/premiere_compatibility.py')],{env,timeout:15000}));}catch{checks.compatibility={status:'detection-failed',repair:'Restore toolkit Python and run the compatibility probe; do not guess a host version.'};}
 }
 if(checks.dependencies.youtube.available&&checks.dependencies.python.available){
  try{checks.youtubeSolver=JSON.parse(await execute(c.python,[path.join(ROOT,'scripts/check_youtube.py')],{env,timeout:15000}));}catch{checks.youtubeSolver={ready:false};}
  if(checks.youtubeSolver.ready!==true)issue('youtube-solver','Run the shared installer to restore yt-dlp[default] with EJS and a working Node 24+ runtime.',false);
 }
 if(checks.framing.ready!==true)issue('framing','Run scripts/install_shared.sh and restore the hash-verified packaged YuNet model before subject tracking.');
 if(checks.dependencies.python.available){
  try{
   const value=JSON.parse(await execute(c.python,[path.join(ROOT,'scripts/materialize.py'),'--verify'],{env,timeout:60000}));
   invariant(value?.ready===true&&Number.isInteger(value.verifiedFiles)&&value.verifiedFiles>0&&Number.isInteger(value.routedEntrypoints)&&value.routedEntrypoints>0,'Unverified runtime');
   checks.skills=value;
  }catch{/* report a repair without raw subprocess output */}
 }
 if(!checks.skills.ready)issue('skills','Install the shared dependencies and selected engine in a fresh checkout; preserve any changed or incomplete runtime.');
 checks.assets={ready:false};
 if(checks.skills.ready){
  try{checks.assets=JSON.parse(await execute(c.python,[path.join(ROOT,'scripts/asset_bundle.py'),'runtime-check',ROOT],{env,timeout:60000}));}catch{/* missing or changed bundle */}
 }
 if(checks.assets.ready!==true)issue('assets','Install the versioned asset bundle selected by this runtime, then verify its hashes. Do not fall back to personal folders.');
 checks.brain={ready:false,remoteAccess:'not-checked'};
 if(checks.skills.ready&&secretsValid){
  try{const value=JSON.parse(await execute(c.python,[path.join(ROOT,'python/brain_receipts.py'),'--check-config','--config',path.join(HOME,'config.json')],{env:secretValues,timeout:15000}));checks.brain={ready:value?.ready===true,remoteAccess:'not-checked'}}catch{/* local probe failed */}
 }
 if(!checks.brain.ready)issue('brain','Configure brainConfig with the supplied context.json and restricted read token; check token ownership and mode 0600. This check never fetches guidance.');
 checks.native={ready:false,checked:false};
 if(checks.skills.ready){
  try{
   const interpreter=c.backend==='resolve'?c.resolvePython:c.python;
   invariant(interpreter,'Configure the selected engine interpreter');
   const value=JSON.parse(await execute(interpreter,[path.join(ROOT,'python/native.py'),'doctor','--backend',c.backend,'--config',path.join(HOME,'config.json')],{env,timeout:60000}));
   let ready=c.backend==='filmcraft'?value?.binaryPresent===true:c.backend==='resolve'?value?.connected===true&&value?.studio===true:value?.ready===true;
   invariant(value?.backend===c.backend,'Unexpected backend');
   if(c.backend==='filmcraft'&&ready){
    try{invariant(c.filmcraft,'Configure FilmCraft');await execute(c.filmcraft,['--help'],{env,timeout:15000,outputLimit:64000})}catch{ready=false}
   }
   const {connectionError,...details}=value;
   checks.native={...details,ready,checked:true};
  }catch{/* do not expose raw profile or connector diagnostics */}
 }
 if(!checks.native.ready)issue('native',c.backend==='resolve'?'Start the supported Resolve Studio version with local scripting enabled; check resolvePython and run doctor again.':c.backend==='premiere'?'Verify the isolated toolkit Premiere profile and open its ACQ Edit Agent panel in the supported Premiere version.':'Install the pinned FilmCraft engine and set its CLI path in setup.');
 checks.readiness={ready:blocking.length===0,blocking,optional,
  unverified:['Agent authentication and account credit','API key validity and quota','Live brain access and restricted token scope','Native editing/render acceptance and human review'],
  qualification:'Local prerequisite checks only; not pilot or editorial acceptance.'};
 return checks;
}

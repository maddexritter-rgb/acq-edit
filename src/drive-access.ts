import path from 'node:path';
import {chmod,readFile,mkdir} from 'node:fs/promises';
import {run} from './process.js';
import {HOME} from './config.js';
import {atomicJson} from './files.js';
import {invariant} from './contracts.js';
import {serviceLock} from './lock.js';

interface Tools {execute?:typeof run;home?:string;signal?:AbortSignal}
const namePattern=/^[A-Za-z0-9_-]+$/;
function settings(tools:Tools){return path.join(tools.home||process.env.ACQ_EDIT_CREDENTIALS_HOME||HOME,'drive.json')}
export function driveLinkKind(link:string):'file'|'folder'{
 const u=new URL(link);invariant(u.protocol==='https:'&&u.hostname==='drive.google.com'&&!u.username&&!u.password&&!u.port,'Paste an HTTPS Google Drive file or folder link');
 if(/^\/drive\/(?:u\/\d+\/)?folders\/[A-Za-z0-9_-]+\/?$/.test(u.pathname))return 'folder';
 if(/^\/file\/d\/[A-Za-z0-9_-]+(?:\/view|\/preview)?\/?$/.test(u.pathname)||(['\/open','\/uc'].includes(u.pathname)&&u.searchParams.getAll('id').length===1&&namePattern.test(u.searchParams.get('id')||'')))return 'file';
 throw Error('Paste a direct Google Drive file or folder link, not a search or Shared Drive home page');
}
export async function driveStatus(tools:Tools={}){
 const execute=tools.execute||run;let version='';
 try{version=(await execute('rclone',['version'],{timeout:15000,signal:tools.signal})).split('\n')[0]||''}catch{throw Error('Google Drive downloader is missing or cannot run. Install/repair rclone through the existing Homebrew or Workbrew installation, then run drive-status.');}
 const parts=version.match(/v(\d+)\.(\d+)\.(\d+)/)?.slice(1).map(Number);
 invariant(parts&&(parts[0]!>1||parts[0]===1&&(parts[1]!>74||parts[1]===74&&parts[2]!>=3)),'Google Drive intake requires rclone 1.74.3 or newer; update rclone through your existing Homebrew/Workbrew installation.');
 let raw:string;
 try{raw=await execute('rclone',['listremotes','--long'],{timeout:15000,signal:tools.signal})}catch{throw Error('Cannot read local Drive connections. Unlock the existing rclone configuration if encrypted; do not replace it or print its credentials.');}
 const all=raw.split('\n').map(line=>line.match(/^([^\s:]+):\s+(\S+)/)).filter(x=>x!==null).map(x=>({name:x![1]!,type:x![2]!}));
 const remotes=all.filter(x=>x.type==='drive'&&namePattern.test(x.name)).map(x=>x.name);
 let selected:string|undefined;
 try{const saved=JSON.parse(await readFile(settings(tools),'utf8'));invariant(saved.schema==='acq-edit/drive-connection-v1'&&typeof saved.remote==='string','Invalid saved Drive selection; preserve it and use drive-connect to select again.');selected=saved.remote}catch(e:any){if(e.code!=='ENOENT')throw e}
 return {installed:true,version,remotes,allNames:all.map(x=>x.name),selected,authentication:'not-checked',next:selected||remotes.length===1?'Paste a Drive link; intake verifies access.':remotes.length?'Choose your work Drive connection with drive-connect NAME.':'Run drive-login and sign into Google in the browser.'};
}
export async function driveRemote(explicit?:string,tools:Tools={}){
 const status=await driveStatus(tools),remote=explicit||status.selected||(status.remotes.length===1?status.remotes[0]:undefined);
 invariant(remote&&status.remotes.includes(remote),'Choose/connect Google Drive first: run drive-status, then drive-connect NAME for an existing connection or drive-login for browser sign-in.');return remote;
}
export async function connectDrive(remote:string,tools:Tools={}){
 const chosen=await driveRemote(remote,tools);
 try{JSON.parse(await (tools.execute||run)('rclone',['about',chosen+':','--json'],{timeout:30000,signal:tools.signal}))}catch{throw Error('Google Drive access could not be verified. Sign in with the account that can open the footage; preserve existing connections and report expired access or organization policy.');}
 const file=settings(tools);await atomicJson(file,{schema:'acq-edit/drive-connection-v1',remote:chosen});await chmod(file,0o600);
 return {ready:true,remote:chosen,authentication:'read-verified',footageAccess:'checked during download',next:'Paste a Google Drive file or folder link into your editing chat.'};
}
export async function loginDrive(tools:Tools={}){
 // Dedicated name, read-only scope and a lock; never overwrite an existing connection.
 const lockHome=path.join(path.dirname(settings(tools)),'drive-login');await mkdir(lockHome,{recursive:true,mode:0o700});
 const release=await serviceLock(lockHome);
 try{
  const status=await driveStatus(tools);const name='acq-edit-drive';
  invariant(!status.allNames.includes(name),'The acq-edit-drive connection already exists. Use drive-connect acq-edit-drive or repair its sign-in through rclone; it was not overwritten.');
  try{await (tools.execute||run)('rclone',['config','create',name,'drive','scope','drive.readonly','config_is_local','true','--no-output'],{timeout:5*60_000,signal:tools.signal})}
  catch{throw Error('Google Drive sign-in did not finish. Check the browser or organization approval. Any partial connection is preserved; run drive-status before retrying.');}
  return await connectDrive(name,tools);
 }finally{await release()}
}

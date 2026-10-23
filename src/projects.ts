import { randomUUID } from 'node:crypto';
import { mkdir,copyFile,stat,rename,chmod,symlink,writeFile } from 'node:fs/promises';
import path from 'node:path';
import { constants } from 'node:fs';
import { Store } from './store.js';
import { type Project,type Backend,type Agent,type Source,now,invariant } from './contracts.js';
import { atomicJson,sha256,safeName } from './files.js';
import { ROOT } from './config.js';
import { run } from './process.js';
export async function createProject(store:Store,root:string,title:string,backend:Backend,agent:Agent):Promise<Project>{
 const id=randomUUID();const folder=path.resolve(root,`${now().slice(0,10)}_${safeName(title)}_${id.slice(0,8)}`);
 await mkdir(folder,{recursive:true});for(const d of ['00_SOURCE','10_WORK','20_DELIVER'])await mkdir(path.join(folder,d));
 const p:Project={id,title,root:folder,backend,agent,createdAt:now()};for(const dir of ['.agents','.claude']){await mkdir(path.join(folder,dir));await symlink(path.join(ROOT,'.local','skills'),path.join(folder,dir,'skills'));}await writeFile(path.join(folder,'AGENTS.md'),`# ACQ Edit project\nBackend: ${backend}. This is fixed. Read ${ROOT}/docs/AGENT_WORKFLOW.md. Use this project's skill links; never substitute global workstation skills. Preserve sources and old versions. Only write project work here.\n`);await writeFile(path.join(folder,'CLAUDE.md'),'Read AGENTS.md and project.json before editing.\n');await atomicJson(path.join(folder,'project.json'),p);store.addProject(p);return p;
}
export async function importLocal(store:Store,projectId:string,file:string,origin='local'):Promise<Source>{
 const p=store.project(projectId);const source=path.resolve(file),before=await stat(source);invariant(before.isFile(),'Source must be a regular file');
 const id=randomUUID();const target=path.join(p.root,'00_SOURCE',id+'_'+safeName(path.basename(source,path.extname(source)))+path.extname(source).toLowerCase());
 const partial=target+'.partial';await copyFile(source,partial,constants.COPYFILE_EXCL);
 const [a,b]=await Promise.all([sha256(source),sha256(partial)]);invariant(a===b,'Source copy hash mismatch');const after=await stat(source);invariant(before.size===after.size&&before.mtimeMs===after.mtimeMs,'Source changed during intake');
 const probe=JSON.parse(await run('ffprobe',['-v','error','-show_format','-show_streams','-of','json',partial]));invariant(probe.streams?.some((s:any)=>s.codec_type==='video'||s.codec_type==='audio'),'No audio/video stream');
 await rename(partial,target);await chmod(target,0o444);const s:Source={id,projectId,path:target,sha256:b,bytes:before.size,origin,probe};store.addSource(s);await exportState(store,projectId);return s;
}
export async function importUrl(store:Store,projectId:string,url:string,kind:'youtube'|'drive',remote='drive'){
 const p=store.project(projectId);const intake=path.join(p.root,'10_WORK','intake',randomUUID());await mkdir(intake,{recursive:true});let downloaded:string;
 if(kind==='youtube'){
  const parsed=new URL(url);invariant(['youtube.com','www.youtube.com','youtu.be','m.youtube.com'].includes(parsed.hostname)&&parsed.protocol==='https:','Expected a YouTube HTTPS URL');
  const result=await run('yt-dlp',['--no-playlist','--restrict-filenames','--print','after_move:filepath','-o',path.join(intake,'source.%(ext)s'),'--',url],{timeout:4*3600_000});downloaded=result.trim().split('\n').at(-1)!;
 }else{
  const parsed=new URL(url);invariant(parsed.hostname==='drive.google.com'&&parsed.protocol==='https:','Expected a Google Drive URL');const id=parsed.pathname.match(/\/d\/([\w-]+)/)?.[1]||parsed.searchParams.get('id');invariant(id,'Use a single Drive file link; folders are imported file by file');invariant(/^[A-Za-z0-9_-]+$/.test(remote),'Invalid rclone remote name');
  downloaded=path.join(intake,'drive-source');await run('rclone',['backend','copyid',remote+':',id,downloaded],{timeout:4*3600_000});
 }
 return importLocal(store,projectId,downloaded,kind+':'+url);
}
const exportsInFlight=new Map<string,Promise<unknown>>();
export async function exportState(store:Store,id:string){const task=(exportsInFlight.get(id)||Promise.resolve()).catch(()=>{}).then(async()=>{const snapshot=store.snapshot(id);await atomicJson(path.join(snapshot.project.root,'10_WORK','review-feedback.json'),snapshot);return snapshot});exportsInFlight.set(id,task);return task}

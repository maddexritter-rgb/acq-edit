import { randomUUID } from 'node:crypto';
import { mkdir,symlink,writeFile } from 'node:fs/promises';
import path from 'node:path';
import { Store } from './store.js';
import { type Project,type Backend,type Agent,now } from './contracts.js';
import { atomicJson,safeName } from './files.js';
import { ROOT } from './config.js';
export async function createProject(store:Store,root:string,title:string,backend:Backend,agent:Agent):Promise<Project>{
 const id=randomUUID();const folder=path.resolve(root,`${now().slice(0,10)}_${safeName(title)}_${id.slice(0,8)}`);
 await mkdir(folder,{recursive:true});for(const d of ['00_SOURCE','10_WORK','20_DELIVER'])await mkdir(path.join(folder,d));
 const p:Project={id,title,root:folder,backend,agent,createdAt:now()};for(const dir of ['.agents','.claude']){await mkdir(path.join(folder,dir));await symlink(path.join(ROOT,'.local','skills'),path.join(folder,dir,'skills'));}await writeFile(path.join(folder,'AGENTS.md'),`# ACQ Edit project\nBackend: ${backend}. This is fixed. Read ${ROOT}/docs/AGENT_WORKFLOW.md. Use this project's skill links; never substitute global workstation skills. Preserve sources and old versions. Only write project work here.\n`);await writeFile(path.join(folder,'CLAUDE.md'),'Read AGENTS.md and project.json before editing.\n');await atomicJson(path.join(folder,'project.json'),p);store.addProject(p);return p;
}
export {importLocal,importUrl} from './intake.js';
const exportsInFlight=new Map<string,Promise<unknown>>();
export async function exportState(store:Store,id:string){const task=(exportsInFlight.get(id)||Promise.resolve()).catch(()=>{}).then(async()=>{const snapshot=store.snapshot(id);await atomicJson(path.join(snapshot.project.root,'10_WORK','review-feedback.json'),snapshot);return snapshot});exportsInFlight.set(id,task);return task}

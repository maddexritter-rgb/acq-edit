import os from 'node:os';
import path from 'node:path';
import { chmod, mkdir, readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { atomicJson, readJson } from './files.js';
import { type Backend,type Agent,invariant } from './contracts.js';
export const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const HOME=process.env.ACQ_EDIT_HOME||path.join(os.homedir(),'.config','acq-edit');
export interface Config {storageRoot:string;backend:Backend;agent:Agent;python:string;filmcraft?:string;premiereProfile?:string;resolvePython?:string;brainConfig?:string;agentCommand?:string;port:number}
export const configPath=path.join(HOME,'config.json');
export async function config(){return readJson<Config>(configPath)}
export async function saveConfig(c:Config){await mkdir(HOME,{recursive:true,mode:0o700});await atomicJson(configPath,c);await chmod(configPath,0o600)}
export async function secretEnv(){const f=path.join(HOME,'credentials.json');try{const s=await stat(f);invariant((s.mode&0o077)===0&&s.uid===os.userInfo().uid,'Credentials must be owned by you and mode 0600');const data=JSON.parse(await readFile(f,'utf8'));const out:Record<string,string>={};for(const key of ['ASSEMBLYAI_API_KEY','GEMINI_API_KEY','EDITORIAL_BRAIN_READ_KEY'])if(typeof data[key]==='string')out[key]=data[key];return out}catch(e:any){if(e.code==='ENOENT')return {};throw e}}

import { createHash, randomUUID } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, rename, writeFile, realpath, stat } from 'node:fs/promises';
import path from 'node:path';
import { invariant } from './contracts.js';
export async function sha256(file:string):Promise<string>{const h=createHash('sha256');for await(const chunk of createReadStream(file))h.update(chunk);return h.digest('hex')}
export async function atomicJson(file:string,value:unknown){await mkdir(path.dirname(file),{recursive:true});const tmp=`${file}.${randomUUID()}.new`;await writeFile(tmp,JSON.stringify(value,null,2)+'\n',{mode:0o600});await rename(tmp,file)}
export async function readJson<T>(file:string):Promise<T>{return JSON.parse(await readFile(file,'utf8')) as T}
export async function containedFile(root:string,file:string):Promise<string>{const [r,f]=await Promise.all([realpath(root),realpath(file)]);invariant(f.startsWith(r+path.sep),'File is outside project');invariant((await stat(f)).isFile(),'Expected a file');return f}
export function safeName(value:string){return value.normalize('NFKD').replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/^-|-$/g,'').slice(0,80)||'project'}

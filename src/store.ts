import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { type Project,type Source,type Clip,type Version,type Feedback,type Job,type Submission,type JobState,now,hash,invariant,routeRevision } from './contracts.js';
const parse=<T>(row:any):T|undefined=>row?JSON.parse(row.data):undefined;
export class Store {
 db:DatabaseSync;
 constructor(file:string){mkdirSync(path.dirname(file),{recursive:true});this.db=new DatabaseSync(file);this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;
 CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,data TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),data TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS clips(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),data TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY,clip_id TEXT NOT NULL REFERENCES clips(id),data TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS feedback(version_id TEXT PRIMARY KEY REFERENCES versions(id),data TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),state TEXT NOT NULL,dedupe TEXT NOT NULL UNIQUE,data TEXT NOT NULL);
 CREATE UNIQUE INDEX IF NOT EXISTS one_mutator ON jobs(project_id) WHERE state IN ('editing','rendering','reconciliation_required');
 CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,created_at TEXT NOT NULL,data TEXT NOT NULL);`)}
 close(){this.db.close()}
 transaction<T>(f:()=>T):T{this.db.exec('BEGIN IMMEDIATE');try{const result=f();this.db.exec('COMMIT');return result}catch(e){this.db.exec('ROLLBACK');throw e}}
 project(id:string){const p=parse<Project>(this.db.prepare('SELECT data FROM projects WHERE id=?').get(id));invariant(p,'Project not found');return p}
 projects(){return this.db.prepare('SELECT data FROM projects ORDER BY rowid DESC').all().map(r=>parse<Project>(r)!)}
 addProject(p:Project){this.db.prepare('INSERT INTO projects VALUES (?,?)').run(p.id,JSON.stringify(p));this.event(p.id,{type:'project.created',backend:p.backend})}
 sources(id:string){return this.db.prepare('SELECT data FROM sources WHERE project_id=?').all(id).map(r=>parse<Source>(r)!)}
 addSource(s:Source){this.project(s.projectId);this.db.prepare('INSERT INTO sources VALUES (?,?,?)').run(s.id,s.projectId,JSON.stringify(s))}
 clips(id:string){return this.db.prepare('SELECT data FROM clips WHERE project_id=? ORDER BY rowid').all(id).map(r=>parse<Clip>(r)!)}
 clip(id:string){const c=parse<Clip>(this.db.prepare('SELECT data FROM clips WHERE id=?').get(id));invariant(c,'Clip not found');return c}
 addClip(c:Clip){this.db.prepare('INSERT INTO clips VALUES (?,?,?)').run(c.id,c.projectId,JSON.stringify(c))}
 version(id:string){const v=parse<Version>(this.db.prepare('SELECT data FROM versions WHERE id=?').get(id));invariant(v,'Version not found');return v}
 versions(clipId:string){return this.db.prepare('SELECT data FROM versions WHERE clip_id=? ORDER BY rowid DESC').all(clipId).map(r=>parse<Version>(r)!)}
 publish(v:Version){this.transaction(()=>{const c=this.clip(v.clipId);invariant(c.currentVersionId===v.parentId,'Clip changed since render started');invariant(v.number===this.versions(c.id).length+1,'Version number conflict');invariant(!this.db.prepare('SELECT id FROM versions WHERE json_extract(data,\'$.media\')=?').get(v.media),'Immutable media path already published');this.db.prepare('INSERT INTO versions VALUES (?,?,?)').run(v.id,c.id,JSON.stringify(v));c.currentVersionId=v.id;this.db.prepare('UPDATE clips SET data=? WHERE id=?').run(JSON.stringify(c),c.id);this.db.prepare('INSERT INTO feedback VALUES (?,?)').run(v.id,JSON.stringify({versionId:v.id,revision:0,decision:null,notes:'',comments:[],updatedAt:now()}));this.event(c.projectId,{type:'version.published',versionId:v.id,parentId:v.parentId})})}
 feedback(id:string){this.version(id);return parse<Feedback>(this.db.prepare('SELECT data FROM feedback WHERE version_id=?').get(id))!}
 saveFeedback(id:string,input:Omit<Feedback,'versionId'|'revision'|'updatedAt'>,expected:number){return this.transaction(()=>{const prior=this.feedback(id);invariant(this.clip(this.version(id).clipId).currentVersionId===id,'Historical feedback is read-only');invariant(prior.revision===expected,'Feedback changed in another window. Reload before saving.');invariant([null,'yes','revise','no'].includes(input.decision),'Invalid decision');invariant(typeof input.notes==='string'&&input.notes.length<=50000&&Array.isArray(input.comments)&&input.comments.length<=500,'Feedback exceeds limits');invariant(new Set(input.comments.map(c=>c.id)).size===input.comments.length,'Duplicate comment id');for(const c of input.comments)invariant(typeof c.id==='string'&&Number.isFinite(c.seconds)&&c.seconds>=0&&typeof c.text==='string'&&c.text.length<=10000,'Invalid timecoded comment');const f:Feedback={versionId:id,decision:input.decision,notes:input.notes,comments:input.comments,revision:prior.revision+1,updatedAt:now()};this.db.prepare('UPDATE feedback SET data=? WHERE version_id=?').run(JSON.stringify(f),id);this.event(this.clip(this.version(id).clipId).projectId,{type:'feedback.saved',versionId:id,revision:f.revision});return f})}
 enqueue(projectId:string,versionIds:string[]):Job{return this.transaction(()=>{
   this.project(projectId);invariant(versionIds.length>0&&new Set(versionIds).size===versionIds.length,'Select one or more distinct clip versions');
   const snapshot:Submission[]=versionIds.sort().map(id=>{const v=this.version(id),c=this.clip(v.clipId),f=this.feedback(id);invariant(c.projectId===projectId&&c.currentVersionId===id,'Only the current version can be submitted');invariant(f.notes.trim()||f.comments.some(c=>c.text.trim()),'Revision notes required');return{clipId:c.id,version:v,feedback:f,owners:routeRevision(f.notes+' '+f.comments.map(c=>c.text).join(' '))}});
   const dedupe=hash({projectId,snapshot});const old=parse<Job>(this.db.prepare('SELECT data FROM jobs WHERE dedupe=?').get(dedupe));if(old)return old;
   const j:Job={id:randomUUID(),projectId,state:'queued',kind:'revision',snapshot,request:'',dedupe,createdAt:now(),updatedAt:now(),error:null,agentSession:null};this.insertJob(j);return j;
 })}
 enqueueBuild(projectId:string,request:string){this.project(projectId);invariant(request.trim(),'Build request required');const j:Job={id:randomUUID(),projectId,state:'queued',kind:'build',snapshot:[],request,dedupe:randomUUID(),createdAt:now(),updatedAt:now(),error:null,agentSession:null};this.insertJob(j);return j}
 private insertJob(j:Job){this.db.prepare('INSERT INTO jobs VALUES (?,?,?,?,?)').run(j.id,j.projectId,j.state,j.dedupe,JSON.stringify(j));this.event(j.projectId,{type:'job.queued',jobId:j.id})}
 job(id:string){const j=parse<Job>(this.db.prepare('SELECT data FROM jobs WHERE id=?').get(id));invariant(j,'Job not found');return j}
 jobs(id:string){return this.db.prepare('SELECT data FROM jobs WHERE project_id=? ORDER BY rowid DESC').all(id).map(r=>parse<Job>(r)!)}
 claim():Job|undefined{return this.transaction(()=>{const row=this.db.prepare(`SELECT data FROM jobs j WHERE state='queued' AND NOT EXISTS (SELECT 1 FROM jobs b WHERE b.project_id=j.project_id AND b.state IN ('editing','rendering','reconciliation_required')) ORDER BY rowid LIMIT 1`).get();const j=parse<Job>(row);if(!j)return;
   if(j.snapshot.some(s=>this.clip(s.clipId).currentVersionId!==s.version.id)){this.setJob(j.id,'failed','Submitted version is no longer current; review the latest version and resubmit.');return}
   return this.setJob(j.id,'editing');})}
 setJob(id:string,state:JobState,error:string|null=null,session?:string){const j=this.job(id);j.state=state;j.error=error;j.updatedAt=now();if(session)j.agentSession=session;this.db.prepare('UPDATE jobs SET state=?,data=? WHERE id=?').run(state,JSON.stringify(j),id);this.event(j.projectId,{type:'job.state',jobId:id,state,error});return j}
 recover(){for(const r of this.db.prepare("SELECT id FROM jobs WHERE state IN ('editing','rendering')").all())this.setJob(String(r.id),'reconciliation_required','Service stopped during native work. Inspect native state and receipts before resolving this job.')}
 event(projectId:string,data:unknown){this.db.prepare('INSERT INTO events(project_id,created_at,data) VALUES (?,?,?)').run(projectId,now(),JSON.stringify(data))}
 snapshot(id:string){return{project:this.project(id),sources:this.sources(id),clips:this.clips(id).map(c=>({...c,versions:this.versions(c.id).map(v=>({...v,feedback:this.feedback(v.id)}))})),jobs:this.jobs(id)}}
}

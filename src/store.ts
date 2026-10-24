import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import {
  type Project, type Source, type Clip, type Version, type Feedback,
  type Job, type Submission, type JobState, type DeferredFeedback, type Intake, type DriveBatch, type NativeOperation,
  now, hash, invariant, routeRevision,
} from './contracts.js';

const parse = <T>(row: any): T | undefined => row ? JSON.parse(row.data) : undefined;
const editorialFeedback = (f: Feedback) => ({ notes: f.notes, comments: f.comments });
const activeStates = ['editing', 'rendering', 'reconciliation_required'];
// Routing hints may improve between releases. Request identity is the exact
// submitted versions/feedback, not the current classifier's suggested owners.
const revisionKey = (projectId:string,snapshot:Submission[]) => hash({projectId,snapshot:snapshot.map(s=>({clipId:s.clipId,version:s.version,feedback:s.feedback,deferred:s.deferred||[]}))});

export class Store {
  db: DatabaseSync;

  constructor(file: string) {
    mkdirSync(path.dirname(file), { recursive: true });
    this.db = new DatabaseSync(file);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS clips(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY,clip_id TEXT NOT NULL REFERENCES clips(id),data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS feedback(version_id TEXT PRIMARY KEY REFERENCES versions(id),data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),state TEXT NOT NULL,dedupe TEXT NOT NULL UNIQUE,data TEXT NOT NULL);
      CREATE UNIQUE INDEX IF NOT EXISTS one_mutator ON jobs(project_id) WHERE state IN ('editing','rendering','reconciliation_required');
      CREATE TABLE IF NOT EXISTS intakes(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),state TEXT NOT NULL,data TEXT NOT NULL);
      CREATE UNIQUE INDEX IF NOT EXISTS one_intake ON intakes(project_id) WHERE state IN ('downloading','verifying','copying','reconciliation_required');
      CREATE TABLE IF NOT EXISTS drive_batches(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),state TEXT NOT NULL,data TEXT NOT NULL);
      CREATE UNIQUE INDEX IF NOT EXISTS one_drive_batch ON drive_batches(project_id) WHERE state NOT IN ('ready','abandoned');
      CREATE TABLE IF NOT EXISTS native_operations(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),state TEXT NOT NULL,data TEXT NOT NULL);
      CREATE UNIQUE INDEX IF NOT EXISTS one_native_operation ON native_operations(project_id) WHERE state IN ('running','reconciliation_required');
      CREATE TABLE IF NOT EXISTS deferred_feedback(
        id TEXT PRIMARY KEY, clip_id TEXT NOT NULL REFERENCES clips(id),
        consumed_by TEXT REFERENCES versions(id), data TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT NOT NULL,created_at TEXT NOT NULL,data TEXT NOT NULL);`);
  }

  close() { this.db.close(); }

  transaction<T>(f: () => T): T {
    this.db.exec('BEGIN IMMEDIATE');
    try { const result = f(); this.db.exec('COMMIT'); return result; }
    catch (e) { this.db.exec('ROLLBACK'); throw e; }
  }

  project(id: string) {
    const p = parse<Project>(this.db.prepare('SELECT data FROM projects WHERE id=?').get(id));
    invariant(p, 'Project not found'); return p;
  }
  projects() { return this.db.prepare('SELECT data FROM projects ORDER BY rowid DESC').all().map(r => parse<Project>(r)!); }
  addProject(p: Project) {
    this.db.prepare('INSERT INTO projects VALUES (?,?)').run(p.id, JSON.stringify(p));
    this.event(p.id, { type: 'project.created', backend: p.backend });
  }
  sources(id: string) { return this.db.prepare('SELECT data FROM sources WHERE project_id=?').all(id).map(r => parse<Source>(r)!); }
  addSource(s: Source) {
    this.project(s.projectId);
    this.db.prepare('INSERT INTO sources VALUES (?,?,?)').run(s.id, s.projectId, JSON.stringify(s));
  }
  intake(id:string) {const value=parse<Intake>(this.db.prepare('SELECT data FROM intakes WHERE id=?').get(id));invariant(value,'Intake not found');return value}
  intakes(projectId:string) {this.project(projectId);return this.db.prepare('SELECT data FROM intakes WHERE project_id=? ORDER BY rowid DESC').all(projectId).map(r=>parse<Intake>(r)!)}
  addIntake(value:Intake) {
    return this.transaction(()=>{
      this.project(value.projectId);
      this.assertNativeSettled(value.projectId);
      const active=this.jobs(value.projectId).find(j=>activeStates.includes(j.state));
      invariant(!active||(active.id===process.env.ACQ_EDIT_JOB_ID&&active.state!=='reconciliation_required'),'An editing job owns this project; intake must belong to that job');
      const batch=this.driveBatches(value.projectId).find(b=>!['ready','abandoned'].includes(b.state));
      invariant(!batch||batch.id===value.batchId&&batch.ownerPid===process.pid&&batch.state==='transferring','A Drive batch owns this project');
      if(value.batchId)invariant(batch?.id===value.batchId,'Drive batch is not active');
      invariant(!this.intakes(value.projectId).some(i=>!['ready','failed'].includes(i.state)),'Another intake is active or needs recovery');
      this.db.prepare('INSERT INTO intakes VALUES (?,?,?,?)').run(value.id,value.projectId,value.state,JSON.stringify(value));
      this.event(value.projectId,{type:'intake.created',intakeId:value.id});return value;
    });
  }
  updateIntake(id:string,patch:Partial<Intake>) {
    const old=this.intake(id);const value={...old,...patch,id:old.id,projectId:old.projectId,updatedAt:now()};
    this.db.prepare('UPDATE intakes SET state=?,data=? WHERE id=?').run(value.state,JSON.stringify(value),id);return value;
  }
  finishIntake(id:string,source:Source) {
    return this.transaction(()=>{const intake=this.intake(id);invariant(source.id===id&&source.projectId===intake.projectId,'Intake source identity differs');
      this.addSource(source);return this.updateIntake(id,{state:'ready',sourceId:source.id,ownerPid:null,childPid:null,error:null});});
  }
  driveBatch(id:string){const b=parse<DriveBatch>(this.db.prepare('SELECT data FROM drive_batches WHERE id=?').get(id));invariant(b,'Drive batch not found');return b}
  driveBatches(projectId:string){this.project(projectId);return this.db.prepare('SELECT data FROM drive_batches WHERE project_id=? ORDER BY rowid DESC').all(projectId).map(r=>parse<DriveBatch>(r)!)}
  addDriveBatch(b:DriveBatch){return this.transaction(()=>{
    this.assertNativeSettled(b.projectId);
    this.project(b.projectId);const job=this.jobs(b.projectId).find(j=>activeStates.includes(j.state));
    invariant(!job||job.id===process.env.ACQ_EDIT_JOB_ID&&job.state!=='reconciliation_required','An editing job owns this project');
    invariant(!this.intakes(b.projectId).some(i=>!['ready','failed'].includes(i.state)),'An intake needs completion or reconciliation');
    invariant(!this.driveBatches(b.projectId).some(x=>!['ready','abandoned'].includes(x.state)),'A Drive batch needs completion or abandonment');
    this.db.prepare('INSERT INTO drive_batches VALUES (?,?,?,?)').run(b.id,b.projectId,b.state,JSON.stringify(b));this.event(b.projectId,{type:'drive-batch.created',batchId:b.id});return b;
  })}
  updateDriveBatch(id:string,patch:Partial<DriveBatch>){const old=this.driveBatch(id),value={...old,...patch,id:old.id,projectId:old.projectId,updatedAt:now()};this.db.prepare('UPDATE drive_batches SET state=?,data=? WHERE id=?').run(value.state,JSON.stringify(value),id);return value}
  nativeOperation(id:string){const value=parse<NativeOperation>(this.db.prepare('SELECT data FROM native_operations WHERE id=?').get(id));invariant(value,'Native operation not found');return value}
  nativeOperations(projectId:string){this.project(projectId);return this.db.prepare('SELECT data FROM native_operations WHERE project_id=? ORDER BY rowid DESC').all(projectId).map(row=>parse<NativeOperation>(row)!)}
  assertNativeSettled(projectId:string){invariant(!this.nativeOperations(projectId).some(o=>['running','reconciliation_required'].includes(o.state)),'Native operation is active or requires reconciliation; inspect native-operations first')}
  addNativeOperation(value:NativeOperation){return this.transaction(()=>{
    const project=this.project(value.projectId);invariant(project.backend===value.backend,'Native operation backend differs');this.assertNativeSettled(project.id);
    const job=this.jobs(project.id).find(j=>activeStates.includes(j.state));
    invariant(!job||job.id===value.jobId&&job.state!=='reconciliation_required','An editing job owns this project');
    if(value.jobId){const owner=this.job(value.jobId);invariant(owner.projectId===project.id&&['editing','rendering'].includes(owner.state),'Native operation belongs to another or inactive job')}
    invariant(!this.intakes(project.id).some(i=>!['ready','failed'].includes(i.state))&&!this.driveBatches(project.id).some(b=>!['ready','abandoned'].includes(b.state)),'Finish or reconcile intake before native work');
    this.db.prepare('INSERT INTO native_operations VALUES (?,?,?,?)').run(value.id,project.id,value.state,JSON.stringify(value));this.event(project.id,{type:'native.started',operationId:value.id,jobId:value.jobId});return value;
  })}
  updateNativeOperation(id:string,patch:Partial<NativeOperation>){const old=this.nativeOperation(id),value={...old,...patch,id:old.id,projectId:old.projectId,updatedAt:now()};this.db.prepare('UPDATE native_operations SET state=?,data=? WHERE id=?').run(value.state,JSON.stringify(value),id);return value}
  clips(id: string) { return this.db.prepare('SELECT data FROM clips WHERE project_id=? ORDER BY rowid').all(id).map(r => parse<Clip>(r)!); }
  clip(id: string) {
    const c = parse<Clip>(this.db.prepare('SELECT data FROM clips WHERE id=?').get(id));
    invariant(c, 'Clip not found'); return c;
  }
  addClip(c: Clip) { this.db.prepare('INSERT INTO clips VALUES (?,?,?)').run(c.id, c.projectId, JSON.stringify(c)); }
  version(id: string) {
    const v = parse<Version>(this.db.prepare('SELECT data FROM versions WHERE id=?').get(id));
    invariant(v, 'Version not found'); return v;
  }
  versions(clipId: string) { return this.db.prepare('SELECT data FROM versions WHERE clip_id=? ORDER BY rowid DESC').all(clipId).map(r => parse<Version>(r)!); }
  pendingFeedback(clipId: string) {
    return this.db.prepare('SELECT data FROM deferred_feedback WHERE clip_id=? AND consumed_by IS NULL ORDER BY rowid')
      .all(clipId).map(r => parse<DeferredFeedback>(r)!);
  }

  /** Validate a publication against the exact job before expensive file verification. Rechecked at commit. */
  publicationJob(clipId: string, parentId: string | null, jobId?: string): Submission | undefined {
    const clip = this.clip(clipId);
    const active = this.jobs(clip.projectId).find(j => activeStates.includes(j.state));
    invariant(!active || active.id === jobId, 'A project job owns publication; supply its exact job ID');
    if (!jobId) return;
    const job = this.job(jobId);
    invariant(job.projectId === clip.projectId && activeStates.includes(job.state), 'Publication job is not active for this project');
    invariant(!this.versions(clipId).some(v => v.jobId === jobId), 'This job already published the clip; reconcile its existing version');
    const submission = job.snapshot.find(s => s.clipId === clipId);
    if (job.kind === 'revision') invariant(submission && submission.version.id === parentId, 'Clip or parent is outside the submitted job snapshot');
    else invariant(parentId === null, 'Build jobs may publish new clips only; use a revision job for existing clips');
    return submission;
  }

  publish(v: Version) {
    this.transaction(() => {
      const c = this.clip(v.clipId);
      invariant(c.currentVersionId === v.parentId, 'Clip changed since render started');
      invariant(v.number === this.versions(c.id).length + 1, 'Version number conflict');
      invariant(!this.db.prepare("SELECT id FROM versions WHERE json_extract(data,'$.media')=?").get(v.media), 'Immutable media path already published');
      const submission = this.publicationJob(c.id, v.parentId, v.jobId);
      this.db.prepare('INSERT INTO versions VALUES (?,?,?)').run(v.id, c.id, JSON.stringify(v));
      if (submission) {
        const latest = this.feedback(submission.version.id);
        if (hash(editorialFeedback(latest)) !== hash(editorialFeedback(submission.feedback))) {
          const deferred: DeferredFeedback = {
            id: hash({ job: v.jobId, version: submission.version.id, revision: latest.revision }),
            clipId: c.id, sourceVersion: submission.version, submitted: submission.feedback,
            latest, originatingJobId: v.jobId!, createdAt: now(),
          };
          this.db.prepare('INSERT INTO deferred_feedback VALUES (?,?,NULL,?)')
            .run(deferred.id, c.id, JSON.stringify(deferred));
          this.event(c.projectId, { type: 'feedback.deferred', id: deferred.id, sourceVersionId: submission.version.id });
        }
        // Only the carryovers in this immutable snapshot were handled. Never consume later notes.
        for (const deferred of submission.deferred || []) {
          const result = this.db.prepare('UPDATE deferred_feedback SET consumed_by=? WHERE id=? AND clip_id=? AND consumed_by IS NULL')
            .run(v.id, deferred.id, c.id);
          invariant(result.changes === 1, 'Deferred feedback changed or was already consumed');
        }
      }
      c.currentVersionId = v.id;
      this.db.prepare('UPDATE clips SET data=? WHERE id=?').run(JSON.stringify(c), c.id);
      this.db.prepare('INSERT INTO feedback VALUES (?,?)').run(v.id, JSON.stringify({
        versionId: v.id, revision: 0, decision: null, notes: '', comments: [], updatedAt: now(),
      }));
      this.event(c.projectId, { type: 'version.published', versionId: v.id, parentId: v.parentId, jobId: v.jobId });
    });
  }

  feedback(id: string) {
    this.version(id);
    return parse<Feedback>(this.db.prepare('SELECT data FROM feedback WHERE version_id=?').get(id))!;
  }
  saveFeedback(id: string, input: Omit<Feedback, 'versionId' | 'revision' | 'updatedAt'>, expected: number) {
    return this.transaction(() => {
      const prior = this.feedback(id);
      invariant(this.clip(this.version(id).clipId).currentVersionId === id, 'Historical feedback is read-only');
      invariant(prior.revision === expected, 'Feedback changed in another window. Reload before saving.');
      invariant([null, 'yes', 'revise', 'no'].includes(input.decision), 'Invalid decision');
      invariant(typeof input.notes === 'string' && input.notes.length <= 50000 && Array.isArray(input.comments) && input.comments.length <= 500, 'Feedback exceeds limits');
      invariant(new Set(input.comments.map(c => c.id)).size === input.comments.length, 'Duplicate comment id');
      for (const c of input.comments) invariant(typeof c.id === 'string' && Number.isFinite(c.seconds) && c.seconds >= 0 && typeof c.text === 'string' && c.text.length <= 10000, 'Invalid timecoded comment');
      const f: Feedback = { versionId: id, decision: input.decision, notes: input.notes, comments: input.comments, revision: prior.revision + 1, updatedAt: now() };
      this.db.prepare('UPDATE feedback SET data=? WHERE version_id=?').run(JSON.stringify(f), id);
      this.event(this.clip(this.version(id).clipId).projectId, { type: 'feedback.saved', versionId: id, revision: f.revision });
      return f;
    });
  }

  enqueue(projectId: string, versionIds: string[]): Job {
    return this.transaction(() => {
      this.project(projectId);
      invariant(versionIds.length > 0 && new Set(versionIds).size === versionIds.length, 'Select one or more distinct clip versions');
      const snapshot: Submission[] = [...versionIds].sort().map(id => {
        const v = this.version(id), c = this.clip(v.clipId), f = this.feedback(id), deferred = this.pendingFeedback(c.id);
        invariant(c.projectId === projectId && c.currentVersionId === id, 'Only the current version can be submitted');
        invariant(f.notes.trim() || f.comments.some(c => c.text.trim()) || deferred.length, 'Revision notes required');
        const text = [f, ...deferred.flatMap(d => [d.submitted, d.latest])].map(x => x.notes + ' ' + x.comments.map(c => c.text).join(' ')).join(' ');
        return { clipId: c.id, version: v, feedback: f, owners: routeRevision(text), deferred };
      });
      const dedupe = revisionKey(projectId,snapshot);
      const old = parse<Job>(this.db.prepare('SELECT data FROM jobs WHERE dedupe=?').get(dedupe))
        // Retain jobs created by releases that included owners in the key.
        // Never rewrite their frozen packet or replay them after an upgrade.
        || this.jobs(projectId).find(j=>j.kind==='revision'&&revisionKey(projectId,j.snapshot)===dedupe);
      if (old) return old;
      const j: Job = { id: randomUUID(), projectId, state: 'queued', kind: 'revision', snapshot, request: '', dedupe, createdAt: now(), updatedAt: now(), error: null, agentSession: null };
      this.insertJob(j); return j;
    });
  }
  enqueueBuild(projectId: string, request: string) {
    this.project(projectId); invariant(request.trim(), 'Build request required');
    const j: Job = { id: randomUUID(), projectId, state: 'queued', kind: 'build', snapshot: [], request, dedupe: randomUUID(), createdAt: now(), updatedAt: now(), error: null, agentSession: null };
    this.insertJob(j); return j;
  }
  private insertJob(j: Job) {
    this.db.prepare('INSERT INTO jobs VALUES (?,?,?,?,?)').run(j.id, j.projectId, j.state, j.dedupe, JSON.stringify(j));
    this.event(j.projectId, { type: 'job.queued', jobId: j.id });
  }
  job(id: string) {
    const j = parse<Job>(this.db.prepare('SELECT data FROM jobs WHERE id=?').get(id));
    invariant(j, 'Job not found'); return j;
  }
  jobs(id: string) { return this.db.prepare('SELECT data FROM jobs WHERE project_id=? ORDER BY rowid DESC').all(id).map(r => parse<Job>(r)!); }
  claim(): Job | undefined {
    return this.transaction(() => {
      const row = this.db.prepare(`SELECT data FROM jobs j WHERE state='queued' AND NOT EXISTS
        (SELECT 1 FROM jobs b WHERE b.project_id=j.project_id AND b.state IN ('editing','rendering','reconciliation_required'))
        AND NOT EXISTS (SELECT 1 FROM intakes i WHERE i.project_id=j.project_id AND i.state NOT IN ('ready','failed'))
        AND NOT EXISTS (SELECT 1 FROM drive_batches d WHERE d.project_id=j.project_id AND d.state NOT IN ('ready','abandoned'))
        AND NOT EXISTS (SELECT 1 FROM native_operations n WHERE n.project_id=j.project_id AND n.state IN ('running','reconciliation_required'))
        ORDER BY rowid LIMIT 1`).get();
      const j = parse<Job>(row); if (!j) return;
      if (j.snapshot.some(s => this.clip(s.clipId).currentVersionId !== s.version.id)) {
        this.setJob(j.id, 'failed', 'Submitted version is no longer current. Later feedback remains pending on the latest clip; review and apply it there.');
        return;
      }
      return this.setJob(j.id, 'editing');
    });
  }
  finishJob(id: string, versionIds: string[]) {
    return this.transaction(() => {
      const j = this.job(id);
      this.assertNativeSettled(j.projectId);
      invariant(activeStates.includes(j.state), 'Only an active or reconciled job can complete');
      invariant(Array.isArray(versionIds) && versionIds.length > 0 && new Set(versionIds).size === versionIds.length, 'Exact distinct published version IDs required');
      const versions = versionIds.map(v => this.version(v));
      invariant(versions.every(v => v.jobId === id && this.clip(v.clipId).projectId === j.projectId), 'Result contains a version from another job');
      if (j.kind === 'revision') {
        invariant(versions.length === j.snapshot.length && j.snapshot.every(s => versions.some(v => v.clipId === s.clipId && v.parentId === s.version.id)), 'Not all selected revisions completed');
      }
      const published = this.clips(j.projectId).flatMap(c => this.versions(c.id)).filter(v => v.jobId === id);
      invariant(published.length === versions.length, 'Result omitted a version published by this job');
      return this.setJob(id, 'ready');
    });
  }
  setJob(id: string, state: JobState, error: string | null = null, session?: string) {
    const j = this.job(id); j.state = state; j.error = error; j.updatedAt = now();
    if (session) j.agentSession = session;
    this.db.prepare('UPDATE jobs SET state=?,data=? WHERE id=?').run(state, JSON.stringify(j), id);
    this.event(j.projectId, { type: 'job.state', jobId: id, state, error }); return j;
  }
  recover() {
    for (const r of this.db.prepare("SELECT id FROM jobs WHERE state IN ('editing','rendering')").all())
      this.setJob(String(r.id), 'reconciliation_required', 'Service stopped during native work. Inspect native state and receipts before resolving this job.');
  }
  event(projectId: string, data: unknown) {
    this.db.prepare('INSERT INTO events(project_id,created_at,data) VALUES (?,?,?)').run(projectId, now(), JSON.stringify(data));
  }
  snapshot(id: string) {
    return {
      project: this.project(id), sources: this.sources(id),
      clips: this.clips(id).map(c => ({ ...c, pendingFeedback: this.pendingFeedback(c.id), versions: this.versions(c.id).map(v => ({ ...v, feedback: this.feedback(v.id) })) })),
      jobs: this.jobs(id),intakes:this.intakes(id),driveBatches:this.driveBatches(id),nativeOperations:this.nativeOperations(id),
    };
  }
}

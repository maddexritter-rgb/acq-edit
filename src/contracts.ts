import { createHash } from 'node:crypto';
export const BACKENDS = ['filmcraft','premiere','resolve'] as const;
export type Backend = typeof BACKENDS[number];
export type Agent = 'codex' | 'claude';
export type Decision = 'yes'|'revise'|'no'|null;
export type JobState = 'queued'|'editing'|'rendering'|'ready'|'failed'|'reconciliation_required';
export interface Project { id:string; title:string; root:string; backend:Backend; agent:Agent; createdAt:string }
export interface Source { id:string; projectId:string; path:string; sha256:string; bytes:number; origin:string; probe:unknown; intakeId?:string; verificationPath?:string; verificationSha256?:string }
export interface Intake {
 id:string;projectId:string;kind:'local'|'youtube'|'drive';input:string;origin:string;remote?:string;fileId?:string;
 state:'downloading'|'verifying'|'copying'|'ready'|'failed'|'reconciliation_required';
 directory:string;candidate?:string;target?:string;expectedSha256?:string;bytes?:number;sourceId?:string;
 ownerPid:number|null;childPid:number|null;childPending?:boolean;createdAt:string;updatedAt:string;error:string|null;
 batchId?:string;driveExpected?:DriveFile;
}
export interface DriveFile {id:string;name:string;parentId:string;folders:string[];bytes:number;md5:string}
export type NativeAction='compile'|'captions'|'hooks'|'inspect'|'build'|'revise'|'render';
export interface NativeOperation {
 id:string;projectId:string;jobId:string|null;backend:Backend;action:NativeAction;
 packetPath:string;packetSha256:string;directory:string;
 state:'running'|'succeeded'|'reconciliation_required'|'reconciled';
 ownerPid:number|null;childPid:number|null;childPending:boolean;
 createdAt:string;updatedAt:string;error:string|null;resultPath?:string;resultSha256?:string;
}
export interface DriveBatch {
 id:string;projectId:string;url:string;remote:string;folderId:string;directory:string;
 state:'enumerating'|'transferring'|'ready'|'failed'|'abandoned';
 ownerPid:number|null;childPid:number|null;childPending?:boolean;createdAt:string;updatedAt:string;error:string|null;
 manifestPath?:string;manifestSha256?:string;
}
export interface Version { id:string; clipId:string; number:number; media:string; sha256:string; nativeProject:string; nativeCheckpoint?:string; nativeFingerprint:string; planPath:string; planSha256?:string; inspectionPath?:string; inspectionSha256?:string; receiptPath:string; receiptSha256?:string; recutVerificationPath?:string; recutVerificationSha256?:string; createdAt:string; parentId:string|null; jobId?:string }
export interface Clip { id:string; projectId:string; number:number; title:string; currentVersionId:string|null }
export interface Feedback { versionId:string; revision:number; decision:Decision; notes:string; comments:Comment[]; updatedAt:string }
export interface Comment { id:string; seconds:number; text:string }
/** Edits made after a job's snapshot. All timestamps still address sourceVersion. */
export interface DeferredFeedback {
  id:string; clipId:string; sourceVersion:Version; submitted:Feedback; latest:Feedback;
  originatingJobId:string; createdAt:string;
}
export interface Submission { clipId:string; version:Version; feedback:Feedback; owners:string[]; deferred?:DeferredFeedback[] }
export interface Job { id:string; projectId:string; state:JobState; kind:'revision'|'build'; snapshot:Submission[]; request:string; dedupe:string; createdAt:string; updatedAt:string; error:string|null; agentSession:string|null }
export const now=()=>new Date().toISOString();
export const hash=(value:unknown)=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export function invariant(value:unknown,message:string):asserts value {if(!value) throw new Error(message)}
export function backend(value:unknown):Backend {invariant(BACKENDS.includes(value as Backend),'Unknown backend');return value as Backend}
export function routeRevision(text:string):string[] {
  // Conservative dependency routing; the agent reads the full request and confirms scope.
  const owners=new Set<string>(['edit']);
  if(/\b(cuts?|recut|trim|shorten|remove|passages?|spoken|sentences?|word ending|reorder|hook replacement)\b/i.test(text)) ['assembly-design','horizontal-to-vertical','caption-clips','text-hook','music','promo'].forEach(x=>owners.add(x));
  if(/caption|subtitle|font/i.test(text)) owners.add('caption-clips');
  if(/fram|crop|zoom|camera|\b(tracking|recenter|recentre|centered|centred)\b|\b(track|follow)\s+(the\s+)?(speaker|subject|face)\b/i.test(text)) owners.add('horizontal-to-vertical');
  if(/\b(split[ -]?screen|panels?|layouts?)\b/i.test(text)) {owners.add('assembly-design');owners.add('horizontal-to-vertical')}
  if(/music|audio|volume|sound/i.test(text)) owners.add('music');
  if(/headline|text hook/i.test(text)) owners.add('text-hook');
  if(/motion|animation|graphic/i.test(text)) owners.add('promo');
  return [...owners];
}
export interface MusicPlacement {
  id:string;sourceId:string;startFrame:number;sourceInSample:number;samples:number;gainDb:number;
  fadeInSamples?:number;fadeOutSamples?:number;receiptPath:string;receiptSha256:string;
}
export interface AudioPlan {gainDb?:number;music?:MusicPlacement[];properties?:Record<string,unknown>}
export interface FixedCrop {mode:'fixed-crop';sourceWidth:number;sourceHeight:number;x:number;y:number;width:number;height:number}
export interface TrackedCrop extends Omit<FixedCrop,'mode'> {mode:'tracked-crop';xByFrame:number[];sourceRange:{sourceId:string;sha256:string;inFrame:number;frames:number}}
export interface PanelLayout {
  mode:'panel-layout'; cameraReceiptPath:string; cameraReceiptSha256:string;
  panels:{id:string;sourceRange:{sourceId:string;sha256:string;inFrame:number;frames:number};
    rect:{x:number;y:number;width:number;height:number};crop:FixedCrop|TrackedCrop}[];
}
export interface FramingPlan {schema:'acq-edit/framing-v1';receiptPath:string;receiptSha256:string;shots:Record<string,FixedCrop|TrackedCrop|PanelLayout>}
export interface EditPlan {
  schema:'acq-edit/plan-v1'; projectId:string; backend:Backend; clipId:string; title:string;
  fps:{numerator:number;denominator:number}; width:number;height:number; sampleRate:number;
  brain:{receiptPath:string;sha256:string;versionsPath?:string;versionsSha256?:string}; editorial:{selectionPath:string;sha256:string;compiledPath?:string;compiledSha256?:string;execution?:{decisionsPath:string;decisionsSha256:string;routingPath:string;routingSha256:string;phonemesPath?:string;phonemesSha256?:string};reviewed:boolean};
  sources:Source[]; cuts:{id:string;sourceId:string;audioSourceId?:string;audioRecordSample?:number;sourceInFrame:number;frames:number;recordFrame:number;audioInSample:number;audioSamples:number;wordIds:string[];boundaryEvidence:string}[];
  captionContract?:{path:string;sha256:string;helperHashes:Record<string,string>};
  hookContract?:{path:string;sha256:string;helperSha256:string;basePlanFingerprint:string;baseReceipt:string;baseReceiptSha256:string};
  captions:{startFrame:number;endFrame:number;text:string;style:Record<string,unknown>}[];
  graphics:{path:string;startFrame:number;frames:number;sha256:string}[];
  framing:FramingPlan|Record<string,never>; audio:AudioPlan;
}
export function validatePlan(p:EditPlan,project:Project):void {
  invariant(p.schema==='acq-edit/plan-v1'&&p.projectId===project.id&&p.backend===project.backend,'Plan identity/backend mismatch');
  invariant(p.fps.numerator>0&&p.fps.denominator>0&&p.width>0&&p.height>0&&p.sampleRate>0,'Invalid sequence geometry');
  invariant(p.editorial.reviewed&&p.editorial.sha256&&p.brain.sha256,'Reviewed source-word selection and pinned brain receipt required');
  invariant(p.cuts.length>0,'Designed cuts required');let end=0;
  for(const cut of p.cuts){
    invariant(p.sources.some(s=>s.id===cut.sourceId&&s.projectId===project.id),'Unknown project source');
    invariant([cut.frames,cut.sourceInFrame,cut.recordFrame,cut.audioInSample,cut.audioSamples].every(Number.isSafeInteger),'Integer frame/sample timing required');
    invariant(cut.frames>0&&cut.sourceInFrame>=0&&cut.audioInSample>=0&&cut.audioSamples>0&&cut.recordFrame===end,'Cuts must form a contiguous sequence');
    if(cut.audioSourceId!==undefined){invariant(p.sources.some(s=>s.id===cut.audioSourceId&&s.projectId===project.id),'Unknown played-audio source');invariant(Number.isSafeInteger(cut.audioRecordSample)&&cut.audioRecordSample!>=0,'Exact audio record sample required')}
    invariant(cut.wordIds.length&&cut.boundaryEvidence,'Source words and inspected speech-boundary evidence required');
    end+=cut.frames;
  }
  for(const c of p.captions) invariant(c.startFrame>=0&&c.endFrame>c.startFrame&&c.endFrame<=end&&c.text.trim(),'Invalid caption range');
}

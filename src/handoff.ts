/** Bounded ACQ checkpoint handoff. Never convert arbitrary native projects or use a final MP4. */
import path from 'node:path';
import {isDeepStrictEqual} from 'node:util';
import {copyFile,mkdir,writeFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {Store} from './store.js';
import {type Config} from './config.js';
import {type EditPlan,invariant,validatePlan,hash} from './contracts.js';
import {atomicJson,containedFile,readJson,sha256} from './files.js';
import {createProject} from './projects.js';
import {importLocal} from './intake.js';
import {executeNative} from './native-operations.js';

export async function prepareHandoff(store:Store,config:Config,projectId:string,request:{planPath:string;destination:'premiere'|'filmcraft'},tools:{inspect?:typeof executeNative}={}){
 const p=store.project(projectId);invariant(config.backend===p.backend,'Use the source editor runtime');invariant(['premiere','filmcraft'].includes(p.backend)&&['premiere','filmcraft'].includes(request.destination)&&p.backend!==request.destination,'Choose the other supported editor');
 const input=await containedFile(p.root,request.planPath),digest=await sha256(input);
 const id=hash({projectId,destination:request.destination,planSha256:digest});
 const folder=path.join(p.root,'10_WORK','handoffs',id);await mkdir(folder,{recursive:true});
 const status=path.join(folder,'status.json');
 const busy=store.jobs(p.id).some(j=>['editing','rendering','reconciliation_required'].includes(j.state))||store.nativeOperations(p.id).some(o=>['running','reconciliation_required'].includes(o.state))||store.intakes(p.id).some(i=>!['ready','failed'].includes(i.state));
 if(busy){const result={id,state:'waiting-for-safe-checkpoint',request,reason:'Finish or reconcile the current operation, then resume with the latest valid plan. No process was interrupted and no editor was switched.'};await atomicJson(status,result);return result;}
 const spec=await readJson<EditPlan>(input);validatePlan(spec,p);
 const supported=new Set(['schema','projectId','backend','clipId','title','fps','width','height','sampleRate','brain','editorial','sources','cuts','captions','graphics','framing','audio','referenceStyle','captionContract','captionVisibility']);
 const unknown=Object.keys(spec).filter(k=>!supported.has(k));
 const stop=async(reason:string)=>{const value={id,state:'needs-editor-choice',request,reason};await atomicJson(status,value);return value};
 if(unknown.length)return stop('Unsupported checkpoint fields: '+unknown.join(', ')+'. Preserve them; ask the editor whether to omit or recreate them.');
 if(spec.graphics.length||spec.captionVisibility||spec.referenceStyle||Object.keys(spec.audio.properties||{}).length)return stop('This checkpoint includes graphics, visibility, reference effects or audio processing without a qualified cross-editor mapping. Ask the editor which effects to retain or recreate; no flattening was performed.');
 const versions=store.versions(spec.clipId),v=versions.find(x=>x.id===store.clip(spec.clipId).currentVersionId);
 const completions=store.jobs(p.id).flatMap(j=>j.nativeCompletions||[]) as any[];
 const native=v?{path:v.nativeProject,fingerprint:v.nativeReopen&&'expectedFingerprint' in v.nativeReopen?v.nativeReopen.expectedFingerprint:undefined,plan:v.planSha256}:completions.filter(x=>x.clipId===spec.clipId).at(0);
 const constructed=store.nativeOperations(p.id).some(o=>['build','revise','render'].includes(o.action)&&o.state==='succeeded');
 if(constructed&&!native)return stop('Native construction has no completed checkpoint. Save and inspect the latest state before changing editors.');
 let inspection:any=null;
 if(native){
  const nativePath=native.path||native.nativeProject,expected=native.fingerprint||native.nativeFingerprint;
  if(!expected&&!(p.backend==='filmcraft'&&v?.inspectionPath&&v.inspectionSha256))return stop('The historical checkpoint lacks a comparable native fingerprint. Inspect and adopt any manual edits first.');
  if(v&&v.planSha256!==digest)return stop('The requested plan is not the current completed checkpoint. Use the latest valid plan.');
  const packet=path.join(folder,'inspect-'+randomUUID()+'.json');await atomicJson(packet,{nativeProject:nativePath,...(p.backend==='filmcraft'?{session:path.join(folder,'inspect-session-'+randomUUID())}:{})});
  inspection=await (tools.inspect||executeNative)(store,config,p.id,'inspect',packet);
  let matches=inspection.fingerprint===expected;
  if(p.backend==='filmcraft'&&v?.inspectionPath&&v.inspectionSha256){
   invariant(await sha256(await containedFile(p.root,v.inspectionPath))===v.inspectionSha256,'Saved inspection changed');
   matches=inspection.fileHash===v.nativeFingerprint&&isDeepStrictEqual(inspection.state,await readJson(v.inspectionPath));
  }
  if(!matches)return stop('Intervening native edits differ from the saved editorial decisions. Ask the editor to adopt them into the plan or explicitly rebuild the saved checkpoint.');
 }
 // A portable evidence archive retains original bytes and an index, not rewritten hashes.
 const files=new Map<string,string>();
 async function visit(value:any):Promise<void>{
  if(typeof value==='string'&&path.isAbsolute(value)){
   const file=await containedFile(p.root,value);if(files.has(file))return;
   const sum=await sha256(file);files.set(file,sum);
   if(path.extname(file)==='.json')await visit(await readJson(file));
  }else if(Array.isArray(value)){for(const item of value)await visit(item)}
  else if(value&&typeof value==='object'){for(const item of Object.values(value))await visit(item)}
 }
 try{await visit(spec)}catch(error){return stop('Checkpoint evidence is not self-contained: '+(error as Error).message)}
 for(const source of spec.sources)invariant(await sha256(await containedFile(p.root,source.path))===source.sha256,'Source bytes changed');
 invariant(await sha256(input)===digest,'Plan changed while preparing handoff');
 store.assertNativeSettled(p.id);invariant(!store.jobs(p.id).some(j=>['editing','rendering','reconciliation_required'].includes(j.state)),'A job started during handoff preparation; resume after it settles');
 const checkpoint={schema:'acq-edit/editor-handoff-v1',id,sourceProject:p,destination:request.destination,planPath:input,planSha256:digest,plan:spec,files:[...files].map(([file,sha256])=>({path:file,sha256})),inspection,nativeReconstruction:'required',qualification:'native-cross-editor-rebuild-unverified'};
 const file=path.join(folder,'checkpoint.json');
 // Idempotent preparation keeps the original snapshot; changed inspection needs a new request.
 try{await writeFile(file,JSON.stringify(checkpoint,null,2),{flag:'wx'})}catch(e:any){if(e.code!=='EEXIST')throw e;const old=await readJson<any>(file);invariant(old.planSha256===digest&&old.destination===request.destination,'Existing handoff differs');}
 const result={id,state:'prepared',checkpoint:file,sha256:await sha256(file),qualification:checkpoint.qualification};await atomicJson(status,result);return result;
}

export async function importHandoff(store:Store,config:Config,file:string,tools:{intake?:typeof importLocal}={}){
 const checkpoint=await readJson<any>(file);invariant(checkpoint.schema==='acq-edit/editor-handoff-v1'&&checkpoint.destination===config.backend,'Handoff belongs to another editor runtime');
 invariant(await sha256(await containedFile(checkpoint.sourceProject.root,checkpoint.planPath))===checkpoint.planSha256,'Original plan changed since handoff');
 invariant(isDeepStrictEqual(await readJson(checkpoint.planPath),checkpoint.plan),'Handoff decisions differ from the pinned original plan');
 invariant(isDeepStrictEqual(await readJson(path.join(checkpoint.sourceProject.root,'project.json')),checkpoint.sourceProject),'Source project identity differs');
 validatePlan(checkpoint.plan,checkpoint.sourceProject);
 invariant(checkpoint.sourceProject.backend!==config.backend&&['filmcraft','premiere'].includes(config.backend),'Destination must be the other supported editor');
 invariant(checkpoint.id===hash({projectId:checkpoint.sourceProject.id,destination:checkpoint.destination,planSha256:checkpoint.planSha256}),'Handoff identity differs');
 for(const entry of checkpoint.files)invariant(await sha256(await containedFile(checkpoint.sourceProject.root,entry.path))===entry.sha256,'Handoff evidence changed');
 // Durable reservation before project creation. A crash never causes duplicate construction.
 store.db.exec('CREATE TABLE IF NOT EXISTS handoff_imports(id TEXT PRIMARY KEY,data TEXT NOT NULL)');
 const old=store.db.prepare('SELECT data FROM handoff_imports WHERE id=?').get(checkpoint.id);
 if(old)return {...JSON.parse(String(old.data)),resumed:true};
 const update=(value:any)=>{store.db.prepare('UPDATE handoff_imports SET data=? WHERE id=?').run(JSON.stringify(value),checkpoint.id);return value};
 store.db.prepare('INSERT INTO handoff_imports VALUES (?,?)').run(checkpoint.id,JSON.stringify({state:'preparing',reason:'Interrupted imports require reconciliation; do not create a second destination.'}));
 const p=await createProject(store,config.storageRoot,checkpoint.plan.title+' — '+config.backend,config.backend,config.agent);
 update({state:'preparing',projectId:p.id});
 try{
  const work=path.join(p.root,'10_WORK','handoff');await mkdir(work);
  const sources=[];
  for(const original of checkpoint.plan.sources){const source=await (tools.intake||importLocal)(store,p.id,original.path,'handoff:'+checkpoint.id);invariant(source.sha256===original.sha256,'Copied source differs');sources.push({originalId:original.id,source});}
  const evidence=[];
  for(const entry of checkpoint.files){if(checkpoint.plan.sources.some((s:any)=>s.path===entry.path))continue;const target=path.join(work,entry.sha256+path.extname(entry.path));try{await copyFile(entry.path,target,1)}catch(e:any){if(e.code!=='EEXIST')throw e}invariant(await sha256(target)===entry.sha256,'Copied evidence differs');evidence.push({...entry,copy:target});}
  const linked={...checkpoint,destinationProjectId:p.id,sources,evidence};const local=path.join(work,'checkpoint.json');await atomicJson(local,linked);
  const clip={id:randomUUID(),projectId:p.id,number:1,title:checkpoint.plan.title,currentVersionId:null};store.addClip(clip);
  const job=store.enqueueBuild(p.id,`Reconstruct ACQ checkpoint ${local} as clip ${clip.id} using this project's ${p.backend} native adapter. Read docs/EDITOR_HANDOFF.md. Preserve exact cuts, picture/audio clocks, captions, framing and audio decisions. Remap source IDs and evidence references through the copied index; recompile and revalidate owner contracts. Do not invent new editorial decisions or use the original finished MP4. Inspect for unsupported native effects; pause and explain before dropping or substituting anything. This is an unqualified handoff until native save/reopen and layer checks pass.`);
  return update({state:'reconstruction-queued',projectId:p.id,jobId:job.id,checkpoint:local,qualification:'awaiting-native-verification'});
 }catch(error){update({state:'reconciliation-required',projectId:p.id,reason:(error as Error).message});throw error;}
}

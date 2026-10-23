import path from 'node:path';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import { sendCommand, type BridgeOptions } from '../bridge/file-bridge.js';
import { buildToolScript } from '../bridge/script-builder.js';
import { SNAPSHOT_FUNCTION, labContext } from './context.js';
import { digest } from './runtime.js';
export const PROJECT_PAGE_SIZE = 50;
export const SNAPSHOT_ITEM_PAGE_SIZE = 50;
export const PROJECT_PAGE_BYTES = 1500000;
const q = (v: unknown) => JSON.stringify(v).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
export const PROJECT_INVENTORY_PAGE = `function __labInventoryPage(offset){
 var p=app.project;if(!p||!p.sequences)throw Error('PROJECT_SEQUENCES_UNAVAILABLE');
 var total=p.sequences.numSequences;if(total>2048)throw Error('PROJECT_INVENTORY_AGGREGATE_LIMIT');
 var r={project_path:String(p.path),active_sequence_id:p.activeSequence?String(p.activeSequence.sequenceID):null,total:total,offset:offset,rows:[]};
 for(var i=offset;i<Math.min(total,offset+50);i++){var s=p.sequences[i];r.rows.push({sequence_id:String(s.sequenceID),name:String(s.name)});}
 if(JSON.stringify(r).length>1500000)throw Error('PROJECT_INVENTORY_PAGE_LIMIT');return r;
}`;
async function read(options: BridgeOptions, body: string) {
 // Inspection only: each page binds the exact project and native sequence. The
 // actual mutation still uses the unchanged active-target guard plus complete
 // paginated prior-state comparisons. Never dispatch an editing handler here.
 const result = await labContext.exit(() => sendCommand(buildToolScript(body), { ...options, pagedResponse:true }));
 if (!result.success) throw Error('PAGED_PROJECT_NATIVE_READ_FAILED: '+(result as any).error);
 if (!result.data || typeof result.data !== 'object' || Array.isArray(result.data)) throw Error('PAGED_PROJECT_INVALID_RESPONSE');
 if (Buffer.byteLength(JSON.stringify(result.data),'utf8')>PROJECT_PAGE_BYTES) throw Error('PAGED_PROJECT_RESPONSE_PAGE_LIMIT');
 return result.data as any;
}
export async function readProjectInventory(options: BridgeOptions, project: string) {
 let first:any, rows:any[]=[];
 for(let offset=0;!first||offset<first.total;offset+=PROJECT_PAGE_SIZE){
  const p=await read(options,`${PROJECT_INVENTORY_PAGE}\nif(!app.project||String(app.project.path)!==${q(project)})throw Error('PROJECT_TARGET_CHANGED');return __result(__labInventoryPage(${offset}));`);
  if(p.project_path!==project||p.offset!==offset||!Number.isInteger(p.total)||p.total<0||p.total>2048||!Array.isArray(p.rows)||p.rows.length!==Math.min(PROJECT_PAGE_SIZE,p.total-offset)||!(p.active_sequence_id===null||typeof p.active_sequence_id==='string'))throw Error('PAGED_PROJECT_INVENTORY_INVALID');
  if(first&&(p.total!==first.total||p.active_sequence_id!==first.active_sequence_id))throw Error('PROJECT_CHANGED_DURING_PAGED_INSPECTION');
  first??=p;rows.push(...p.rows);if(p.total===0)break;
 }
 const ids=rows.map(r=>r.sequence_id);
 if(rows.some(r=>!r||typeof r.sequence_id!=='string'||!r.sequence_id||r.sequence_id==='undefined'||typeof r.name!=='string')||new Set(ids).size!==ids.length||first.active_sequence_id!==null&&!ids.includes(first.active_sequence_id))throw Error('PAGED_PROJECT_SEQUENCE_ID_AMBIGUOUS');
 return {project_path:project,active_sequence_id:first.active_sequence_id,sequences:rows};
}
export async function readSequencePages(options: BridgeOptions, project:string, id:string) {
 const pages:any[]=[];let total:number|undefined, assembled:any,limit=SNAPSHOT_ITEM_PAGE_SIZE;
 for(let offset=0;total===undefined||offset<total;offset+=limit){
  let p:any;limit=SNAPSHOT_ITEM_PAGE_SIZE;while(true){try{p=await read(options,`${SNAPSHOT_FUNCTION}\nif(!app.project||String(app.project.path)!==${q(project)})throw Error('PROJECT_TARGET_CHANGED');var seq=null;for(var i=0;i<app.project.sequences.numSequences;i++)if(String(app.project.sequences[i].sequenceID)===${q(id)}){if(seq)throw Error('PROJECT_SEQUENCE_ID_AMBIGUOUS');seq=app.project.sequences[i];}if(!seq)throw Error('PAGED_SEQUENCE_REMOVED');return __result(__labSnapshot(seq,{offset:${offset},limit:${limit}}));`);;break;}catch(e){if(!/LAB_SNAPSHOT_PAGE_SIZE_LIMIT|PAGED_PROJECT_RESPONSE_PAGE_LIMIT/.test(String(e))||limit===1)throw e;limit=Math.max(1,Math.floor(limit/2));}}
  const cursor=p._paging;
  if(p.projectPath!==project||p.sequenceId!==id||!cursor||cursor.offset!==offset||cursor.limit!==limit||!Number.isInteger(cursor.total)||cursor.total<0||cursor.total>10000||!Array.isArray(p.tracks))throw Error('PAGED_SEQUENCE_RESPONSE_INVALID');
  if(total!==undefined&&total!==cursor.total)throw Error('PAGED_SEQUENCE_COUNT_CHANGED');total=cursor.total;
  const metadata={...p};delete metadata._paging;metadata.tracks=p.tracks.map((t:any)=>({...t,clips:[]}));
  if(!assembled){assembled=structuredClone(metadata);}else{
   const baseline={...assembled,tracks:assembled.tracks.map((t:any)=>({...t,clips:[]}))};
   if(digest(metadata)!==digest(baseline))throw Error('PAGED_SEQUENCE_METADATA_CHANGED');
  }
  let pageCount=0;
  for(let t=0;t<p.tracks.length;t++){
   const tr=p.tracks[t];if(!Array.isArray(tr.clips)||!Number.isInteger(tr._clip_total)||tr._clip_total<0)throw Error('PAGED_TRACK_INVALID');
   pageCount+=tr.clips.length;assembled.tracks[t].clips.push(...tr.clips);
  }
  if(pageCount!==Math.min(limit,cursor.total-offset))throw Error('PAGED_SEQUENCE_MISSING_OR_DUPLICATE_ITEMS');
  pages.push(p);if(total===0)break;
 }
 const ids:string[]=[];
 for(const tr of assembled.tracks){if(tr.clips.length!==tr._clip_total)throw Error('PAGED_TRACK_COVERAGE_INCOMPLETE');delete tr._clip_total;for(const c of tr.clips){if(typeof c.id!=='string'||!c.id)throw Error('PAGED_ITEM_ID_INVALID');ids.push(c.id);}}
 if(new Set(ids).size!==ids.length||ids.length!==total)throw Error('PAGED_ITEM_ID_AMBIGUOUS');
 return {snapshot:assembled,pages};
}
export async function inspectPagedProject(options:BridgeOptions,project:string){
 const pass=async()=>{
  const inventory=await readProjectInventory(options,project);const sequences:any[]=[];const pagesBySequence:any[]=[];
  for(const row of inventory.sequences){const s=await readSequencePages(options,project,row.sequence_id);sequences.push({...row,snapshot:s.snapshot});pagesBySequence.push({sequence_id:row.sequence_id,pages:s.pages});}
  const after=await readProjectInventory(options,project);if(digest(inventory)!==digest(after))throw Error('PROJECT_INVENTORY_CHANGED_DURING_PAGED_INSPECTION');
  return {state:{project_path:project,active_sequence_id:inventory.active_sequence_id,sequences},pagesBySequence};
 };
 const a=await pass(),b=await pass();if(digest(a.state)!==digest(b.state))throw Error('PROJECT_CHANGED_DURING_PAGED_INSPECTION');
 return {...b.state,revision:digest(b.state),verification:'stable_complete_paged_all_sequence_snapshots'};
}

export async function cacheGuardSnapshot(options:BridgeOptions,snapshot:any,pages:any[]){
 if(!options.tempDir)throw Error('GUARD_PRIVATE_CACHE_REQUIRED');
 const folder=path.join(options.tempDir,'prepared-inputs','guard-pages');await mkdir(folder,{recursive:true,mode:0o700});
 const manifest:any={projectPath:snapshot.projectPath,sequenceId:snapshot.sequenceId,tracks:[],snapshotEncoding:'complete-native-pages-v2',pages:[]};
 for(const page of pages){const raw=JSON.stringify(page),sha=digest(page),file=path.join(folder,sha+'.json');if(Buffer.byteLength(raw,'utf8')>PROJECT_PAGE_BYTES)throw Error('GUARD_PAGE_SIZE_LIMIT');try{await writeFile(file,raw,{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}if(digest(JSON.parse(await readFile(file,'utf8')))!==sha)throw Error('GUARD_CACHE_CHANGED');manifest.pages.push({...page._paging,sha256:sha,path:file});}
 const raw=JSON.stringify(manifest),file=path.join(folder,'manifest-'+digest(manifest)+'.json');try{await writeFile(file,raw,{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}return manifest;
}
export async function readPagedGuardSnapshot(options:BridgeOptions){
 const p=await read(options,`${PROJECT_INVENTORY_PAGE}\nreturn __result(__labInventoryPage(0));`);
 if(!p.active_sequence_id)throw Error('PAGED_GUARD_OWNED_SEQUENCE_REQUIRED');
 const data=await readSequencePages(options,p.project_path,p.active_sequence_id);
 return cacheGuardSnapshot(options,data.snapshot,data.pages);
}
export async function inspectPagedGuardProject(options:BridgeOptions,project:string){
 const pass=async()=>{const inventory=await readProjectInventory(options,project),sequences=[];
 for(const row of inventory.sequences){const data=await readSequencePages(options,project,row.sequence_id);sequences.push({...row,snapshot:await cacheGuardSnapshot(options,data.snapshot,data.pages)});}
 if(digest(inventory)!==digest(await readProjectInventory(options,project)))throw Error('PROJECT_INVENTORY_CHANGED_DURING_PAGED_INSPECTION');
 return {project_path:project,active_sequence_id:inventory.active_sequence_id,sequences};};
 const a=await pass(),b=await pass();if(digest(a)!==digest(b))throw Error('PROJECT_CHANGED_DURING_PAGED_INSPECTION');
 if(!options.tempDir)throw Error('GUARD_PRIVATE_CACHE_REQUIRED');const folder=path.join(options.tempDir,'prepared-inputs','guard-pages'),file=path.join(folder,'project-'+digest(b)+'.json');try{await writeFile(file,JSON.stringify(b),{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}
 return {...b,revision:digest(b),verification:'stable_complete_paged_all_sequence_snapshots'};
}

// Only an immutable baseline is cached. CEP still compares every current native
// effect/timing/identity page atomically before dispatching the mutation body.
export async function readCachedPagedBaseline(options:BridgeOptions,revision:string){
 if(!options.tempDir||!/^[a-f0-9]{64}$/.test(revision))return undefined;
 const file=path.join(options.tempDir,'prepared-inputs','guard-pages','manifest-'+revision+'.json');let raw:string;
 try{raw=await readFile(file,'utf8');}catch(e:any){if(e.code==='ENOENT')return undefined;throw e;}
 const state=JSON.parse(raw);if(digest(state)!==revision||state.snapshotEncoding!=='complete-native-pages-v2'||!Array.isArray(state.pages)||!state.pages.length)throw Error('GUARD_BASELINE_CACHE_CHANGED');
 for(const page of state.pages){if(path.dirname(page.path)!==path.dirname(file)||path.basename(page.path)!==page.sha256+'.json'||digest(JSON.parse(await readFile(page.path,'utf8')))!==page.sha256)throw Error('GUARD_BASELINE_CACHE_CHANGED');}
 return state;
}

export async function readCachedPagedProject(options:BridgeOptions,revision:string,project:string){
 if(!options.tempDir||!/^[a-f0-9]{64}$/.test(revision))return undefined;
 const file=path.join(options.tempDir,'prepared-inputs','guard-pages','project-'+revision+'.json');let raw:string;try{raw=await readFile(file,'utf8');}catch(e:any){if(e.code==='ENOENT')return undefined;throw e;}
 const state=JSON.parse(raw);if(digest(state)!==revision||state.project_path!==project||!Array.isArray(state.sequences)||state.sequences.length>50)throw Error('PROJECT_BASELINE_CACHE_CHANGED');
 for(const row of state.sequences){if(row.snapshot.projectPath!==project||row.snapshot.sequenceId!==row.sequence_id||!await readCachedPagedBaseline(options,digest(row.snapshot)))throw Error('PROJECT_BASELINE_CACHE_CHANGED');}
 return {...state,revision,verification:'cached_complete_paged_baseline_native_atomic_recheck_required'};
}

import path from 'node:path';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {parse} from 'acorn';
import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {PAGED_COMPARE_FUNCTION,labContext} from './context.js';
import {PROJECT_SEQUENCES_PAGED_SNAPSHOT,getLabProjectStateTools} from './project-state.js';
import {readCachedPagedProject,cacheGuardSnapshot} from './project-state-paged.js';
import {validateTransfer,stagePrepared,NATIVE_STATE_COMPARE,type TransferRequest} from './caption-transfer.js';
import {mediaHash} from './music-placement.js';
import {digest} from './runtime.js';
export async function importCaptionBatch(options:BridgeOptions,args:TransferRequest & {additional_sequences?:TransferRequest[]}){
 const ctx=labContext.getStore();if(!ctx||ctx.snapshotMode!=='paged'||!options.tempDir)return {success:false,error:'COMPLETE_PAGED_CAPTION_GUARD_REQUIRED'};
 const {additional_sequences,...first}=args;const requests=[first,...(additional_sequences||[])];if(requests.length>6)return {success:false,error:'CAPTION_BATCH_LIMIT'};
 let state:any;const staged:string[]=[];
 try{
  for(const r of requests){validateTransfer(r);if(r.expected_project_revision!==args.expected_project_revision)throw Error('CAPTION_BATCH_BASELINE_MISMATCH');staged.push(await stagePrepared(r.prepared_path,r.prepared_sha256,options.tempDir,ctx.projectPath));}
  let data=await readCachedPagedProject(options,args.expected_project_revision,ctx.projectPath);
  if(!data){const result:any=await getLabProjectStateTools(options).inspect_project_sequences.handler({project_path:ctx.projectPath,paged_digest:true});if(!result.success)throw Error(result.error);data=result.data;}
  if(data.revision!==args.expected_project_revision||data.active_sequence_id!==ctx.sequenceId)throw Error('PROJECT_STATE_STALE');
  const ids=requests.map(r=>r.sequence_id),names=requests.map(r=>r.sequence_name);if(new Set(ids).size!==ids.length||new Set(names).size!==names.length||data.sequences.some((s:any)=>ids.includes(s.sequence_id)||names.includes(s.name)))throw Error('PREPARED_SEQUENCE_ALREADY_PRESENT');
  const {revision,verification,...before}=data;state=before;
 }catch(e){return {success:false,error:String(e)};}
 const folder=path.join(options.tempDir,'prepared-inputs'),input={requests,staged,before:state},file=path.join(folder,'caption-batch-'+digest(input)+'.json');await mkdir(folder,{recursive:true,mode:0o700});
 if(Buffer.byteLength(JSON.stringify(input),'utf8')>1500000)return {success:false,error:'CAPTION_BATCH_INPUT_PAGE_LIMIT'};
 try{await writeFile(file,JSON.stringify(input),{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}if(digest(JSON.parse(await readFile(file,'utf8')))!==digest(input))return {success:false,error:'CAPTION_BATCH_PRIVATE_INPUT_CHANGED'};
 const literal=JSON.stringify(file);
 const script=buildToolScript(`${PAGED_COMPARE_FUNCTION}\n${NATIVE_STATE_COMPARE}\n${PROJECT_SEQUENCES_PAGED_SNAPSHOT}
 var r=__labReadGuardPage(${literal}),before=__labProjectSequences(),old={},names={},outputs=[],captures={};
 if(!same(JSON.parse(JSON.stringify(before)),r.before))throw Error('PROJECT_CHANGED_BEFORE_TRANSFER');
 for(var i=0;i<before.sequences.length;i++)old['id:'+before.sequences[i].sequence_id]=before.sequences[i];
 for(var i=0;i<r.requests.length;i++){var want=r.requests[i],file=new File(r.staged[i]);if(!file.exists)throw Error('STAGED_PROJECT_MISSING');app.project.importSequences(file.fsName,[want.sequence_id]);}
 // Preserve every old sequence with the complete page comparator. New sequences
 // are captured pagewise rather than weakening the old full-snapshot byte cap.
 var p=app.project;if(String(p.path)!==before.project_path||!p.activeSequence||String(p.activeSequence.sequenceID)!==before.active_sequence_id||p.sequences.numSequences!==before.sequences.length+r.requests.length)throw Error('PROJECT_OR_SEQUENCE_SET_CHANGED_DURING_TRANSFER');
 for(var i=0;i<p.sequences.numSequences;i++){var s=p.sequences[i],prior=old['id:'+String(s.sequenceID)];if(prior){if(String(s.name)!==prior.name||!__labVerifyPages(prior.snapshot,s,same))throw Error('PROTECTED_SEQUENCE_CHANGED');delete old['id:'+String(s.sequenceID)];}}
 for(var k in old)if(Object.prototype.hasOwnProperty.call(old,k))throw Error('PROTECTED_SEQUENCE_REMOVED');
 for(var ri=0;ri<r.requests.length;ri++){
  var want=r.requests[ri],s=null,count=0;for(var i=0;i<p.sequences.numSequences;i++)if(String(p.sequences[i].sequenceID)===want.sequence_id){s=p.sequences[i];count++;}
  if(count!==1||String(s.name)!==want.sequence_name)throw Error('IMPORTED_SEQUENCE_IDENTITY');var settings=s.getSettings();if(settings.videoFrameWidth!==want.width||settings.videoFrameHeight!==want.height||String(s.timebase)!==want.frame_duration_ticks)throw Error('IMPORTED_CANVAS_OR_RATE');
  var captured=__labCapturePages(s),metadata=captured.nativePages[0];if(!same(metadata.markers,want.markers)||s.videoTracks.numTracks+s.audioTracks.numTracks!==want.tracks.length)throw Error('IMPORTED_MARKERS_OR_TRACK_COUNT');var mapping=[],seen={};
  for(var ti=0;ti<want.tracks.length;ti++){var wt=want.tracks[ti],tracks=wt.kind==='video'?s.videoTracks:s.audioTracks,tr=tracks[wt.index];if(!tr||String(tr.name)!==wt.name||flag(tr.isMuted())!==wt.muted||flag(tr.isLocked())!==wt.locked||tr.clips.numItems!==wt.items.length||!tr.transitions||tr.transitions.numItems!==0)throw Error('IMPORTED_TRACK_STATE');
   for(var j=0;j<wt.items.length;j++){var e=wt.items[j],item=tr.clips[j],id=String(item.nodeId),source=item.projectItem;if(!id||id==='undefined'||seen['id:'+id])throw Error('IMPORTED_ITEM_IDENTITY');seen['id:'+id]=true;
    if(String(item.start.ticks)!==e.start_ticks||String(item.end.ticks)!==e.end_ticks||String(item.inPoint.ticks)!==e.source_in_ticks||String(item.outPoint.ticks)!==e.source_out_ticks||item.getSpeed()!==e.speed||flag(item.isSpeedReversed())!==e.speed_reversed||flag(item.disabled)!==e.disabled)throw Error('IMPORTED_ITEM_CLOCK');var matches=[];for(var ci=0;ci<item.components.numItems;ci++)matches.push(String(item.components[ci].matchName));if(!same(matches,e.component_match_names))throw Error('IMPORTED_COMPONENT_CHAIN');
    if(e.source_kind==='media'){if(!source||source.isSequence()||source.isOffline()||normalPath(source.getMediaPath())!==normalPath(e.media_path))throw Error('IMPORTED_SOURCE_LINK');}else{var tc=0;for(var ci=0;ci<matches.length;ci++)if(matches[ci]==='AE.ADBE Text')tc++;if(tc!==1)throw Error('IMPORTED_GRAPHIC_TEXT_COUNT');}
    mapping.push({token:e.token,node_id:id,source_id:source?String(source.nodeId):null,kind:wt.kind,track_index:wt.index,item_index:j});
   }
  }
  if(!__labVerifyPages(captured,s,same))throw Error('IMPORTED_STATE_CHANGED_DURING_READBACK');captures['id:'+want.sequence_id]=captured;outputs.push({sequence_id:want.sequence_id,sequence_name:want.sequence_name,mapping:mapping,pages:[]});
 }
 // One final complete comparison of old and new, then persist bounded inspection
 // pages under unique private paths for Node hashing and archival, never edits.
 for(var i=0;i<p.sequences.numSequences;i++){var s=p.sequences[i],prior=null,cap=captures['id:'+String(s.sequenceID)];for(var j=0;j<r.before.sequences.length;j++)if(r.before.sequences[j].sequence_id===String(s.sequenceID))prior=r.before.sequences[j];if(prior){if(String(s.name)!==prior.name||!__labVerifyPages(prior.snapshot,s,same))throw Error('PROTECTED_STATE_CHANGED_DURING_READBACK');}else if(!cap||!__labVerifyPages(cap,s,same))throw Error('NEW_SEQUENCE_CHANGED_DURING_READBACK');}
 for(var oi=0;oi<outputs.length;oi++){var cap=captures['id:'+outputs[oi].sequence_id];for(var pi=0;pi<cap.nativePages.length;pi++){var name=${literal}+'.native-'+oi+'-'+pi+'.json',file=new File(name);if(file.exists)throw Error('NATIVE_CAPTURE_EXISTS');file.encoding='UTF-8';if(!file.open('w'))throw Error('NATIVE_CAPTURE_OPEN');file.write(JSON.stringify(cap.nativePages[pi]));file.close();outputs[oi].pages.push(name);}}
 return __result({project_path:String(p.path),active_sequence_id:String(p.activeSequence.sequenceID),sequences:outputs,verification:'complete_prior_and_new_native_pages_and_declared_tracks',decoded_text:'saved_file_verification_required',persistence:'not_run',rendered:'not_run'});
 `);
 try{parse(script,{ecmaVersion:3,allowReserved:false});}catch(e){return {success:false,error:'ES3_SYNTAX_REJECTED_BEFORE_DISPATCH: '+String(e)};}
 if(Buffer.byteLength(script,'utf8')>450000)return {success:false,error:'CAPTION_BATCH_SCRIPT_LIMIT'};
 const result=await sendCommand(script,{...options,timeoutMs:3600000});
 for(let i=0;i<requests.length;i++)if(await mediaHash(staged[i])!==requests[i].prepared_sha256||await mediaHash(requests[i].prepared_path)!==requests[i].prepared_sha256)return {success:false,error:'PREPARED_INPUT_CHANGED_AFTER_DISPATCH',native_result:result};
 if(!result.success)return result;const data:any=result.data;if(data?.project_path!==state.project_path||!Array.isArray(data.sequences)||data.sequences.length!==requests.length)return {success:false,error:'INVALID_CAPTION_BATCH_RESULT',native_result:result};
 // Validate every private native page's full count/identity before caching.
 const rows=[];
 for(let i=0;i<requests.length;i++){const row=data.sequences[i],want=requests[i];if(row.sequence_id!==want.sequence_id||row.sequence_name!==want.sequence_name||!Array.isArray(row.pages))throw Error('INVALID_NATIVE_CAPTION_IDENTITY');const pages=[];let offset=0,total:number|undefined,snapshot:any;
  for(const pagePath of row.pages){if(path.dirname(pagePath)!==folder||!path.basename(pagePath).startsWith(path.basename(file)+'.native-'+i+'-'))throw Error('FOREIGN_NATIVE_CAPTURE_PATH');const raw=await readFile(pagePath,'utf8');if(Buffer.byteLength(raw,'utf8')>1500000)throw Error('NATIVE_CAPTURE_PAGE_LIMIT');const p=JSON.parse(raw),c=p._paging;if(p.projectPath!==state.project_path||p.sequenceId!==row.sequence_id||!c||c.offset!==offset||c.limit<1||c.limit>50||total!==undefined&&total!==c.total)throw Error('NATIVE_CAPTURE_PAGE_IDENTITY');total=c.total;offset+=c.limit;pages.push(p);snapshot??={...p,tracks:p.tracks.map((t:any)=>({...t,clips:[]}))};for(let ti=0;ti<p.tracks.length;ti++)snapshot.tracks[ti].clips.push(...p.tracks[ti].clips);}
  if(total===undefined||offset<total||snapshot.tracks.some((t:any)=>t.clips.length!==t._clip_total))throw Error('NATIVE_CAPTURE_INCOMPLETE');delete snapshot._paging;for(const t of snapshot.tracks)delete t._clip_total;const manifest=await cacheGuardSnapshot(options,snapshot,pages);rows.push({sequence_id:row.sequence_id,name:row.sequence_name,snapshot:manifest});row.snapshot=manifest;row.sequence_revision=digest(manifest);
 }
 const after={...state,sequences:[...state.sequences,...rows]},revision=digest(after),projectCache=path.join(folder,'guard-pages','project-'+revision+'.json');try{await writeFile(projectCache,JSON.stringify(after),{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}
 return {...result,data:{...data,project_revision:revision,project_snapshot:after,prepared_hashes:requests.map(r=>r.prepared_sha256)}};
}

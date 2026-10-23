// One guarded import transaction for up to three independent original v2 chains.
// All existing sequences are compared in complete bounded native pages before
// and after; inputs remain compiler-reproduced and every new AV pair is checked.
import path from 'node:path';
import {parse} from 'acorn';
import {mkdir,readFile,writeFile,stat} from 'node:fs/promises';
import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {PAGED_COMPARE_FUNCTION,labContext} from './context.js';
import {PROJECT_SEQUENCES_PAGED_SNAPSHOT,getLabProjectStateTools} from './project-state.js';
import {readCachedPagedProject} from './project-state-paged.js';
import {ASSEMBLY_LINK_SNAPSHOT} from './assembly-links.js';
import {NATIVE_STATE_COMPARE} from './caption-transfer.js';
import {SNAPSHOT_UNPACK,packSnapshot} from './snapshot-packing.js';
import {validateCompiledAssembly,checkCompilerArtifacts,type AssemblyRequest,type CompilerProof} from './assembly-provenance.js';
import {mediaHash} from './music-placement.js';
import {digest} from './runtime.js';
import {readCoverage,prepareCoverage,COVERAGE_NATIVE,type CoverageInput} from './assembly-coverage.js';
export type AdditionalAssembly = Omit<AssemblyRequest,'expected_project_revision'>;
export async function importAssemblyBatch(options:BridgeOptions,args:AssemblyRequest & {additional_assemblies:AdditionalAssembly[];target_canvas?:{width:number;height:number};coverage?:CoverageInput}){
 const ctx=labContext.getStore();if(!ctx||ctx.snapshotMode!=='paged'||!options.tempDir)return {success:false,error:'COMPLETE_PAGED_BATCH_GUARD_REQUIRED'};
 if(!Array.isArray(args.additional_assemblies)||args.additional_assemblies.length<1||args.additional_assemblies.length>2)return {success:false,error:'BOUNDED_ADDITIONAL_ASSEMBLIES_REQUIRED'};
 if(args.target_canvas&&(args.target_canvas.width!==1920||args.target_canvas.height!==1080))return {success:false,error:'BOUNDED_HORIZONTAL_CANVAS_REQUIRED'};
 const requests:AssemblyRequest[]=[args,...args.additional_assemblies.map(x=>({...x,expected_project_revision:args.expected_project_revision}))],proofs:CompilerProof[]=[],staged:string[]=[],stagedHashes:string[]=[],adapterHashes:string[]=[];let state:any,requestFile:string,coverage:any,coverageRows:any[]=[];
 try{
  for(const request of requests){for(const p of [request.xml_path,request.expected_path,request.resolved_path])if(typeof p!=='string'||!path.isAbsolute(p)||p.includes('\0')||p.length>4096)throw Error('Invalid compiler artifact path');for(const h of [request.xml_sha256,request.expected_sha256,request.resolved_sha256,request.expected_project_revision])if(typeof h!=='string'||!/^[a-f0-9]{64}$/.test(h))throw Error('Invalid compiler artifact hash');if(!Number.isInteger(request.gap_frames)||request.gap_frames<0||request.gap_frames>2147483647)throw Error('Invalid compiler gap');proofs.push(await validateCompiledAssembly(request,path.join(path.dirname(options.tempDir),'fixtures')));}
  let data=await readCachedPagedProject(options,args.expected_project_revision,ctx.projectPath);
  if(!data){const result=await getLabProjectStateTools(options).inspect_project_sequences.handler({project_path:ctx.projectPath,paged_digest:true});if(!result.success)throw Error('Complete project preflight failed: '+(result as any).error);data=(result as any).data;}
  if(data.revision!==args.expected_project_revision||data.active_sequence_id!==ctx.sequenceId)throw Error('PROJECT_STATE_STALE');
  if(args.coverage)coverage=await readCoverage(args.coverage,data);
  const names=proofs.map(p=>p.expectation.sequence_name);if(new Set(names).size!==names.length||data.sequences.some((s:any)=>names.includes(s.name)))throw Error('ASSEMBLY_SEQUENCE_ALREADY_PRESENT');
  const {revision,verification,...before}=data;state=before;
  const folder=path.join(options.tempDir,'prepared-inputs');await mkdir(folder,{recursive:true,mode:0o700});
  for(let i=0;i<requests.length;i++){const request=requests[i],file=path.join(folder,request.xml_sha256+'.xml');try{await writeFile(file,await readFile(request.xml_path),{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}await checkCompilerArtifacts(proofs[i]);if(await mediaHash(file)!==request.xml_sha256)throw Error('STAGED_XML_CHANGED');if(coverage){const prepared=await prepareCoverage(request,proofs[i],coverage,folder);staged.push(prepared.path);stagedHashes.push(prepared.sha256);adapterHashes.push(prepared.adapter_sha256);coverageRows.push(prepared.items);}else {staged.push(file);stagedHashes.push(request.xml_sha256);}}
 }catch(e){return {success:false,error:String(e)};}
 const commandInput={expected:proofs.map(p=>p.expectation),before:state,staged,target_canvas:args.target_canvas,coverage,coverageRows};requestFile=path.join(options.tempDir,'prepared-inputs','batch-'+digest(commandInput)+'.json');try{await writeFile(requestFile,JSON.stringify(commandInput),{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}if(digest(JSON.parse(await readFile(requestFile,'utf8')))!==digest(commandInput))return {success:false,error:'BATCH_COMMAND_INPUT_CHANGED'};
 const literal=JSON.stringify(requestFile).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
 const script=buildToolScript(`${PAGED_COMPARE_FUNCTION}\n${PROJECT_SEQUENCES_PAGED_SNAPSHOT}\n${ASSEMBLY_LINK_SNAPSHOT}\n${COVERAGE_NATIVE}\n${NATIVE_STATE_COMPARE}\n${SNAPSHOT_UNPACK}
 var r=__labReadGuardPage(${literal});var before=__labProjectSequences();
 if(!same(JSON.parse(JSON.stringify(before)),r.before))throw Error('PROJECT_CHANGED_BEFORE_ASSEMBLY_IMPORT');
 if(r.coverage)verifyCoverageAnchors(r.coverage);
 var old={},names={},added=[];for(var i=0;i<before.sequences.length;i++){var row=before.sequences[i];old['id:'+row.sequence_id]=row;names['name:'+row.name]=true;}
 for(var i=0;i<r.expected.length;i++){if(names['name:'+r.expected[i].sequence_name])throw Error('ASSEMBLY_SEQUENCE_ALREADY_PRESENT');names['name:'+r.expected[i].sequence_name]=true;}
 for(var i=0;i<r.staged.length;i++){var file=new File(r.staged[i]);if(!file.exists||!app.project.importFiles([file.fsName],true,app.project.rootItem,false))throw Error('ASSEMBLY_BATCH_IMPORT_PARTIAL_OR_UNCONFIRMED');}
 var after=__labProjectSequences();if(after.project_path!==before.project_path||after.active_sequence_id!==before.active_sequence_id)throw Error('PROJECT_OR_ACTIVATION_CHANGED_DURING_ASSEMBLY_IMPORT');
 for(var i=0;i<after.sequences.length;i++){var row=after.sequences[i],prior=old['id:'+row.sequence_id];if(prior){if(!same(row,prior))throw Error('PROTECTED_SEQUENCE_CHANGED');delete old['id:'+row.sequence_id];}else added.push(row);}
 for(var k in old)if(Object.prototype.hasOwnProperty.call(old,k))throw Error('PROTECTED_SEQUENCE_REMOVED');if(added.length!==r.expected.length)throw Error('UNEXPECTED_ASSEMBLY_SEQUENCE_SET');
 var outputs=[];
 for(var ei=0;ei<r.expected.length;ei++){
 var e=r.expected[ei],imported=null,s=null;for(var i=0;i<added.length;i++)if(added[i].name===e.sequence_name){if(imported)throw Error('ASSEMBLY_NAME_AMBIGUOUS');imported=added[i];}
 if(!imported)throw Error('ASSEMBLY_BATCH_MEMBER_MISSING');for(var i=0;i<app.project.sequences.numSequences;i++)if(String(app.project.sequences[i].sequenceID)===imported.sequence_id)s=app.project.sequences[i];if(!s)throw Error('IMPORTED_ASSEMBLY_UNRESOLVED');
 if(imported.snapshot.settings.videoFrameWidth!==e.width||imported.snapshot.settings.videoFrameHeight!==e.height)throw Error('ASSEMBLY_CANVAS_MISMATCH');
 var markers=[];for(var i=0;i<e.markers.length;i++){var m=e.markers[i];markers.push({name:m.name,comments:m.comments,start:m.start_ticks,end:m.start_ticks});}if(!same(imported.snapshot.markers,markers))throw Error('ASSEMBLY_MARKER_MISMATCH');
 for(var k=0;k<2;k++){var tracks=k?s.audioTracks:s.videoTracks;for(var t=0;t<tracks.numTracks;t++)if(!tracks[t].transitions||tracks[t].transitions.numItems!==0||flag(tracks[t].isMuted())||flag(tracks[t].isLocked()))throw Error('ASSEMBLY_TRACK_STATE_MISMATCH');}
 if(r.coverage){conformCoverage(s,r.coverageRows[ei]);imported.snapshot=__labSnapshot(s);}
 var links=__labAssemblyLinks(after.project_path,imported.sequence_id),found={},mapping=[];if(links.frame_duration_ticks!==e.frame_ticks||links.items.length!==e.items.length*2+(r.coverage?r.coverageRows[ei].length:0))throw Error('ASSEMBLY_RATE_OR_ITEM_COUNT_MISMATCH');
 for(var i=0;i<links.items.length;i++){var row=links.items[i];if(row.track_index!==0){if(!r.coverage)throw Error('ASSEMBLY_ITEM_ON_UNEXPECTED_TRACK');continue;}found[row.kind+':'+row.item_index]=row;}
 for(var i=0;i<e.items.length;i++){var want=e.items[i],v=found['video:'+i],a=found['audio:'+i];if(!v||!a||!v.item.source_id||v.item.source_id!==a.item.source_id)throw Error('ASSEMBLY_PAIRED_SOURCE_MISMATCH');if(!same(v.linked_node_ids,[a.item.node_id])||!same(a.linked_node_ids,[v.item.node_id]))throw Error('ASSEMBLY_NATIVE_AV_LINK_MISMATCH');
 for(var k=0;k<2;k++){var c=(k?a:v).item;if(normalPath(c.media_path)!==normalPath(want.media_path)||c.offline!==false||c.speed!==1||c.speed_reversed!==false||c.disabled!==false||c.start_ticks!==want.start_ticks||c.end_ticks!==want.end_ticks||c.source_in_ticks!==want.source_in_ticks||c.source_out_ticks!==want.source_out_ticks)throw Error('ASSEMBLY_SOURCE_OR_CLOCK_MISMATCH');}
 mapping.push({assembly_item_index:i,clip_id:want.clip_id,video_node_id:v.item.node_id,audio_node_id:a.item.node_id,source_node_id:v.item.source_id});}
 var coverageMap=r.coverage?verifyCoverage(s,r.coverageRows[ei],links):[];
 if(!same(links,__labAssemblyLinks(after.project_path,imported.sequence_id)))throw Error('ASSEMBLY_CHANGED_DURING_READBACK');
 if(r.target_canvas&&(e.width!==r.target_canvas.width||e.height!==r.target_canvas.height)){
  if(e.width*r.target_canvas.height!==e.height*r.target_canvas.width)throw Error('CANVAS_ASPECT_CHANGED');var scaleFactor=r.target_canvas.width/e.width,expected=JSON.parse(JSON.stringify(imported.snapshot)),settings=s.getSettings();settings.videoFrameWidth=r.target_canvas.width;settings.videoFrameHeight=r.target_canvas.height;if(!s.setSettings(settings))throw Error('MASTER_CANVAS_NOT_CONFIRMED');
  expected.settings.videoFrameWidth=r.target_canvas.width;expected.settings.videoFrameHeight=r.target_canvas.height;
  for(var videoTrack=0;videoTrack<s.videoTracks.numTracks;videoTrack++)for(var vi=0;vi<s.videoTracks[videoTrack].clips.numItems;vi++){var nativeItem=s.videoTracks[videoTrack].clips[vi],scale=null,expectedScale=null;for(var ci=0;ci<nativeItem.components.numItems;ci++){var comp=nativeItem.components[ci];if(String(comp.matchName)!=='AE.ADBE Motion')continue;for(var pi=0;pi<comp.properties.numItems;pi++){var prop=comp.properties[pi];if(String(prop.displayName)==='Scale'){if(scale||prop.isTimeVarying())throw Error('STATIC_MASTER_SCALE_REQUIRED');scale=prop;}}}
   for(var ti=0;ti<expected.tracks.length;ti++){var tr=expected.tracks[ti];if(tr.kind!==0||tr.index!==videoTrack)continue;for(var ci=0;ci<tr.clips[vi].components.length;ci++){var co=tr.clips[vi].components[ci];if(co.matchName!=='AE.ADBE Motion')continue;for(var pi=0;pi<co.properties.length;pi++)if(co.properties[pi].name==='Scale')expectedScale=co.properties[pi];}}
   if(!scale||!expectedScale)throw Error('MASTER_SCALE_IDENTITY');var value=scale.getValue()*scaleFactor;scale.setValue(value,true);if(scale.getValue()!==value)throw Error('MASTER_FIT_SCALE_NOT_CONFIRMED');expectedScale.value=value;
  }
  var fitted=__labSnapshot(s);if(!same(JSON.parse(JSON.stringify(fitted)),expected)||!same(links,__labAssemblyLinks(after.project_path,imported.sequence_id)))throw Error('UNEXPECTED_STATE_CHANGE_DURING_MASTER_FIT');imported.snapshot=fitted;
 }
 outputs.push({sequence_id:imported.sequence_id,sequence_name:e.sequence_name,snapshot:imported.snapshot,mapping:mapping,coverage:coverageMap});}
 if(!same(JSON.parse(JSON.stringify(after)),JSON.parse(JSON.stringify(__labProjectSequences()))))throw Error('ASSEMBLY_OR_PROTECTED_PROJECT_CHANGED_DURING_READBACK');
 return __result({project_path:after.project_path,assemblies:outputs,project_snapshot:after,verification:'native_linked_batch_and_complete_prior_sequence_pages',persistence:'not_run',rendered:'not_run',source_processing:'not_verified',rollback:'not_attempted'});
 `);
 if(Buffer.byteLength(script,'utf8')>450000)return {success:false,error:'Assembly batch exceeds bounded native script size'};
 try{parse(script,{ecmaVersion:3,allowReserved:false});}catch(e){return {success:false,error:'ES3_SYNTAX_REJECTED_BEFORE_NATIVE_DISPATCH: '+String(e)};}
 const dispatchFile=path.join(options.tempDir,'prepared-inputs','dispatch-'+digest(script)+'.jsx');try{await writeFile(dispatchFile,script,{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}
 const result=await sendCommand(script,{...options,timeoutMs:3600000});
 try{for(let i=0;i<proofs.length;i++){await checkCompilerArtifacts(proofs[i]);if(await mediaHash(staged[i])!==stagedHashes[i])throw Error('STAGED_XML_CHANGED');}}
 catch(e){return {success:false,error:'Batch compiler input changed after dispatch; reconcile original operation: '+String(e)};}
 if(digest(JSON.parse(await readFile(requestFile,'utf8')))!==digest(commandInput))return {success:false,error:'BATCH_COMMAND_INPUT_CHANGED_AFTER_DISPATCH',native_result:result};
 if(coverage){for(const s of coverage.sources){const st=await stat(s.media_path,{bigint:true});if(st.size.toString()!==s.file_identity.size||st.mtimeNs.toString()!==s.file_identity.mtime_ns)return {success:false,error:'COVERAGE_MEDIA_CHANGED_AFTER_DISPATCH',native_result:result};}}
 if(args.coverage&&await mediaHash(args.coverage.coverage_path)!==args.coverage.coverage_sha256)return {success:false,error:'COVERAGE_CONFIG_CHANGED_AFTER_DISPATCH',native_result:result};
 const data:any=result.data;
 if(result.success&&(!data||data.project_path!==state.project_path||!Array.isArray(data.assemblies)||data.assemblies.length!==proofs.length||data.assemblies.some((a:any,i:number)=>typeof a.sequence_id!=='string'||!a.sequence_id||a.sequence_name!==proofs[i].expectation.sequence_name||a.snapshot?.sequenceId!==a.sequence_id||a.snapshot?.projectPath!==state.project_path||!Array.isArray(a.mapping)||a.mapping.length!==proofs[i].expectation.items.length)))return {success:false,error:'Invalid native batch result; reconcile original operation',native_result:result};
 return result.success?{...result,data:{...data,assemblies:data.assemblies.map((a:any,i:number)=>({...a,sequence_revision:digest(a.snapshot),provenance:proofs[i].provenance,staged_xml:staged[i]}))}}:result;
}

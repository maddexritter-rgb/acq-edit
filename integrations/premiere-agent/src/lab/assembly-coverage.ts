import path from 'node:path';
import {readFile,writeFile,stat,realpath} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {fileURLToPath} from 'node:url';
import {labContext} from './context.js';
import {digest} from './runtime.js';
import {mediaHash} from './music-placement.js';
import type {AssemblyRequest,CompilerProof} from './assembly-provenance.js';
const run=promisify(execFile);
export type CoverageInput={coverage_path:string;coverage_sha256:string};
export async function readCoverage(input:CoverageInput,state:any){
 if(!path.isAbsolute(input.coverage_path)||!/^[a-f0-9]{64}$/.test(input.coverage_sha256)||await mediaHash(input.coverage_path)!==input.coverage_sha256)throw Error('COVERAGE_INPUT_IDENTITY');
 const config=JSON.parse(await readFile(input.coverage_path,'utf8'));
 if(config.schema!=='edit.assembly-coverage-adapter/v1'||!Array.isArray(config.sources)||config.sources.length!==6||new Set(config.sources.map((s:any)=>s.source_id)).size!==6||config.sources.filter((s:any)=>s.kind==='camera').length!==4||config.sources.slice(4).some((s:any)=>s.kind!=='audio')||config.sources[0].source_id!==config.primary_camera_source_id||config.sources[0].delta_ticks!=='0')throw Error('BOUNDED_COVERAGE_CONFIGURATION');
 const raw=state.sequences.find((s:any)=>s.sequence_id===config.raw_sequence_id);if(!raw)throw Error('PROTECTED_RAW_SOURCE_REQUIRED');
 const tracks:any[]=[];for(const p of raw.snapshot.pages){const page=JSON.parse(await readFile(p.path,'utf8'));if(digest(page)!==p.sha256)throw Error('PROTECTED_RAW_PAGE_CHANGED');for(const t of page.tracks)for(const c of t.clips)tracks.push({kind:t.kind,index:t.index,clip:c});}
 const ctx=labContext.getStore();let authorized:any;
 if(ctx){if(!ctx.expectedSnapshotPath)throw Error('COVERAGE_EXACT_SCOPE_REQUIRED');const runtime=path.dirname(path.dirname(ctx.expectedSnapshotPath));authorized=JSON.parse(await readFile(path.join(runtime,'edit-project-authorization.json'),'utf8'));if(authorized.schema!=='premiere-agent/edit-project-authorization-v1'||authorized.projectPath!==ctx.projectPath||!authorized.tools.includes('lab_import_compiled_assembly')||Date.parse(authorized.expiresAt)<=Date.now())throw Error('COVERAGE_EXACT_SCOPE_REQUIRED');}
 const anchor=BigInt(config.sources[0].in_ticks);
 for(let i=0;i<6;i++){
  const s=config.sources[i],matches=tracks.filter(t=>t.kind===s.raw_kind&&t.index===s.raw_track_index&&t.clip.id===s.raw_item_id),c=matches[0]?.clip;
  if(matches.length!==1||!c||c.sourceId!==s.source_id||c.start!=='0'||c.end!==config.raw_duration_ticks||c.inPoint!==s.in_ticks||c.outPoint!==s.out_ticks||c.speed!==1||BigInt(s.delta_ticks)!==BigInt(c.inPoint)-anchor||s.raw_kind!==(i<4?0:1)||!path.isAbsolute(s.media_path)||s.channels<1||s.channels>8||s.duration_frames<1||s.duration_frames>1000000)throw Error('COVERAGE_RAW_CLOCK_OR_IDENTITY_MISMATCH');
  if(authorized&&!authorized.readPaths.includes(s.media_path))throw Error('COVERAGE_SOURCE_OUTSIDE_EXACT_INPUT_SET');
  const info=await stat(s.media_path,{bigint:true});if(!info.isFile()||await realpath(s.media_path)!==s.media_path)throw Error('COVERAGE_MEDIA_IDENTITY');s.file_identity={size:info.size.toString(),mtime_ns:info.mtimeNs.toString()};
 }
 return config;
}
export async function prepareCoverage(request:AssemblyRequest,proof:CompilerProof,config:any,folder:string){
 const input=path.join(folder,'coverage-'+digest(config)+'.json');try{await writeFile(input,JSON.stringify(config),{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}
 if(digest(JSON.parse(await readFile(input,'utf8')))!==digest(config))throw Error('COVERAGE_PRIVATE_INPUT_CHANGED');
 const expected=path.join(folder,'coverage-expectation-'+digest(proof.expectation)+'.json');try{await writeFile(expected,JSON.stringify(proof.expectation),{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}if(digest(JSON.parse(await readFile(expected,'utf8')))!==digest(proof.expectation))throw Error('COVERAGE_EXPECTATION_CHANGED');
 const output=path.join(folder,'coverage-'+digest({config,xml:request.xml_sha256})+'.xml');const script=fileURLToPath(new URL('../../scripts/prepare-assembly-coverage.py',import.meta.url));
 // Adapter only appends coverage. Original canonical XML/provenance was already reproduced.
 const temporary=output+'.prepared';const {stdout}=await run('python3',[script,request.xml_path,expected,input,temporary],{timeout:30000,maxBuffer:1500000});const data=JSON.parse(stdout);
 if(!Array.isArray(data.items)||data.items.length!==proof.expectation.items.length*10)throw Error('COVERAGE_ITEM_COUNT');
 const raw=await readFile(temporary);try{await writeFile(output,raw,{flag:'wx',mode:0o400});}catch(e:any){if(e.code!=='EEXIST')throw e;}if(await mediaHash(output)!==await mediaHash(temporary))throw Error('COVERAGE_XML_CHANGED');
 return {path:output,sha256:await mediaHash(output),items:data.items,adapter_sha256:await mediaHash(script)};
}
export const COVERAGE_NATIVE=`
function verifyCoverageAnchors(config){var raw=null;for(var i=0;i<app.project.sequences.numSequences;i++)if(String(app.project.sequences[i].sequenceID)===config.raw_sequence_id)raw=app.project.sequences[i];if(!raw)throw Error('RAW_SOURCE_REMOVED');for(var i=0;i<config.sources.length;i++){var want=config.sources[i],tracks=want.raw_kind?raw.audioTracks:raw.videoTracks,tr=tracks[want.raw_track_index],c=null;for(var j=0;j<tr.clips.numItems;j++)if(String(tr.clips[j].nodeId)===want.raw_item_id)c=tr.clips[j];if(!c||String(c.projectItem.nodeId)!==want.source_id||String(c.projectItem.getMediaPath())!==want.media_path||c.projectItem.isOffline()||String(c.start.ticks)!=='0'||String(c.end.ticks)!==config.raw_duration_ticks||String(c.inPoint.ticks)!==want.in_ticks||String(c.outPoint.ticks)!==want.out_ticks||c.getSpeed()!==1||c.isSpeedReversed())throw Error('RAW_SOURCE_CLOCK_OR_MEDIA_CHANGED');}}
function establishCoverageAudioPairs(sequence,rows){
 function members(c){var linked=c.getLinkedItems(),ids=[];if(!linked)return ids;for(var i=0;i<linked.numItems;i++)ids.push(String(linked[i].nodeId));ids.sort();return ids;}
 for(var i=0;i<rows.length;i++){var w=rows[i];if(w.kind!=='audio'||w.track_index!==5)continue;var a=sequence.audioTracks[5].clips[w.item_index],b=sequence.audioTracks[6].clips[w.item_index],ids=[String(a.nodeId),String(b.nodeId)].sort(),am=members(a),bm=members(b);if(same(am,ids)&&same(bm,ids))continue;
 if(am.length>1||bm.length>1||am.length===1&&am[0]!==String(a.nodeId)||bm.length===1&&bm[0]!==String(b.nodeId))throw Error('COVERAGE_FOREIGN_AUDIO_LINK');
 var selected=sequence.getSelection(),saved=[];for(var j=0;j<selected.length;j++){saved.push(selected[j]);selected[j].setSelected(false,true);}a.setSelected(true,true);b.setSelected(true,true);var picked=sequence.getSelection(),check=[];for(var j=0;j<picked.length;j++)check.push(String(picked[j].nodeId));check.sort();if(!same(check,ids))throw Error('COVERAGE_AUDIO_PAIR_SELECTION');sequence.linkSelection();if(!same(members(a),ids)||!same(members(b),ids))throw Error('COVERAGE_AUDIO_PAIR_LINK');var now=sequence.getSelection();for(var j=0;j<now.length;j++)now[j].setSelected(false,true);for(var j=0;j<saved.length;j++)saved[j].setSelected(true,true);
 }
}
function conformCoverage(sequence,rows){for(var i=0;i<rows.length;i++){var want=rows[i],tracks=want.kind==='video'?sequence.videoTracks:sequence.audioTracks,c=tracks[want.track_index].clips[want.item_index];if(!c||String(c.projectItem.getMediaPath())!==want.media_path||c.projectItem.isOffline()||c.getSpeed()!==1||c.isSpeedReversed()||!c.disabled||String(c.start.ticks)!==want.start_ticks||String(c.end.ticks)!==want.end_ticks||String(c.inPoint.ticks)!==want.import_source_in_ticks||String(c.outPoint.ticks)!==want.import_source_out_ticks)throw Error('COVERAGE_IMPORT_IDENTITY_OR_CLOCK');if(want.kind==='audio'&&want.source_in_ticks!==want.import_source_in_ticks){var si=new Time(),so=new Time(),ts=new Time(),te=new Time();si.ticks=want.source_in_ticks;so.ticks=want.source_out_ticks;ts.ticks=want.start_ticks;te.ticks=want.end_ticks;c.inPoint=si;c.outPoint=so;c.start=ts;c.end=te;}}establishCoverageAudioPairs(sequence,rows);}
function verifyCoverage(sequence,rows,links){var map={},out=[];for(var i=0;i<links.items.length;i++){var x=links.items[i];map[x.kind+':'+x.track_index+':'+x.item_index]=x;}
 for(var i=0;i<rows.length;i++){var w=rows[i],r=map[w.kind+':'+w.track_index+':'+w.item_index];if(!r)throw Error('COVERAGE_NATIVE_ITEM_MISSING');var c=r.item;if(c.media_path!==w.media_path||c.offline!==false||c.speed!==1||c.speed_reversed!==false||c.disabled!==true||c.start_ticks!==w.start_ticks||c.end_ticks!==w.end_ticks||c.source_in_ticks!==w.source_in_ticks||c.source_out_ticks!==w.source_out_ticks)throw Error('COVERAGE_NATIVE_CLOCK_OR_STATE');var peers=[];for(var j=0;j<w.peer_tracks.length;j++){var p=w.peer_tracks[j],peer=map[p.kind+':'+p.track_index+':'+w.item_index];if(!peer)throw Error('COVERAGE_NATIVE_PEER_MISSING');peers.push(peer.item.node_id);}peers.sort();if(!same(peers,r.linked_node_ids))throw Error('COVERAGE_NATIVE_LINK_GROUP');out.push({kind:w.kind,track_index:w.track_index,item_index:w.item_index,node_id:c.node_id,source_id:c.source_id,media_path:c.media_path,source_in_ticks:c.source_in_ticks,source_out_ticks:c.source_out_ticks});}return out;}
`;

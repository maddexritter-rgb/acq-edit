import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { isAbsolute } from 'node:path';
import { stat } from 'node:fs/promises';
import { mediaHash } from './music-placement.js';
import { SNAPSHOT_FUNCTION, labContext } from './context.js';
import { NATIVE_STATE_COMPARE } from './caption-transfer.js';
import { sendCommand, type BridgeOptions } from '../bridge/file-bridge.js';
import { buildToolScript } from '../bridge/script-builder.js';

const run=promisify(execFile);
export type GraphicAssetRequest={source_item_id?:string;media_path:string;media_sha256:string;track_index:number;track_id:string;start_ticks:string;end_ticks:string;width:number;height:number;frame_duration_ticks:string};
const tick={type:'string',pattern:'^(0|[1-9][0-9]{0,18})$'};
function exact(v:string){if(typeof v!=='string'||!/^(0|[1-9][0-9]{0,18})$/.test(v)||BigInt(v)>9223372036854775807n)throw Error('Exact nonnegative ticks required');return BigInt(v);}
export function validateGraphicAsset(r:GraphicAssetRequest){
  if(!r||!isAbsolute(r.media_path)||r.media_path.includes('\0')||!r.media_path.toLowerCase().endsWith('.png')||!/^[a-f0-9]{64}$/.test(r.media_sha256))throw Error('Hash-bound PNG path required');
  if(r.source_item_id!==undefined&&(typeof r.source_item_id!=='string'||!r.source_item_id||r.source_item_id.length>512))throw Error('Invalid explicit source identity');
  if(!Number.isInteger(r.track_index)||r.track_index<0||r.track_index>255||typeof r.track_id!=='string'||!r.track_id||r.track_id.length>512)throw Error('Exact existing video track required');
  if(![r.width,r.height].every(v=>Number.isInteger(v)&&v>0&&v<=8192))throw Error('Bounded image canvas required');
  const a=exact(r.start_ticks),b=exact(r.end_ticks),step=exact(r.frame_duration_ticks);
  if(!step||b<=a||a%step||b%step||b>BigInt(Number.MAX_SAFE_INTEGER))throw Error('Positive exactly representable frame-aligned placement required');
}
export async function probeGraphicAsset(r:GraphicAssetRequest){
  validateGraphicAsset(r);const info=await stat(r.media_path);
  if(!info.isFile()||!info.size||info.size>64*1024**2||await mediaHash(r.media_path)!==r.media_sha256)throw Error('Graphic asset changed or excessive');
  const {stdout}=await run('ffprobe',['-v','error','-show_entries','stream=codec_type,codec_name,width,height','-of','json',r.media_path],{timeout:15000,maxBuffer:1048576});
  const s=JSON.parse(stdout).streams;
  if(!Array.isArray(s)||s.length!==1||s[0].codec_type!=='video'||s[0].codec_name!=='png'||s[0].width!==r.width||s[0].height!==r.height||await mediaHash(r.media_path)!==r.media_sha256)throw Error('One exact-canvas PNG stream required');
}
export function graphicAssetScript(r:GraphicAssetRequest){
  validateGraphicAsset(r);
  const literal=JSON.stringify({...r,duration_ticks:String(exact(r.end_ticks)-exact(r.start_ticks))}).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
  return buildToolScript(`
    ${SNAPSHOT_FUNCTION}
    ${NATIVE_STATE_COMPARE}
    function clock(v){var t=new Time();t.ticks=v;return t;}
    function off(v){return v===false||v===0;}
    function tree(){var rows=[],refs={};function walk(n,parent,depth){if(depth>64||rows.length>=10000)throw Error('PROJECT_TREE_LIMIT');var id=String(n.nodeId);if(!id||id==='undefined'||refs[id])throw Error('AMBIGUOUS_PROJECT_ITEM');refs[id]=n;var bin=n.type===2||n.type===3;rows.push({id:id,parent:parent,type:n.type,name:String(n.name),path:bin?null:String(n.getMediaPath())});if(bin)for(var i=0;i<n.children.numItems;i++)walk(n.children[i],id,depth+1);}walk(app.project.rootItem,null,0);return {rows:rows,refs:refs};}
    var r=${literal},s=app.project.activeSequence,before=JSON.parse(JSON.stringify(__labSnapshot())),assets=tree();
    if(!s||String(s.timebase)!==r.frame_duration_ticks||Number(s.end)<Number(r.end_ticks))throw Error('SEQUENCE_CLOCK_MISMATCH');
    var settings=s.getSettings();if(settings.videoFrameWidth!==r.width||settings.videoFrameHeight!==r.height)throw Error('GRAPHIC_CANVAS_MISMATCH');
    var track=s.videoTracks[r.track_index];
    if(!track||String(track.id)!==r.track_id||typeof track.isLocked!=='function'||!off(track.isLocked())||typeof track.isMuted!=='function'||!off(track.isMuted())||track.transitions.numItems!==0)throw Error('GRAPHIC_TRACK_UNAVAILABLE');
    for(var i=0;i<track.clips.numItems;i++)if(Number(track.clips[i].end.ticks)>Number(r.start_ticks)&&Number(track.clips[i].start.ticks)<Number(r.end_ticks))throw Error('GRAPHIC_DESTINATION_OCCUPIED');
    var matches=[];for(var i=0;i<assets.rows.length;i++)if(assets.rows[i].path===r.media_path)matches.push(assets.rows[i]);
    if(r.source_item_id){if(matches.length!==1||matches[0].id!==r.source_item_id)throw Error('EXPLICIT_GRAPHIC_SOURCE_CHANGED');}
    else if(matches.length)throw Error('GRAPHIC_SOURCE_ALREADY_REGISTERED_RECONCILE');
    if(typeof track.overwriteClip!=='function')throw Error('GRAPHIC_PLACEMENT_API_UNAVAILABLE');
    if(r.source_item_id){
      if(app.project.sequences.numSequences>64)throw Error('SOURCE_CONSUMER_SCAN_LIMIT');
      var count=0;
      for(var q=0;q<app.project.sequences.numSequences;q++){var seq=app.project.sequences[q];for(var k=0;k<2;k++){var tracks=k===0?seq.videoTracks:seq.audioTracks;for(var t=0;t<tracks.numTracks;t++)for(var c=0;c<tracks[t].clips.numItems;c++){if(++count>10000)throw Error('SOURCE_CONSUMER_SCAN_LIMIT');var used=tracks[t].clips[c];if(used.projectItem&&String(used.projectItem.nodeId)===r.source_item_id)throw Error('GRAPHIC_SOURCE_HAS_CONSUMERS');}}}
    }else app.project.importFiles([r.media_path],true,app.project.rootItem,false);
    var imported=tree(),fresh=[];for(var i=0;i<imported.rows.length;i++)if(!assets.refs[imported.rows[i].id])fresh.push(imported.rows[i]);
    if(r.source_item_id){if(fresh.length||!same(imported.rows,assets.rows))throw Error('PROJECT_TREE_CHANGED');fresh=matches;}
    else if(fresh.length!==1||fresh[0].path!==r.media_path)throw Error('GRAPHIC_IMPORT_AMBIGUOUS');
    var source=imported.refs[fresh[0].id];
    if(!off(source.isSequence())||!off(source.isOffline()))throw Error('GRAPHIC_SOURCE_UNAVAILABLE');
    var protectedRows=[];for(var i=0;i<imported.rows.length;i++)if(r.source_item_id||imported.rows[i].id!==fresh[0].id)protectedRows.push(imported.rows[i]);
    if(!same(assets.rows,protectedRows)||!same(before,JSON.parse(JSON.stringify(__labSnapshot()))))throw Error('PROTECTED_STATE_CHANGED_ON_IMPORT');
    source.setInPoint(0,1);source.setOutPoint(clock(r.duration_ticks).seconds,1);
    var sourceOut=Number(source.getOutPoint(1).ticks),wanted=Number(r.duration_ticks);
    if(String(source.getInPoint(1).ticks)!=='0'||!isFinite(sourceOut)||sourceOut<=0||sourceOut>wanted||wanted-sourceOut>2*Number(r.frame_duration_ticks))throw Error('GRAPHIC_SOURCE_MARK_READBACK');
    var oldIds={};for(var i=0;i<track.clips.numItems;i++)oldIds[String(track.clips[i].nodeId)]=true;
    track.overwriteClip(source,clock(r.start_ticks));
    var added=[];for(var i=0;i<track.clips.numItems;i++)if(!oldIds[String(track.clips[i].nodeId)])added.push(track.clips[i]);
    if(added.length!==1)throw Error('GRAPHIC_PLACEMENT_AMBIGUOUS');
    var item=added[0];
    // Still images inherit a source frame rate. Never let its rounded source mark
    // overrun the empty interval; extend only this new native timeline item.
    if(String(item.start.ticks)!==r.start_ticks||Number(item.end.ticks)>Number(r.end_ticks))throw Error('GRAPHIC_INITIAL_RANGE_UNSAFE');
    var nativeIn=String(item.inPoint.ticks);
    item.end=clock(r.end_ticks);
    if(String(item.projectItem.nodeId)!==fresh[0].id||String(item.start.ticks)!==r.start_ticks||String(item.end.ticks)!==r.end_ticks||String(item.inPoint.ticks)!==nativeIn||Number(item.outPoint.ticks)-Number(item.inPoint.ticks)!==Number(r.duration_ticks)||item.getSpeed()!==1||!off(item.isSpeedReversed())||!off(item.disabled))throw Error('GRAPHIC_PLACEMENT_READBACK');
    var after=JSON.parse(JSON.stringify(__labSnapshot())),removed=0;
    for(var t=0;t<after.tracks.length;t++)if(after.tracks[t].kind===0&&after.tracks[t].index===r.track_index)for(var c=after.tracks[t].clips.length-1;c>=0;c--)if(after.tracks[t].clips[c].id===String(item.nodeId)){after.tracks[t].clips.splice(c,1);removed++;}
    if(removed!==1||!same(before,after)||!same(imported.rows,tree().rows))throw Error('PROTECTED_STATE_CHANGED_AFTER_GRAPHIC');
    return __result({project_path:app.project.path,sequence_id:String(s.sequenceID),node_id:String(item.nodeId),source_id:fresh[0].id,source_mark_out_ticks:String(sourceOut),native_item_in_ticks:String(item.inPoint.ticks),native_item_out_ticks:String(item.outPoint.ticks),media_path:r.media_path,media_sha256:r.media_sha256,track_index:r.track_index,track_id:r.track_id,start_ticks:r.start_ticks,end_ticks:r.end_ticks,verification:'exact_native_item_and_protected_timeline',persistence:'not_run',rendered:'not_run',rollback:'not_attempted'});
  `);
}
export function getLabGraphicAssetTools(options:BridgeOptions){return {lab_place_graphic_asset:{
  description:'Import one new hash-bound full-canvas PNG, or use an explicit unused imported source, and place it into a proven empty range on an existing visible video track. No ripple, new tracks, nesting or alternate renderer. Preserves all prior bounded timeline and project-tree state. Failed imports remain for reconciliation; never retry blindly. Text must stay in separate native editable Graphics.',
  parameters:{type:'object',additionalProperties:false,required:['media_path','media_sha256','track_index','track_id','start_ticks','end_ticks','width','height','frame_duration_ticks'],properties:{source_item_id:{type:'string',minLength:1,maxLength:512,description:'Optional exact previously imported image; it must have no timeline consumers. Reconcile any earlier failure before use.'},media_path:{type:'string',minLength:1,maxLength:4096},media_sha256:{type:'string',pattern:'^[a-f0-9]{64}$'},track_index:{type:'integer',minimum:0,maximum:255},track_id:{type:'string',minLength:1,maxLength:512},start_ticks:tick,end_ticks:tick,frame_duration_ticks:tick,width:{type:'integer',minimum:1,maximum:8192},height:{type:'integer',minimum:1,maximum:8192}}},
  operationalCapability:{backend:'CEP/ExtendScript',backends:['cep','extendscript'],status:'experimental',minimumPremiereVersion:'26.3.0',hostVerificationRequired:true,notes:['PNG-only static artwork; native placement, save/reopen and pixels require host acceptance.']},
  handler:async(r:GraphicAssetRequest)=>{
    try{if(!labContext.getStore())throw Error('LAB_GUARD_REQUIRED');await probeGraphicAsset(r);}catch(e){return {success:false,error:String(e)};}
    const result=await sendCommand(graphicAssetScript(r),options);
    if(result.success&&await mediaHash(r.media_path)!==r.media_sha256)return {success:false,error:'Graphic changed after native placement; reconcile original operation'};
    return result;
  }
}};}

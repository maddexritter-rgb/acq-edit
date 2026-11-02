import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {SNAPSHOT_FUNCTION,labContext} from './context.js';
import {motionHelpers,capability} from './reframe.js';

type Shot={name:string;track_index:number;start_ticks:string;end_ticks:string;frame_ticks:string;source_id:string;media_path:string;source_in_ticks:string;source_out_ticks:string;scale:number;anchor_keys:number[][]};
export function validateCameraShot(r:Shot){
 const clock=(s:string)=>{if(typeof s!=='string'||!/^\d+$/.test(s)||!Number.isSafeInteger(Number(s)))throw Error('INVALID_SHOT_CLOCK');return BigInt(s);};
 const a=clock(r.start_ticks),b=clock(r.end_ticks),f=clock(r.frame_ticks),si=clock(r.source_in_ticks),so=clock(r.source_out_ticks);
 if(!f||b<=a||b-a!==so-si||[a,b,si,so].some(v=>v%f!==0n)||b-a>5000n*f)throw Error('SHOT_FRAME_GRID');
 if(!Number.isInteger(r.track_index)||r.track_index<0||r.track_index>32||!r.source_id||typeof r.media_path!=='string'||!r.media_path.startsWith('/')||r.media_path.includes('\0')||!/^\w[\w -]{0,120}$/.test(r.name))throw Error('INVALID_SHOT_TARGET');
 if(!Number.isFinite(r.scale)||r.scale<1||r.scale>500||!Array.isArray(r.anchor_keys)||r.anchor_keys.length!==Number((b-a)/f)||r.anchor_keys.some(k=>!Array.isArray(k)||k.length!==2||k.some(v=>!Number.isFinite(v)||v<0||v>1)))throw Error('DENSE_SHOT_KEYS_REQUIRED');
}
export function cameraShotScript(r:Shot){
 validateCameraShot(r);
 return buildToolScript(`${SNAPSHOT_FUNCTION}${motionHelpers}
 var r=${JSON.stringify(r)},p=app.project,s=p.activeSequence,before=JSON.parse(JSON.stringify(__labSnapshot())),prior=[];
 function tm(n){var t=new Time();t.ticks=String(n);return t;}
 function same(a,b){return JSON.stringify(a)===JSON.stringify(b);}
 function track(x){for(var i=0;i<x.tracks.length;i++)if(x.tracks[i].kind===0&&x.tracks[i].index===r.track_index)return x.tracks[i];throw Error('SHOT_TRACK_MISSING');}
 if(String(s.timebase)!==r.frame_ticks||before.settings.videoFrameWidth!==1080||before.settings.videoFrameHeight!==1920)throw Error('SHOT_MASTER_CHANGED');
 var tr=s.videoTracks[r.track_index];if(!tr||tr.isLocked()||tr.isMuted()||tr.transitions.numItems)throw Error('SHOT_TRACK_UNAVAILABLE');
 var original=track(before),expected=[];
 for(var i=0;i<original.clips.length;i++){
  var c=original.clips[i],a=Number(c.start),b=Number(c.end),lo=Number(r.start_ticks),hi=Number(r.end_ticks);
  if(b<=lo||a>=hi){expected.push(JSON.parse(JSON.stringify(c)));continue;}
  if(c.speed!==1||c.disabled)throw Error('SHOT_REPLACED_RANGE_UNSUPPORTED');
  // Replacement is explicitly bounded. Preserve the original source clocks and
  // effects on both surviving sides, including newly assigned fragment IDs.
  if(a<lo){var left=JSON.parse(JSON.stringify(c));left.end=String(lo);left.outPoint=String(Number(c.inPoint)+lo-a);expected.push(left);}
  if(b>hi){var right=JSON.parse(JSON.stringify(c));right.start=String(hi);right.inPoint=String(Number(c.inPoint)+hi-a);expected.push(right);}
 }
 var src=null;function walk(n,d){if(d>64)throw Error('TREE_LIMIT');if(String(n.nodeId)===r.source_id){if(src)throw Error('SOURCE_AMBIGUOUS');src=n;}if(n.type===2||n.type===3)for(var i=0;i<n.children.numItems;i++)walk(n.children[i],d+1);}walk(p.rootItem,0);
 if(!src||src.isSequence()||src.isOffline()||src.getMediaPath()!==r.media_path)throw Error('SHOT_SOURCE_CHANGED');
 for(var i=0;i<p.sequences.numSequences;i++)if(String(p.sequences[i].sequenceID)!==String(s.sequenceID))prior.push({seq:p.sequences[i],state:JSON.stringify(__labSnapshot(p.sequences[i]))});
 var sub=src.createSubClip(r.name,'0',r.source_out_ticks,0,1,0);if(!sub)throw Error('SHOT_SUBCLIP_FAILED');
 sub.setInPoint(tm(r.source_in_ticks).seconds,1);sub.setOutPoint(tm(r.source_out_ticks).seconds,1);
 tr.overwriteClip(sub,tm(r.start_ticks));
 var item=null;for(var i=0;i<tr.clips.numItems;i++)if(String(tr.clips[i].projectItem.nodeId)===String(sub.nodeId)){if(item)throw Error('SHOT_ITEM_AMBIGUOUS');item=tr.clips[i];}
 if(!item)throw Error('SHOT_ITEM_MISSING');
 item.inPoint=tm(r.source_in_ticks);item.outPoint=tm(r.source_out_ticks);item.start=tm(r.start_ticks);item.end=tm(r.end_ticks);
 // Remove only audio introduced by this new video-only source, never dialogue.
 for(var at=0;at<s.audioTracks.numTracks;at++)for(var ac=s.audioTracks[at].clips.numItems-1;ac>=0;ac--){var x=s.audioTracks[at].clips[ac];if(String(x.projectItem.nodeId)===String(sub.nodeId))x.remove(false,false);}
 var ap=motionProp(item,'Anchor Point'),pos=motionProp(item,'Position'),sc=motionProp(item,'Scale');pos.setValue([.5,.5],false);sc.setValue(r.scale,false);ap.setTimeVarying(true);
 for(var i=0;i<r.anchor_keys.length;i++){var t=tm(Number(r.source_in_ticks)+i*Number(r.frame_ticks));ap.addKey(t);ap.setValueAtKey(t,r.anchor_keys[i],false);ap.setInterpolationTypeAtKey(t,0,false);}
 var keys=anchorKeys(ap);if(keys.length!==r.anchor_keys.length||!pair(pos.getValue(),[.5,.5])||Math.abs(sc.getValue()-r.scale)>.0001)throw Error('SHOT_MOTION_READBACK');
 for(var i=0;i<keys.length;i++)if(keys[i].ticks!==String(Number(r.source_in_ticks)+i*Number(r.frame_ticks))||!pair(keys[i].value,r.anchor_keys[i]))throw Error('SHOT_KEY_READBACK');
 if(item.projectItem.getMediaPath()!==r.media_path||String(item.start.ticks)!==r.start_ticks||String(item.end.ticks)!==r.end_ticks||String(item.inPoint.ticks)!==r.source_in_ticks||String(item.outPoint.ticks)!==r.source_out_ticks||item.getSpeed()!==1||item.isSpeedReversed())throw Error('SHOT_SOURCE_CLOCK_READBACK');
 var after=JSON.parse(JSON.stringify(__labSnapshot())),remaining=[],actual=track(after),observed=null;
 for(var i=0;i<actual.clips.length;i++)if(actual.clips[i].id===String(item.nodeId))observed=actual.clips[i];else remaining.push(actual.clips[i]);
 function normalized(rows){var out=JSON.parse(JSON.stringify(rows));for(var i=0;i<out.length;i++)delete out[i].id;out.sort(function(a,b){return Number(a.start)-Number(b.start);});return out;}
 if(!observed||!same(normalized(remaining),normalized(expected)))throw Error('SHOT_RESIDUAL_RANGE_CHANGED_PARTIAL_EXECUTION');
 actual.clips=original.clips;if(!same(before,after))throw Error('SHOT_PROTECTED_STATE_CHANGED_PARTIAL_EXECUTION');
 for(var i=0;i<prior.length;i++)if(prior[i].state!==JSON.stringify(__labSnapshot(prior[i].seq)))throw Error('SHOT_UNRELATED_SEQUENCE_CHANGED');
 return __result({project_path:p.path,sequence_id:String(s.sequenceID),item:observed,keys:keys.length,source_path:r.media_path,protected_state_verified:true,persistence:'not_run',rendered:'not_run'});
 `);
}
export function getCameraShotTools(options:BridgeOptions){return {lab_place_tracked_camera_shot:{
 description:'Replace one explicitly scoped picture-track interval with an original-camera, video-only shot and dense native Motion keys. Preserves residual source ranges, all other tracks and sequences. Requires a fresh revision; reconcile partial failures, never replay.',
 parameters:{type:'object',additionalProperties:false,required:['name','track_index','start_ticks','end_ticks','frame_ticks','source_id','media_path','source_in_ticks','source_out_ticks','scale','anchor_keys'],properties:{name:{type:'string'},track_index:{type:'integer'},start_ticks:{type:'string'},end_ticks:{type:'string'},frame_ticks:{type:'string'},source_id:{type:'string'},media_path:{type:'string'},source_in_ticks:{type:'string'},source_out_ticks:{type:'string'},scale:{type:'number'},anchor_keys:{type:'array',items:{type:'array',items:{type:'number'}}}}},operationalCapability:capability,
 handler:async(r:Shot)=>{try{if(!labContext.getStore())throw Error('LAB_GUARD_REQUIRED');return await sendCommand(cameraShotScript(r),options);}catch(e){return {success:false,error:String(e)};}}
}};}

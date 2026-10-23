import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {SNAPSHOT_FUNCTION,labContext} from './context.js';
import {capability} from './reframe.js';
export function getReframeShotTools(options:BridgeOptions){return {
 lab_split_reframe_shots:{
  description:'Split only static source-linked picture items at reviewed internal camera switches. Experimental QE razor. Requires exact target item IDs, frame-grid ticks, guarded snapshot and before/after preservation checks. Audio, markers, effects and selected source coverage remain unchanged. No retry or rollback after partial execution.',
  parameters:{type:'object',additionalProperties:false,required:['cuts'],properties:{cuts:{type:'array',minItems:1,maxItems:128,items:{type:'object',additionalProperties:false,required:['node_id','ticks','track_index'],properties:{node_id:{type:'string',minLength:1},ticks:{type:'string',pattern:'^[0-9]{1,18}$'},track_index:{type:'integer',minimum:0}}}}}},
  operationalCapability:{...capability,backends:['cep','extendscript','qe'],notes:['Experimental QE picture-only split. Requires bounded host acceptance; no key redistribution supported.']},
  handler:async(args:{cuts:{node_id:string,ticks:string,track_index:number}[]})=>{
   if(!labContext.getStore())return {success:false,error:'LAB_GUARD_REQUIRED'};
   if(!Array.isArray(args.cuts)||!args.cuts.length||args.cuts.length>128)return {success:false,error:'INVALID_CUTS'};
   const seen=new Set<string>();for(const c of args.cuts){if(!/^\d{1,18}$/.test(c.ticks)||!Number.isSafeInteger(c.track_index)||c.track_index<0||!c.node_id||seen.has(c.track_index+':'+c.ticks))return {success:false,error:'INVALID_OR_DUPLICATE_CUT'};seen.add(c.track_index+':'+c.ticks);}
   const literal=JSON.stringify(args.cuts).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
   return sendCommand(buildToolScript(`${SNAPSHOT_FUNCTION}
    var cuts=${literal},s=app.project.activeSequence,before=__labSnapshot(),grid=Number(s.timebase),fps=254016000000/grid,initial={};
    if(Math.abs(fps-Math.round(fps))>0.000001)throw new Error('INTEGER_SEQUENCE_RATE_REQUIRED_FOR_VERIFIED_QE_ROUTE');
    fps=Math.round(fps);
    for(var t=0;t<before.tracks.length;t++){var tr=before.tracks[t];if(tr.kind!==0)continue;for(var c=0;c<tr.clips.length;c++)initial[tr.clips[c].id]={row:tr.clips[c],track:tr.index};}
    for(var i=0;i<cuts.length;i++){var r=cuts[i],b=initial[r.node_id],cut=Number(r.ticks);if(!b||b.track!==r.track_index||cut%grid!==0||cut<=Number(b.row.start)||cut>=Number(b.row.end)||b.row.speed!==1)throw new Error('CUT_BASELINE_OR_GRID_INVALID');
     for(var f=0;f<b.row.components.length;f++)for(var p=0;p<b.row.components[f].properties.length;p++)if(b.row.components[f].properties[p].keys)throw new Error('ANIMATED_PICTURE_SPLIT_UNSUPPORTED');
     if(s.videoTracks[r.track_index].isLocked())throw new Error('PICTURE_TRACK_LOCKED');
    }
    app.enableQE();var q=qe.project.getActiveSequence();if(!q)throw new Error('QE_SEQUENCE_UNAVAILABLE');
    function pad(v){return v<10?'0'+v:String(v);}
    for(var i=0;i<cuts.length;i++){var r=cuts[i],f=Math.round(Number(r.ticks)/grid),tc=pad(Math.floor(f/(fps*3600)))+':'+pad(Math.floor(f/(fps*60))%60)+':'+pad(Math.floor(f/fps)%60)+':'+pad(f%fps);q.getVideoTrackAt(r.track_index).razor(tc);}
    var after=__labSnapshot(),expectedCount=0,actualCount=0;
    for(var t=0;t<before.tracks.length;t++){
     var bt=before.tracks[t],at=after.tracks[t];if(bt.kind!==0)continue;expectedCount+=bt.clips.length;actualCount+=at.clips.length;
     for(var c=0;c<bt.clips.length;c++){
      var old=bt.clips[c],pieces=[],points=[Number(old.start),Number(old.end)];for(var k=0;k<cuts.length;k++)if(cuts[k].node_id===old.id)points.push(Number(cuts[k].ticks));points.sort(function(a,b){return a-b;});
      for(var n=0;n<at.clips.length;n++)if(Number(at.clips[n].start)>=Number(old.start)&&Number(at.clips[n].end)<=Number(old.end))pieces.push(at.clips[n]);
      if(pieces.length!==points.length-1)throw new Error('PICTURE_SPLIT_COUNT_FAILED');
      for(var n=0;n<pieces.length;n++){var piece=pieces[n],expected=JSON.parse(JSON.stringify(old));expected.id=piece.id;expected.start=String(points[n]);expected.end=String(points[n+1]);expected.inPoint=String(Number(old.inPoint)+points[n]-Number(old.start));expected.outPoint=String(Number(old.inPoint)+points[n+1]-Number(old.start));if(JSON.stringify(expected)!==JSON.stringify(piece))throw new Error('PICTURE_SPLIT_COVERAGE_OR_EFFECTS_CHANGED '+old.id);}
     }
     at.clips=bt.clips;
    }
    if(actualCount!==expectedCount+cuts.length||JSON.stringify(before)!==JSON.stringify(after))throw new Error('PROTECTED_STATE_CHANGED');
    return __result({splits:cuts.length,video_items:actualCount,audio_and_other_state_unchanged:true,verification:'exact_source_coverage_components_and_protected_state'});
   `),options);
  }
 }
};}

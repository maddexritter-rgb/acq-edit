import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {SNAPSHOT_FUNCTION,labContext} from './context.js';
import {capability,motionHelpers} from './reframe.js';
export function getEmbeddedPanelTools(options:BridgeOptions){return {
 lab_reframe_embedded_panels:{
  description:'Reflow reviewed left/right panels baked into source footage into two native editable stacked picture items. Uses video-only subclips and native Crop/Motion; never duplicates audio. Experimental QE effect insertion. Requires empty overlay intervals and static original Motion. Source geometry, seams, persistence and rendered review require separate verification.',
  parameters:{type:'object',additionalProperties:false,required:['items'],properties:{items:{type:'array',minItems:1,maxItems:80,items:{type:'object',additionalProperties:false,required:['node_id','upper_track','source_width','source_height'],properties:{node_id:{type:'string'},upper_track:{type:'integer',minimum:1},source_width:{type:'integer',minimum:100},source_height:{type:'integer',minimum:100},split_x:{type:'number',minimum:0.1,maximum:0.9}}}}}},
  operationalCapability:{...capability,backends:['cep','extendscript','qe']},
  handler:async(args:{items:{node_id:string,upper_track:number,source_width:number,source_height:number,split_x?:number}[]})=>{
   if(!labContext.getStore())return {success:false,error:'LAB_GUARD_REQUIRED'};
   if(!Array.isArray(args.items)||!args.items.length||args.items.length>80)return {success:false,error:'INVALID_PANEL_ITEMS'};
   const ids=new Set<string>();for(const r of args.items){if(!r.node_id||ids.has(r.node_id)||!Number.isInteger(r.upper_track)||r.upper_track<1||!Number.isInteger(r.source_width)||r.source_width<100||!Number.isInteger(r.source_height)||r.source_height<100)return {success:false,error:'INVALID_PANEL_GEOMETRY'};if(r.split_x!==undefined&&(!Number.isFinite(r.split_x)||r.split_x<0.1||r.split_x>0.9))return {success:false,error:'INVALID_SPLIT'};ids.add(r.node_id);}
   const literal=JSON.stringify(args.items).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
   return sendCommand(buildToolScript(`${SNAPSHOT_FUNCTION}${motionHelpers}
    var requests=${literal},s=app.project.activeSequence,before=__labSnapshot(),checked=[],created=[];
    if(s.getSettings().videoFrameWidth!==1080||s.getSettings().videoFrameHeight!==1920)throw new Error('VERTICAL_REQUIRED');
    app.enableQE();var qeSeq=qe.project.getActiveSequence(),cropEffect=qe.project.getVideoEffectByName('Crop');if(!qeSeq||!cropEffect)throw new Error('NATIVE_CROP_UNAVAILABLE');
    for(var i=0;i<requests.length;i++){
     var r=requests[i],found=__findClip(r.node_id);if(!found||found.trackType!=='video'||found.trackIndex===r.upper_track)throw new Error('PANEL_SOURCE_MISSING');
     var c=found.clip;if(c.getSpeed()!==1||c.projectItem.isSequence()||c.projectItem.isOffline())throw new Error('DIRECT_UNIT_SPEED_MEDIA_REQUIRED');
     if(motionProp(c,'Anchor Point').isTimeVarying()||motionProp(c,'Position').isTimeVarying()||motionProp(c,'Scale').isTimeVarying())throw new Error('STATIC_PANEL_SOURCE_REQUIRED');
     if(r.upper_track>=s.videoTracks.numTracks||s.videoTracks[r.upper_track].isLocked()||s.videoTracks[found.trackIndex].isLocked())throw new Error('EDITABLE_OVERLAY_TRACK_REQUIRED');
     var tr=s.videoTracks[r.upper_track];for(var n=0;n<tr.clips.numItems;n++)if(Number(tr.clips[n].start.ticks)<Number(c.end.ticks)&&Number(tr.clips[n].end.ticks)>Number(c.start.ticks))throw new Error('OVERLAY_COLLISION');
     for(var f=0;f<c.components.numItems;f++)if(c.components[f].displayName==='Crop')throw new Error('EXISTING_CROP');
     checked.push({r:r,c:c,track:found.trackIndex,start:String(c.start.ticks),end:String(c.end.ticks),sin:String(c.inPoint.ticks),sout:String(c.outPoint.ticks),path:c.projectItem.getMediaPath()});
    }
    function time(t){var x=new Time();x.ticks=t;return x;}
    function panel(c,track,anchor,position,scale,left,right){
     var qc=__findQeClipByDomClip(qeSeq.getVideoTrackAt(track),c);if(!qc)throw new Error('QE_PANEL_NOT_FOUND');qc.addVideoEffect(cropEffect);
     var crop=null;for(var f=0;f<c.components.numItems;f++)if(c.components[f].displayName==='Crop')crop=c.components[f];if(!crop)throw new Error('CROP_INSERT_NOT_VERIFIED');
     for(var p=0;p<crop.properties.numItems;p++){var prop=crop.properties[p],name=prop.displayName;if(name==='Left')prop.setValue(left,false);else if(name==='Right')prop.setValue(right,false);else if(name==='Top'||name==='Bottom')prop.setValue(0,false);else if(name==='Zoom')prop.setValue(false,false);}
     for(var p=0;p<crop.properties.numItems;p++){var prop=crop.properties[p],name=prop.displayName,expected=name==='Left'?left:name==='Right'?right:(name==='Top'||name==='Bottom')?0:name==='Zoom'?false:null;if(expected!==null&&Number(prop.getValue())!==Number(expected))throw new Error('CROP_READBACK_FAILED '+name);}
     motionProp(c,'Anchor Point').setValue(anchor,false);motionProp(c,'Position').setValue(position,false);motionProp(c,'Scale').setValue(scale,false);
     if(!pair(motionProp(c,'Anchor Point').getValue(),anchor)||!pair(motionProp(c,'Position').getValue(),position)||Math.abs(motionProp(c,'Scale').getValue()-scale)>0.00001)throw new Error('PANEL_MOTION_READBACK_FAILED');
    }
    for(var i=0;i<checked.length;i++){
     var x=checked[i],r=x.r,c=x.c,sub=c.projectItem.createSubClip('PANEL_'+r.node_id,'0',x.sout,0,1,0);if(!sub)throw new Error('VIDEO_ONLY_PANEL_SUBCLIP_FAILED');
     var placed=__overwriteRangeOnTrack(s.videoTracks[r.upper_track],sub,x.start,x.sin,x.sout,1);if(!placed.ok||!placed.marksRestored)throw new Error('PANEL_OVERWRITE_FAILED '+placed.error);
     var added=null,tr=s.videoTracks[r.upper_track];for(var n=0;n<tr.clips.numItems;n++)if(String(tr.clips[n].start.ticks)===x.start){if(added)throw new Error('AMBIGUOUS_ADDED_PANEL');added=tr.clips[n];}
     if(!added||added.projectItem.getMediaPath()!==x.path||String(added.inPoint.ticks)!==x.sin||String(added.outPoint.ticks)!==x.sout||String(added.end.ticks)!==x.end)throw new Error('PANEL_SOURCE_CLOCK_OR_DURATION_CHANGED');
     added.name=c.name+' [GRAPHIC]';var split=r.split_x===undefined?0.5:r.split_x,scale=Math.min(1080/(r.source_width*split),960/r.source_height)*100,scaleRight=Math.min(1080/(r.source_width*(1-split)),960/r.source_height)*100;
     panel(c,x.track,[split/2,0.5],[0.5,0.25],scale,0,100*(1-split));panel(added,r.upper_track,[(1+split)/2,0.5],[0.5,0.75],scaleRight,100*split,0);
     created.push({source_node_id:r.node_id,panel_node_id:String(added.nodeId),scale:scale,start:x.start,end:x.end,source_in:x.sin,source_out:x.sout});
    }
    var after=__labSnapshot();
    for(var t=0;t<before.tracks.length;t++)if(before.tracks[t].kind===1&&JSON.stringify(before.tracks[t])!==JSON.stringify(after.tracks[t]))throw new Error('DIALOGUE_CHANGED');
    if(JSON.stringify(before.markers)!==JSON.stringify(after.markers)||JSON.stringify(before.settings)!==JSON.stringify(after.settings))throw new Error('MARKERS_OR_SETTINGS_CHANGED');
    var sourceIds={},addedIds={};for(var i=0;i<created.length;i++){sourceIds[created[i].source_node_id]=true;addedIds[created[i].panel_node_id]=true;}
    for(var t=0;t<before.tracks.length;t++)if(before.tracks[t].kind===0){
     var bt=before.tracks[t],at=after.tracks[t],kept=[];
     for(var c=0;c<at.clips.length;c++)if(!addedIds[at.clips[c].id])kept.push(at.clips[c]);
     if(kept.length!==bt.clips.length)throw new Error('UNEXPECTED_VIDEO_ITEM_COUNT');
     for(var c=0;c<kept.length;c++)if(sourceIds[kept[c].id]){
      var old=bt.clips[c],cur=kept[c],filtered=[];
      for(var f=0;f<cur.components.length;f++){var fx=cur.components[f];if(fx.name==='Crop')continue;if(fx.name==='Motion'){for(var p=0;p<fx.properties.length;p++){var prop=fx.properties[p];if(prop.name==='Anchor Point'||prop.name==='Position'||prop.name==='Scale'){for(var of=0;of<old.components.length;of++)if(old.components[of].name==='Motion')for(var op=0;op<old.components[of].properties.length;op++)if(old.components[of].properties[op].name===prop.name)fx.properties[p]=old.components[of].properties[op];}}}filtered.push(fx);}cur.components=filtered;
     }
     at.clips=kept;
    }
    if(JSON.stringify(before)!==JSON.stringify(after))throw new Error('UNRELATED_PICTURE_STATE_CHANGED');
    return __result({panels:created,audio_unchanged:true,rendered:'not_run',persistence:'not_run'});
   `),options);
  }
 }
};}

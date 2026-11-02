import {sendCommand, type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {SNAPSHOT_FUNCTION, labContext} from './context.js';
import {motionHelpers, capability} from './reframe.js';

export const CAMERA_SOURCE_ROWS=`function read(){var rows=[];for(var t=0;t<s.videoTracks.numTracks;t++)for(var c=0;c<s.videoTracks[t].clips.numItems;c++){var x=s.videoTracks[t].clips[c],p=x.projectItem;rows.push({kind:"video",track_index:t,item_index:c,item:{node_id:String(x.nodeId),source_id:p?String(p.nodeId):null,media_path:p?(p.getMediaPath()||null):null,offline:p?p.isOffline():null,speed_reversed:!!x.isSpeedReversed(),is_sequence:p?p.isSequence():null}});}return rows;}`;

// One occurrence, two independent source sequences. The shadow and clean top
// occurrence share a sequence project item; no rendered camera intermediates.
type Panel = {source_id:string; media_path:string; source_in_ticks:string;
  source_out_ticks:string; scale:number; anchor_keys:number[][]};
export type CameraSplit = {name:string; start_ticks:string; end_ticks:string;
  frame_ticks:string; tracks:number[]; panels:Panel[]};
const tick={type:'string',pattern:'^(0|[1-9][0-9]{0,15})$'};
function clock(v:string):bigint {
  if(typeof v!=='string'||!/^(0|[1-9][0-9]{0,15})$/.test(v)||BigInt(v)>BigInt(Number.MAX_SAFE_INTEGER))throw Error('Exact safe ticks required');
  return BigInt(v);
}
export function validateCameraSplit(r:CameraSplit){
  if(!r||typeof r.name!=='string'||!/^[A-Za-z0-9_-]{1,100}$/.test(r.name))throw Error('Unique bounded split name required');
  const a=clock(r.start_ticks),b=clock(r.end_ticks),f=clock(r.frame_ticks);
  if(f===0n||b<=a||a%f||b%f||(b-a)/f>5000n)throw Error('Bounded frame aligned split required');
  if(!Array.isArray(r.tracks)||r.tracks.length!==3||r.tracks.some((v,i)=>!Number.isInteger(v)||v<1||v>63||(i>0&&v<=r.tracks[i-1]!)))throw Error('Three ordered overlay tracks required');
  if(!Array.isArray(r.panels)||r.panels.length!==2)throw Error('Exactly top and bottom panels required');
  for(const p of r.panels){
    if(!p||typeof p.source_id!=='string'||!p.source_id||p.source_id.length>512||typeof p.media_path!=='string'||!p.media_path.startsWith('/')||p.media_path.includes('\0'))throw Error('Explicit imported source identity required');
    const si=clock(p.source_in_ticks),so=clock(p.source_out_ticks);
    if(si%f||so%f||so-si!==b-a)throw Error('Panel source clocks differ');
    if(!Number.isFinite(p.scale)||p.scale<=0||p.scale>1000||!Array.isArray(p.anchor_keys)||p.anchor_keys.length!==Number((b-a)/f))throw Error('Dense panel keys and calibrated scale required');
    if(p.anchor_keys.some(k=>!Array.isArray(k)||k.length!==2||k.some(v=>typeof v!=='number'||!Number.isFinite(v)||v<0||v>1)))throw Error('Normalized dense anchor pairs required');
  }
}
export function cameraSplitScript(request:CameraSplit){
  validateCameraSplit(request);
  const r={...request,panels:request.panels.map(p=>({...p,scale:Math.fround(p.scale)}))};
  const literal=JSON.stringify(r).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
  return buildToolScript(`${SNAPSHOT_FUNCTION}${motionHelpers}
    var r=${literal},project=app.project,master=project.activeSequence,before=JSON.parse(JSON.stringify(__labSnapshot())),sources=[],prior=[],created=[],added=[];
    function tm(v){var t=new Time();t.ticks=String(v);return t;}
    function same(a,b){return JSON.stringify(a)===JSON.stringify(b);}
    function close(a,b){return typeof a==='number'&&isFinite(a)&&Math.abs(a-b)<0.0001;}
    function lookup(id){var found=null;function walk(n,d){if(d>64)throw Error('TREE_LIMIT');if(String(n.nodeId)===id){if(found)throw Error('DUPLICATE_SOURCE_ID');found=n;}if(n.type===2||n.type===3)for(var i=0;i<n.children.numItems;i++)walk(n.children[i],d+1);}walk(project.rootItem,0);return found;}
    if(!master||String(master.timebase)!==r.frame_ticks)throw Error('MASTER_CLOCK_CHANGED');
    var originalVideoTracks=master.videoTracks.numTracks,originalAudioTracks=master.audioTracks.numTracks;
    function protectedMaster(snap){for(var i=snap.tracks.length-1;i>=0;i--)if((snap.tracks[i].kind===0&&snap.tracks[i].index>=originalVideoTracks)||(snap.tracks[i].kind===1&&snap.tracks[i].index>=originalAudioTracks)){if(snap.tracks[i].clips.length)throw Error('UNEXPECTED_NEW_TRACK_CONTENT');snap.tracks.splice(i,1);}return snap;}
    var st=master.getSettings();if(st.videoFrameWidth!==1080||st.videoFrameHeight!==1920)throw Error('MASTER_CANVAS_CHANGED');
    if(project.sequences.numSequences>45)throw Error('SEQUENCE_LIMIT');
    for(var q=0;q<project.sequences.numSequences;q++){var s=project.sequences[q];if(String(s.name).indexOf(r.name)===0)throw Error('SPLIT_ALREADY_EXISTS_RECONCILE');prior.push({id:String(s.sequenceID),state:JSON.stringify(__labSnapshot(s))});}
    if(r.tracks[2]>=originalVideoTracks+3)throw Error('EXCESSIVE_NEW_TRACKS');
    for(var i=0;i<3;i++){var t=master.videoTracks[r.tracks[i]];if(!t)continue;if(t.isLocked()||t.isMuted()||t.transitions.numItems)throw Error('OVERLAY_TRACK_UNAVAILABLE');for(var j=0;j<t.clips.numItems;j++)if(Number(t.clips[j].end.ticks)>Number(r.start_ticks)&&Number(t.clips[j].start.ticks)<Number(r.end_ticks))throw Error('OVERLAY_OCCUPIED');}
    for(var i=0;i<2;i++){var p=r.panels[i],src=lookup(p.source_id);if(!src||src.getMediaPath()!==p.media_path||src.isOffline()||src.isSequence())throw Error('PANEL_SOURCE_CHANGED');sources.push(src);}
    app.enableQE();var shadowFx=qe.project.getVideoEffectByName('Drop Shadow');if(!shadowFx)throw Error('NATIVE_SHADOW_UNAVAILABLE');
    var missing=Math.max(0,r.tracks[2]+1-originalVideoTracks);
    if(missing){var publicError=null;try{if(typeof master.insertVideoTrackAt==='function')master.insertVideoTrackAt(originalVideoTracks,missing);}catch(e){publicError=String(e);}
      if(master.videoTracks.numTracks===originalVideoTracks)qe.project.getActiveSequence().addTracks(missing,originalVideoTracks,0);
      if(master.videoTracks.numTracks!==originalVideoTracks+missing||!same(before,protectedMaster(JSON.parse(JSON.stringify(__labSnapshot(master))))))throw Error('TRACK_CREATION_CHANGED_EXISTING_STATE');}
    function verifyItem(item,p){if(item.projectItem.getMediaPath()!==p.media_path||String(item.inPoint.ticks)!==p.source_in_ticks||String(item.outPoint.ticks)!==p.source_out_ticks||String(item.start.ticks)!=='0'||Number(item.end.ticks)!==Number(r.end_ticks)-Number(r.start_ticks)||item.getSpeed()!==1||item.isSpeedReversed()||item.disabled)throw Error('PANEL_SOURCE_CLOCK_READBACK');}
    for(var i=0;i<2;i++){
      var p=r.panels[i],sub=sources[i].createSubClip(r.name+'_SOURCE_'+i,'0',p.source_out_ticks,0,1,0);
      if(!sub)throw Error('VIDEO_ONLY_SUBCLIP_FAILED');
      sub.setInPoint(tm(p.source_in_ticks).seconds,1);sub.setOutPoint(tm(p.source_out_ticks).seconds,1);
      var seq=project.createNewSequenceFromClips(r.name+'_PANEL_'+i,[sub]);if(!seq)throw Error('PANEL_SEQUENCE_FAILED');
      if(seq.videoTracks[0].clips.numItems!==1)throw Error('PANEL_ITEM_COUNT');
      for(var a=0;a<seq.audioTracks.numTracks;a++)if(seq.audioTracks[a].clips.numItems)throw Error('PANEL_DUPLICATED_AUDIO');
      if(String(seq.timebase)!==r.frame_ticks)throw Error('PANEL_FRAME_GRID_CHANGED');
      var settings=seq.getSettings();settings.videoFrameWidth=1080;settings.videoFrameHeight=960;settings.previewFrameWidth=1080;settings.previewFrameHeight=960;seq.setSettings(settings);
      settings=seq.getSettings();if(settings.videoFrameWidth!==1080||settings.videoFrameHeight!==960)throw Error('PANEL_CANVAS_READBACK');
      var item=seq.videoTracks[0].clips[0];
      // Sequence-from-clips can round seconds-based source marks down one frame.
      // Set only this newly-created item using exact native tick Times.
      item.inPoint=tm(p.source_in_ticks);item.outPoint=tm(p.source_out_ticks);item.start=tm('0');item.end=tm(Number(r.end_ticks)-Number(r.start_ticks));
      verifyItem(item,p);
      var anchor=motionProp(item,'Anchor Point'),position=motionProp(item,'Position'),scale=motionProp(item,'Scale');
      position.setValue([0.5,0.5],false);scale.setValue(p.scale,false);anchor.setTimeVarying(true);
      for(var k=0;k<p.anchor_keys.length;k++){var key=tm(Number(p.source_in_ticks)+k*Number(r.frame_ticks));anchor.addKey(key);anchor.setValueAtKey(key,p.anchor_keys[k],false);anchor.setInterpolationTypeAtKey(key,0,false);}
      var keys=anchorKeys(anchor);if(keys.length!==p.anchor_keys.length||!pair(position.getValue(),[0.5,0.5])||!close(scale.getValue(),p.scale))throw Error('PANEL_MOTION_READBACK');
      for(var k=0;k<keys.length;k++)if(Number(keys[k].ticks)!==Number(p.source_in_ticks)+k*Number(r.frame_ticks)||!pair(keys[k].value,p.anchor_keys[k]))throw Error('PANEL_KEY_READBACK');
      verifyItem(item,p);created.push({sequence:seq,source:seq.projectItem,id:String(seq.sequenceID),item_id:String(item.nodeId),source_id:p.source_id,keys:keys.length});
    }
    project.openSequence(master.sequenceID);
    if(!same(before,protectedMaster(JSON.parse(JSON.stringify(__labSnapshot(master))))))throw Error('MASTER_CHANGED_DURING_PANEL_CREATION');
    var duration=Number(r.end_ticks)-Number(r.start_ticks),placements=[{panel:1,y:0.75,scale:100},{panel:0,y:0.25,scale:115},{panel:0,y:0.25,scale:100}];
    for(var i=0;i<3;i++){
      var spec=placements[i],source=created[spec.panel].source,track=master.videoTracks[r.tracks[i]];
      // Only newly-created video-only nests are inserted, so no shared source marks change.
      source.clearInPoint();source.clearOutPoint();track.overwriteClip(source,tm(r.start_ticks));
      // Premiere may add a silent audio nest even for a video-only panel.
      // Remove only the just-created nest's audio, non-ripple; original dialogue is protected.
      for(var at=0;at<master.audioTracks.numTracks;at++)for(var ac=master.audioTracks[at].clips.numItems-1;ac>=0;ac--){var ai=master.audioTracks[at].clips[ac];if(String(ai.projectItem.nodeId)===String(source.nodeId)&&String(ai.start.ticks)===r.start_ticks){ai.remove(false,false);}}
      var item=null;for(var c=0;c<track.clips.numItems;c++)if(String(track.clips[c].start.ticks)===r.start_ticks){if(item)throw Error('AMBIGUOUS_NEST');item=track.clips[c];}
      if(!item||String(item.projectItem.nodeId)!==String(source.nodeId))throw Error('NEST_IDENTITY_READBACK');
      item.inPoint=tm('0');item.outPoint=tm(duration);item.start=tm(r.start_ticks);item.end=tm(r.end_ticks);
      if(String(item.end.ticks)!==r.end_ticks||String(item.inPoint.ticks)!=='0'||Number(item.outPoint.ticks)!==duration||item.getSpeed()!==1||item.isSpeedReversed())throw Error('NEST_CLOCK_READBACK');
      motionProp(item,'Anchor Point').setValue([0.5,0.5],false);motionProp(item,'Position').setValue([0.5,spec.y],false);motionProp(item,'Scale').setValue(spec.scale,false);
      if(i===1){var qs=qe.project.getActiveSequence(),qc=__findQeClipByDomClip(qs.getVideoTrackAt(r.tracks[i]),item);if(!qc)throw Error('SHADOW_ITEM_UNAVAILABLE');qc.addVideoEffect(shadowFx);
        var fx=null;for(var f=0;f<item.components.numItems;f++)if(item.components[f].matchName==='AE.ADBE Drop Shadow'){if(fx)throw Error('DUPLICATE_SHADOW');fx=item.components[f];}if(!fx)throw Error('SHADOW_EFFECT_READBACK');
        var wants={'Opacity':98,'Direction':180,'Distance':49.700008392334,'Softness':150,'Shadow Only':true},seen={};
        for(var p=0;p<fx.properties.numItems;p++){var prop=fx.properties[p],n=String(prop.displayName);if(wants.hasOwnProperty(n)){prop.setValue(wants[n],false);var v=prop.getValue();if(typeof wants[n]==='boolean'?!(v===true||v===1):!close(v,wants[n]))throw Error('SHADOW_PARAMETER_READBACK '+n);seen[n]=true;}}
        for(var n in wants)if(!seen[n])throw Error('SHADOW_PARAMETER_UNAVAILABLE '+n);
      }
      added.push({node_id:String(item.nodeId),sequence_id:created[spec.panel].id,track_index:r.tracks[i],source_id:String(source.nodeId)});
    }
    var after=JSON.parse(JSON.stringify(__labSnapshot(master)));
    for(var t=0;t<after.tracks.length;t++)for(var c=after.tracks[t].clips.length-1;c>=0;c--)for(var a=0;a<added.length;a++)if(after.tracks[t].clips[c].id===added[a].node_id){after.tracks[t].clips.splice(c,1);break;}
    if(!same(before,protectedMaster(after)))throw Error('PROTECTED_MASTER_CHANGED');
    for(var i=0;i<prior.length;i++)if(prior[i].id!==String(master.sequenceID)){var found=false;for(var j=0;j<project.sequences.numSequences;j++)if(String(project.sequences[j].sequenceID)===prior[i].id){found=true;if(JSON.stringify(__labSnapshot(project.sequences[j]))!==prior[i].state)throw Error('UNRELATED_SEQUENCE_CHANGED');}if(!found)throw Error('UNRELATED_SEQUENCE_REMOVED');}
    if(project.sequences.numSequences!==prior.length+2)throw Error('UNEXPECTED_SEQUENCE_CREATION');
    var result=[];for(var i=0;i<created.length;i++)result.push({sequence_id:created[i].id,source_item_id:created[i].source_id,picture_item_id:created[i].item_id,keys:created[i].keys,snapshot:__labSnapshot(created[i].sequence)});
    return __result({project_path:project.path,sequence_id:String(master.sequenceID),panels:result,placements:added,shadow:'native-controls-preset-equivalent-pending-pixel-qualification',protected_state_verified:true,persistence:'not_run',rendered:'not_run'});
  `);
}
export function getCameraSplitTools(options:BridgeOptions){return {
lab_prepare_camera_source:{
  description:'Import or identify one exact authorized camera file without changing any sequence. Returns its native source identity for independent panel construction. Reconcile uncertain imports before retrying.',
  parameters:{type:'object',additionalProperties:false,required:['media_path'],properties:{media_path:{type:'string'}}},
  operationalCapability:{...capability,backends:['cep','extendscript']},
  handler:async(r:{media_path:string})=>{
    try{
      if(!labContext.getStore())throw Error('LAB_GUARD_REQUIRED');
      if(typeof r.media_path!=='string'||!r.media_path.startsWith('/')||r.media_path.includes('\0'))throw Error('Exact authorized media path required');
      return await sendCommand(buildToolScript(`${SNAPSHOT_FUNCTION}
        var file=${JSON.stringify(r.media_path)},p=app.project,states=[],active=p.activeSequence?String(p.activeSequence.sequenceID):null;
        for(var i=0;i<p.sequences.numSequences;i++)states.push(JSON.stringify(__labSnapshot(p.sequences[i])));
        function matches(){var rows=[];function walk(n,d){if(d>64)throw Error('TREE_LIMIT');if(n.type===2||n.type===3){for(var j=0;j<n.children.numItems;j++)walk(n.children[j],d+1);}else if(!n.isSequence()&&n.getMediaPath()===file)rows.push(n);}walk(p.rootItem,0);return rows;}
        var rows=matches(),imported=false;
        if(!rows.length){if(!p.importFiles([file],true,p.rootItem,false))throw Error('CAMERA_IMPORT_NOT_CONFIRMED');imported=true;rows=matches();}
        if(rows.length!==1||rows[0].isOffline())throw Error('CAMERA_SOURCE_AMBIGUOUS_OR_OFFLINE');
        if(states.length!==p.sequences.numSequences||(p.activeSequence?String(p.activeSequence.sequenceID):null)!==active)throw Error('CAMERA_IMPORT_CHANGED_SEQUENCE_SET');
        for(var i=0;i<states.length;i++)if(states[i]!==JSON.stringify(__labSnapshot(p.sequences[i])))throw Error('CAMERA_IMPORT_CHANGED_TIMELINE');
        return __result({source_id:String(rows[0].nodeId),media_path:file,imported:imported,sequence_state_preserved:true});
      `),options);
    }catch(e){return {success:false,error:String(e)};}
  }
},inspect_camera_panel_sources:{
  description:"Read original camera paths and playback flags in one exact panel sequence without activation or mutation. Does not infer AV linkage from an unlinked video-only item.",
  parameters:{type:"object",additionalProperties:false,required:["project_path","sequence_id"],properties:{project_path:{type:"string"},sequence_id:{type:"string"}}},
  operationalCapability:{...capability,backends:["cep","extendscript"]},
  handler:async(a:{project_path:string;sequence_id:string})=>{
    if(typeof a.project_path!=="string"||!a.project_path.startsWith("/")||typeof a.sequence_id!=="string"||!a.sequence_id)return {success:false,error:"Exact panel target required"};
    const input=JSON.stringify(a);
    return sendCommand(buildToolScript(`
      var r=${input};if(String(app.project.path)!==r.project_path)throw Error("PROJECT_CHANGED");
      var s=null;for(var i=0;i<app.project.sequences.numSequences;i++)if(String(app.project.sequences[i].sequenceID)===r.sequence_id)s=app.project.sequences[i];if(!s)throw Error("PANEL_MISSING");
      ${CAMERA_SOURCE_ROWS}
      var one=read(),two=read();if(JSON.stringify(one)!==JSON.stringify(two))throw Error("PANEL_CHANGED_DURING_READ");
      return __result({project_path:r.project_path,sequence_id:r.sequence_id,verification:"stable_native_panel_sources",items:one});
    `),options);
  }
},lab_place_camera_split:{
  description:'Create two source-linked video-only 1080x960 panel sequences with dense native keys and place a split occurrence with a linked top shadow. Requires three empty overlay tracks; appends at most three missing video tracks and verifies existing state and exact imported sources. Experimental until native pixels and reopen are verified. A failed write needs reconciliation; never replay.',
  parameters:{type:'object',additionalProperties:false,required:['name','start_ticks','end_ticks','frame_ticks','tracks','panels'],properties:{name:{type:'string'},start_ticks:tick,end_ticks:tick,frame_ticks:tick,tracks:{type:'array',minItems:3,maxItems:3,items:{type:'integer'}},panels:{type:'array',minItems:2,maxItems:2,items:{type:'object',additionalProperties:false,required:['source_id','media_path','source_in_ticks','source_out_ticks','scale','anchor_keys'],properties:{source_id:{type:'string'},media_path:{type:'string'},source_in_ticks:tick,source_out_ticks:tick,scale:{type:'number'},anchor_keys:{type:'array',minItems:1,maxItems:5000,items:{type:'array',minItems:2,maxItems:2,items:{type:'number'}}}}}}}},
  operationalCapability:{...capability,backends:['cep','extendscript','qe']},
  handler:async(r:CameraSplit)=>{try{if(!labContext.getStore())throw Error('LAB_GUARD_REQUIRED');validateCameraSplit(r);return await sendCommand(cameraSplitScript(r),options);}catch(e){return {success:false,error:String(e)};}}
}};}

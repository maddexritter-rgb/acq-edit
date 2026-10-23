import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {SNAPSHOT_FUNCTION,labContext} from './context.js';
import {NATIVE_STATE_COMPARE} from './caption-transfer.js';
import {parse} from 'acorn';
export function getCameraVisibilityTools(options:BridgeOptions){return {lab_prepare_sequence_name:{
 description:'Rename only the exact active sequence and its owned project item for a reviewed finishing-stage history copy. Verify current name and all timeline/settings state; refuse sequences referenced by another sequence.',
 parameters:{type:'object',additionalProperties:false,required:['expected_name','new_name'],properties:{expected_name:{type:'string',minLength:1,maxLength:200},new_name:{type:'string',minLength:1,maxLength:200}}},
 operationalCapability:{backend:'CEP/ExtendScript',backends:['cep','extendscript'],status:'experimental',minimumPremiereVersion:'26.3.0',hostVerificationRequired:true,notes:['Name-only preparation; no content edits, persistence or rendered claim.']},
 handler:async(args:{expected_name:string;new_name:string})=>{
  if(!labContext.getStore()||!args.expected_name||!args.new_name||args.new_name.length>200||/[\x00-\x1f]/.test(args.new_name))return {success:false,error:'EXACT_SEQUENCE_NAME_REQUIRED'};
  const literal=JSON.stringify(args).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
  const script=buildToolScript(`${SNAPSHOT_FUNCTION}\n${NATIVE_STATE_COMPARE}
   var r=${literal},p=app.project,s=p.activeSequence,before=__labSnapshot();if(!s||String(s.name)!==r.expected_name||!s.projectItem||String(s.projectItem.name)!==r.expected_name)throw Error('SEQUENCE_NAME_CHANGED');
   var names=[];for(var i=0;i<p.sequences.numSequences;i++){var other=p.sequences[i];names.push({id:String(other.sequenceID),name:String(other.name)});if(String(other.sequenceID)===String(s.sequenceID))continue;for(var kind=0;kind<2;kind++){var tracks=kind?other.audioTracks:other.videoTracks;for(var t=0;t<tracks.numTracks;t++)for(var j=0;j<tracks[t].clips.numItems;j++){var c=tracks[t].clips[j];if(c.projectItem&&String(c.projectItem.nodeId)===String(s.projectItem.nodeId))throw Error('REFERENCED_SEQUENCE_NAME_PROTECTED');}}}
   s.projectItem.name=r.new_name;s.name=r.new_name;if(String(s.name)!==r.new_name||String(s.projectItem.name)!==r.new_name||!same(JSON.parse(JSON.stringify(before)),JSON.parse(JSON.stringify(__labSnapshot()))))throw Error('UNEXPECTED_CHANGE_DURING_SEQUENCE_NAME');
   if(p.sequences.numSequences!==names.length)throw Error('SEQUENCE_SET_CHANGED');for(var i=0;i<names.length;i++)if(String(p.sequences[i].sequenceID)!==names[i].id||String(p.sequences[i].name)!==(names[i].id===String(s.sequenceID)?r.new_name:names[i].name))throw Error('OTHER_SEQUENCE_NAME_CHANGED');
   return __result({sequence_id:String(s.sequenceID),sequence_name:String(s.name),verification:'only_owned_unreferenced_sequence_name_changed',persistence:'not_run'});
  `);try{parse(script,{ecmaVersion:3,allowReserved:false});}catch(e){return {success:false,error:'ES3_SYNTAX_REJECTED: '+String(e)};}return sendCommand(script,options);
 }
},lab_apply_camera_visibility:{
 description:'Change only explicit video-item disabled flags to implement reviewed camera choices on a retained flat coverage stack. Requires exact native identity, current flags, guarded active sequence, and complete unchanged audio/effects/timing readback. Does not cut, move, nest, reframe or save.',
 parameters:{type:'object',additionalProperties:false,required:['items'],properties:{items:{type:'array',minItems:1,maxItems:512,items:{type:'object',additionalProperties:false,required:['node_id','source_id','media_path','before_disabled','after_disabled'],properties:{node_id:{type:'string',minLength:1,maxLength:512},source_id:{type:'string',minLength:1,maxLength:512},media_path:{type:'string',minLength:1,maxLength:4096},before_disabled:{type:'boolean'},after_disabled:{type:'boolean'}}}}}},
 operationalCapability:{backend:'CEP/ExtendScript',backends:['cep','extendscript'],status:'experimental',minimumPremiereVersion:'26.3.0',hostVerificationRequired:true,notes:['Only video visibility flags; native preservation and rendered camera judgment remain separate.']},
 handler:async(args:{items:{node_id:string;source_id:string;media_path:string;before_disabled:boolean;after_disabled:boolean}[]})=>{
  if(!labContext.getStore()||!Array.isArray(args.items)||!args.items.length||args.items.length>512||new Set(args.items.map(x=>x.node_id)).size!==args.items.length||args.items.some(x=>!x.node_id||!x.source_id||!x.media_path.startsWith('/')||typeof x.before_disabled!=='boolean'||typeof x.after_disabled!=='boolean'||x.before_disabled===x.after_disabled))return {success:false,error:'EXACT_CAMERA_VISIBILITY_DECISIONS_REQUIRED'};
  const literal=JSON.stringify(args.items).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
  const script=buildToolScript(`${SNAPSHOT_FUNCTION}\n${NATIVE_STATE_COMPARE}
   var requests=${literal},s=app.project.activeSequence,before=__labSnapshot(),expected=JSON.parse(JSON.stringify(before)),checked=[];
   for(var i=0;i<requests.length;i++){var w=requests[i],found=null,copy=null;for(var t=0;t<s.videoTracks.numTracks;t++)for(var j=0;j<s.videoTracks[t].clips.numItems;j++){var c=s.videoTracks[t].clips[j];if(String(c.nodeId)===w.node_id){if(found)throw Error('CAMERA_ITEM_AMBIGUOUS');found=c;}}
    for(var t=0;t<expected.tracks.length;t++)if(expected.tracks[t].kind===0)for(var j=0;j<expected.tracks[t].clips.length;j++)if(expected.tracks[t].clips[j].id===w.node_id)copy=expected.tracks[t].clips[j];
    if(!found||!copy||!found.projectItem||String(found.projectItem.nodeId)!==w.source_id||String(found.projectItem.getMediaPath())!==w.media_path||found.projectItem.isOffline()||flag(found.disabled)!==w.before_disabled)throw Error('CAMERA_TARGET_CHANGED');copy.disabled=w.after_disabled;checked.push(found);
   }
   for(var i=0;i<checked.length;i++)checked[i].disabled=requests[i].after_disabled;
   var after=__labSnapshot();if(!same(JSON.parse(JSON.stringify(after)),expected))throw Error('UNEXPECTED_CHANGE_DURING_CAMERA_SELECTION');
   return __result({changed_items:checked.length,snapshot:after,verification:'only_requested_video_visibility_changed',audio:'unchanged',source_clocks:'unchanged',effects:'unchanged',persistence:'not_run',rendered:'not_run'});
  `);
  try{parse(script,{ecmaVersion:3,allowReserved:false});}catch(e){return {success:false,error:'ES3_SYNTAX_REJECTED_BEFORE_DISPATCH: '+String(e)};}
  return sendCommand(script,options);
 }
}};}

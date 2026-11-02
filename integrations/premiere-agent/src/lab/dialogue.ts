import { sendCommand, type BridgeOptions } from '../bridge/file-bridge.js';
import { buildToolScript } from '../bridge/script-builder.js';
import { SNAPSHOT_FUNCTION, labContext } from './context.js';

// An explicit, item-local chain. No automatic settings, source replacement,
// track/master processing, or parameter-unit inference.
export type DialogueEffect = { node_id:string; source_id:string; effect_name:string;
  action:'append'|'configure'; parameters:{name:string;value:number}[] };
const effects=['Amplify','Single-band Compressor','Hard Limiter','Highpass'];
export function validateDialogueEffect(r:DialogueEffect){
  if(!r || !['node_id','source_id'].every(k=>typeof (r as any)[k]==='string' && (r as any)[k].length>0 && (r as any)[k].length<512)
     || !effects.includes(r.effect_name) || !['append','configure'].includes(r.action))throw Error('INVALID_DIALOGUE_TARGET');
  if(!Array.isArray(r.parameters)||r.parameters.length>16 || (r.action==='append' && r.parameters.length) || (r.action==='configure'&&!r.parameters.length))throw Error('INVALID_DIALOGUE_PARAMETERS');
  if(new Set(r.parameters.map(p=>p.name)).size!==r.parameters.length || r.parameters.some(p=>typeof p.name!=='string'||!p.name||p.name.length>128||typeof p.value!=='number'||!Number.isFinite(p.value)||Math.abs(p.value)>20000))throw Error('INVALID_DIALOGUE_PARAMETERS');
}
export function dialogueEffectScript(r:DialogueEffect){
  validateDialogueEffect(r);
  return `${SNAPSHOT_FUNCTION}
  var r=${JSON.stringify(r).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029')},s=app.project.activeSequence;
  var before=JSON.parse(JSON.stringify(__labSnapshot())),found=null,ti=-1;
  for(var t=0;t<s.audioTracks.numTracks;t++){var tr=s.audioTracks[t];for(var i=0;i<tr.clips.numItems;i++){var c=tr.clips[i];if(String(c.nodeId)===r.node_id){if(found)throw Error('AMBIGUOUS_DIALOGUE_ITEM');found=c;ti=t;}}}
  if(!found||!found.projectItem||String(found.projectItem.nodeId)!==r.source_id||s.audioTracks[ti].isLocked()||s.audioTracks[ti].isMuted()||found.getSpeed()!==1||found.isSpeedReversed())throw Error('DIALOGUE_TARGET_CHANGED');
  function chain(){var out=[];for(var i=0;i<found.components.numItems;i++)out.push(found.components[i]);return out;}
  var old=chain(),matches=[];for(var i=0;i<old.length;i++)if(String(old[i].displayName)===r.effect_name)matches.push(i);
  var ci=-1;
  if(r.action==='append'){
    if(matches.length)throw Error('DIALOGUE_EFFECT_EXISTS_RECONCILE');
    app.enableQE();var qs=qe.project.getActiveSequence(),qt=qs&&qs.getAudioTrackAt(ti),qc=qt&&__findQeClipByDomClip(qt,found);
    var fx=qe.project.getAudioEffectByName(r.effect_name);
    if(!qc||!fx)throw Error('DIALOGUE_EFFECT_UNAVAILABLE');
    qc.addAudioEffect(fx);var now=chain();
    if(now.length!==old.length+1||String(now[now.length-1].displayName)!==r.effect_name)throw Error('DIALOGUE_APPEND_READBACK_FAILED');
    ci=now.length-1;
  }else{
    if(matches.length!==1)throw Error('DIALOGUE_EFFECT_NOT_UNIQUE');ci=matches[0];
    var comp=found.components[ci],resolved=[];
    for(var i=0;i<r.parameters.length;i++){
      var pp=null;for(var j=0;j<comp.properties.numItems;j++)if(String(comp.properties[j].displayName)===r.parameters[i].name){if(pp)throw Error('AMBIGUOUS_DIALOGUE_PARAMETER');pp=comp.properties[j];}
      if(!pp||typeof pp.getValue()!=='number'||pp.isTimeVarying())throw Error('DIALOGUE_PARAMETER_UNAVAILABLE');resolved.push(pp);
    }
    for(var i=0;i<resolved.length;i++){resolved[i].setValue(r.parameters[i].value,false);if(Math.abs(resolved[i].getValue()-r.parameters[i].value)>0.000001)throw Error('DIALOGUE_PARAMETER_READBACK_FAILED');}
  }
  var after=JSON.parse(JSON.stringify(__labSnapshot()));
  function item(x){for(var t=0;t<x.tracks.length;t++)if(x.tracks[t].kind===1)for(var i=0;i<x.tracks[t].clips.length;i++)if(x.tracks[t].clips[i].id===r.node_id)return x.tracks[t].clips[i];throw Error('DIALOGUE_SNAPSHOT_MISSING');}
  var bi=item(before),ai=item(after),observed=JSON.parse(JSON.stringify(ai.components[ci]));
  if(r.action==='append')ai.components.splice(ci,1);
  else{for(var i=0;i<r.parameters.length;i++){var n=r.parameters[i].name;for(var j=0;j<ai.components[ci].properties.length;j++)if(ai.components[ci].properties[j].name===n)ai.components[ci].properties[j]=bi.components[ci].properties[j];}}
  if(JSON.stringify(before)!==JSON.stringify(after))throw Error('PROTECTED_DIALOGUE_STATE_CHANGED_PARTIAL_EXECUTION');
  return __result({node_id:r.node_id,component_index:ci,component:observed,verification:'item_local_effect_only',rendered:'pending',listening:'not_performed'});`;
}
export function getDialogueTools(options:BridgeOptions){return {
  lab_apply_dialogue_effect:{description:'Append or configure one explicit native dialogue effect on one identified audio item. Exact scoped host and snapshot guard required. Parameters are raw inspected values; final rendered mix must be measured.',
    parameters:{type:'object',additionalProperties:false,required:['node_id','source_id','effect_name','action','parameters'],properties:{node_id:{type:'string'},source_id:{type:'string'},effect_name:{type:'string',enum:effects},action:{type:'string',enum:['append','configure']},parameters:{type:'array',items:{type:'object',additionalProperties:false,required:['name','value'],properties:{name:{type:'string'},value:{type:'number'}}}}}},
    operationalCapability:{backend:'CEP/ExtendScript',backends:['cep','extendscript'],status:'experimental',minimumPremiereVersion:'26.3.0',hostVerificationRequired:true,notes:['Native dialogue effect transport; no automatic acoustic approval.']},
    handler:async(r:DialogueEffect)=>{try{if(!labContext.getStore())throw Error('LAB_GUARD_REQUIRED');return await sendCommand(buildToolScript(dialogueEffectScript(r)),options);}catch(e){return {success:false,error:String(e)};}}
  }
};}

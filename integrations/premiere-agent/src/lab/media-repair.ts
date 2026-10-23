import { existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { buildToolScript, escapeForExtendScript } from '../bridge/script-builder.js';
import { sendCommand, type BridgeOptions } from '../bridge/file-bridge.js';
import { labContext } from './context.js';

export function getLabMediaRepairTools(options: BridgeOptions) {
 return { lab_relink_media_batch: {
  description: 'Repair an explicitly scoped offline-media batch in a new saved project copy. Preflights exact item IDs, old paths and existing replacements before writes. Preserves structural state across every sequence, relinks with compatibility checks, saves and reopens the copy, then verifies paths/online state and sequence structure. Unlisted offline media stays untouched. Requires media_repair snapshot and expiring media-repair scope. Effects and rendered appearance are outside this guard. No retry or rollback after partial failure.',
  parameters: { type:'object', additionalProperties:false, required:['items','output_path'], properties:{
   items:{type:'array',minItems:1,maxItems:100,description:'Exact offline items to repair.',items:{type:'object',additionalProperties:false,required:['item_id','expected_current_path','new_path'],properties:{item_id:{type:'string',minLength:1,description:'Exact native item node ID.'},expected_current_path:{type:'string',description:'Exact current offline media path.'},new_path:{type:'string',description:'Existing absolute replacement path in authorized inputs.'}}}},
   output_path:{type:'string',description:'New .prproj copy inside authorized write root; must not exist.'}
  }},
  operationalCapability:{backend:'CEP/ExtendScript',backends:['cep','extendscript'],status:'experimental' as const,minimumPremiereVersion:'26.3.0',hostVerificationRequired:true,notes:['Media and structural state only; effects/rendering excluded.']},
  handler:async(args:{items:{item_id:string,expected_current_path:string,new_path:string}[],output_path:string})=>{
   if(labContext.getStore()?.snapshotMode!=='media_repair')return {success:false,error:'MEDIA_REPAIR_GUARD_REQUIRED'};
   if(!Array.isArray(args.items)||args.items.length<1||args.items.length>100||new Set(args.items.map(x=>x.item_id)).size!==args.items.length)return {success:false,error:'MEDIA_REPAIR_ITEMS_INVALID'};
   if(!path.isAbsolute(args.output_path)||!args.output_path.endsWith('.prproj')||existsSync(args.output_path)||!existsSync(path.dirname(args.output_path)))return {success:false,error:'MEDIA_REPAIR_OUTPUT_MUST_BE_NEW'};
   for(const item of args.items)if(!/^[a-zA-Z0-9_-]+$/.test(item.item_id)||!path.isAbsolute(item.new_path)||!existsSync(item.new_path)||!statSync(item.new_path).isFile())return {success:false,error:'MEDIA_REPAIR_INPUT_INVALID'};
   const q=(s:string)=>'"'+escapeForExtendScript(s)+'"';
   const batch='['+args.items.map(x=>`{id:${q(x.item_id)},old:${q(x.expected_current_path)},next:${q(x.new_path)}}`).join(',')+']';
   return sendCommand(buildToolScript(`
    var batch=${batch},out=${q(args.output_path)},baseline=__labSnapshot(),expected=JSON.parse(JSON.stringify(baseline)),targets=[];
    for(var i=0;i<batch.length;i++){
     var item=__findProjectItem(batch[i].id);if(!item||String(item.nodeId)!==batch[i].id||String(item.getMediaPath())!==batch[i].old||!item.isOffline())throw Error('MEDIA_REPAIR_TARGET_CHANGED:'+batch[i].id);
     if(!File(batch[i].next).exists)throw Error('MEDIA_REPAIR_FILE_MISSING');targets.push(item);
     var found=false;for(var m=0;m<expected.media.length;m++)if(expected.media[m].id===batch[i].id){expected.media[m].path=batch[i].next;expected.media[m].offline=false;found=true;}if(!found)throw Error('MEDIA_REPAIR_ID_NOT_IN_BASELINE');
    }
    if(File(out).exists)throw Error('MEDIA_REPAIR_OUTPUT_EXISTS');
    app.project.saveAs(out);if(String(app.project.path)!==out||!File(out).exists)throw Error('MEDIA_REPAIR_SAVE_AS_FAILED');
    expected.projectPath=out;
    for(var j=0;j<targets.length;j++){
     targets[j].changeMediaPath(batch[j].next,false);
     if(String(targets[j].getMediaPath())!==batch[j].next||targets[j].isOffline())throw Error('MEDIA_REPAIR_POSTCONDITION_FAILED:'+batch[j].id);
    }
    var repaired=__labSnapshot();if(JSON.stringify(repaired)!==JSON.stringify(expected))throw Error('MEDIA_REPAIR_PROTECTED_STATE_CHANGED');
    app.project.save();if(!File(out).exists)throw Error('MEDIA_REPAIR_SAVE_FAILED');
    app.project.closeDocument(0,0);if(!app.openDocument(out,true,true,true))throw Error('MEDIA_REPAIR_REOPEN_FAILED');
    var seq=null;for(var si=0;si<app.project.sequences.numSequences;si++)if(String(app.project.sequences[si].sequenceID)===expected.sequenceId)seq=app.project.sequences[si];
    if(!seq)throw Error('MEDIA_REPAIR_SEQUENCE_MISSING_AFTER_REOPEN');app.project.activeSequence=seq;
    var reopened=__labSnapshot();
    function persistent(v){var x=JSON.parse(JSON.stringify(v)),ids={};for(var m=0;m<x.media.length;m++){ids[x.media[m].id]=x.media[m].name;delete x.media[m].id;}
     for(var s=0;s<x.sequences.length;s++)for(var t=0;t<x.sequences[s].tracks.length;t++)for(var c=0;c<x.sequences[s].tracks[t].clips.length;c++){var clip=x.sequences[s].tracks[t].clips[c];delete clip.id;clip.sourceId=ids[clip.sourceId]||clip.sourceName||null;}return x;}
    if(JSON.stringify(persistent(reopened))!==JSON.stringify(persistent(repaired)))throw Error('MEDIA_REPAIR_PERSISTENCE_CHANGED');
    var offline=[];for(var k=0;k<reopened.media.length;k++)if(reopened.media[k].offline)offline.push(reopened.media[k]);
    return __result({verified:true,relinked:batch.length,projectPath:out,sequenceId:reopened.sequenceId,offline:offline,persistence:'saved_closed_reopened_media_and_structural_state_verified',protectedState:'all sequence timing/source identities, markers, settings and track states; effect values/rendering not inspected'});
   `),options);
  }
 }};
}

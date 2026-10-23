import { AsyncLocalStorage } from "node:async_hooks";
import { escapeForExtendScript } from "../bridge/script-builder.js";
import { PAGED_COMPARE_HELPERS } from "./paged-snapshot.js";
import { MEDIA_REPAIR_SNAPSHOT } from "./media-repair-snapshot.js";

export interface LabCallContext {
  operationId: string;
  projectPath: string;
  sequenceId: string | null;
  expectedSnapshot: string;
  expectedSnapshotPath?: string;
  dispatched: boolean;
  allowNoSequence?: boolean;
  snapshotMode?: "media_repair" | "paged";
}
export const labContext = new AsyncLocalStorage<LabCallContext>();

// ES3 only. Bounded active-sequence precondition, not a complete project digest.
export const SNAPSHOT_FUNCTION = `function __labSnapshot(sequence,page){
 if(page&&(!isFinite(page.offset)||page.offset<0||page.offset%1||!isFinite(page.limit)||page.limit<1||page.limit>50||page.limit%1))throw Error('LAB_SNAPSHOT_PAGE_INVALID');
 var p=app.project,s=sequence||(p&&p.activeSequence),r={projectPath:p?String(p.path):'',sequenceId:s?String(s.sequenceID):null,tracks:[]};
 // Premiere may expose a different open project's active timeline after newProject.
 if(s&&p&&p.sequences){var owned=false;for(var si=0;si<p.sequences.numSequences;si++)if(String(p.sequences[si].sequenceID)===String(s.sequenceID)){owned=true;break;}if(!owned){s=null;r.sequenceId=null;}}
 if(!s)return r;
 var count=0;
 function components(clip){
  var out=[],chain=clip.components;
  if(!chain)return out;
  for(var ci=0;ci<chain.numItems;ci++){
   var comp=chain[ci],cr={name:String(comp.displayName),matchName:String(comp.matchName),properties:[]};
   for(var pi=0;pi<comp.properties.numItems;pi++){
    var prop=comp.properties[pi],pr={name:String(prop.displayName)};
    try{pr.value=prop.getValue();}catch(e){pr.valueUnavailable=true;}
    try{
     if(prop.isTimeVarying()){
      var keys=prop.getKeys();pr.keys=[];
      if(keys&&keys.length>1000)throw new Error('LAB_KEYFRAME_LIMIT');
      for(var ki=0;keys&&ki<keys.length;ki++)pr.keys.push({ticks:String(keys[ki].ticks),value:prop.getValueAtKey(keys[ki])});
     }
    }catch(e2){if(String(e2).indexOf('LAB_KEYFRAME_LIMIT')>=0)throw e2;pr.keyframesUnavailable=true;}
    cr.properties.push(pr);
   }
   out.push(cr);
  }
  return out;
 }
 r.markers=[];
 if(s.markers){
  var marker=s.markers.getFirstMarker(),mc=0;
  while(marker){if(++mc>2000)throw new Error('LAB_MARKER_LIMIT');r.markers.push({name:String(marker.name),comments:String(marker.comments),start:String(marker.start.ticks),end:String(marker.end.ticks)});marker=s.markers.getNextMarker(marker);}
 }
 if(typeof s.getSettings==='function')r.settings=s.getSettings();
 for(var kind=0;kind<2;kind++){
  var tracks=kind?s.audioTracks:s.videoTracks;
  for(var t=0;t<tracks.numTracks;t++){
   var tr=tracks[t],row={kind:kind,index:t,name:String(tr.name),locked:typeof tr.isLocked==='function'?tr.isLocked():null,muted:typeof tr.isMuted==='function'?tr.isMuted():null,clips:[]};
   var clipTotal=tr.clips.numItems;
   for(var c=0;c<clipTotal;c++){
    if(++count>10000)throw new Error('LAB_SNAPSHOT_LIMIT');
    if(page&&(count<=page.offset||count>page.offset+page.limit))continue;
    var clip=tr.clips[c];
    row.clips.push({id:String(clip.nodeId),name:String(clip.name),sourceId:clip.projectItem?String(clip.projectItem.nodeId):null,start:String(clip.start.ticks),end:String(clip.end.ticks),inPoint:String(clip.inPoint.ticks),outPoint:String(clip.outPoint.ticks),speed:clip.getSpeed(),disabled:!!clip.disabled,components:components(clip)});
   }
   if(page)row._clip_total=clipTotal;
   r.tracks.push(row);
  }
 }
 // Full snapshots remain bounded; transport pages large responses without truncation.
 if(page)r._paging={offset:page.offset,limit:page.limit,total:count};
 if(JSON.stringify(r).length>(page?1500000:4000000))throw new Error(page?'LAB_SNAPSHOT_PAGE_SIZE_LIMIT':'LAB_SNAPSHOT_SIZE_LIMIT');
 return r;
}`;

export const PAGED_COMPARE_FUNCTION = SNAPSHOT_FUNCTION + "\n" + PAGED_COMPARE_HELPERS;

export function guardCepScript(script: string): string {
  const ctx = labContext.getStore();
  if (!ctx) return script;
  ctx.dispatched = true;
  const q = (v: string) => '"' + escapeForExtendScript(v) + '"';
  const expected = ctx.expectedSnapshotPath
    ? `(function(){var f=File(${q(ctx.expectedSnapshotPath!)});if(!f.exists||!f.open('r'))throw new Error('GUARD_SNAPSHOT_MISSING');f.encoding='UTF-8';var v=f.read();f.close();return v;})()`
    : q(ctx.expectedSnapshot);
  return `(function(){${ctx.snapshotMode === 'media_repair' ? MEDIA_REPAIR_SNAPSHOT : ctx.snapshotMode === 'paged' ? PAGED_COMPARE_FUNCTION : SNAPSHOT_FUNCTION}
 var op=${q(ctx.operationId)},p=${q(ctx.projectPath)},s=${ctx.sequenceId === null ? "null" : q(ctx.sequenceId)};
 function same(a,b){if(a===b)return true;if(a===null||b===null||typeof a!==typeof b||typeof a!=='object')return false;var aa=Object.prototype.toString.call(a)==='[object Array]',bb=Object.prototype.toString.call(b)==='[object Array]';if(aa!==bb||(aa&&a.length!==b.length))return false;var count=0;for(var k in a)if(Object.prototype.hasOwnProperty.call(a,k)){count++;if(!Object.prototype.hasOwnProperty.call(b,k)||!same(a[k],b[k]))return false;}for(var k in b)if(Object.prototype.hasOwnProperty.call(b,k))count--;return count===0;}
 if(!app.project||!app.project.sequences)return JSON.stringify({success:false,error:'LAB_SEQUENCE_OWNERSHIP_UNAVAILABLE'});
 ${ctx.snapshotMode === 'paged' ? `
 if(s===null)return JSON.stringify({success:false,error:'LAB_OWNED_SEQUENCE_REQUIRED'});
 if(!app.project||String(app.project.path)!==p||!app.project.activeSequence||String(app.project.activeSequence.sequenceID)!==s)return JSON.stringify({success:false,error:'LAB_TARGET_CHANGED'});
 var key='__premiereAgentLabGuard',previous=$.global[key];
 var expected=previous&&previous.op===op&&previous.nativeExpected?previous.nativeExpected:JSON.parse(${expected});
 if(!__labVerifyPages(expected,null,same))return JSON.stringify({success:false,error:'LAB_STALE_STATE'});
 ` : `
 var current=__labSnapshot();
 if(s===null&&${ctx.allowNoSequence === true ? 'false' : 'true'})return JSON.stringify({success:false,error:'LAB_OWNED_SEQUENCE_REQUIRED'});
 if(current.projectPath!==p||current.sequenceId!==s)return JSON.stringify({success:false,error:'LAB_TARGET_CHANGED'});
 var key='__premiereAgentLabGuard';
 var previous=$.global[key];
 var expected=previous&&previous.op===op?previous.snapshot:${expected};
 if(typeof JSON.parse!=='function')return JSON.stringify({success:false,error:'LAB_JSON_PARSE_UNAVAILABLE'});
 if(!same(JSON.parse(JSON.stringify(current)),JSON.parse(expected)))return JSON.stringify({success:false,error:'LAB_STALE_STATE'});
 `}
 var result=(function(){return ${script.trim().replace(/;\s*$/, "")};}());
 ${ctx.snapshotMode === 'paged' ? '$.global[key]={op:op,nativeExpected:__labCapturePages()};' : '$.global[key]={op:op,snapshot:JSON.stringify(__labSnapshot())};'}
 return result;
}())`;
}

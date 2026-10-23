/** Assembly-owned, sample-precise audio edge operation for the opt-in Lab.
 * Uses the existing Lab guard, queue, journal and CEP transport. No raw-code
 * parameter, new connector authority, source selection or automatic replay.
 */
import {openSync, readSync, closeSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
export const TOOL = 'lab_apply_assembly_audio_edges';
export const TPS = 254016000000n;
const KEYS = ['start', 'end', 'inPoint', 'outPoint'];
const tick = v => typeof v === 'string' && /^(0|[1-9][0-9]{0,15})$/.test(v) && BigInt(v) <= BigInt(Number.MAX_SAFE_INTEGER);

export function inspectWave(file) {
  const fd=openSync(file,'r');
  try {
    const h=Buffer.alloc(12);if(readSync(fd,h,0,12,0)!==12 || !['RIFF','RF64'].includes(h.toString('ascii',0,4)) || h.toString('ascii',8,12)!=='WAVE')throw Error('PCM_WAVE_SOURCE_REQUIRED');
    let at=12;
    for(let n=0;n<128;n++){
      const b=Buffer.alloc(8);if(readSync(fd,b,0,8,at)!==8)break;
      const size=b.readUInt32LE(4);
      if(b.toString('ascii',0,4)==='fmt '){
        if(size<16||size>4096)throw Error('INVALID_WAVE_FORMAT');
        const fmt=Buffer.alloc(size);if(readSync(fd,fmt,0,size,at+8)!==size)throw Error('TRUNCATED_WAVE_FORMAT');
        let tag=fmt.readUInt16LE(0);
        if(tag===65534&&size>=40)tag=fmt.readUInt16LE(24);
        if(![1,3].includes(tag))throw Error('UNCOMPRESSED_PCM_WAVE_REQUIRED');
        return {sample_rate:fmt.readUInt32LE(4),channels:fmt.readUInt16LE(2),bits:fmt.readUInt16LE(14)};
      }
      at+=8+size+(size%2);if(at>16*1024*1024)break;
    }
    throw Error('WAVE_FORMAT_NOT_FOUND');
  } finally {closeSync(fd);}
}

export function inspectPcmSource(file) {
  if(/\.wav$/i.test(file))return inspectWave(file);
  // PCM-in-MOV keeps source-linked picture/audio together without re-encoding picture.
  const data=JSON.parse(execFileSync(process.env.ASSEMBLY_FFPROBE||'ffprobe',[
    '-v','error','-select_streams','a:0','-show_entries','stream=codec_name,sample_rate,channels','-of','json',file
  ],{encoding:'utf8',timeout:15000,maxBuffer:1024*1024}));
  const stream=data.streams?.[0];
  if(!stream||!/^pcm_(s16|s24|s32|f32|f64)(le|be)$/.test(stream.codec_name))throw Error('CONFORM_TO_PCM_SOURCE_FIRST');
  return {sample_rate:Number(stream.sample_rate),channels:stream.channels};
}

export function validateAudioEdges(args) {
  if (!args || !Number.isInteger(args.sample_rate) || ![44100, 48000, 96000].includes(args.sample_rate)) throw Error('SUPPORTED_SAMPLE_RATE_REQUIRED');
  if (!Array.isArray(args.items) || !args.items.length || args.items.length > 128) throw Error('BOUNDED_AUDIO_ITEMS_REQUIRED');
  const sampleTicks = TPS / BigInt(args.sample_rate), ids = new Set();
  for (const r of args.items) {
    if (!r || typeof r.node_id !== 'string' || !r.node_id || ids.has(r.node_id) || typeof r.source_id !== 'string' || !r.source_id) throw Error('UNIQUE_NATIVE_AUDIO_IDENTITIES_REQUIRED');
    if(typeof r.media_path!=='string'||!r.media_path.startsWith('/')||r.media_path.includes('\0'))throw Error('EXACT_PCM_SOURCE_PATH_REQUIRED');
    ids.add(r.node_id);
    for (const state of [r.before, r.after]) {
      if (!state || !KEYS.every(k => tick(state[k]))) throw Error('EXACT_SAFE_TICK_STRINGS_REQUIRED');
      const [s,e,i,o] = KEYS.map(k => BigInt(state[k]));
      if (e <= s || o <= i || e-s !== o-i) throw Error('SOURCE_TIMELINE_DURATION_MISMATCH');
    }
    const b = r.before, a = r.after;
    if (BigInt(a.start)-BigInt(b.start) !== BigInt(a.inPoint)-BigInt(b.inPoint) || BigInt(a.end)-BigInt(b.end) !== BigInt(a.outPoint)-BigInt(b.outPoint)) throw Error('AUDIO_SYNC_OFFSET_CHANGED');
    if (KEYS.some(k => BigInt(a[k]) % sampleTicks !== 0n)) throw Error('AUDIO_EDGE_OFF_SAMPLE_GRID');
    if (KEYS.some(k => { const d=BigInt(a[k])-BigInt(b[k]); return d > TPS || d < -TPS; })) throw Error('EDGE_CHANGE_EXCEEDS_ONE_SECOND');
    if (BigInt(a.start) >= BigInt(b.end) || BigInt(b.start) >= BigInt(a.end)) throw Error('EDGE_REPAIR_MUST_OVERLAP_ORIGINAL');
  }
  return args;
}

export function makeAudioEdgeTool({sendCommand, buildToolScript, snapshotFunction, inspectPcm=inspectPcmSource}, options) {
  const geometry = {type:'object', additionalProperties:false, required:KEYS, properties:Object.fromEntries(KEYS.map(k=>[k,{type:'string',pattern:'^(0|[1-9][0-9]{0,15})$'}]))};
  return {
    description:'Adjust only explicitly identified audio source/timeline edges at sample precision while preserving source-to-timeline sync, picture, other items and effects. Requires full expected geometry. Exact tick readback, no one-frame tolerance, no implicit save/rollback or listening approval. Requires an exact-project assembly scope or disposable-research lease.',
    parameters:{type:'object', additionalProperties:false, required:['sample_rate','items'],properties:{sample_rate:{type:'integer',enum:[44100,48000,96000]},items:{type:'array',minItems:1,maxItems:128,items:{type:'object',additionalProperties:false,required:['node_id','source_id','media_path','before','after'],properties:{node_id:{type:'string',minLength:1,maxLength:512},source_id:{type:'string',minLength:1,maxLength:512},media_path:{type:'string',minLength:1,maxLength:4096},before:geometry,after:geometry}}}}},
    operationalCapability:{backend:'CEP/ExtendScript',backends:['cep','extendscript'],status:'experimental',minimumPremiereVersion:'26.3.0',hostVerificationRequired:true,notes:['Assembly-owned exact audio edge operation; bounded fixture evidence only.']},
    handler:async args=>{
      try {
        validateAudioEdges(args);
        for(const row of args.items)if(inspectPcm(row.media_path).sample_rate!==args.sample_rate)throw Error('CONFORM_PCM_TO_SEQUENCE_SAMPLE_RATE_FIRST');
      } catch(e) {return {success:false,error:String(e)};}
      const literal=JSON.stringify(args).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
      return sendCommand(buildToolScript(`${snapshotFunction}
var request=${literal},seq=app.project.activeSequence,before=__labSnapshot(),targets=[],byId={},linkPairs=[],relinked=[];
function geom(c){return {start:String(c.start.ticks),end:String(c.end.ticks),inPoint:String(c.inPoint.ticks),outPoint:String(c.outPoint.ticks)};}
function same(a,b){return JSON.stringify(a)===JSON.stringify(b);}
function assignTime(c,key,ticks){var t=new Time();t.ticks=ticks;c[key]=t;}
if(!seq)throw Error('NO_ACTIVE_SEQUENCE');
if(typeof seq.getSelection!=='function'||typeof seq.linkSelection!=='function')throw Error('NATIVE_LINK_RESTORE_API_UNAVAILABLE');
var originalSelection=seq.getSelection(),selectedIds=[];
for(var si=0;si<originalSelection.length;si++)selectedIds.push(String(originalSelection[si].nodeId));
function members(c){
 if(typeof c.getLinkedItems!=='function')throw Error('NATIVE_LINK_API_UNAVAILABLE');
 var items=c.getLinkedItems();if(items===null)return null;
 if(!items||typeof items.numItems!=='number')throw Error('NATIVE_LINK_COLLECTION_UNAVAILABLE');
 var ids=[];for(var i=0;i<items.numItems;i++)ids.push(String(items[i].nodeId));return ids.sort();
}
function clearSelection(){
 var current=seq.getSelection();for(var i=0;i<current.length;i++)current[i].setSelected(false,true);
}
if(!before.settings||!before.settings.audioSampleRate||String(before.settings.audioSampleRate.ticks)!==String(TICKS_PER_SECOND/request.sample_rate))throw Error('SEQUENCE_SAMPLE_RATE_MISMATCH');
for(var n=0;n<request.items.length;n++){
 var r=request.items[n],found=__findClip(r.node_id);
 if(!found||found.trackType!=='audio')throw Error('AUDIO_TARGET_NOT_FOUND');
 var c=found.clip,tr=seq.audioTracks[found.trackIndex];
 if(tr.isLocked()||c.disabled||!c.projectItem||String(c.projectItem.nodeId)!==r.source_id||String(c.projectItem.getMediaPath())!==r.media_path||c.projectItem.isOffline())throw Error('AUDIO_TARGET_UNAVAILABLE');
 if(c.getSpeed()!==1||c.isSpeedReversed())throw Error('ONLY_FORWARD_UNIT_SPEED_AUDIO');
 if(!same(geom(c),r.before))throw Error('STALE_AUDIO_GEOMETRY');
 var group=members(c);
 if(!group||group.length!==2||group.indexOf(String(c.nodeId))<0)throw Error('EXACT_NATIVE_AV_PAIR_REQUIRED');
 var peerId=group[0]===String(c.nodeId)?group[1]:group[0],peer=__findClip(peerId);
 if(!peer||peer.trackType!=='video'||!peer.clip.projectItem||String(peer.clip.projectItem.nodeId)!==r.source_id||!same(members(peer.clip),group))throw Error('EXACT_NATIVE_AV_PAIR_REQUIRED');
 linkPairs.push({audio:c,video:peer.clip,ids:group});
 for(var ci=0;ci<c.components.numItems;ci++)for(var pi=0;pi<c.components[ci].properties.numItems;pi++){
  var prop=c.components[ci].properties[pi];
  if(prop.isTimeVarying&&prop.isTimeVarying()){
   var keys=prop.getKeys();if(keys&&keys.length)throw Error('KEYFRAMED_AUDIO_REQUIRES_OWNED_RETIMING');
  }
 }
 targets.push({clip:c,row:r,track:found.trackIndex});byId['id:'+r.node_id]=r;
}
// Check all final audio intervals before any write, including unmodified peers.
for(var ti=0;ti<seq.audioTracks.numTracks;ti++){
 var track=seq.audioTracks[ti],ranges=[];
 for(var j=0;j<track.clips.numItems;j++){var item=track.clips[j],rr=byId['id:'+String(item.nodeId)],g=rr?rr.after:geom(item);ranges.push({s:Number(g.start),e:Number(g.end),changed:!!rr});}
 ranges.sort(function(a,b){return a.s-b.s;});
 for(var x=0;x<ranges.length;x++)for(var y=x+1;y<ranges.length&&ranges[y].s<ranges[x].e;y++)if(ranges[x].changed||ranges[y].changed)throw Error('PLANNED_AUDIO_OVERLAP');
}
// Shrink to shared intervals first. Extending final edges cannot overwrite a peer.
for(var n=0;n<targets.length;n++){
 var x=targets[n],c=x.clip,b=x.row.before,a=x.row.after;
 assignTime(c,'start',String(Math.max(Number(b.start),Number(a.start))));
 assignTime(c,'end',String(Math.min(Number(b.end),Number(a.end))));
}
for(var n=0;n<targets.length;n++){
 var x=targets[n],c=x.clip,a=x.row.after;
 assignTime(c,'inPoint',a.inPoint);assignTime(c,'outPoint',a.outPoint);
 assignTime(c,'end',a.end);assignTime(c,'start',a.start);
 var actual=geom(c);if(!same(actual,a))throw Error('EXACT_AUDIO_EDGE_READBACK_FAILED:'+x.row.node_id+':'+JSON.stringify(actual));
}
// Some native independent trims remove AV links while preserving exact geometry.
// Restore only a proven original pair whose current memberships are both null.
for(var n=0;n<linkPairs.length;n++){
 var pair=linkPairs[n],am=members(pair.audio),vm=members(pair.video);
 if(same(am,pair.ids)&&same(vm,pair.ids))continue;
 if(am!==null||vm!==null)throw Error('UNEXPECTED_NATIVE_LINK_CHANGE');
 clearSelection();pair.video.setSelected(true,true);pair.audio.setSelected(true,true);
 var selection=seq.getSelection(),ids=[];for(var j=0;j<selection.length;j++)ids.push(String(selection[j].nodeId));ids.sort();
 if(!same(ids,pair.ids))throw Error('NATIVE_PAIR_SELECTION_MISMATCH');
 seq.linkSelection();
 if(!same(members(pair.audio),pair.ids)||!same(members(pair.video),pair.ids))throw Error('NATIVE_PAIR_RESTORE_FAILED');
 relinked.push(pair.ids);
}
if(relinked.length){clearSelection();for(var si=0;si<selectedIds.length;si++){var item=__findClip(selectedIds[si]);if(!item)throw Error('ORIGINAL_SELECTION_ITEM_MISSING');item.clip.setSelected(true,true);}}
var after=__labSnapshot(),expected=JSON.parse(JSON.stringify(before));
for(var ti=0;ti<expected.tracks.length;ti++)for(var j=0;j<expected.tracks[ti].clips.length;j++){
 var item=expected.tracks[ti].clips[j],rr=byId['id:'+item.id];if(rr)for(var key in rr.after)if(rr.after.hasOwnProperty(key))item[key]=rr.after[key];
}
if(!same(after,expected))throw Error('PROTECTED_SEQUENCE_STATE_CHANGED');
return __result({sample_rate:request.sample_rate,items:request.items,snapshot:after,restored_link_pairs:relinked,verification:'exact_ticks_protected_snapshot_and_native_av_pairs',persistence:'not_run',listening:'not_run'});
`),options);
    }
  };
}

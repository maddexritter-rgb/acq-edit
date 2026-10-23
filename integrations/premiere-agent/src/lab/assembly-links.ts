import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {randomUUID,createHash} from 'node:crypto';
import path from 'node:path';
import { labContext } from "./context.js";
import { digest } from "./runtime.js";
import type { ToolOperationalOverride } from "../tool-capability-report.js";

// Adobe's CEP declarations expose getLinkedItems(): TrackItemCollection:
// https://github.com/Adobe-CEP/Samples/blob/master/PProPanel/jsx/PremierePro.23.0.d.ts
// This is native membership, never the same-source/overlap heuristic.
export const ASSEMBLY_LINK_SNAPSHOT = `
function __labAssemblyLinks(projectPath,sequenceId){
 var p=app.project;if(!p||String(p.path)!==projectPath)throw Error('PROJECT_TARGET_CHANGED');
 if(!p.sequences||p.sequences.numSequences>50)throw Error('SEQUENCE_COLLECTION_UNAVAILABLE');
 var s=null,count=0;for(var i=0;i<p.sequences.numSequences;i++)if(String(p.sequences[i].sequenceID)===sequenceId){s=p.sequences[i];count++;}
 if(count!==1)throw Error('SEQUENCE_TARGET_AMBIGUOUS');
 var rows=[],clips=[],byId={},totalLinks=0;
 function id(v){var x=String(v);if(!x||x==='undefined'||x==='null')throw Error('NATIVE_ID_UNAVAILABLE');return x;}
 function ticks(v){var x=String(v);if(!/^(0|[1-9][0-9]{0,18})$/.test(x)||(x.length===19&&x>'9223372036854775807'))throw Error('EXACT_TICKS_UNAVAILABLE');return x;}
 function flag(v){if(v===true||v===1)return true;if(v===false||v===0)return false;throw Error('NATIVE_FLAG_UNAVAILABLE');}
 function details(c){
  var source=c.projectItem,speed=c.getSpeed();
  if(typeof speed!=='number'||!isFinite(speed)||speed<0)throw Error('PLAYBACK_RATE_UNAVAILABLE');
  if(typeof c.isSpeedReversed!=='function')throw Error('PLAYBACK_DIRECTION_UNAVAILABLE');
  return {node_id:id(c.nodeId),source_id:source?id(source.nodeId):null,
   media_path:source?String(source.getMediaPath()):null,offline:source?flag(source.isOffline()):null,
   start_ticks:ticks(c.start.ticks),end_ticks:ticks(c.end.ticks),source_in_ticks:ticks(c.inPoint.ticks),source_out_ticks:ticks(c.outPoint.ticks),
   speed:speed,speed_reversed:flag(c.isSpeedReversed()),disabled:flag(c.disabled)};
 }
 for(var kind=0;kind<2;kind++){
  var tracks=kind?s.audioTracks:s.videoTracks;if(!tracks||tracks.numTracks>256)throw Error('TRACK_COLLECTION_UNAVAILABLE');
  for(var t=0;t<tracks.numTracks;t++)for(var j=0;j<tracks[t].clips.numItems;j++){
   if(rows.length>=10000)throw Error('LINK_INSPECTION_ITEM_LIMIT');
   var c=tracks[t].clips[j],d=details(c),key='id:'+d.node_id;
   if(byId[key])throw Error('NATIVE_ITEM_ID_AMBIGUOUS');
   var row={kind:kind?'audio':'video',track_index:t,item_index:j,item:d,linked_node_ids:[],self_included:false};
   byId[key]=row;rows.push(row);clips.push(c);
  }
 }
 for(var i=0;i<rows.length;i++){
  var c=clips[i],row=rows[i];if(typeof c.getLinkedItems!=='function')throw Error('NATIVE_LINK_API_UNAVAILABLE');
  var linked=c.getLinkedItems();
  if(!linked||typeof linked.numItems!=='number'||linked.numItems<0||linked.numItems%1||linked.numItems>10000)throw Error('NATIVE_LINK_COLLECTION_UNAVAILABLE');
  var seen={};
  for(var j=0;j<linked.numItems;j++){
   if(++totalLinks>100000)throw Error('LINK_INSPECTION_EDGE_LIMIT');
   var d=details(linked[j]),key='id:'+d.node_id,owned=byId[key];
   if(!owned||seen[key]||JSON.stringify(d)!==JSON.stringify(owned.item))throw Error('FOREIGN_DUPLICATE_OR_CHANGED_LINK_MEMBER');seen[key]=true;
   if(d.node_id===row.item.node_id)row.self_included=true;else row.linked_node_ids.push(d.node_id);
  }
  row.linked_node_ids.sort();
 }
 // Membership must describe whole reciprocal groups, not one-way adjacency.
 for(var i=0;i<rows.length;i++){
  var row=rows[i],group=row.linked_node_ids.concat([row.item.node_id]).sort();
  for(var j=0;j<row.linked_node_ids.length;j++){
   var peer=byId['id:'+row.linked_node_ids[j]],other=peer.linked_node_ids.concat([peer.item.node_id]).sort();
   if(JSON.stringify(group)!==JSON.stringify(other))throw Error('NATIVE_LINK_GROUP_INCONSISTENT');
  }
 }
 if(String(app.project.path)!==projectPath)throw Error('PROJECT_CHANGED_DURING_LINK_INSPECTION');
 var result={project_path:projectPath,sequence_id:sequenceId,frame_duration_ticks:ticks(s.timebase),items:rows};
 if(JSON.stringify(result).length>1500000)throw Error('LINK_INSPECTION_SIZE_LIMIT');
 return result;
}`;

export function validNativeResponse(data: any, target: { project_path: string; sequence_id: string }) {
  const tick = (v: any) => typeof v === "string" && /^(0|[1-9][0-9]{0,18})$/.test(v) && BigInt(v) <= 9223372036854775807n;
  const id = (v: any) => typeof v === "string" && !!v && v !== "undefined" && v !== "null";
  if (!data || typeof data !== "object" || data.project_path !== target.project_path || data.sequence_id !== target.sequence_id || !Array.isArray(data.items) || data.items.length > 10000 || !tick(data.frame_duration_ticks) || data.frame_duration_ticks === "0") return false;
  const ids = new Map<string, any>(), positions = new Set<string>(); let edges = 0;
  for (const r of data.items) {
    const c = r?.item;
    if (!r || !["video", "audio"].includes(r.kind) || !Number.isInteger(r.track_index) || r.track_index < 0 || r.track_index > 255 || !Number.isInteger(r.item_index) || r.item_index < 0 || r.item_index > 9999 || !c || !id(c.node_id) || ids.has(c.node_id) || !Array.isArray(r.linked_node_ids) || typeof r.self_included !== "boolean" || typeof c.speed !== "number" || !Number.isFinite(c.speed) || c.speed < 0 || typeof c.speed_reversed !== "boolean" || typeof c.disabled !== "boolean") return false;
    if (![c.start_ticks, c.end_ticks, c.source_in_ticks, c.source_out_ticks].every(tick) || BigInt(c.end_ticks) <= BigInt(c.start_ticks) || BigInt(c.source_out_ticks) < BigInt(c.source_in_ticks)) return false;
    if (c.source_id === null ? c.media_path !== null || c.offline !== null : !id(c.source_id) || typeof c.media_path !== "string" || typeof c.offline !== "boolean") return false;
    const position = `${r.kind}:${r.track_index}:${r.item_index}`;
    if (positions.has(position) || (edges += r.linked_node_ids.length) > 100000 || r.linked_node_ids.some((v: any) => !id(v) || v === c.node_id) || new Set(r.linked_node_ids).size !== r.linked_node_ids.length) return false;
    positions.add(position); ids.set(c.node_id, r);
  }
  for (const r of data.items) {
    const group = JSON.stringify([...r.linked_node_ids, r.item.node_id].sort());
    for (const peer of r.linked_node_ids) {
      const other = ids.get(peer);
      if (!other || group !== JSON.stringify([...other.linked_node_ids, peer].sort())) return false;
    }
  }
  return true;
}

export function getLabAssemblyLinkTools(options: BridgeOptions) {
  return { inspect_assembly_links: {
    description: "Read exact native TrackItem.getLinkedItems membership for every item in an explicitly owned sequence without activation. Includes source paths, playback and exact ticks. Rejects unavailable, foreign, ambiguous, nonreciprocal or unstable membership. Does not infer linking from matching sources/timing, establish persistence or certify spoken edits.",
    parameters: { type: "object", additionalProperties: false, required: ["project_path", "sequence_id"], properties: {
      project_path: { type: "string", minLength: 1, maxLength: 4096 }, sequence_id: { type: "string", minLength: 1, maxLength: 512 }, paged: { type:"boolean" },
      baseline_path: {type:"string",minLength:1,maxLength:4096}, baseline_sha256:{type:"string",pattern:"^[a-f0-9]{64}$"},
    } },
    operationalCapability: { backend: "CEP/ExtendScript", backends: ["cep", "extendscript"], status: "experimental", minimumPremiereVersion: "26.3.0", hostVerificationRequired: true,
      notes: ["Native getLinkedItems membership requires local host validation. Empty collections establish unlinked items only when the native call succeeds; missing APIs fail. No activation or writes."] } satisfies ToolOperationalOverride,
    handler: async (args: { project_path: string; sequence_id: string; paged?: boolean; baseline_path?:string; baseline_sha256?:string }) => {
      if(args.baseline_path!==undefined||args.baseline_sha256!==undefined){if(args.paged!==true)return {success:false,error:'Baseline requires bounded paged inspection'};return inspectBaselineBoundedLinks(options,args);}
      if(args.paged===true)return inspectStreamedLinks(options,args);
      if(args.paged!==undefined&&typeof args.paged!=="boolean")return {success:false,error:"Invalid paged flag"};
      if (typeof args.project_path !== "string" || !args.project_path.startsWith("/") || args.project_path.length > 4096 || args.project_path.includes("\0") || typeof args.sequence_id !== "string" || !args.sequence_id || args.sequence_id.length > 512 || args.sequence_id.includes("\0")) return { success: false, error: "Exact project and sequence identity required" };
      const literal = JSON.stringify(args).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
      const result = await sendCommand(buildToolScript(`${ASSEMBLY_LINK_SNAPSHOT}
        var target=${literal},first=__labAssemblyLinks(target.project_path,target.sequence_id),second=__labAssemblyLinks(target.project_path,target.sequence_id);
        if(JSON.stringify(first)!==JSON.stringify(second))throw Error('LINK_STATE_CHANGED_DURING_INSPECTION');
        return __result(first);
      `), options);
      if (!result.success) return result;
      const data: any = result.data;
      if (!validNativeResponse(data, args))
        return { success: false, error: "INVALID_NATIVE_LINK_RESPONSE" };
      return { success: true, data: { ...data, revision: digest(data), verification: "stable_native_link_membership", persistence: "not_run" } };
    },
  } };
}

// A previously captured native inventory supplies exact positions and peers,
// never current evidence. Each target and peer is read fresh in batches of50.
// This avoids one monolithic native call on slow long-form media while retaining
// all existing bounds and two complete independently acquired matching passes.
export const BASELINE_LINK_PAGE = `function __labBaselineLinkPage(request){
 var p=app.project;if(!p||String(p.path)!==request.project_path)throw Error('PROJECT_TARGET_CHANGED');
 if(!p.sequences||p.sequences.numSequences>2048)throw Error('SEQUENCE_COLLECTION_UNAVAILABLE');
 var s=null,found=0;for(var i=0;i<p.sequences.numSequences;i++)if(String(p.sequences[i].sequenceID)===request.sequence_id){s=p.sequences[i];found++;}
 if(found!==1)throw Error('SEQUENCE_TARGET_AMBIGUOUS');
 var total=0;for(var kind=0;kind<2;kind++){var tracks=kind?s.audioTracks:s.videoTracks;if(tracks.numTracks>256)throw Error('TRACK_COLLECTION_UNAVAILABLE');for(var t=0;t<tracks.numTracks;t++)total+=tracks[t].clips.numItems;}
 if(total!==request.total||total>10000||String(s.timebase)!==request.frame_duration_ticks)throw Error('BASELINE_INVENTORY_OR_RATE_CHANGED');
 var file=new File(request.page_path);file.encoding='UTF-8';if(!file.open('r'))throw Error('BASELINE_PAGE_UNAVAILABLE');var targets=JSON.parse(file.read());file.close();
 if(!targets||targets.length!==Math.min(50,total-request.offset))throw Error('BASELINE_PAGE_COUNT');
 function flag(v){if(v===true||v===1)return true;if(v===false||v===0)return false;throw Error('NATIVE_FLAG_UNAVAILABLE');}
 function details(c){var src=c.projectItem,speed=c.getSpeed();if(!src||typeof speed!=='number'||!isFinite(speed)||speed<0||typeof c.isSpeedReversed!=='function')throw Error('NATIVE_SOURCE_OR_PLAYBACK_UNAVAILABLE');return {node_id:String(c.nodeId),source_id:String(src.nodeId),media_path:String(src.getMediaPath()),offline:flag(src.isOffline()),start_ticks:String(c.start.ticks),end_ticks:String(c.end.ticks),source_in_ticks:String(c.inPoint.ticks),source_out_ticks:String(c.outPoint.ticks),speed:speed,speed_reversed:flag(c.isSpeedReversed()),disabled:flag(c.disabled)};}
 var rows=[],edges=0;for(var i=0;i<targets.length;i++){var want=targets[i],tracks=want.row.kind==='audio'?s.audioTracks:s.videoTracks,track=tracks[want.row.track_index];if(!track||want.row.item_index>=track.clips.numItems)throw Error('BASELINE_POSITION_CHANGED');var c=track.clips[want.row.item_index],d=details(c);if(JSON.stringify(d)!==JSON.stringify(want.row.item))throw Error('BASELINE_NATIVE_ITEM_CHANGED');
  if(typeof c.getLinkedItems!=='function')throw Error('NATIVE_LINK_API_UNAVAILABLE');var linked=c.getLinkedItems();if(!linked||typeof linked.numItems!=='number'||linked.numItems%1||linked.numItems<0||linked.numItems>10000)throw Error('NATIVE_LINK_COLLECTION_UNAVAILABLE');var peers=[],self=false,seen={};
  for(var j=0;j<linked.numItems;j++){if(++edges>100000)throw Error('LINK_INSPECTION_EDGE_LIMIT');var ld=details(linked[j]),id=ld.node_id;if(seen['id:'+id])throw Error('DUPLICATE_LINK_MEMBER');seen['id:'+id]=true;var expected=id===d.node_id?want.row.item:want.peers['id:'+id];if(!expected||JSON.stringify(ld)!==JSON.stringify(expected))throw Error('FOREIGN_OR_CHANGED_LINK_MEMBER');if(id===d.node_id)self=true;else peers.push(id);}
  peers.sort();if(JSON.stringify(peers)!==JSON.stringify(want.row.linked_node_ids)||self!==want.row.self_included)throw Error('BASELINE_NATIVE_MEMBERSHIP_CHANGED');rows.push({kind:want.row.kind,track_index:want.row.track_index,item_index:want.row.item_index,item:d,linked_node_ids:peers,self_included:self});
 }
 if(String(app.project.path)!==request.project_path)throw Error('PROJECT_CHANGED_DURING_LINK_INSPECTION');var result={project_path:request.project_path,sequence_id:request.sequence_id,frame_duration_ticks:String(s.timebase),items:rows,_paging:{offset:request.offset,limit:50,total:total}};if(JSON.stringify(result).length>1500000)throw Error('LINK_INSPECTION_SIZE_LIMIT');return result;
}`;

export async function inspectBaselineBoundedLinks(options:BridgeOptions,args:{project_path:string;sequence_id:string;baseline_path?:string;baseline_sha256?:string}){
 try{
  if(!options.tempDir||typeof args.baseline_path!=='string'||!path.isAbsolute(args.baseline_path)||args.baseline_path.length>4096||args.baseline_path.includes('\0')||!args.baseline_sha256||!/^[a-f0-9]{64}$/.test(args.baseline_sha256))throw Error('EXACT_NATIVE_BASELINE_PIN_REQUIRED');
  const raw=await readFile(args.baseline_path);if(raw.length>20000000||createHash('sha256').update(raw).digest('hex')!==args.baseline_sha256)throw Error('NATIVE_BASELINE_PIN_CHANGED');const base=JSON.parse(raw.toString('utf8'));if(!validNativeResponse(base,args))throw Error('INVALID_NATIVE_BASELINE');
  const dir=path.join(options.tempDir,'inspection-pages',randomUUID());await mkdir(dir,{recursive:true,mode:0o700});const byId=new Map<string,any>(base.items.map((r:any)=>[r.item.node_id,r.item]));const packets:string[]=[];
  for(let at=0;at<base.items.length||at===0;at+=50){const rows=base.items.slice(at,at+50).map((row:any)=>({row,peers:Object.fromEntries(row.linked_node_ids.map((id:string)=>['id:'+id,byId.get(id)]))}));const text=JSON.stringify(rows);if(Buffer.byteLength(text)>1500000)throw Error('NATIVE_BASELINE_PAGE_LIMIT');const p=path.join(dir,'targets-'+at+'.json');await writeFile(p,text,{flag:'wx',mode:0o400});packets.push(p);if(base.items.length===0)break;}
  const q=(v:unknown)=>JSON.stringify(v).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
  const pass=async(n:number)=>{const data:any={project_path:base.project_path,sequence_id:base.sequence_id,frame_duration_ticks:base.frame_duration_ticks,items:[]};for(let i=0;i<packets.length;i++){const request={project_path:args.project_path,sequence_id:args.sequence_id,total:base.items.length,frame_duration_ticks:base.frame_duration_ticks,offset:i*50,page_path:packets[i]};const reply=await labContext.exit(()=>sendCommand(buildToolScript(`${BASELINE_LINK_PAGE}\nreturn __result(__labBaselineLinkPage(${q(request)}));`),{...options,pagedResponse:true}));if(!reply.success)throw Error('BOUNDED_NATIVE_LINK_READ_FAILED:'+reply.error);const p:any=reply.data;if(!p||p.project_path!==base.project_path||p.sequence_id!==base.sequence_id||p.frame_duration_ticks!==base.frame_duration_ticks||p._paging?.offset!==i*50||p._paging?.limit!==50||p._paging?.total!==base.items.length||!Array.isArray(p.items)||p.items.length!==Math.min(50,base.items.length-i*50)||Buffer.byteLength(JSON.stringify(p))>1500000)throw Error('INVALID_BOUNDED_NATIVE_LINK_PAGE');await writeFile(path.join(dir,`pass-${n}-page-${i*50}.json`),JSON.stringify(p),{flag:'wx',mode:0o400});data.items.push(...p.items);}
   if(!validNativeResponse(data,args)||digest(data)!==digest({project_path:base.project_path,sequence_id:base.sequence_id,frame_duration_ticks:base.frame_duration_ticks,items:base.items}))throw Error('NATIVE_BASELINE_CHANGED_DURING_PASS');return data;};
  const a=await pass(1),b=await pass(2);if(digest(a)!==digest(b))throw Error('LINK_STATE_CHANGED_DURING_BOUNDED_INSPECTION');return {success:true,data:{...b,revision:digest(b),verification:'stable_complete_baseline_bounded_native_link_membership',persistence:'not_run',page_evidence_dir:dir}};
 }catch(e){return {success:false,error:String(e)};}
}

// Per-page native membership proofs retain the original aggregate item/edge caps.
export const ASSEMBLY_LINK_PAGE = `function __labAssemblyLinkPage(projectPath,sequenceId,offset){
 var p=app.project;if(!p||String(p.path)!==projectPath)throw Error('PROJECT_TARGET_CHANGED');
 if(!p.sequences||p.sequences.numSequences>2048)throw Error('SEQUENCE_COLLECTION_UNAVAILABLE');
 var s=null,count=0;for(var i=0;i<p.sequences.numSequences;i++)if(String(p.sequences[i].sequenceID)===sequenceId){s=p.sequences[i];count++;}
 if(count!==1)throw Error('SEQUENCE_TARGET_AMBIGUOUS');
 var all=[],byId={},rows=[],totalLinks=0;
 function id(v){var x=String(v);if(!x||x==='undefined'||x==='null')throw Error('NATIVE_ID_UNAVAILABLE');return x;}
 function ticks(v){var x=String(v);if(!/^(0|[1-9][0-9]{0,18})$/.test(x)||(x.length===19&&x>'9223372036854775807'))throw Error('EXACT_TICKS_UNAVAILABLE');return x;}
 function flag(v){if(v===true||v===1)return true;if(v===false||v===0)return false;throw Error('NATIVE_FLAG_UNAVAILABLE');}
 function details(c){var source=c.projectItem,speed=c.getSpeed();if(typeof speed!=='number'||!isFinite(speed)||speed<0||typeof c.isSpeedReversed!=='function')throw Error('PLAYBACK_RATE_UNAVAILABLE');return {node_id:id(c.nodeId),source_id:source?id(source.nodeId):null,media_path:source?String(source.getMediaPath()):null,offline:source?flag(source.isOffline()):null,start_ticks:ticks(c.start.ticks),end_ticks:ticks(c.end.ticks),source_in_ticks:ticks(c.inPoint.ticks),source_out_ticks:ticks(c.outPoint.ticks),speed:speed,speed_reversed:flag(c.isSpeedReversed()),disabled:flag(c.disabled)};}
 function group(c){if(typeof c.getLinkedItems!=='function')throw Error('NATIVE_LINK_API_UNAVAILABLE');var linked=c.getLinkedItems();if(!linked||typeof linked.numItems!=='number'||linked.numItems<0||linked.numItems%1||linked.numItems>10000)throw Error('NATIVE_LINK_COLLECTION_UNAVAILABLE');var ids=[],seen={};for(var j=0;j<linked.numItems;j++){if(++totalLinks>100000)throw Error('LINK_INSPECTION_EDGE_LIMIT');var d=details(linked[j]),key='id:'+d.node_id,owned=byId[key];if(!owned||seen[key]||JSON.stringify(d)!==JSON.stringify(details(owned.clip)))throw Error('FOREIGN_DUPLICATE_OR_CHANGED_LINK_MEMBER');seen[key]=true;ids.push(d.node_id);}return ids.sort();}
 for(var kind=0;kind<2;kind++){var tracks=kind?s.audioTracks:s.videoTracks;if(!tracks||tracks.numTracks>256)throw Error('TRACK_COLLECTION_UNAVAILABLE');for(var t=0;t<tracks.numTracks;t++)for(var j=0;j<tracks[t].clips.numItems;j++){if(all.length>=10000)throw Error('LINK_INSPECTION_ITEM_LIMIT');var c=tracks[t].clips[j],key='id:'+id(c.nodeId);if(byId[key])throw Error('NATIVE_ITEM_ID_AMBIGUOUS');var r={kind:kind?'audio':'video',track_index:t,item_index:j,clip:c};byId[key]=r;all.push(r);}}
 for(var i=offset;i<Math.min(all.length,offset+50);i++){var x=all[i],d=details(x.clip),g=group(x.clip),self=g.indexOf(d.node_id)>=0,peers=[];for(var j=0;j<g.length;j++)if(g[j]!==d.node_id)peers.push(g[j]);var complete=peers.concat([d.node_id]).sort();for(var j=0;j<peers.length;j++){var pg=group(byId['id:'+peers[j]].clip);if(pg.indexOf(peers[j])<0)pg.push(peers[j]);pg.sort();if(JSON.stringify(pg)!==JSON.stringify(complete))throw Error('NATIVE_LINK_GROUP_INCONSISTENT');}rows.push({kind:x.kind,track_index:x.track_index,item_index:x.item_index,item:d,linked_node_ids:peers,self_included:self});}
 if(String(app.project.path)!==projectPath)throw Error('PROJECT_CHANGED_DURING_LINK_INSPECTION');var result={project_path:projectPath,sequence_id:sequenceId,frame_duration_ticks:ticks(s.timebase),items:rows,_paging:{offset:offset,limit:50,total:all.length}};if(JSON.stringify(result).length>1500000)throw Error('LINK_INSPECTION_SIZE_LIMIT');return result;
}`;
export async function inspectPagedLinks(options:BridgeOptions,args:{project_path:string;sequence_id:string}){
 if(!args.project_path.startsWith('/')||args.project_path.length>4096||!args.sequence_id||args.sequence_id.length>512||args.project_path.includes('\0')||args.sequence_id.includes('\0'))return {success:false,error:'Exact project and sequence identity required'};
 const q=(v:unknown)=>JSON.stringify(v).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
 try{
  const pass=async()=>{let total:number|undefined,data:any;const items:any[]=[];
   for(let offset=0;total===undefined||offset<total;offset+=50){const r=await labContext.exit(()=>sendCommand(buildToolScript(`${ASSEMBLY_LINK_PAGE}\nreturn __result(__labAssemblyLinkPage(${q(args.project_path)},${q(args.sequence_id)},${offset}));`),{...options,pagedResponse:true}));if(!r.success)throw Error('LINK_PAGE_NATIVE_READ_FAILED:'+r.error);const p:any=r.data,c=p?._paging;
    if(Buffer.byteLength(JSON.stringify(p),'utf8')>1500000||!c||p.project_path!==args.project_path||p.sequence_id!==args.sequence_id||c.offset!==offset||c.limit!==50||!Number.isInteger(c.total)||c.total<0||c.total>10000||!Array.isArray(p.items)||p.items.length!==Math.min(50,c.total-offset))throw Error('LINK_PAGE_RESPONSE_INVALID');
    if(data&&(p.frame_duration_ticks!==data.frame_duration_ticks||c.total!==total))throw Error('LINK_PAGE_STATE_CHANGED');total=c.total;data??={project_path:p.project_path,sequence_id:p.sequence_id,frame_duration_ticks:p.frame_duration_ticks};items.push(...p.items);if(total===0)break;
   }data.items=items;if(!validNativeResponse(data,args))throw Error('INVALID_NATIVE_LINK_RESPONSE');return data;
  };const a=await pass(),b=await pass();if(digest(a)!==digest(b))throw Error('LINK_STATE_CHANGED_DURING_PAGED_INSPECTION');return {success:true,data:{...b,revision:digest(b),verification:'stable_complete_paged_native_link_membership',persistence:'not_run'}};
 }catch(e){return {success:false,error:String(e)};}
}

// Collect reciprocal membership once per complete pass, then emit immutable
// local50-item pages. Native item/edge caps and per-page byte caps are unchanged.
export async function inspectStreamedLinks(options:BridgeOptions,args:{project_path:string;sequence_id:string}){
 if(typeof args.project_path!=='string'||!args.project_path.startsWith('/')||args.project_path.length>4096||typeof args.sequence_id!=='string'||!args.sequence_id||args.sequence_id.length>512||args.project_path.includes('\0')||args.sequence_id.includes('\0')||!options.tempDir)return {success:false,error:'Exact native target and private mailbox required'};
 const q=(v:unknown)=>JSON.stringify(v).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
 try{
  const pass=async()=>{
   const dir=path.join(options.tempDir!,'inspection-pages',randomUUID());await mkdir(dir,{recursive:true,mode:0o700});
   const source=ASSEMBLY_LINK_SNAPSHOT.replace('p.sequences.numSequences>50','p.sequences.numSequences>2048').replace(`if(JSON.stringify(result).length>1500000)throw Error('LINK_INSPECTION_SIZE_LIMIT');\n return result;`,
    `var folder=${q(dir)},pages=[];for(var at=0;at<rows.length||at===0;at+=50){var page={project_path:projectPath,sequence_id:sequenceId,frame_duration_ticks:result.frame_duration_ticks,items:rows.slice(at,at+50),_paging:{offset:at,limit:50,total:rows.length}},text=JSON.stringify(page);if(text.length>1500000)throw Error('LINK_INSPECTION_SIZE_LIMIT');var name='page-'+at+'.json',file=new File(folder+'/'+name);if(file.exists||!file.open('w'))throw Error('LINK_INSPECTION_PAGE_FILE_UNAVAILABLE');file.encoding='UTF-8';if(!file.write(text)){file.close();throw Error('LINK_INSPECTION_PAGE_WRITE_FAILED');}file.close();pages.push({name:name,offset:at,count:page.items.length});if(rows.length===0)break;}return {project_path:projectPath,sequence_id:sequenceId,frame_duration_ticks:result.frame_duration_ticks,total:rows.length,pages:pages};`);
   const r=await labContext.exit(()=>sendCommand(buildToolScript(`${source}\nreturn __result(__labAssemblyLinks(${q(args.project_path)},${q(args.sequence_id)}));`),{...options,pagedResponse:true}));if(!r.success)throw Error('LINK_STREAM_NATIVE_READ_FAILED:'+r.error);const m:any=r.data;
   if(!m||m.project_path!==args.project_path||m.sequence_id!==args.sequence_id||!Number.isInteger(m.total)||m.total<0||m.total>10000||!Array.isArray(m.pages)||m.pages.length!==Math.max(1,Math.ceil(m.total/50)))throw Error('INVALID_LINK_STREAM_MANIFEST');
   const data:any={project_path:m.project_path,sequence_id:m.sequence_id,frame_duration_ticks:m.frame_duration_ticks,items:[]};
   for(let i=0;i<m.pages.length;i++){const row=m.pages[i],offset=i*50;if(row.name!==`page-${offset}.json`||row.offset!==offset||row.count!==Math.min(50,m.total-offset))throw Error('INVALID_LINK_STREAM_PAGE_ID');const raw=await readFile(path.join(dir,row.name));if(raw.length>1500000)throw Error('LINK_INSPECTION_SIZE_LIMIT');const page=JSON.parse(raw.toString('utf8'));if(page.project_path!==args.project_path||page.sequence_id!==args.sequence_id||page.frame_duration_ticks!==m.frame_duration_ticks||page._paging?.offset!==offset||page._paging?.limit!==50||page._paging?.total!==m.total||!Array.isArray(page.items)||page.items.length!==row.count)throw Error('INVALID_LINK_STREAM_PAGE');data.items.push(...page.items);}
   if(!validNativeResponse(data,args))throw Error('INVALID_NATIVE_LINK_RESPONSE');return data;
  };const a=await pass(),b=await pass();if(digest(a)!==digest(b))throw Error('LINK_STATE_CHANGED_DURING_PAGED_INSPECTION');return {success:true,data:{...b,revision:digest(b),verification:'stable_complete_paged_native_link_membership',persistence:'not_run'}};
 }catch(e){return {success:false,error:String(e)};}
}

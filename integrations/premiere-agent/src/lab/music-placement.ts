import { createHash } from "node:crypto";
import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { isAbsolute } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import { AUDIO_SOURCE_CLOCK } from "./music-source-clock.js";
import { SNAPSHOT_FUNCTION, labContext } from "./context.js";
import type { ToolOperationalOverride } from "../tool-capability-report.js";

const run = promisify(execFile), TPS = 254016000000n;
export async function mediaHash(path: string): Promise<string> {
  const hash = createHash("sha256");
  for await (const block of createReadStream(path)) hash.update(block);
  return hash.digest("hex");
}
export async function probeMusicMedia(path: string, expectedHash: string) {
  if (!isAbsolute(path) || path.includes("\0") || !/^[a-f0-9]{64}$/.test(expectedHash)) throw new Error("Invalid absolute media identity");
  const before = await stat(path);
  if (!before.isFile() || before.size === 0 || before.size > 8 * 1024 ** 3 || await mediaHash(path) !== expectedHash) throw new Error("Media file missing, excessive or changed");
  const { stdout } = await run("ffprobe", ["-v", "error", "-show_entries", "stream=codec_type,channels,sample_rate,time_base,duration_ts", "-of", "json", path], { timeout: 15000, maxBuffer: 1024 * 1024 });
  const streams = JSON.parse(stdout).streams;
  if (!Array.isArray(streams) || streams.length !== 1 || streams[0].codec_type !== "audio" || ![1, 2].includes(streams[0].channels)) throw new Error("Music placement requires one mono/stereo audio stream and no video/other stream");
  const stream = streams[0], base = /^(\d+)\/(\d+)$/.exec(stream.time_base);
  if (!base || !Number.isSafeInteger(stream.duration_ts) || stream.duration_ts <= 0 || !/^\d+$/.test(stream.sample_rate) || Number(stream.sample_rate) <= 0 || BigInt(base[2]) === 0n) throw new Error("Exact audio duration unavailable");
  const numerator = BigInt(stream.duration_ts) * BigInt(base[1]) * TPS, denominator = BigInt(base[2]);
  if (numerator % denominator || numerator / denominator > 9223372036854775807n || await mediaHash(path) !== expectedHash) throw new Error("Audio duration not representable or media changed during probe");
  return { sha256: expectedHash, channels: stream.channels, sample_rate: stream.sample_rate, duration_ticks: String(numerator / denominator) };
}
const capability = { backend: "CEP/ExtendScript", backends: ["cep", "extendscript"], status: "experimental", minimumPremiereVersion: "26.3.0", hostVerificationRequired: true,
  notes: ["Audio-only mono/stereo. Exact Time objects and subclip source clocks require native acceptance. Preserves bounded source marks/project tree and active timeline; source processing/channel routing, persistence and sound remain unverified."] } satisfies ToolOperationalOverride;
const tick = { type: "string", description: "Exact nonnegative int64 Premiere ticks.", pattern: "^(0|[1-9][0-9]{0,18})$" };
const identity = { type: "string", description: "Exact native identity from fresh inspection.", minLength: 1, maxLength: 512 };
const mediaProperties = {
  media_path: { type: "string", description: "Absolute selected audio file path.", minLength: 1, maxLength: 4096 },
  media_sha256: { type: "string", description: "SHA-256 binding the selected audio file.", pattern: "^[a-f0-9]{64}$" },
  source_in_ticks: tick, source_out_ticks: tick,
};
function exact(t: string) { if (typeof t !== "string" || !/^(0|[1-9]\d{0,18})$/.test(t) || BigInt(t) > 9223372036854775807n) throw new Error("Invalid exact time"); return BigInt(t); }
function id(value: string) { if (typeof value !== "string" || !value || value.length > 512) throw new Error("Invalid native identity"); }
const helpers = `
${AUDIO_SOURCE_CLOCK}
function isOff(value){return value===false||value===0;}
function clock(ticks){var t=new Time();t.ticks=ticks;return t;}
function tree(){var nodes=[],refs={},count=0;function visit(item,parent,depth){if(depth>64||++count>10000)throw new Error('PROJECT_TREE_LIMIT');var id=String(item.nodeId);if(!id||id==='undefined'||refs['id:'+id])throw new Error('AMBIGUOUS_PROJECT_ITEM_ID');refs['id:'+id]=item;var bin=item.type===2||item.type===3,row={id:id,parent:parent,name:String(item.name),type:item.type};if(!bin){row.path=typeof item.getMediaPath==='function'?String(item.getMediaPath()):null;row.sequence=typeof item.isSequence==='function'?!!item.isSequence():null;try{row.audioIn=String(item.getInPoint(2).ticks);row.audioOut=String(item.getOutPoint(2).ticks);}catch(e){row.audioMarksUnavailable=true;}}nodes.push(row);if(bin)for(var i=0;i<item.children.numItems;i++)visit(item.children[i],id,depth+1);}visit(app.project.rootItem,null,0);return {nodes:nodes,refs:refs};}
function preserveTree(old,current,allowed){var normalized=[];for(var i=0;i<current.nodes.length;i++){var row=current.nodes[i];if(!allowed['id:'+row.id])normalized.push(row);}if(JSON.stringify(normalized)!==JSON.stringify(old.nodes))throw new Error('PROTECTED_PROJECT_TREE_CHANGED');}
function requireSource(item,path,sin,sout,offset){if(!item||item.type===2||item.type===3||typeof item.isSequence!=='function'||!isOff(item.isSequence())||typeof item.isOffline!=='function'||!isOff(item.isOffline())||item.getMediaPath()!==path)throw new Error('SOURCE_IDENTITY_OR_ONLINE_STATE_CHANGED');if(String(item.getInPoint(2).ticks)!==sin||String(item.getOutPoint(2).ticks)!==sout)throw new Error('SOURCE_RANGE_READBACK_FAILED');if(audioSourceOffset(item)!==offset)throw new Error('SOURCE_OFFSET_READBACK_FAILED');}
function compareTicks(a,b){a=String(a);b=String(b);if(!/^(0|[1-9][0-9]*)$/.test(a)||!/^(0|[1-9][0-9]*)$/.test(b))throw new Error('INVALID_NATIVE_TICKS');return a.length!==b.length?(a.length<b.length?-1:1):(a===b?0:(a<b?-1:1));}
`;
export type SourceRequest = { media_path: string; media_sha256: string; source_in_ticks: string; source_out_ticks: string; source_item_id?: string };
export type PlacementRequest = SourceRequest & { source_item_id: string; track_index: number; track_id: string; start_ticks: string; end_ticks: string };
export function getLabMusicPlacementTools(options: BridgeOptions) {
  return {
    lab_prepare_music_source: {
      description: "Resolve an explicit existing music source, or import a new audio-only file when absent, then create a new hard-bounded subclip for the selected exact source range. Never changes shared source marks. Rejects ambiguous existing matches. Verifies bounded project tree and unchanged active timeline. Added project items remain after partial failure; no rollback/save/persistence claim.",
      parameters: { type: "object", additionalProperties: false, required: ["media_path", "media_sha256", "source_in_ticks", "source_out_ticks"], properties: { ...mediaProperties, source_item_id: { ...identity, description: "Optional explicit existing source ID. Required when media path matches multiple existing items." } } },
      operationalCapability: capability,
      handler: async (args: SourceRequest) => {
        let probe;
        try {
          if (!labContext.getStore()) throw new Error("LAB_GUARD_REQUIRED");
          if (exact(args.source_out_ticks) <= exact(args.source_in_ticks)) throw new Error("Empty source range");
          if (args.source_item_id !== undefined) id(args.source_item_id);
          probe = await probeMusicMedia(args.media_path, args.media_sha256);
          if (exact(args.source_out_ticks) > exact(probe.duration_ticks)) throw new Error("Source range exceeds audio duration");
        } catch (e) { return { success: false, error: String(e) }; }
        const request = JSON.stringify({ ...args, subclip_name: "Music section " + labContext.getStore()!.operationId, native_out_ticks: String(exact(args.source_out_ticks)-exact(args.source_in_ticks)) }).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
        const result = await sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          ${helpers}
          var r=${request},beforeJson=JSON.stringify(__labSnapshot()),before=tree(),allowed={},source=null,matches=[];
          if(!app.project.activeSequence)throw new Error('NO_ACTIVE_SEQUENCE');
          for(var i=0;i<before.nodes.length;i++){var row=before.nodes[i];if(row.name===r.subclip_name)throw new Error('SOURCE_PREPARATION_ALREADY_EXISTS');if(row.path===r.media_path&&!row.sequence)matches.push(row.id);}
          if(r.source_item_id){source=before.refs['id:'+r.source_item_id];if(!source||source.getMediaPath()!==r.media_path)throw new Error('EXPLICIT_SOURCE_CHANGED');}
          else if(matches.length===1)source=before.refs['id:'+matches[0]];
          else if(matches.length>1)throw new Error('AMBIGUOUS_SOURCE_SELECT_NATIVE_ID');
          else {
            if(!app.project.importFiles([r.media_path],true,app.project.rootItem,false))throw new Error('IMPORT_NOT_CONFIRMED_PARTIAL_EXECUTION_POSSIBLE');
            var imported=tree(),fresh=[];for(var i=0;i<imported.nodes.length;i++){var row=imported.nodes[i];if(!before.refs['id:'+row.id])fresh.push(row);}
            if(fresh.length!==1||fresh[0].path!==r.media_path||fresh[0].sequence!==false)throw new Error('UNEXPECTED_IMPORTED_PROJECT_ITEMS');
            source=imported.refs['id:'+fresh[0].id];allowed['id:'+fresh[0].id]=true;preserveTree(before,imported,allowed);
          }
          if(typeof source.isSequence!=='function'||!isOff(source.isSequence())||typeof source.isOffline!=='function'||!isOff(source.isOffline())||typeof source.createSubClip!=='function')throw new Error('SOURCE_SUBCLIP_API_OR_ONLINE_STATE_UNAVAILABLE');
          if(audioSourceOffset(source)!=='0')throw new Error('NESTED_SUBCLIP_SOURCE_UNSUPPORTED');
          var sourceId=String(source.nodeId),sourceIn=String(source.getInPoint(2).ticks),sourceOut=String(source.getOutPoint(2).ticks),preSub=tree();
          // Both stream flags are enabled because ffprobe proved audio-only media.
          // This also avoids the historical takeAudio/takeVideo argument-order discrepancy.
          var sub=source.createSubClip(r.subclip_name,clock(r.source_in_ticks),clock(r.source_out_ticks),1,1,1);
          if(!sub||!sub.nodeId||String(sub.nodeId)===sourceId)throw new Error('SUBCLIP_CREATION_NOT_CONFIRMED');
          var subId=String(sub.nodeId),after=tree(),newIds=[];
          for(var i=0;i<after.nodes.length;i++)if(!preSub.refs['id:'+after.nodes[i].id])newIds.push(after.nodes[i].id);
          if(newIds.length!==1||newIds[0]!==subId)throw new Error('UNEXPECTED_SUBCLIP_PROJECT_ITEMS');
          allowed['id:'+subId]=true;preserveTree(before,after,allowed);
          requireSource(sub,r.media_path,'0',r.native_out_ticks,r.source_in_ticks);
          if(String(source.getInPoint(2).ticks)!==sourceIn||String(source.getOutPoint(2).ticks)!==sourceOut)throw new Error('SHARED_SOURCE_MARKS_CHANGED');
          if(beforeJson!==JSON.stringify(__labSnapshot()))throw new Error('TIMELINE_CHANGED_DURING_SOURCE_PREPARATION');
          return __result({project_path:app.project.path,sequence_id:String(app.project.activeSequence.sequenceID),source_item_id:subId,parent_source_id:sourceId,media_path:r.media_path,source_in_ticks:r.source_in_ticks,source_out_ticks:r.source_out_ticks,native_source_in_ticks:'0',native_source_out_ticks:r.native_out_ticks,source_offset_ticks:r.source_in_ticks,clock_evidence:'project_metadata_audio_in_out_offsets',added_project_item_ids:(function(){var result=[];for(var i=0;i<after.nodes.length;i++)if(allowed['id:'+after.nodes[i].id])result.push(after.nodes[i].id);return result;}()),verification:'bounded_source_marks_tree_and_unchanged_timeline',source_processing:'not_inspected',persistence:'not_run',rollback:'not_attempted'});
        `), options);
        if (result.success && await mediaHash(args.media_path) !== args.media_sha256) return { success: false, error: "Media changed after native source preparation; reconcile original operation" };
        return result.success ? { ...result, data: { ...(result.data as object), media_probe: probe } } : result;
      },
    },
    lab_place_music_item: {
      description: "Place one prepared audio-only source subclip into a proven empty range on an existing audio track, without ripple. Uses exact Time objects and verifies new native ID/source/ranges/forward playback and all other bounded timeline/project-tree fields. Does not overwrite occupied music or dialogue, create tracks, apply gain/EQ, retry or save. Native time overload/source-clock behavior still requires host acceptance.",
      parameters: { type: "object", additionalProperties: false, required: ["media_path", "media_sha256", "source_item_id", "source_in_ticks", "source_out_ticks", "track_index", "track_id", "start_ticks", "end_ticks"], properties: { ...mediaProperties, source_item_id: identity, track_index: { type: "integer", description: "Zero-based audio track index from fresh inspection.", minimum: 0, maximum: 255 }, track_id: identity, start_ticks: tick, end_ticks: tick } },
      operationalCapability: capability,
      handler: async (args: PlacementRequest) => {
        try {
          if (!labContext.getStore()) throw new Error("LAB_GUARD_REQUIRED");
          id(args.source_item_id); id(args.track_id);
          if (!Number.isInteger(args.track_index) || args.track_index < 0 || args.track_index > 255) throw new Error("Invalid audio track index");
          const duration = exact(args.end_ticks) - exact(args.start_ticks);
          if (duration <= 0n || duration !== exact(args.source_out_ticks) - exact(args.source_in_ticks)) throw new Error("Placement/source duration mismatch");
          const probe = await probeMusicMedia(args.media_path, args.media_sha256);
          if (exact(args.source_out_ticks) > exact(probe.duration_ticks)) throw new Error("Source range exceeds audio duration");
        } catch (e) { return { success: false, error: String(e) }; }
        const literal = JSON.stringify({...args,native_out_ticks:String(exact(args.source_out_ticks)-exact(args.source_in_ticks))}).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
        const result = await sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          ${helpers}
          var r=${literal},s=app.project.activeSequence,beforeJson=JSON.stringify(__labSnapshot()),assets=tree();
          if(!s)throw new Error('NO_ACTIVE_SEQUENCE');
          var track=s.audioTracks[r.track_index];
          if(!track||String(track.id)!==r.track_id||typeof track.isLocked!=='function'||!isOff(track.isLocked()))throw new Error('AUDIO_TRACK_IDENTITY_OR_LOCK_CHANGED');
          if(typeof track.isMuted!=='function'||!isOff(track.isMuted()))throw new Error('MUSIC_TRACK_MUTED_OR_UNVERIFIED');
          if(!track.transitions||track.transitions.numItems!==0)throw new Error('DESTINATION_TRANSITIONS_UNSUPPORTED');
          if(typeof track.overwriteClip!=='function')throw new Error('TRACK_PLACEMENT_API_UNAVAILABLE');
          var source=assets.refs['id:'+r.source_item_id];requireSource(source,r.media_path,'0',r.native_out_ticks,r.source_in_ticks);
          var ids={};for(var t=0;t<s.audioTracks.numTracks;t++)for(var c=0;c<s.audioTracks[t].clips.numItems;c++){var clip=s.audioTracks[t].clips[c];ids['id:'+String(clip.nodeId)]=true;}
          for(var c=0;c<track.clips.numItems;c++){var clip=track.clips[c];if(compareTicks(clip.end.ticks,r.start_ticks)>0&&compareTicks(clip.start.ticks,r.end_ticks)<0)throw new Error('MUSIC_DESTINATION_OCCUPIED');}
          track.overwriteClip(source,clock(r.start_ticks));
          var fresh=[];for(var t=0;t<s.audioTracks.numTracks;t++)for(var c=0;c<s.audioTracks[t].clips.numItems;c++){var clip=s.audioTracks[t].clips[c];if(!ids['id:'+String(clip.nodeId)])fresh.push({item:clip,track:t});}
          if(fresh.length!==1||fresh[0].track!==r.track_index)throw new Error('PLACED_MUSIC_IDENTITY_AMBIGUOUS');
          var item=fresh[0].item;
          if(!item.projectItem||String(item.projectItem.nodeId)!==r.source_item_id||item.projectItem.getMediaPath()!==r.media_path||String(item.start.ticks)!==r.start_ticks||String(item.end.ticks)!==r.end_ticks||String(item.inPoint.ticks)!=='0'||String(item.outPoint.ticks)!==r.native_out_ticks||item.getSpeed()!==1||typeof item.isSpeedReversed!=='function'||!isOff(item.isSpeedReversed())||(item.disabled!==false&&item.disabled!==0))throw new Error('MUSIC_PLACEMENT_READBACK_FAILED');
          if(String(track.id)!==r.track_id||track.transitions.numItems!==0)throw new Error('MUSIC_TRACK_CHANGED_AFTER_PLACEMENT');
          var after=JSON.parse(JSON.stringify(__labSnapshot())),removed=0;
          for(var t=0;t<after.tracks.length;t++){var row=after.tracks[t];if(row.kind!==1||row.index!==r.track_index)continue;for(var c=row.clips.length-1;c>=0;c--)if(row.clips[c].id===String(item.nodeId)){row.clips.splice(c,1);removed++;}}
          if(removed!==1||beforeJson!==JSON.stringify(after))throw new Error('PROTECTED_TIMELINE_STATE_CHANGED_PARTIAL_EXECUTION');
          preserveTree(assets,tree(),{});
          return __result({project_path:app.project.path,sequence_id:String(s.sequenceID),node_id:String(item.nodeId),source_id:r.source_item_id,media_path:r.media_path,start_ticks:r.start_ticks,end_ticks:r.end_ticks,source_in_ticks:r.source_in_ticks,source_out_ticks:r.source_out_ticks,native_source_in_ticks:'0',native_source_out_ticks:r.native_out_ticks,source_offset_ticks:r.source_in_ticks,clock_evidence:'project_metadata_audio_in_out_offsets',track_id:r.track_id,track_index:r.track_index,verification:'exact_placement_and_bounded_protected_state',channels_and_routing:'not_inspected',persistence:'not_run',rendered:'not_run',listening:'not_run',rollback:'not_attempted'});
        `), options);
        if (result.success && await mediaHash(args.media_path) !== args.media_sha256) return { success: false, error: "Media changed after native placement; reconcile original operation" };
        return result;
      },
    },
  };
}

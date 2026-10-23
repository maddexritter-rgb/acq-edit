import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import { SNAPSHOT_FUNCTION, labContext } from "./context.js";
import { AUDIO_SOURCE_CLOCK } from "./music-source-clock.js";
import { getLabMusicPlacementTools } from "./music-placement.js";
import { digest } from "./runtime.js";
import type { ToolOperationalOverride } from "../tool-capability-report.js";

const capability = {
  backend: "CEP/ExtendScript", backends: ["cep", "extendscript"], status: "experimental",
  minimumPremiereVersion: "26.3.0", hostVerificationRequired: true,
  notes: ["Item-local native Volume/Level only. Raw values have no inferred dB units. Media-time automation and interpolation require rendered calibration; no live acceptance."],
} satisfies ToolOperationalOverride;
const helpers = `
${AUDIO_SOURCE_CLOCK}
function nativeFlag(v){if(v===false||v===0){return false;}if(v===true||v===1){return true;}return null;}
function level(c){var found=null;for(var i=0;i<c.components.numItems;i++){var fx=c.components[i];if(String(fx.matchName)!=='audioVolume'&&String(fx.matchName)!=='Internal Volume Mono'&&String(fx.matchName)!=='Internal Volume Stereo')continue;for(var j=0;j<fx.properties.numItems;j++){var p=fx.properties[j];if(String(p.displayName)==='Level'){if(found)throw new Error('AMBIGUOUS_AUDIO_LEVEL');found={component_index:i,component_match_name:String(fx.matchName),parameter_index:j,display_name:String(p.displayName),prop:p};}}}if(!found)throw new Error('AUDIO_LEVEL_UNAVAILABLE');return found;}
function values(p){var out=[],keys=p.isTimeVarying()?p.getKeys():[];if(!keys)keys=[];if(keys.length>1000)throw new Error('AUDIO_KEY_LIMIT');for(var i=0;i<keys.length;i++)out.push({ticks:String(keys[i].ticks),value:p.getValueAtKey(keys[i])});return out;}
function numberClose(a,b){return typeof a==='number'&&isFinite(a)&&Math.abs(a-b)<=0.0000001;}
`;
export type MusicEnvelope = { node_id: string; source_id: string; media_path: string;
  start_ticks: string; end_ticks: string; source_in_ticks: string; source_out_ticks: string; source_offset_ticks: string;
  parameter: { component_index: number; component_match_name: string; parameter_index: number; display_name: string };
  keys: { ticks: string; value: number }[] };
const tick = { description: "Exact nonnegative Premiere tick count, encoded as a decimal string.", type: "string", pattern: "^(0|[1-9][0-9]{0,18})$" };
export function getLabMusicTools(options: BridgeOptions) {
  return {
    ...getLabMusicPlacementTools(options),
    inspect_music_state: {
      description: "Inspect native audio items, exact ranges and Volume/Level descriptors/raw keys against a stable bounded snapshot. Reports dB units and automation time domain as unverified; does not choose a music item or change any audio.",
      parameters: { type: "object", additionalProperties: false, properties: {} },
      operationalCapability: capability,
      handler: async () => {
        const result = await sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          ${helpers}
          var s=app.project.activeSequence;if(!s)throw new Error('NO_ACTIVE_SEQUENCE');
          var beforeJson=JSON.stringify(__labSnapshot()),tracks=[];
          for(var t=0;t<s.audioTracks.numTracks;t++){
            var tr=s.audioTracks[t],clips=[];
            for(var c=0;c<tr.clips.numItems;c++){
              var item=tr.clips[c],descriptor=null,unavailable=null,sourceOffset=null,clockUnavailable=null;
              try{sourceOffset=audioSourceOffset(item.projectItem);}catch(e){clockUnavailable=String(e);}
              try{var l=level(item);descriptor={component_index:l.component_index,component_match_name:l.component_match_name,parameter_index:l.parameter_index,display_name:l.display_name,value:l.prop.getValue(),time_varying:nativeFlag(l.prop.isTimeVarying()),keys:values(l.prop),keyframes_supported:typeof l.prop.areKeyframesSupported==='function'?nativeFlag(l.prop.areKeyframesSupported()):null};}catch(e){unavailable=String(e);}
              clips.push({node_id:String(item.nodeId),source_id:item.projectItem?String(item.projectItem.nodeId):null,media_path:item.projectItem?item.projectItem.getMediaPath():null,
                source_offset_ticks:sourceOffset,source_clock_unavailable:clockUnavailable,source_clock_evidence:'project_metadata_audio_in_out_offsets',start_ticks:String(item.start.ticks),end_ticks:String(item.end.ticks),source_in_ticks:String(item.inPoint.ticks),source_out_ticks:String(item.outPoint.ticks),
                speed:item.getSpeed(),speed_reversed:typeof item.isSpeedReversed==='function'?nativeFlag(item.isSpeedReversed()):null,
                level:descriptor,level_unavailable:unavailable,units:'native_value_db_mapping_unverified',key_time_domain:'media_requested_not_host_verified'});
            }
            tracks.push({index:t,track_id:typeof tr.id==='undefined'?null:String(tr.id),transition_count:tr.transitions?tr.transitions.numItems:null,name:String(tr.name),muted:typeof tr.isMuted==='function'?nativeFlag(tr.isMuted()):null,locked:typeof tr.isLocked==='function'?nativeFlag(tr.isLocked()):null,clips:clips});
          }
          if(beforeJson!==JSON.stringify(__labSnapshot()))throw new Error('MUSIC_STATE_CHANGED_DURING_INSPECTION');
          return __result({project_path:app.project.path,sequence_id:String(s.sequenceID),audio_tracks:tracks,snapshot:JSON.parse(beforeJson)});
        `), options);
        if (!result.success) return result;
        const data: any = result.data;
        if (!data || typeof data !== "object" || Array.isArray(data) || !data.snapshot || !Array.isArray(data.snapshot.tracks) ||
            typeof data.project_path !== "string" || !data.project_path.startsWith("/") || typeof data.sequence_id !== "string" || !data.sequence_id ||
            !Array.isArray(data.audio_tracks) || data.snapshot.projectPath !== data.project_path || data.snapshot.sequenceId !== data.sequence_id) return { success: false, error: "INVALID_NATIVE_STATE_RESPONSE" };
        return { success: true, data: { ...data, revision: digest(data.snapshot) } };
      },
    },
    lab_apply_music_envelope: {
      description: "Replace only the explicitly owned audio item's Volume/Level envelope with exact media-time keys in raw native units. No dB conversion, source effects, placement, gain inference, EQ, save or rollback. The stage must bind selection/audition and calibrated units. Preflight exact identity/descriptor; read back all keys and compare all other bounded snapshot fields. Partial failure is uncertain.",
      parameters: { type: "object", additionalProperties: false,
        required: ["node_id", "source_id", "media_path", "start_ticks", "end_ticks", "source_in_ticks", "source_out_ticks", "source_offset_ticks", "parameter", "keys"],
        properties: { node_id: { description: "Exact native ID of the single stage-owned music item.", type: "string", minLength: 1, maxLength: 512 }, source_id: { description: "Expected native project-item ID.", type: "string", minLength: 1, maxLength: 512 }, media_path: { description: "Expected source media path from fresh inspection.", type: "string", minLength: 1, maxLength: 4096 },
          start_ticks: tick, end_ticks: tick, source_in_ticks: tick, source_out_ticks: tick, source_offset_ticks: tick,
          parameter: { description: "Exact item-local Volume/Level descriptor from inspection.", type: "object", additionalProperties: false, required: ["component_index", "component_match_name", "parameter_index", "display_name"], properties: {
            component_index: { description: "Zero-based native component index.", type: "integer", minimum: 0, maximum: 255 }, component_match_name: { description: "Required native Volume component match name.", enum: ["audioVolume", "Internal Volume Mono", "Internal Volume Stereo"], type: "string" },
            parameter_index: { description: "Zero-based native Level parameter index.", type: "integer", minimum: 0, maximum: 255 }, display_name: { description: "Expected parameter display name; this route supports English Level.", const: "Level", type: "string" },
          } },
          keys: { description: "Complete replacement envelope, including both media-time source boundaries, in calibrated raw native units.", type: "array", minItems: 2, maxItems: 1000, items: { type: "object", additionalProperties: false, required: ["ticks", "value"], properties: { ticks: tick, value: { description: "Finite native parameter value. This is not dB or an inferred gain ratio.", type: "number", minimum: 0, maximum: 1 } } } },
        } },
      operationalCapability: capability,
      handler: async (args: MusicEnvelope) => {
        try {
          if (!labContext.getStore()) throw new Error("LAB_GUARD_REQUIRED");
          for (const field of ["node_id", "source_id", "media_path"] as const) if (typeof args[field] !== "string" || !args[field] || args[field].length > (field === "media_path" ? 4096 : 512)) throw new Error("Invalid native identity");
          const exact = (v: string) => { if (typeof v !== "string" || !/^(0|[1-9]\d{0,18})$/.test(v) || BigInt(v) > 9223372036854775807n) throw new Error("Invalid exact time"); return BigInt(v); };
          const start = exact(args.start_ticks), end = exact(args.end_ticks), sin = exact(args.source_in_ticks), sout = exact(args.source_out_ticks);
          if (end <= start || sout <= sin || end - start !== sout - sin) throw new Error("Forward unit-speed ranges required");
          exact(args.source_offset_ticks);
          const p = args.parameter;
          if (!["audioVolume", "Internal Volume Mono", "Internal Volume Stereo"].includes(p.component_match_name) || p.display_name !== "Level" || ![p.component_index, p.parameter_index].every(i => Number.isInteger(i) && i >= 0 && i <= 255)) throw new Error("Unsupported parameter descriptor");
          if (!Array.isArray(args.keys) || args.keys.length < 2 || args.keys.length > 1000) throw new Error("Invalid envelope key count");
          let last = -1n;
          for (const key of args.keys) {
            const time = exact(key.ticks);
            if (time <= last || time < sin || time > sout || typeof key.value !== "number" || !Number.isFinite(key.value) || key.value < 0 || key.value > 1) throw new Error("Invalid native envelope key");
            last = time;
          }
          if (args.keys[0].ticks !== args.source_in_ticks || args.keys.at(-1)!.ticks !== args.source_out_ticks) throw new Error("Envelope must cover both exact source boundaries");
        } catch (error) { return { success: false, error: String(error) }; }
        const literal = JSON.stringify(args).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
        return sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          ${helpers}
          var r=${literal},s=app.project.activeSequence,beforeJson=JSON.stringify(__labSnapshot()),found=null,track=null;
          if(!s)throw new Error('NO_ACTIVE_SEQUENCE');
          for(var t=0;t<s.audioTracks.numTracks;t++){var tr=s.audioTracks[t];for(var c=0;c<tr.clips.numItems;c++){var item=tr.clips[c];if(String(item.nodeId)===r.node_id){if(found)throw new Error('AMBIGUOUS_MUSIC_ITEM');found=item;track=tr;}}}
          if(!found||typeof track.isLocked!=='function'||track.isLocked())throw new Error('MUSIC_ITEM_MISSING_OR_LOCKED');
          if(!found.projectItem||String(found.projectItem.nodeId)!==r.source_id||found.projectItem.getMediaPath()!==r.media_path||String(found.start.ticks)!==r.start_ticks||String(found.end.ticks)!==r.end_ticks||String(found.inPoint.ticks)!==r.source_in_ticks||String(found.outPoint.ticks)!==r.source_out_ticks)throw new Error('MUSIC_SOURCE_OR_TIMING_CHANGED');
          if(found.getSpeed()!==1||typeof found.isSpeedReversed!=='function'||found.isSpeedReversed())throw new Error('MUSIC_PLAYBACK_UNVERIFIED');
          if(audioSourceOffset(found.projectItem)!==r.source_offset_ticks)throw new Error('MUSIC_SOURCE_CLOCK_CHANGED');
          var l=level(found),p=l.prop;
          if(l.component_index!==r.parameter.component_index||l.parameter_index!==r.parameter.parameter_index||l.component_match_name!==r.parameter.component_match_name||l.display_name!==r.parameter.display_name)throw new Error('MUSIC_PARAMETER_CHANGED');
          if(typeof p.areKeyframesSupported!=='function'||!p.areKeyframesSupported()||typeof p.removeKey!=='function'||typeof p.setInterpolationTypeAtKey!=='function')throw new Error('MUSIC_KEY_API_UNAVAILABLE');
          var oldKeys=p.isTimeVarying()?p.getKeys():[];if(!oldKeys)oldKeys=[];if(oldKeys.length>1000)throw new Error('AUDIO_KEY_LIMIT');
          // CEP is not atomic. A failed removal/addition leaves an uncertain operation for reconciliation.
          for(var k=0;k<oldKeys.length;k++)p.removeKey(oldKeys[k]);
          p.setTimeVarying(true);
          for(var k=0;k<r.keys.length;k++){var time=new Time();time.ticks=r.keys[k].ticks;p.addKey(time);p.setValueAtKey(time,r.keys[k].value,false);p.setInterpolationTypeAtKey(time,0,false);}
          var keys=values(p);if(!p.isTimeVarying()||keys.length!==r.keys.length)throw new Error('MUSIC_KEY_COUNT_READBACK_FAILED');
          for(var k=0;k<keys.length;k++)if(keys[k].ticks!==r.keys[k].ticks||!numberClose(keys[k].value,r.keys[k].value))throw new Error('MUSIC_KEY_READBACK_FAILED');
          if(found.getSpeed()!==1||found.isSpeedReversed())throw new Error('MUSIC_PLAYBACK_CHANGED');
          if(audioSourceOffset(found.projectItem)!==r.source_offset_ticks)throw new Error('MUSIC_SOURCE_CLOCK_CHANGED_AFTER_WRITE');
          var before=JSON.parse(beforeJson),after=JSON.parse(JSON.stringify(__labSnapshot()));
          function snapshotLevel(state){var result=null;for(var t=0;t<state.tracks.length;t++){var tr=state.tracks[t];if(tr.kind!==1)continue;for(var c=0;c<tr.clips.length;c++){var item=tr.clips[c];if(item.id!==r.node_id)continue;var fx=item.components[r.parameter.component_index];if(!fx||fx.matchName!==r.parameter.component_match_name)throw new Error('MUSIC_SNAPSHOT_DESCRIPTOR_CHANGED');var param=fx.properties[r.parameter.parameter_index];if(!param||param.name!==r.parameter.display_name||result)throw new Error('MUSIC_SNAPSHOT_PARAMETER_AMBIGUOUS');result=param;}}if(!result||result.valueUnavailable||result.keyframesUnavailable)throw new Error('MUSIC_SNAPSHOT_PARAMETER_UNAVAILABLE');return result;}
          var old=snapshotLevel(before),observed=snapshotLevel(after);
          if(!observed.keys||observed.keys.length!==r.keys.length)throw new Error('MUSIC_SNAPSHOT_KEYS_CHANGED');
          for(var k=0;k<observed.keys.length;k++)if(observed.keys[k].ticks!==r.keys[k].ticks||!numberClose(observed.keys[k].value,r.keys[k].value))throw new Error('MUSIC_SNAPSHOT_KEY_READBACK_FAILED');
          if(old.keys)observed.keys=old.keys;else delete observed.keys;observed.value=old.value;
          if(JSON.stringify(before)!==JSON.stringify(after))throw new Error('PROTECTED_TIMELINE_STATE_CHANGED_PARTIAL_EXECUTION');
          return __result({node_id:r.node_id,keys:keys,verification:'exact_raw_keys_and_bounded_protected_state',units:'raw_native_values_no_db_claim',interpolation:'requested_linear_not_read_back',persistence:'not_run',rendered:'not_run',listening:'not_run',rollback:'not_attempted'});
        `), options);
      },
    },
  };
}

import {getPanelGeometryTools} from './reframe-panel-repair.js';
import {getReframeFrameTools} from './reframe-frames.js';
import {getEmbeddedPanelTools} from './reframe-panels.js';
import {getReframeShotTools} from './reframe-shots.js';
import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import { SNAPSHOT_FUNCTION, labContext } from "./context.js";
import { getLabFreshReframeTools } from "./reframe-apply.js";
import { digest } from "./runtime.js";
import type { ToolOperationalOverride } from "../tool-capability-report.js";

export const motionHelpers = `
function nativeFlag(v){if(v===false||v===0){return false;}if(v===true||v===1){return true;}return null;}
function motionProp(c,name){var found=null;for(var i=0;i<c.components.numItems;i++){var fx=c.components[i];if(fx.displayName!=='Motion')continue;for(var j=0;j<fx.properties.numItems;j++){var p=fx.properties[j];if(p.displayName===name){if(found)throw new Error('AMBIGUOUS_MOTION_PROPERTY');found=p;}}}if(!found)throw new Error('MOTION_PROPERTY_UNAVAILABLE '+name);return found;}
function anchorKeys(p){var out=[],keys=p.isTimeVarying()?p.getKeys():[];if(!keys)keys=[];if(keys.length>1000)throw new Error('KEY_LIMIT');for(var k=0;k<keys.length;k++)out.push({ticks:String(keys[k].ticks),value:p.getValueAtKey(keys[k])});return out;}
function pair(a,b){return a&&b&&a.length===2&&b.length===2&&Math.abs(a[0]-b[0])<=0.0000001&&Math.abs(a[1]-b[1])<=0.0000001;}
`;
export const capability = {
  backend: "CEP/ExtendScript", backends: ["cep", "extendscript"],
  status: "experimental", minimumPremiereVersion: "26.3.0",
  hostVerificationRequired: true,
  notes: ["English native Motion descriptors; item-local only. Live behavior, interpolation preservation, persistence and pixels are unverified."],
} satisfies ToolOperationalOverride;
type Key = { ticks: string; before: number[]; after: number[] };
type Repair = { node_id: string; keys: Key[] };

export function getLabReframeTools(options: BridgeOptions) {
  return {
    ...getLabFreshReframeTools(options),
    ...getReframeShotTools(options),
    ...getEmbeddedPanelTools(options), ...getReframeFrameTools(options), ...getPanelGeometryTools(options),
    lab_duplicate_vertical_sequence: {
      description: "Clone the exact active sequence into a new 1080x1920 sequence in the same disposable project. Identifies the new sequence by ID-set difference, never by whichever sequence clone activates. Checks source preservation, source-linked video/audio equivalence and all other bounded snapshot fields except new item/sequence IDs and the intended canvas. No save, rollback, link-group, persistence or rendered claim.",
      parameters: {
        type: "object", additionalProperties: false,
        required: ["source_sequence_id", "sequence_name"],
        properties: { source_sequence_id: { type: "string", minLength: 1, maxLength: 512 },
          sequence_name: { type: "string", minLength: 1, maxLength: 200 } },
      },
      operationalCapability: capability,
      handler: async (args: { source_sequence_id: string; sequence_name: string }) => {
        if (!labContext.getStore()) return { success: false, error: "LAB_GUARD_REQUIRED" };
        if (typeof args.source_sequence_id !== "string" || !args.source_sequence_id || args.source_sequence_id.length > 512 ||
            typeof args.sequence_name !== "string" || !args.sequence_name.trim() || args.sequence_name.length > 200 || /[\x00-\x1f]/.test(args.sequence_name)) {
          return { success: false, error: "Invalid source identity or destination name" };
        }
        const literal = JSON.stringify(args).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
        return sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          var request=${literal},project=app.project,src=project&&project.activeSequence;
          if(!src||String(src.sequenceID)!==request.source_sequence_id)throw new Error('SOURCE_SEQUENCE_CHANGED');
          var sourceName=String(src.name),sourceState=__labSnapshot(src),sourceJson=JSON.stringify(sourceState),ids={},initialCount=project.sequences.numSequences;
          if(!sourceState.settings)throw new Error('SOURCE_SETTINGS_UNAVAILABLE');
          var sourceWidth=sourceState.settings.videoFrameWidth,sourceHeight=sourceState.settings.videoFrameHeight;
          function copySettings(st){var out={};for(var key in st)out[key]=st[key];return out;}
          if(initialCount>2000)throw new Error('SEQUENCE_ENUMERATION_LIMIT');
          for(var i=0;i<initialCount;i++){var seq=project.sequences[i],id=String(seq.sequenceID);if(ids['id:'+id])throw new Error('AMBIGUOUS_SEQUENCE_ID');ids['id:'+id]=true;if(String(seq.name)===request.sequence_name)throw new Error('DEST_SEQUENCE_EXISTS');}
          if(!src.clone())throw new Error('CLONE_NOT_CONFIRMED_PARTIAL_EXECUTION_POSSIBLE');
          if(app.project!==project||String(app.project.path)!==sourceState.projectPath)throw new Error('PROJECT_CHANGED_AFTER_CLONE');
          if(project.sequences.numSequences!==initialCount+1)throw new Error('UNEXPECTED_SEQUENCE_SET_AFTER_CLONE');
          var dup=null,found=0;
          for(var i=0;i<project.sequences.numSequences;i++){var seq=project.sequences[i];if(!ids['id:'+String(seq.sequenceID)]){dup=seq;found++;}}
          if(found!==1||!dup||String(dup.sequenceID)===String(src.sequenceID))throw new Error('CLONE_IDENTITY_UNVERIFIED');
          if(String(src.name)!==sourceName||JSON.stringify(__labSnapshot(src))!==sourceJson)throw new Error('SOURCE_CHANGED_DURING_CLONE');
          function equivalent(original,copy){
            var map=[];
            if(original.tracks.length!==copy.tracks.length)throw new Error('CLONE_TRACK_COUNT_CHANGED');
            var unique={};
            for(var t=0;t<original.tracks.length;t++){
              var a=original.tracks[t],b=copy.tracks[t];if(a.clips.length!==b.clips.length)throw new Error('CLONE_ITEM_COUNT_CHANGED');
              for(var c=0;c<a.clips.length;c++){
                var old=a.clips[c].id,fresh=b.clips[c].id;
                if(!fresh||fresh==='undefined'||unique['id:'+fresh])throw new Error('CLONE_ITEM_ID_AMBIGUOUS');unique['id:'+fresh]=true;
                map.push({kind:a.kind,track_index:a.index,item_index:c,source_item_id:old,duplicate_item_id:fresh,source_id:a.clips[c].sourceId});
                b.clips[c].id=old;
              }
            }
            copy.sequenceId=original.sequenceId;
            if(JSON.stringify(original)!==JSON.stringify(copy))throw new Error('CLONE_CONTENT_CHANGED');
            return map;
          }
          var itemMap=equivalent(sourceState,__labSnapshot(dup));
          dup.projectItem.name=request.sequence_name;
          var settings=dup.getSettings();settings.videoFrameWidth=1080;settings.videoFrameHeight=1920;
          if(!dup.setSettings(settings))throw new Error('VERTICAL_SETTINGS_NOT_CONFIRMED');
          var resized=__labSnapshot(dup),actual=resized.settings;
          if(String(dup.name)!==request.sequence_name||!actual||actual.videoFrameWidth!==1080||actual.videoFrameHeight!==1920)throw new Error('VERTICAL_IDENTITY_OR_CANVAS_READBACK_FAILED');
          resized.settings=copySettings(resized.settings);resized.settings.videoFrameWidth=sourceWidth;resized.settings.videoFrameHeight=sourceHeight;
          equivalent(sourceState,resized);
          if(String(src.name)!==sourceName||JSON.stringify(__labSnapshot(src))!==sourceJson)throw new Error('SOURCE_CHANGED_AFTER_RESIZE');
          project.openSequence(dup.sequenceID);
          if(app.project!==project||!project.activeSequence||String(project.activeSequence.sequenceID)!==String(dup.sequenceID))throw new Error('CLONE_ACTIVATION_UNVERIFIED');
          var activated=__labSnapshot();if(activated.settings.videoFrameWidth!==1080||activated.settings.videoFrameHeight!==1920)throw new Error('ACTIVATION_CANVAS_CHANGED');
          activated.settings=copySettings(activated.settings);activated.settings.videoFrameWidth=sourceWidth;activated.settings.videoFrameHeight=sourceHeight;
          equivalent(sourceState,activated);
          if(String(src.name)!==sourceName||JSON.stringify(__labSnapshot(src))!==sourceJson)throw new Error('SOURCE_CHANGED_AFTER_ACTIVATION');
          return __result({project_path:project.path,sequence_name:dup.name,sequence_id:String(dup.sequenceID),source_sequence_id:String(src.sequenceID),item_map:itemMap,
            verification:'bounded_clone_content_and_source_preservation',native_linkage:'not_read_back',persistence:'not_run',rendered:'not_run',rollback:'not_attempted'});
        `), options);
      },
    },
    inspect_reframe_state: {
      description: "Read item-local Motion state, exact item/source identities and media-time Anchor samples for the existing reframing planner. Double-checks the complete bounded Lab snapshot; rejects ambiguous Motion descriptors. No writing or native acceptance claim.",
      parameters: { type: "object", properties: {}, additionalProperties: false },
      operationalCapability: capability,
      handler: async () => {
        const result = await sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          ${motionHelpers}
          var s=app.project.activeSequence;if(!s)return __error('NO_ACTIVE_SEQUENCE');
          var before=__labSnapshot();if(before.sequenceId!==String(s.sequenceID))return __error('REFRAME_SEQUENCE_NOT_OWNED');var st=s.getSettings(),tracks=[],inactive=[];
          for(var t=0;t<s.videoTracks.numTracks;t++){
            var track=s.videoTracks[t],clips=[];
            for(var c=0;c<track.clips.numItems;c++){
              var item=track.clips[c];if(item.disabled||(typeof track.isMuted==='function'&&track.isMuted())){inactive.push({track_index:t,item_index:c,node_id:String(item.nodeId),source_id:item.projectItem?String(item.projectItem.nodeId):null,media_path:item.projectItem?item.projectItem.getMediaPath():'',disabled:!!item.disabled,track_muted:typeof track.isMuted==='function'?track.isMuted():null,start_ticks:String(item.start.ticks),end_ticks:String(item.end.ticks),source_in_ticks:String(item.inPoint.ticks),source_out_ticks:String(item.outPoint.ticks)});continue;}var a=motionProp(item,'Anchor Point'),p=motionProp(item,'Position'),sc=motionProp(item,'Scale');
              clips.push({track_index:t,item_index:c,node_id:String(item.nodeId),source_id:item.projectItem?String(item.projectItem.nodeId):null,
                name:String(item.name),media_path:item.projectItem?item.projectItem.getMediaPath():'',
                start:item.start.seconds,end:item.end.seconds,source_in:item.inPoint.seconds,source_out:item.outPoint.seconds,
                start_ticks:String(item.start.ticks),end_ticks:String(item.end.ticks),source_in_ticks:String(item.inPoint.ticks),source_out_ticks:String(item.outPoint.ticks),speed:item.getSpeed(),speed_reversed:typeof item.isSpeedReversed==='function'?nativeFlag(item.isSpeedReversed()):null,
                motion:{anchor:a.getValue(),position:p.getValue(),scale:sc.getValue(),anchor_time_varying:a.isTimeVarying(),position_time_varying:p.isTimeVarying(),scale_time_varying:sc.isTimeVarying(),anchor_keys:anchorKeys(a),anchor_display_start:a.getValueAtTime(item.inPoint),anchor_display_end:a.getValueAtTime(item.outPoint)}});
            }
            tracks.push({index:t,name:String(track.name),clips:clips});
          }
          if(JSON.stringify(before)!==JSON.stringify(__labSnapshot()))return __error('REFRAME_STATE_CHANGED_DURING_INSPECTION');
          return __result({inspection:{project_path:app.project.path,sequence_name:s.name,sequence_id:s.sequenceID,width:st.videoFrameWidth,height:st.videoFrameHeight,video_tracks:tracks,inactive_picture_items:inactive},snapshot:before});
        `), options);
        if (!result.success) return result;
        const data: any = result.data;
        if (!data || typeof data !== "object" || Array.isArray(data) || !data.snapshot || !Array.isArray(data.snapshot.tracks) ||
            !data.inspection || typeof data.inspection.project_path !== "string" || !data.inspection.project_path.startsWith("/") ||
            typeof data.inspection.sequence_id !== "string" || !data.inspection.sequence_id || !Array.isArray(data.inspection.video_tracks) ||
            data.snapshot.projectPath !== data.inspection.project_path || data.snapshot.sequenceId !== data.inspection.sequence_id) return { success: false, error: "INVALID_NATIVE_STATE_RESPONSE" };
        return { success: true, data: { ...data, revision: digest(data.snapshot) } };
      },
    },
    lab_repair_anchor_x_keys: {
      description: "Change only X on existing item-local native Motion Anchor Point keys. Requires guarded Lab context. Prechecks all identities/key values before writes, verifies key readback and bounded protected timeline state afterward. Never changes Y/times, adds/removes keys, saves, retries or attempts rollback. Partial host failure is uncertain; interpolation, persistence and rendered proof remain separate.",
      parameters: {
        type: "object", additionalProperties: false, required: ["items"],
        properties: { items: { type: "array", minItems: 1, maxItems: 512, items: {
          type: "object", additionalProperties: false, required: ["node_id", "keys"],
          properties: { node_id: { type: "string", minLength: 1, maxLength: 512 },
            keys: { type: "array", minItems: 1, maxItems: 1000, items: {
              type: "object", additionalProperties: false, required: ["ticks", "before", "after"],
              properties: { ticks: { type: "string", pattern: "^(0|[1-9][0-9]{0,18})$" },
                before: { type: "array", minItems: 2, maxItems: 2, items: { type: "number" } },
                after: { type: "array", minItems: 2, maxItems: 2, items: { type: "number" } } },
            } } },
        } } },
      },
      operationalCapability: capability,
      handler: async (args: { items: Repair[] }) => {
        try {
          if (!labContext.getStore()) throw new Error("LAB_GUARD_REQUIRED");
          if (!Array.isArray(args.items) || !args.items.length || args.items.length > 512) throw new Error("Invalid item count");
          const ids = new Set<string>();
          let total = 0;
          for (const item of args.items) {
            if (typeof item.node_id !== "string" || !item.node_id || item.node_id.length > 512 || ids.has(item.node_id)) throw new Error("Invalid/duplicate item identity");
            ids.add(item.node_id);
            if (!Array.isArray(item.keys) || !item.keys.length || item.keys.length > 1000) throw new Error("Invalid key count");
            let previous = -1n;
            for (const key of item.keys) {
              if (typeof key.ticks !== "string" || !/^(0|[1-9]\d{0,18})$/.test(key.ticks)) throw new Error("Invalid exact key time");
              const ticks = BigInt(key.ticks);
              if (ticks <= previous || ticks > 9223372036854775807n) throw new Error("Unordered/out-of-range key time");
              previous = ticks;
              if (![key.before, key.after].every(v => Array.isArray(v) && v.length === 2 && v.every(n => typeof n === "number" && Number.isFinite(n)))) throw new Error("Invalid Anchor pair");
              if (key.before[1] !== key.after[1] || key.after[0] < 0 || key.after[0] > 1) throw new Error("Only normalized X changes are allowed");
              if (++total > 10000) throw new Error("Key batch limit");
            }
          }
        } catch (error) { return { success: false, error: String(error) }; }
        const literal = JSON.stringify(args.items).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
        return sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          ${motionHelpers}
          var requests=${literal},before=__labSnapshot(),s=app.project.activeSequence,checked=[];
          if(!s)return __error('NO_ACTIVE_SEQUENCE');
          for(var i=0;i<requests.length;i++){
            var r=requests[i],found=null,tr=null;
            for(var t=0;t<s.videoTracks.numTracks;t++){var track=s.videoTracks[t];for(var c=0;c<track.clips.numItems;c++){var item=track.clips[c];if(String(item.nodeId)===r.node_id){if(found)throw new Error('AMBIGUOUS_ITEM_ID');found=item;tr=track;}}}
            if(!found||typeof tr.isLocked!=='function'||tr.isLocked())throw new Error('TARGET_MISSING_OR_LOCKED');
            var anchor=motionProp(found,'Anchor Point');if(!anchor.isTimeVarying())throw new Error('EXISTING_KEYS_REQUIRED');
            var keys=anchor.getKeys();if(!keys||keys.length!==r.keys.length)throw new Error('KEY_COUNT_CHANGED');
            for(var k=0;k<keys.length;k++){if(String(keys[k].ticks)!==r.keys[k].ticks||!pair(anchor.getValueAtKey(keys[k]),r.keys[k].before))throw new Error('KEY_BASELINE_CHANGED');}
            checked.push({request:r,anchor:anchor,keys:keys});
          }
          for(var i=0;i<checked.length;i++){var row=checked[i];for(var k=0;k<row.keys.length;k++)row.anchor.setValueAtKey(row.keys[k],row.request.keys[k].after,false);}
          for(var i=0;i<checked.length;i++){var row=checked[i],now=row.anchor.getKeys();if(!now||now.length!==row.keys.length)throw new Error('KEY_READBACK_COUNT_CHANGED');for(var k=0;k<now.length;k++){if(String(now[k].ticks)!==row.request.keys[k].ticks||!pair(row.anchor.getValueAtKey(now[k]),row.request.keys[k].after))throw new Error('KEY_READBACK_FAILED');}}
          var after=__labSnapshot();
          function snapshotAnchor(state,id){var found=null;for(var t=0;t<state.tracks.length;t++){var tr=state.tracks[t];if(tr.kind!==0)continue;for(var c=0;c<tr.clips.length;c++){var clip=tr.clips[c];if(clip.id!==id)continue;for(var x=0;x<clip.components.length;x++){var comp=clip.components[x];if(comp.name!=='Motion')continue;for(var p=0;p<comp.properties.length;p++){if(comp.properties[p].name==='Anchor Point'){if(found)throw new Error('AMBIGUOUS_SNAPSHOT_ANCHOR');found=comp.properties[p];}}}}}if(!found)throw new Error('SNAPSHOT_ANCHOR_MISSING');return found;}
          for(var i=0;i<requests.length;i++){
            var old=snapshotAnchor(before,requests[i].node_id),observed=snapshotAnchor(after,requests[i].node_id);
            if(!observed.keys||observed.keys.length!==requests[i].keys.length)throw new Error('SNAPSHOT_KEYS_CHANGED');
            for(var k=0;k<observed.keys.length;k++){if(observed.keys[k].ticks!==requests[i].keys[k].ticks||!pair(observed.keys[k].value,requests[i].keys[k].after))throw new Error('SNAPSHOT_KEY_READBACK_FAILED');}
            // Direct key readback above verifies the only allowed key edits.
            observed.keys=old.keys;
            if(old.value&&observed.value&&old.value.length===2&&observed.value.length===2){if(Math.abs(old.value[1]-observed.value[1])>0.0000001)throw new Error('ANCHOR_Y_CHANGED');observed.value[0]=old.value[0];}
          }
          if(JSON.stringify(before)!==JSON.stringify(after))throw new Error('PROTECTED_TIMELINE_STATE_CHANGED_PARTIAL_EXECUTION');
          return __result({changed_items:checked.length,verification:'existing_x_keys_and_bounded_protected_snapshot',interpolation:'not_read_back',persistence:'not_run',rendered:'not_run',rollback:'not_attempted'});
        `), options);
      },
    },
  };
}

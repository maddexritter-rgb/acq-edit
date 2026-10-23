import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import { SNAPSHOT_FUNCTION, labContext } from "./context.js";
import { motionHelpers, capability } from "./reframe.js";

type Pair = number[];
export type FreshMotion = {
  node_id: string; source_id: string; media_path: string;
  start_ticks: string; end_ticks: string; source_in_ticks: string; source_out_ticks: string;
  baseline: { anchor: Pair; position: Pair; scale: number };
  position: Pair; scale: number; keys: { ticks: string; value: Pair }[];
};
const tickSchema = { type: "string", pattern: "^(0|[1-9][0-9]{0,18})$" };
const pairSchema = { type: "array", minItems: 2, maxItems: 2, items: { type: "number" } };
function exact(value: string): bigint {
  if (typeof value !== "string" || !/^(0|[1-9]\d{0,18})$/.test(value) || BigInt(value) > 9223372036854775807n) throw new Error("Invalid exact time");
  return BigInt(value);
}
function pair(value: Pair) {
  if (!Array.isArray(value) || value.length !== 2 || !value.every(v => typeof v === "number" && Number.isFinite(v))) throw new Error("Invalid Motion pair");
}
export function getLabFreshReframeTools(options: BridgeOptions) {
  return {
    lab_apply_reframe_motion: {
      description: "Apply fresh item-local Motion to a guarded 1080x1920 sequence: static Position/Scale and exact media-time Anchor Point keys. All targets must have static Motion and forward unit-speed source ranges. Preflights every target before writes, checks exact keys and bounded protected state. Requests linear interpolation but cannot read it back. Partial failure is uncertain; never retries, rolls back or saves.",
      parameters: { type: "object", additionalProperties: false, required: ["items"], properties: {
        items: { type: "array", minItems: 1, maxItems: 512, items: {
          type: "object", additionalProperties: false,
          required: ["node_id", "source_id", "media_path", "start_ticks", "end_ticks", "source_in_ticks", "source_out_ticks", "baseline", "position", "scale", "keys"],
          properties: {
            node_id: { type: "string", minLength: 1, maxLength: 512 }, source_id: { type: "string", minLength: 1, maxLength: 512 },
            media_path: { type: "string", minLength: 1, maxLength: 4096 },
            start_ticks: tickSchema, end_ticks: tickSchema, source_in_ticks: tickSchema, source_out_ticks: tickSchema,
            baseline: { type: "object", additionalProperties: false, required: ["anchor", "position", "scale"], properties: { anchor: pairSchema, position: pairSchema, scale: { type: "number" } } },
            position: pairSchema, scale: { type: "number", exclusiveMinimum: 0, description: "Scale percent. Quantized to the observed Premiere 26.3 binary32 storage before write; the result records requested and stored values." },
            keys: { type: "array", minItems: 1, maxItems: 1000, items: { type: "object", additionalProperties: false, required: ["ticks", "value"], properties: { ticks: tickSchema, value: pairSchema } } },
          },
        } },
      } },
      operationalCapability: capability,
      handler: async (args: { items: FreshMotion[] }) => {
        try {
          if (!labContext.getStore()) throw new Error("LAB_GUARD_REQUIRED");
          if (!Array.isArray(args.items) || !args.items.length || args.items.length > 512) throw new Error("Invalid item count");
          const ids = new Set<string>(); let count = 0;
          for (const r of args.items) {
            for (const field of ["node_id", "source_id", "media_path"] as const) {
              if (typeof r[field] !== "string" || !r[field] || r[field].length > (field === "media_path" ? 4096 : 512)) throw new Error("Invalid native identity");
            }
            if (ids.has(r.node_id)) throw new Error("Duplicate target"); ids.add(r.node_id);
            const start = exact(r.start_ticks), end = exact(r.end_ticks), sin = exact(r.source_in_ticks), sout = exact(r.source_out_ticks);
            if (end <= start || sout <= sin || end - start !== sout - sin) throw new Error("Only forward unit-speed ranges supported");
            pair(r.baseline.anchor); pair(r.baseline.position); pair(r.position);
            if (![r.scale, r.baseline.scale].every(v => typeof v === "number" && Number.isFinite(v) && v > 0)) throw new Error("Invalid scale");
            if (!Number.isFinite(Math.fround(r.scale)) || Math.fround(r.scale) <= 0) throw new Error("Scale outside native float32 storage");
            if (!Array.isArray(r.keys) || !r.keys.length || r.keys.length > 1000) throw new Error("Invalid key count");
            let previous = -1n;
            for (const key of r.keys) {
              const t = exact(key.ticks); pair(key.value);
              if (t <= previous || t < sin || t > sout) throw new Error("Unordered or out-of-source key time");
              if (key.value.some(v => v < 0 || v > 1)) throw new Error("Anchor must be normalized");
              previous = t; if (++count > 10000) throw new Error("Key batch limit");
            }
          }
        } catch (error) { return { success: false, error: String(error) }; }
        // Observed on the 26.3 fixture: Scale is stored as IEEE binary32.
        // Normalize the intended write explicitly; do not widen all readback tolerances.
        const requests = args.items.map(r => ({ ...r, requested_scale: r.scale, scale: Math.fround(r.scale) }));
        const literal = JSON.stringify(requests).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
        return sendCommand(buildToolScript(`
          ${SNAPSHOT_FUNCTION}
          ${motionHelpers}
          var requests=${literal},s=app.project.activeSequence,beforeJson=JSON.stringify(__labSnapshot()),checked=[];
          if(!s)throw new Error('NO_ACTIVE_SEQUENCE');
          var settings=s.getSettings();if(settings.videoFrameWidth!==1080||settings.videoFrameHeight!==1920)throw new Error('VERTICAL_CANVAS_REQUIRED');
          function tm(ticks){var t=new Time();t.ticks=ticks;return t;}
          function scalar(a,b){return typeof a==='number'&&isFinite(a)&&Math.abs(a-b)<=0.0000001;}
          function staticMotion(a,p,sc){if(a.isTimeVarying()||p.isTimeVarying()||sc.isTimeVarying())throw new Error('EXISTING_MOTION_ANIMATION');}
          for(var i=0;i<requests.length;i++){
            var r=requests[i],found=null,tr=null;
            for(var t=0;t<s.videoTracks.numTracks;t++){var track=s.videoTracks[t];for(var c=0;c<track.clips.numItems;c++){var item=track.clips[c];if(String(item.nodeId)===r.node_id){if(found)throw new Error('AMBIGUOUS_ITEM_ID');found=item;tr=track;}}}
            if(!found||typeof tr.isLocked!=='function'||tr.isLocked())throw new Error('TARGET_MISSING_OR_LOCKED');
            if(!found.projectItem||String(found.projectItem.nodeId)!==r.source_id||found.projectItem.getMediaPath()!==r.media_path||String(found.start.ticks)!==r.start_ticks||String(found.end.ticks)!==r.end_ticks||String(found.inPoint.ticks)!==r.source_in_ticks||String(found.outPoint.ticks)!==r.source_out_ticks||found.getSpeed()!==1)throw new Error('SOURCE_OR_TIMELINE_BASELINE_CHANGED');
            if(typeof found.isSpeedReversed!=='function'||found.isSpeedReversed())throw new Error('FORWARD_PLAYBACK_UNVERIFIED');
            var a=motionProp(found,'Anchor Point'),p=motionProp(found,'Position'),sc=motionProp(found,'Scale');staticMotion(a,p,sc);
            if(!pair(a.getValue(),r.baseline.anchor)||!pair(p.getValue(),r.baseline.position)||!scalar(sc.getValue(),r.baseline.scale))throw new Error('STATIC_MOTION_BASELINE_CHANGED');
            if(typeof a.areKeyframesSupported!=='function'||!a.areKeyframesSupported()||typeof a.setInterpolationTypeAtKey!=='function')throw new Error('ANCHOR_KEY_API_UNAVAILABLE');
            checked.push({request:r,item:found,anchor:a,position:p,scale:sc});
          }
          // Preflight every item before the first native mutation. No atomic rollback is promised.
          for(var i=0;i<checked.length;i++){
            var row=checked[i],r=row.request;row.position.setValue(r.position,false);row.scale.setValue(r.scale,false);row.anchor.setTimeVarying(true);
            for(var k=0;k<r.keys.length;k++){var key=r.keys[k],time=tm(key.ticks);row.anchor.addKey(time);row.anchor.setValueAtKey(time,key.value,false);row.anchor.setInterpolationTypeAtKey(time,0,false);}
          }
          for(var i=0;i<checked.length;i++){
            var row=checked[i],r=row.request,keys=anchorKeys(row.anchor);
            if(row.item.isSpeedReversed()||row.item.getSpeed()!==1)throw new Error('PLAYBACK_CHANGED_DURING_MOTION_WRITE');
            if(!row.anchor.isTimeVarying()||row.position.isTimeVarying()||row.scale.isTimeVarying()||!pair(row.position.getValue(),r.position)||!scalar(row.scale.getValue(),r.scale))throw new Error('MOTION_READBACK_FAILED');
            if(keys.length!==r.keys.length)throw new Error('KEY_COUNT_READBACK_FAILED');
            for(var k=0;k<keys.length;k++)if(keys[k].ticks!==r.keys[k].ticks||!pair(keys[k].value,r.keys[k].value))throw new Error('KEY_READBACK_FAILED');
          }
          var before=JSON.parse(beforeJson),after=JSON.parse(JSON.stringify(__labSnapshot()));
          function snapshotProp(state,id,name){var found=null;for(var t=0;t<state.tracks.length;t++){var tr=state.tracks[t];if(tr.kind!==0)continue;for(var c=0;c<tr.clips.length;c++){var clip=tr.clips[c];if(clip.id!==id)continue;for(var x=0;x<clip.components.length;x++){var comp=clip.components[x];if(comp.name!=='Motion')continue;for(var p=0;p<comp.properties.length;p++){if(comp.properties[p].name===name){if(found)throw new Error('AMBIGUOUS_SNAPSHOT_PROPERTY');found=comp.properties[p];}}}}}if(!found)throw new Error('SNAPSHOT_PROPERTY_MISSING');return found;}
          for(var i=0;i<requests.length;i++){
            var r=requests[i],names=['Anchor Point','Position','Scale'];
            for(var n=0;n<names.length;n++){
              var old=snapshotProp(before,r.node_id,names[n]),observed=snapshotProp(after,r.node_id,names[n]);
              if(old.valueUnavailable||observed.valueUnavailable||old.keyframesUnavailable||observed.keyframesUnavailable)throw new Error('MOTION_SNAPSHOT_UNAVAILABLE');
              if(n===0){if(!observed.keys||observed.keys.length!==r.keys.length)throw new Error('SNAPSHOT_KEYS_CHANGED');for(var k=0;k<observed.keys.length;k++)if(observed.keys[k].ticks!==r.keys[k].ticks||!pair(observed.keys[k].value,r.keys[k].value))throw new Error('SNAPSHOT_KEY_READBACK_FAILED');delete observed.keys;}
              else if(n===1?!pair(observed.value,r.position):!scalar(observed.value,r.scale))throw new Error('SNAPSHOT_MOTION_READBACK_FAILED');
              observed.value=old.value;
            }
          }
          if(JSON.stringify(before)!==JSON.stringify(after))throw new Error('PROTECTED_TIMELINE_STATE_CHANGED_PARTIAL_EXECUTION');
          var scales=[];for(var i=0;i<requests.length;i++)scales.push({node_id:requests[i].node_id,requested:requests[i].requested_scale,stored:requests[i].scale});
          return __result({keyed_items:checked.length,scale_storage:'float32',scales:scales,verification:'exact_keys_static_motion_and_bounded_protected_snapshot',interpolation:'requested_linear_not_read_back',persistence:'not_run',rendered:'not_run',rollback:'not_attempted'});
        `), options);
      },
    },
  };
}

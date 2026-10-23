import {importCaptionBatch} from "./caption-batch.js";
import { createHash } from "node:crypto";
import { mkdir, readFile, realpath, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import { SNAPSHOT_FUNCTION, labContext } from "./context.js";
import { getLabProjectStateTools, PROJECT_SEQUENCES_SNAPSHOT } from "./project-state.js";
import { mediaHash } from "./music-placement.js";
import type { ToolOperationalOverride } from "../tool-capability-report.js";
import { digest } from "./runtime.js";

export type TransferItem = { token: string; source_kind: "media" | "graphic"; media_path: string | null;
  start_ticks: string; end_ticks: string; source_in_ticks: string; source_out_ticks: string;
  speed: number; speed_reversed: boolean; disabled: boolean; component_match_names: string[] };
export type TransferRequest = { prepared_path: string; prepared_sha256: string; expected_project_revision: string;
  sequence_id: string; sequence_name: string; width: number; height: number; frame_duration_ticks: string;
  tracks: { kind: "video" | "audio"; index: number; name: string; muted: boolean; locked: boolean; items: TransferItem[] }[];
  markers: { name: string; comments: string; start: string; end: string }[] };
const tick = { type: "string", pattern: "^(0|[1-9][0-9]{0,18})$" };
const text = { type: "string", minLength: 1, maxLength: 512 };
const hex = { type: "string", pattern: "^[a-f0-9]{64}$" };
export const transferSchema = { type: "object", additionalProperties: false,
  required: ["prepared_path", "prepared_sha256", "expected_project_revision", "sequence_id", "sequence_name", "width", "height", "frame_duration_ticks", "tracks", "markers"],
  properties: { prepared_path: { type: "string", minLength: 1, maxLength: 4096 }, prepared_sha256: hex, expected_project_revision: hex,
    sequence_id: text, sequence_name: text, width: { type: "integer", minimum: 1, maximum: 32768 }, height: { type: "integer", minimum: 1, maximum: 32768 }, frame_duration_ticks: tick,
    tracks: { type: "array", minItems: 1, maxItems: 512, items: { type: "object", additionalProperties: false,
      required: ["kind", "index", "name", "muted", "locked", "items"], properties: {
        kind: { type: "string", enum: ["video", "audio"] }, index: { type: "integer", minimum: 0, maximum: 255 }, name: text,
        muted: { type: "boolean" }, locked: { type: "boolean" }, items: { type: "array", maxItems: 10000, items: {
          type: "object", additionalProperties: false, required: ["token", "source_kind", "media_path", "start_ticks", "end_ticks", "source_in_ticks", "source_out_ticks", "speed", "speed_reversed", "disabled", "component_match_names"],
          properties: { token: text, source_kind: { type: "string", enum: ["media", "graphic"] }, media_path: { type: ["string", "null"], maxLength: 4096 },
            start_ticks: tick, end_ticks: tick, source_in_ticks: tick, source_out_ticks: tick, speed: { type: "number", minimum: 0 }, speed_reversed: { type: "boolean" }, disabled: { type: "boolean" },
            component_match_names: { type: "array", maxItems: 256, items: text },
          },
        } },
      },
    } },
    markers: { type: "array", maxItems: 2000, items: { type: "object", additionalProperties: false, required: ["name", "comments", "start", "end"], properties: {
      name: { type: "string", maxLength: 4096 }, comments: { type: "string", maxLength: 16384 }, start: tick, end: tick,
    } } },
  },
};
function exact(v: string) { if (typeof v !== "string" || !/^(0|[1-9][0-9]{0,18})$/.test(v) || BigInt(v) > 9223372036854775807n) throw Error("Invalid exact ticks"); return BigInt(v); }
function named(v: string) { if (typeof v !== "string" || !v || v.length > 512 || v.includes("\0")) throw Error("Invalid identity"); }
export function validateTransfer(r: TransferRequest) {
  if (!r || typeof r !== "object") throw Error("Transfer request required");
  named(r.sequence_id); named(r.sequence_name);
  if (typeof r.prepared_path !== "string" || !path.isAbsolute(r.prepared_path) || !r.prepared_path.endsWith(".prproj") || r.prepared_path.length > 4096 || r.prepared_path.includes("\0") || !/^[a-f0-9]{64}$/.test(r.prepared_sha256) || !/^[a-f0-9]{64}$/.test(r.expected_project_revision)) throw Error("Invalid prepared file or project revision identity");
  for (const v of [r.width, r.height]) if (!Number.isInteger(v) || v < 1 || v > 32768) throw Error("Invalid canvas");
  if (!exact(r.frame_duration_ticks)) throw Error("Positive frame duration required");
  if (!Array.isArray(r.tracks) || !r.tracks.length || r.tracks.length > 512 || !Array.isArray(r.markers) || r.markers.length > 2000) throw Error("Invalid bounded structure");
  const indices: Record<string, number[]> = { video: [], audio: [] }, tokens = new Set<string>(); let count = 0;
  for (const t of r.tracks) {
    if (!["video", "audio"].includes(t.kind) || !Number.isInteger(t.index) || t.index < 0 || t.index > 255 || typeof t.muted !== "boolean" || typeof t.locked !== "boolean" || !Array.isArray(t.items)) throw Error("Invalid track expectation");
    named(t.name); indices[t.kind].push(t.index);
    for (const c of t.items) {
      named(c.token); if (tokens.has(c.token) || ++count > 10000) throw Error("Ambiguous/excessive item tokens"); tokens.add(c.token);
      if (exact(c.end_ticks) <= exact(c.start_ticks) || exact(c.source_out_ticks) < exact(c.source_in_ticks) || typeof c.speed !== "number" || !Number.isFinite(c.speed) || c.speed < 0 || typeof c.disabled !== "boolean" || typeof c.speed_reversed !== "boolean") throw Error("Invalid expected item clock/playback");
      if (c.source_kind === "graphic") { if (t.kind !== "video" || c.media_path !== null) throw Error("Invalid generated Graphics source"); }
      else if (c.source_kind !== "media" || typeof c.media_path !== "string" || !path.isAbsolute(c.media_path) || c.media_path.length > 4096 || c.media_path.includes("\0")) throw Error("Exact media source path required");
      if (!Array.isArray(c.component_match_names) || c.component_match_names.length > 256) throw Error("Invalid component expectations");
      c.component_match_names.forEach(named);
      if (c.source_kind === "graphic" && c.component_match_names.filter(n => n === "AE.ADBE Text").length !== 1) throw Error("Exactly one Text component required per card");
    }
  }
  for (const values of Object.values(indices)) if (values.some((v, i) => v !== i)) throw Error("Every track must be listed exactly once in native index order");
  for (const m of r.markers) if (typeof m.name !== "string" || m.name.length > 4096 || typeof m.comments !== "string" || m.comments.length > 16384 || exact(m.end) < exact(m.start)) throw Error("Invalid expected marker");
  if (JSON.stringify(r).length > 750000) throw Error("Transfer expectation too large");
}
export async function stagePrepared(input: string, sha: string, mailbox: string, destination: string) {
  const resolved = await realpath(input), target = await realpath(destination), info = await stat(resolved);
  if (resolved === target || !info.isFile() || !info.size || info.size > 256 * 1024 ** 2) throw Error("Prepared source must be a separate bounded project file");
  const bytes = await readFile(resolved);
  if (createHash("sha256").update(bytes).digest("hex") !== sha) throw Error("Prepared file hash changed");
  const folder = path.join(mailbox, "prepared-inputs"); await mkdir(folder, { recursive: true, mode: 0o700 });
  const staged = path.join(folder, sha + ".prproj");
  try { await writeFile(staged, bytes, { flag: "wx", mode: 0o400 }); }
  catch (error: any) { if (error.code !== "EEXIST") throw error; }
  if (await mediaHash(staged) !== sha || await mediaHash(input) !== sha) throw Error("Prepared/staged file changed during staging");
  return staged;
}
export const NATIVE_STATE_COMPARE = `function same(a,b){if(a===b)return true;if(a===null||b===null||typeof a!==typeof b||typeof a!=='object')return false;var aa=Object.prototype.toString.call(a)==='[object Array]',bb=Object.prototype.toString.call(b)==='[object Array]';if(aa!==bb||(aa&&a.length!==b.length))return false;var n=0;for(var k in a)if(Object.prototype.hasOwnProperty.call(a,k)){n++;if(!Object.prototype.hasOwnProperty.call(b,k)||!same(a[k],b[k]))return false;}for(var k in b)if(Object.prototype.hasOwnProperty.call(b,k))n--;return n===0;}
function flag(v){if(v===false||v===0)return false;if(v===true||v===1)return true;throw Error('NATIVE_FLAG_UNAVAILABLE');}
function normalPath(p){return String(p).replace(/^\\/+/, '/');}`;
export function getLabCaptionTransferTools(options: BridgeOptions) {
  return { lab_import_prepared_caption_sequence: {
    description: "Import one hash-bound prepared sequence, or up to six with complete paged protection, into the exact guarded Lab project. Stages checked input bytes, rechecks ALL existing sequence snapshots immediately before import, requires exact new sequence identity and declared complete track/item/source-clock/media/component layout, and preserves every earlier sequence. No activation, save, retry or rollback. Nested/dependent sequence additions and transitions are unsupported. Imported effect values, decoded text/geometry, persistence and rendered proof remain separate.",
    parameters: {...transferSchema,properties:{...transferSchema.properties,additional_sequences:{type:"array",minItems:1,maxItems:5,description:"Optional additional prepared ratio sequences in one complete paged transaction; each retains its full track/source declaration.",items:transferSchema}}},
    operationalCapability: { backend: "CEP/ExtendScript", backends: ["cep", "extendscript"], status: "experimental", minimumPremiereVersion: "26.3.0", hostVerificationRequired: true,
      notes: ["Bounded one-to-six prepared sequences; complete declared tracks and complete prior native pages checked in paged mode. Native Graphics text is opaque. Existing saved-file caption verifier remains mandatory."] } satisfies ToolOperationalOverride,
    handler: async (args: TransferRequest & {additional_sequences?:TransferRequest[]}) => {
      if(args.additional_sequences!==undefined||labContext.getStore()?.snapshotMode==='paged')return importCaptionBatch(options,args);
      let staged: string, state: any;
      try {
        const ctx = labContext.getStore(); if (!ctx || !options.tempDir) throw Error("LAB_GUARD_REQUIRED");
        validateTransfer(args);
        staged = await stagePrepared(args.prepared_path, args.prepared_sha256, options.tempDir, ctx.projectPath);
        // This nested context contains reads only; failure before the import is not a possible mutation.
        const result = await labContext.run({ ...ctx, dispatched: false }, () => getLabProjectStateTools(options).inspect_project_sequences.handler({ project_path: ctx.projectPath }));
        if (!result.success) throw Error("Project preflight failed: " + (result as any).error);
        const data: any = result.data;
        if (data.revision !== args.expected_project_revision) throw Error("PROJECT_STATE_STALE");
        if (data.sequences.some((s: any) => s.sequence_id === args.sequence_id || s.name === args.sequence_name)) throw Error("PREPARED_SEQUENCE_ALREADY_PRESENT");
        const { revision, verification, ...snapshot } = data; state = snapshot;
        if (await mediaHash(staged) !== args.prepared_sha256) throw Error("Staged project changed before dispatch");
      } catch (e) { return { success: false, error: String(e) }; }
      const literal = JSON.stringify({ ...args, staged_path: staged, expected_state: state }).replace(/\u2028/g,"\\u2028").replace(/\u2029/g,"\\u2029");
      const script = buildToolScript(`
        ${SNAPSHOT_FUNCTION}\n${PROJECT_SEQUENCES_SNAPSHOT}\n${NATIVE_STATE_COMPARE}
        var r=${literal},before=__labProjectSequences();
        if(!same(JSON.parse(JSON.stringify(before)),r.expected_state))throw Error('PROJECT_CHANGED_BEFORE_TRANSFER');
        var file=new File(r.staged_path);if(!file.exists)throw Error('STAGED_PROJECT_MISSING');
        var old={};for(var i=0;i<before.sequences.length;i++){var row=before.sequences[i];if(row.sequence_id===r.sequence_id||row.name===r.sequence_name)throw Error('PREPARED_SEQUENCE_ALREADY_PRESENT');old['id:'+row.sequence_id]=row;}
        app.project.importSequences(file.fsName,[r.sequence_id]);
        var after=__labProjectSequences(),added=[],found=null;
        if(after.project_path!==before.project_path||after.active_sequence_id!==before.active_sequence_id)throw Error('PROJECT_OR_ACTIVATION_CHANGED_DURING_TRANSFER');
        for(var i=0;i<after.sequences.length;i++){var row=after.sequences[i],prior=old['id:'+row.sequence_id];if(prior){if(!same(JSON.parse(JSON.stringify(row)),JSON.parse(JSON.stringify(prior))))throw Error('PROTECTED_SEQUENCE_CHANGED');delete old['id:'+row.sequence_id];}else added.push(row);}
        for(var key in old)if(Object.prototype.hasOwnProperty.call(old,key))throw Error('PROTECTED_SEQUENCE_REMOVED');
        if(added.length!==1||added[0].sequence_id!==r.sequence_id||added[0].name!==r.sequence_name)throw Error('UNEXPECTED_IMPORTED_SEQUENCE_SET');
        for(var i=0;i<app.project.sequences.numSequences;i++)if(String(app.project.sequences[i].sequenceID)===r.sequence_id)found=app.project.sequences[i];
        if(!found)throw Error('IMPORTED_SEQUENCE_UNRESOLVED');
        var snapshot=added[0].snapshot,settings=snapshot.settings;
        if(settings.videoFrameWidth!==r.width||settings.videoFrameHeight!==r.height||String(found.timebase)!==r.frame_duration_ticks)throw Error('IMPORTED_CANVAS_OR_TIMEBASE_MISMATCH');
        if(!same(snapshot.markers,r.markers))throw Error('IMPORTED_MARKERS_MISMATCH');
        if(found.videoTracks.numTracks+found.audioTracks.numTracks!==r.tracks.length)throw Error('IMPORTED_TRACK_COUNT_MISMATCH');
        var mapping=[],seen={};
        for(var i=0;i<r.tracks.length;i++){
          var want=r.tracks[i],tracks=want.kind==='video'?found.videoTracks:found.audioTracks,tr=tracks[want.index];
          if(!tr||String(tr.name)!==want.name||flag(tr.isMuted())!==want.muted||flag(tr.isLocked())!==want.locked||tr.clips.numItems!==want.items.length)throw Error('IMPORTED_TRACK_STATE_MISMATCH');
          if(!tr.transitions||tr.transitions.numItems!==0)throw Error('IMPORTED_TRANSITIONS_UNSUPPORTED');
          for(var j=0;j<want.items.length;j++){
            var e=want.items[j],item=tr.clips[j],id=String(item.nodeId),source=item.projectItem;
            if(!id||id==='undefined'||seen['id:'+id])throw Error('IMPORTED_ITEM_IDENTITY_AMBIGUOUS');seen['id:'+id]=true;
            if(String(item.start.ticks)!==e.start_ticks||String(item.end.ticks)!==e.end_ticks||String(item.inPoint.ticks)!==e.source_in_ticks||String(item.outPoint.ticks)!==e.source_out_ticks||item.getSpeed()!==e.speed||typeof item.isSpeedReversed!=='function'||flag(item.isSpeedReversed())!==e.speed_reversed||flag(item.disabled)!==e.disabled)throw Error('IMPORTED_ITEM_CLOCK_MISMATCH');
            var matches=[];for(var k=0;k<item.components.numItems;k++)matches.push(String(item.components[k].matchName));
            if(!same(matches,e.component_match_names))throw Error('IMPORTED_COMPONENT_CHAIN_MISMATCH');
            if(e.source_kind==='media'){if(!source||typeof source.isSequence!=='function'||flag(source.isSequence())||typeof source.isOffline!=='function'||flag(source.isOffline())||normalPath(source.getMediaPath())!==normalPath(e.media_path))throw Error('IMPORTED_MEDIA_LINKAGE_MISMATCH');}
            else {var textCount=0;for(var k=0;k<matches.length;k++)if(matches[k]==='AE.ADBE Text')textCount++;if(textCount!==1)throw Error('IMPORTED_GRAPHICS_COMPONENT_MISMATCH');}
            mapping.push({token:e.token,node_id:id,source_id:source?String(source.nodeId):null,kind:want.kind,track_index:want.index,item_index:j});
          }
        }
        if(!same(JSON.parse(JSON.stringify(after)),JSON.parse(JSON.stringify(__labProjectSequences()))))throw Error('PROJECT_CHANGED_DURING_TRANSFER_READBACK');
        return __result({project_path:after.project_path,sequence_id:r.sequence_id,sequence_name:r.sequence_name,snapshot:snapshot,mapping:mapping,prepared_sha256:r.prepared_sha256,staged_path:r.staged_path,verification:'complete_declared_track_structure_and_protected_prior_sequences',imported_effect_values:'not_verified',decoded_graphics_text:'saved_file_verifier_required',persistence:'not_run',rendered:'not_run',rollback:'not_attempted'});
      `);
      if (Buffer.byteLength(script, "utf8") > 450000) return { success: false, error: "Transfer preconditions exceed bounded native script size" };
      const result = await sendCommand(script, options);
      if (await mediaHash(staged) !== args.prepared_sha256 || await mediaHash(args.prepared_path) !== args.prepared_sha256) return { success: false, error: "Prepared file changed after dispatch; reconcile original transfer; do not retry" };
      const data: any = result.data;
      if (result.success && (!data || typeof data !== "object" || data.sequence_id !== args.sequence_id || !Array.isArray(data.mapping) || data.snapshot?.projectPath !== state.project_path || data.snapshot?.sequenceId !== args.sequence_id || !Array.isArray(data.snapshot?.tracks))) return { success: false, error: "Invalid native transfer readback; reconcile original operation" };
      return result.success ? { ...result, data: { ...data, sequence_revision: digest(data.snapshot) } } : result;
    },
  } };
}

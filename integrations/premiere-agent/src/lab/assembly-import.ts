import {importAssemblyBatch,type AdditionalAssembly} from "./assembly-batch.js";
import { importMasterAssembly } from "./assembly-master.js";
import path from "node:path";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import { SNAPSHOT_FUNCTION, PAGED_COMPARE_FUNCTION, labContext } from "./context.js";
import { PROJECT_SEQUENCES_SNAPSHOT, PROJECT_SEQUENCES_PAGED_SNAPSHOT, getLabProjectStateTools } from "./project-state.js";
import { ASSEMBLY_LINK_SNAPSHOT } from "./assembly-links.js";
import { NATIVE_STATE_COMPARE } from "./caption-transfer.js";
import { validateCompiledAssembly, checkCompilerArtifacts, type AssemblyRequest, type CompilerProof } from "./assembly-provenance.js";
import { mediaHash } from "./music-placement.js";
import type { ToolOperationalOverride } from "../tool-capability-report.js";
import { digest } from "./runtime.js";
import { packSnapshot, SNAPSHOT_UNPACK } from "./snapshot-packing.js";
const sha = { type: "string", pattern: "^[a-f0-9]{64}$" }, file = { type: "string", minLength: 1, maxLength: 4096 };
export function getLabAssemblyImportTools(options: BridgeOptions) {
  return { lab_import_compiled_assembly: {
    description: "Import one or up to three independent assemblies from the existing v2 source-word compiler/resolved-frame chain. Reproduces the canonical XML before dispatch, guards every existing sequence, checks exact native linked V1/A1 pairs and source clocks. Requires inputs/media inside Lab fixtures or the exact authorized input set. Does not activate, save, retry or roll back. No editorial selection/review. Source effects, audio channel processing and rendered/persistent proof remain separate.",
    parameters: { type: "object", additionalProperties: false, required: ["xml_path", "xml_sha256", "expected_path", "expected_sha256", "resolved_path", "resolved_sha256", "gap_frames", "expected_project_revision"],
      properties: { coverage:{type:"object",additionalProperties:false,required:["coverage_path","coverage_sha256"],description:"Retain four original synchronized cameras and two raw dialogue WAVs over every compiled span on disabled editable tracks.",properties:{coverage_path:file,coverage_sha256:sha}}, target_canvas:{type:"object",additionalProperties:false,required:["width","height"],description:"Fit newly imported batch masters to 1920x1080 while preserving dialogue, rate, links and all prior sequences.",properties:{width:{type:"integer",enum:[1920]},height:{type:"integer",enum:[1080]}}}, additional_assemblies: {type:"array", minItems:1, maxItems:2, description:"Optional second and third original compiler chains in the same complete paged transaction.", items:{type:"object",additionalProperties:false,required:["xml_path","xml_sha256","expected_path","expected_sha256","resolved_path","resolved_sha256","gap_frames"],properties:{xml_path:file,xml_sha256:sha,expected_path:file,expected_sha256:sha,resolved_path:file,resolved_sha256:sha,gap_frames:{type:"integer",minimum:0,maximum:2147483647}}}}, master_mode: {type:"boolean"}, output_dir: file, xml_path: file, xml_sha256: sha, expected_path: file, expected_sha256: sha, resolved_path: file, resolved_sha256: sha, gap_frames: { type: "integer", minimum: 0, maximum: 2147483647 }, expected_project_revision: sha } },
    operationalCapability: { backend: "CEP/ExtendScript", backends: ["cep", "extendscript"], status: "experimental", minimumPremiereVersion: "26.3.0", hostVerificationRequired: true,
      notes: ["Only exact existing compiler output from a v2 selection; no legacy/raw span packets. Native linked-pair acceptance pending. Partial imports stay uncertain with no replay or rollback."] } satisfies ToolOperationalOverride,
    handler: async (args: AssemblyRequest & {master_mode?:boolean;output_dir?:string;additional_assemblies?:AdditionalAssembly[];target_canvas?:{width:number;height:number};coverage?:{coverage_path:string;coverage_sha256:string}}) => {
      if(args.additional_assemblies!==undefined){if(args.master_mode!==undefined||args.output_dir!==undefined)return {success:false,error:"Batch and master modes are mutually exclusive"};return importAssemblyBatch(options,args as AssemblyRequest & {additional_assemblies:AdditionalAssembly[];target_canvas?:{width:number;height:number};coverage?:{coverage_path:string;coverage_sha256:string}});}
      if(args.master_mode===true)return importMasterAssembly(options,args);
      if(args.master_mode!==undefined||args.output_dir!==undefined||args.target_canvas!==undefined||args.coverage!==undefined)return {success:false,error:"Explicit master mode required for these fields"};
      let proof: CompilerProof, state: any, staged: string;
      try {
        const ctx = labContext.getStore(); if (!ctx || !options.tempDir) throw Error("LAB_GUARD_REQUIRED");
        for (const p of [args.xml_path,args.expected_path,args.resolved_path]) if (typeof p !== "string" || !path.isAbsolute(p) || p.includes("\0") || p.length > 4096) throw Error("Invalid absolute compiler artifact path");
        for (const hash of [args.xml_sha256,args.expected_sha256,args.resolved_sha256,args.expected_project_revision]) if (typeof hash !== "string" || !/^[a-f0-9]{64}$/.test(hash)) throw Error("Invalid compiler artifact hash");
        if (!Number.isInteger(args.gap_frames) || args.gap_frames < 0 || args.gap_frames > 2147483647) throw Error("Invalid compiler gap");
        proof = await validateCompiledAssembly(args, path.join(path.dirname(options.tempDir), "fixtures"));
        const result = await labContext.run({ ...ctx, dispatched: false }, () => getLabProjectStateTools(options).inspect_project_sequences.handler({ project_path: ctx.projectPath, paged_digest:ctx.snapshotMode === "paged" }));
        if (!result.success) throw Error("Project preflight failed: " + (result as any).error);
        const data: any = result.data;
        if (data.revision !== args.expected_project_revision) throw Error("PROJECT_STATE_STALE");
        if (data.sequences.some((s: any) => s.name === proof.expectation.sequence_name)) throw Error("ASSEMBLY_SEQUENCE_ALREADY_PRESENT");
        const { revision, verification, ...snapshot } = data; state = snapshot;
        const folder = path.join(options.tempDir, "prepared-inputs"); await mkdir(folder, { recursive: true, mode: 0o700 });
        staged = path.join(folder, args.xml_sha256 + ".xml");
        try { await writeFile(staged, await readFile(args.xml_path), { flag: "wx", mode: 0o400 }); } catch (e: any) { if (e.code !== "EEXIST") throw e; }
        await checkCompilerArtifacts(proof);
        if (await mediaHash(staged) !== args.xml_sha256) throw Error("STAGED_XML_CHANGED");
      } catch (e) { return { success: false, error: String(e) }; }
      const literal = JSON.stringify({ expected: proof.expectation, before: packSnapshot(JSON.parse(JSON.stringify(state))), staged }).replace(/\u2028/g,"\\u2028").replace(/\u2029/g,"\\u2029");
      const script = buildToolScript(`
        ${labContext.getStore()?.snapshotMode === "paged" ? PAGED_COMPARE_FUNCTION : SNAPSHOT_FUNCTION}\n${labContext.getStore()?.snapshotMode === "paged" ? PROJECT_SEQUENCES_PAGED_SNAPSHOT : PROJECT_SEQUENCES_SNAPSHOT}\n${ASSEMBLY_LINK_SNAPSHOT}\n${NATIVE_STATE_COMPARE}\n${SNAPSHOT_UNPACK}
        var r=${literal};r.before=__unpackSnapshot(r.before);
        var before=__labProjectSequences(),e=r.expected;
        if(!same(JSON.parse(JSON.stringify(before)),r.before))throw Error('PROJECT_CHANGED_BEFORE_ASSEMBLY_IMPORT');
        var old={};for(var i=0;i<before.sequences.length;i++){var row=before.sequences[i];if(row.name===e.sequence_name)throw Error('ASSEMBLY_SEQUENCE_ALREADY_PRESENT');old['id:'+row.sequence_id]=row;}
        var file=new File(r.staged);if(!file.exists)throw Error('STAGED_XML_MISSING');
        if(!app.project.importFiles([file.fsName],true,app.project.rootItem,false))throw Error('ASSEMBLY_IMPORT_NOT_CONFIRMED_PARTIAL_POSSIBLE');
        var after=__labProjectSequences(),added=[];
        if(after.project_path!==before.project_path||after.active_sequence_id!==before.active_sequence_id)throw Error('PROJECT_OR_ACTIVATION_CHANGED_DURING_ASSEMBLY_IMPORT');
        for(var i=0;i<after.sequences.length;i++){var row=after.sequences[i],prior=old['id:'+row.sequence_id];if(prior){if(!same(JSON.parse(JSON.stringify(row)),JSON.parse(JSON.stringify(prior))))throw Error('PROTECTED_SEQUENCE_CHANGED');delete old['id:'+row.sequence_id];}else added.push(row);}
        for(var key in old)if(Object.prototype.hasOwnProperty.call(old,key))throw Error('PROTECTED_SEQUENCE_REMOVED');
        if(added.length!==1||added[0].name!==e.sequence_name)throw Error('UNEXPECTED_ASSEMBLY_SEQUENCE_SET');
        var imported=added[0],s=null;for(var i=0;i<app.project.sequences.numSequences;i++)if(String(app.project.sequences[i].sequenceID)===imported.sequence_id)s=app.project.sequences[i];
        if(!s)throw Error('IMPORTED_ASSEMBLY_UNRESOLVED');
        imported={sequence_id:imported.sequence_id,name:imported.name,snapshot:__labSnapshot(s)};
        if(imported.snapshot.settings.videoFrameWidth!==e.width||imported.snapshot.settings.videoFrameHeight!==e.height)throw Error('ASSEMBLY_CANVAS_MISMATCH');
        var markers=[];for(var i=0;i<e.markers.length;i++){var m=e.markers[i];markers.push({name:m.name,comments:m.comments,start:m.start_ticks,end:m.start_ticks});}
        if(!same(imported.snapshot.markers,markers))throw Error('ASSEMBLY_MARKER_MISMATCH');
        for(var k=0;k<2;k++){var tracks=k?s.audioTracks:s.videoTracks;for(var t=0;t<tracks.numTracks;t++)if(!tracks[t].transitions||tracks[t].transitions.numItems!==0||flag(tracks[t].isMuted())||flag(tracks[t].isLocked()))throw Error('ASSEMBLY_TRACK_STATE_MISMATCH');}
        var links=__labAssemblyLinks(after.project_path,imported.sequence_id),found={},mapping=[];
        if(links.frame_duration_ticks!==e.frame_ticks||links.items.length!==e.items.length*2)throw Error('ASSEMBLY_RATE_OR_ITEM_COUNT_MISMATCH');
        for(var i=0;i<links.items.length;i++){var row=links.items[i];if(row.track_index!==0)throw Error('ASSEMBLY_ITEM_ON_UNEXPECTED_TRACK');found[row.kind+':'+row.item_index]=row;}
        for(var i=0;i<e.items.length;i++){
          var want=e.items[i],v=found['video:'+i],a=found['audio:'+i];if(!v||!a||!v.item.source_id||v.item.source_id!==a.item.source_id)throw Error('ASSEMBLY_PAIRED_SOURCE_MISMATCH');
          if(!same(v.linked_node_ids,[a.item.node_id])||!same(a.linked_node_ids,[v.item.node_id]))throw Error('ASSEMBLY_NATIVE_AV_LINK_MISMATCH');
          for(var k=0;k<2;k++){var c=(k?a:v).item;if(normalPath(c.media_path)!==normalPath(want.media_path)||c.offline!==false||c.speed!==1||c.speed_reversed!==false||c.disabled!==false||c.start_ticks!==want.start_ticks||c.end_ticks!==want.end_ticks||c.source_in_ticks!==want.source_in_ticks||c.source_out_ticks!==want.source_out_ticks)throw Error('ASSEMBLY_SOURCE_OR_CLOCK_MISMATCH');}
          mapping.push({assembly_item_index:i,clip_id:want.clip_id,video_node_id:v.item.node_id,audio_node_id:a.item.node_id,source_node_id:v.item.source_id});
        }
        if(!same(JSON.parse(JSON.stringify(after)),JSON.parse(JSON.stringify(__labProjectSequences())))||!same(links,__labAssemblyLinks(after.project_path,imported.sequence_id)))throw Error('ASSEMBLY_CHANGED_DURING_READBACK');
        return __result({project_path:after.project_path,sequence_id:imported.sequence_id,sequence_name:e.sequence_name,snapshot:imported.snapshot,mapping:mapping,verification:'native_linked_assembly_and_prior_sequence_structure',persistence:'not_run',rendered:'not_run',source_processing:'not_verified',rollback:'not_attempted'});
      `);
      if (Buffer.byteLength(script, "utf8") > 450000) return { success: false, error: "Assembly preconditions exceed bounded native script size" };
      const result = await sendCommand(script, options);
      try { await checkCompilerArtifacts(proof); if (await mediaHash(staged) !== args.xml_sha256) throw Error("STAGED_XML_CHANGED"); }
      catch (e) { return { success: false, error: "Compiler inputs changed after dispatch; reconcile original operation: " + String(e) }; }
      const data: any = result.data;
      if (result.success && (!data || typeof data !== "object" || data.project_path !== state.project_path || typeof data.sequence_id !== "string" || !data.sequence_id || data.sequence_name !== proof.expectation.sequence_name || !Array.isArray(data.mapping) || data.mapping.length !== proof.expectation.items.length || data.snapshot?.projectPath !== state.project_path || data.snapshot?.sequenceId !== data.sequence_id || !Array.isArray(data.snapshot?.tracks))) return { success: false, error: "Invalid native assembly response; reconcile original operation" };
      return result.success ? { ...result, data: { ...data, sequence_revision: digest(data.snapshot), provenance: proof.provenance, staged_xml: staged } } : result;
    },
  } };
}

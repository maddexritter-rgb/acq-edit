import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import { SNAPSHOT_FUNCTION } from "./context.js";
import { inspectPagedProject, inspectPagedGuardProject } from "./project-state-paged.js";
import { digest } from "./runtime.js";
import type { ToolOperationalOverride } from "../tool-capability-report.js";

// No activation or writes. Reused by prepared sequence transfer and stage guards.
export const PROJECT_SEQUENCES_SNAPSHOT = `
function __labProjectSequences(){
 var p=app.project;if(!p||!p.sequences)throw new Error('PROJECT_SEQUENCES_UNAVAILABLE');
 if(p.sequences.numSequences>50)throw new Error('PROJECT_SEQUENCE_LIMIT');
 var result={project_path:String(p.path),active_sequence_id:p.activeSequence?String(p.activeSequence.sequenceID):null,sequences:[]},seen={};
 for(var i=0;i<p.sequences.numSequences;i++){
  var s=p.sequences[i],id=String(s.sequenceID);
  if(!id||id==='undefined'||seen['id:'+id])throw new Error('PROJECT_SEQUENCE_ID_AMBIGUOUS');seen['id:'+id]=true;
  result.sequences.push({sequence_id:id,name:String(s.name),snapshot:__labSnapshot(s)});
 }
 if(result.active_sequence_id&&!seen['id:'+result.active_sequence_id])throw new Error('FOREIGN_ACTIVE_SEQUENCE');
 if(JSON.stringify(result).length>1500000)throw new Error('PROJECT_SEQUENCE_STATE_LIMIT');
 return result;
}`;
export const PROJECT_SEQUENCES_PAGED_SNAPSHOT = `
function __labProjectSequences(){
 var p=app.project;if(!p||!p.sequences||p.sequences.numSequences>50)throw Error('PROJECT_SEQUENCES_UNAVAILABLE_OR_LIMIT');var result={project_path:String(p.path),active_sequence_id:p.activeSequence?String(p.activeSequence.sequenceID):null,sequences:[]},seen={};
 for(var i=0;i<p.sequences.numSequences;i++){var s=p.sequences[i],id=String(s.sequenceID),prior=null;if(!id||id==='undefined'||seen['id:'+id])throw Error('PROJECT_SEQUENCE_ID_AMBIGUOUS');seen['id:'+id]=true;
 for(var j=0;j<r.before.sequences.length;j++)if(r.before.sequences[j].sequence_id===id)prior=r.before.sequences[j];
 if(prior){if(String(s.name)!==prior.name||!__labVerifyPages(prior.snapshot,s,same))throw Error('PROTECTED_SEQUENCE_CHANGED');result.sequences.push(prior);}else result.sequences.push({sequence_id:id,name:String(s.name),snapshot:__labSnapshot(s)});}
 if(result.active_sequence_id&&!seen['id:'+result.active_sequence_id])throw Error('FOREIGN_ACTIVE_SEQUENCE');if(JSON.stringify(result).length>1500000)throw Error('PROJECT_SEQUENCE_STATE_LIMIT');return result;
}`;
export function getLabProjectStateTools(options: BridgeOptions) {
  return {
    inspect_project_sequences: {
      description: "Read every owned sequence's bounded timeline/effect/settings snapshot without activating any sequence. Requires exact project path, unique native IDs and stable repeated reads. At most 50 sequences and 1.5 MB. Not a complete project tree, source-processing or rendered inspection.",
      parameters: { type: "object", additionalProperties: false, required: ["project_path"], properties: { paged_digest: { type:"boolean", description:"Complete per-sequence native page hashes with stable repeated reads; bounded summary for assembly preconditions." }, paged: { type: "boolean", description: "Opt-in complete paginated snapshots; unchanged per-page limits and repeated complete reads." }, project_path: { type: "string", description: "Exact currently open project path.", minLength: 1, maxLength: 4096 } } },
      operationalCapability: { backend: "CEP/ExtendScript", backends: ["cep", "extendscript"], status: "experimental", minimumPremiereVersion: "26.3.0", hostVerificationRequired: true, notes: ["Stable bounded snapshots only. No activation; native Graphics text may be unavailable through component values."] } satisfies ToolOperationalOverride,
      handler: async (args: { project_path: string; paged?: boolean; paged_digest?: boolean }) => {
        if (typeof args.project_path !== "string" || !args.project_path.startsWith("/") || args.project_path.length > 4096 || args.project_path.includes("\0")) return { success: false, error: "Exact absolute project path required" };
        if(args.paged!==undefined&&typeof args.paged!=="boolean")return {success:false,error:"Invalid paged flag"};
        if(args.paged_digest!==undefined&&typeof args.paged_digest!=="boolean")return {success:false,error:"Invalid paged_digest flag"};
        if(args.paged_digest===true){try{return {success:true,data:await inspectPagedGuardProject(options,args.project_path)};}catch(error){return {success:false,error:String(error)};}}
        if(args.paged===true){try{return {success:true,data:await inspectPagedProject(options,args.project_path)};}catch(error){return {success:false,error:String(error)};}}
        const target = JSON.stringify(args.project_path).replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
        const result = await sendCommand(buildToolScript(`${SNAPSHOT_FUNCTION}\n${PROJECT_SEQUENCES_SNAPSHOT}
          if(!app.project||String(app.project.path)!==${target})throw new Error('PROJECT_TARGET_CHANGED');
          var first=__labProjectSequences(),second=__labProjectSequences();
          if(JSON.stringify(first)!==JSON.stringify(second))throw new Error('PROJECT_CHANGED_DURING_INSPECTION');
          return __result(first);
        `), options);
        if (!result.success) return result;
        const data: any = result.data;
        if (!data || typeof data !== "object" || Array.isArray(data) || data.project_path !== args.project_path ||
            !Array.isArray(data.sequences) || data.sequences.length > 50 ||
            !(data.active_sequence_id === null || typeof data.active_sequence_id === "string") ||
            data.sequences.some((s: any) => !s || typeof s.sequence_id !== "string" || !s.sequence_id || typeof s.name !== "string" ||
              !s.snapshot || s.snapshot.projectPath !== args.project_path || s.snapshot.sequenceId !== s.sequence_id || !Array.isArray(s.snapshot.tracks)) ||
            new Set(data.sequences.map((s: any) => s.sequence_id)).size !== data.sequences.length ||
            (data.active_sequence_id !== null && !data.sequences.some((s: any) => s.sequence_id === data.active_sequence_id)))
          return { success: false, error: "PROJECT_STATE_INVALID_NATIVE_RESPONSE" };
        return { success: true, data: { ...data, revision: digest(data), verification: "stable_bounded_all_sequence_snapshots" } };
      },
    },
  };
}

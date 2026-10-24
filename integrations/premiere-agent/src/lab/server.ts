import {getCameraVisibilityTools} from "./camera-visibility.js";
import {ToolkitProjects} from "./toolkit-projects.js";
import { getLabAssemblyImportTools } from "./assembly-import.js";
import { getLabAssemblyLinkTools } from "./assembly-links.js";
import { getLabCaptionTransferTools } from "./caption-transfer.js";
import { getLabProjectStateTools } from "./project-state.js";
import { LabJobs } from "./jobs.js";
import { getLabMusicTools } from "./music.js";
import { getLabReframeTools } from "./reframe.js";
import { getLabTimingTools } from "./timing.js";
import { getLabResearchTools } from "./research.js";
import {
  McpServer,
  fromJsonSchema,
  type JsonSchemaType,
} from "@modelcontextprotocol/server";
import { collectTools } from "../server.js";
import { UxpWebSocketBridge } from "../bridge/uxp-websocket-bridge.js";
import { sendCommand } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
import {
  isToolPermitted,
  resolveCapabilities,
} from "../security/capabilities.js";
import {readPagedGuardSnapshot,readCachedPagedBaseline} from "./project-state-paged.js";
import { SNAPSHOT_FUNCTION } from "./context.js";
import { MEDIA_REPAIR_SNAPSHOT } from "./media-repair-snapshot.js";
import { getLabMediaRepairTools } from "./media-repair.js";
import {
  LabRuntime,
  labToolSchema,
  guardSchema,
  digest,
  type Guard,
  type Snapshot,
} from "./runtime.js";
import { catalog } from "./catalog.js";
import path from "node:path";
export function createLab(
  root: string,
  runtimeRoot: string,
  uxp: UxpWebSocketBridge,
) {
  const bridgeOptions = {
    tempDir: path.join(runtimeRoot, "mailbox"),
    timeoutMs: 300000,
    pagedResponse: true,
    failFastOnUnreadyHeartbeat: true,
  };
  const tools = {
    ...collectTools(bridgeOptions, resolveCapabilities(), uxp),
    ...getLabResearchTools(bridgeOptions),
    ...getLabTimingTools(bridgeOptions),
    ...getLabReframeTools(bridgeOptions),
    ...getCameraVisibilityTools(bridgeOptions),
    ...getLabMusicTools(bridgeOptions),
    ...getLabProjectStateTools(bridgeOptions),
    ...getLabAssemblyLinkTools(bridgeOptions),
    ...getLabAssemblyImportTools(bridgeOptions),
    ...getLabCaptionTransferTools(bridgeOptions),
    ...getLabMediaRepairTools(bridgeOptions),
  };
  const snapshot = async (mode?: "media_repair" | "paged") => {
    if(mode === "paged")return readPagedGuardSnapshot(bridgeOptions);
    const r = await sendCommand(
      buildToolScript(
        `${mode === 'media_repair' ? MEDIA_REPAIR_SNAPSHOT : SNAPSHOT_FUNCTION}\nreturn __result(__labSnapshot());`,
      ),
      bridgeOptions,
    );
    if (!r.success) throw new Error(r.error || "Snapshot unavailable");
    return r.data as Snapshot;
  };
  const runtime = new LabRuntime(runtimeRoot, tools, snapshot, revision=>readCachedPagedBaseline(bridgeOptions,revision));
  const jobs = new LabJobs(runtime);
  const inventory = catalog(root, tools);
  const server = new McpServer(
    { name: "premiere-agent-lab", version: "0.1.0" },
    {
      instructions:
        "Premiere Agent for the canonical editing skills on 26.3. Production stage tools require an exact-project, expiring tool/input/output scope and exclusive lease. Inspect lab_snapshot and supply _lab for mutations. Other operations remain disposable-fixture research. Use ~/.agents/skills/edit/scripts/premiere_agent.py doctor for connection diagnosis and the shared skill guide for stage drivers. A committed_unverified response is not editing or persistence proof. No UI fallback or cross-backend mutation replay. The coverage catalog includes unverified and unavailable operations.",
    },
  );
  const result = (v: unknown) => ({
    content: [{ type: "text" as const, text: JSON.stringify(v) }],
  });
  const projects = new ToolkitProjects(runtimeRoot, bridgeOptions, sendCommand, {snapshot});
  server.registerTool('lab_inspect_toolkit_workspace', {
    description: 'Read open-project identities for toolkit lifecycle preflight; never closes or saves a project.',
    inputSchema: fromJsonSchema({type:'object',properties:{operationId:{type:'string',pattern:'^[A-Za-z0-9_-]{1,80}$'}},additionalProperties:false}),
  }, async (args:any) => {
    try { return result(await projects.inspect(args.operationId)); }
    catch(error) { return {isError:true,...result({error:String(error)})}; }
  });
  server.registerTool('lab_reconcile_toolkit_project', {
    description:'Reconcile a terminal uncertain toolkit lifecycle operation from pinned process/native evidence. Reads native state and releases only its original writer lock; never opens, creates, saves or replays a project request.',
    inputSchema:fromJsonSchema({type:'object',additionalProperties:false,required:['operationId','evidencePath','evidenceSha256'],properties:{
      operationId:{type:'string',pattern:'^[A-Za-z0-9_-]{1,80}$'},evidencePath:{type:'string'},evidenceSha256:{type:'string',pattern:'^[a-f0-9]{64}$'},
    }}),
  },async(args:any)=>{try{return result(await projects.reconcile(args))}catch(error){return {isError:true,...result({error:String(error)})}}});
  server.registerTool('lab_toolkit_project', {
    description: 'Create or reopen one exact toolkit project from an empty workspace under a short-lived lifecycle scope. General lifecycle tools remain blocked. Unknown outcomes retain the shared writer lock; never replay.',
    inputSchema: fromJsonSchema({type:'object',additionalProperties:false,
      required:['operationId','mode','projectPath','expectedWorkspaceRevision'],properties:{
        operationId:{type:'string',pattern:'^[A-Za-z0-9_-]{1,80}$'},mode:{type:'string',enum:['create','open']},
        projectPath:{type:'string'},expectedWorkspaceRevision:{type:'string',pattern:'^[a-f0-9]{64}$'},
        expectedNativeSha256:{type:'string',pattern:'^[a-f0-9]{64}$'},
      }}),
  }, async (args:any) => {
    try { return result(await projects.execute(args)); }
    catch(error) { return {isError:true,...result({error:String(error)})}; }
  });
  server.registerTool(
    "lab_snapshot",
    {
      description:
        "Read exact current lab project/sequence and timeline timing revision. Does not mutate or establish ownership.",
      inputSchema: fromJsonSchema({
        type: "object",
        properties: { snapshot_mode: {type:'string',enum:['media_repair','paged'],description:'Paged hashes complete active-sequence component/keyframe pages; media_repair is structural relinking only.'} },
        additionalProperties: false,
      }),
    },
    async (args: any) => {
      try {
        const s = await snapshot(args.snapshot_mode);
        return result({
          ...s,
          revision: digest(s),
          revisionScope: args.snapshot_mode === 'media_repair' ? 'all sequence structural timing/markers/settings/track states and media identities/paths/offline states; effect values excluded; typed media repair only' :
            "active sequence item identities, timing, components/keyframes, markers, settings and track states; project metadata and unexposed properties require operation-specific preconditions",
          uxp: uxp.getState(),
        });
      } catch (e) {
        return { isError: true, ...result({ error: String(e) }) };
      }
    },
  );
  server.registerTool(
    "lab_search_capabilities",
    {
      description:
        "Search the complete pinned operation catalog. Includes unavailable operations with evidence boundaries; never equates enumeration with host support.",
      inputSchema: fromJsonSchema({
        type: "object",
        properties: {
          query: { type: "string" },
          offset: { type: "integer", minimum: 0 },
          limit: { type: "integer", minimum: 1, maximum: 100 },
        },
        additionalProperties: false,
      }),
    },
    async (args: any) => {
      const q = String(args.query ?? "").toLowerCase(),
        rows = inventory.operations.filter((t) =>
          (t.name + " " + t.description).toLowerCase().includes(q),
        );
      return result({
        total: rows.length,
        operations: rows.slice(
          args.offset ?? 0,
          (args.offset ?? 0) + (args.limit ?? 20),
        ),
      });
    },
  );
  server.registerTool(
    "lab_get_operation",
    {
      description:
        "Inspect a durable operation receipt. Unknown/running receipts must not be replayed automatically.",
      inputSchema: fromJsonSchema({
        type: "object",
        properties: {
          operation_id: { type: "string", pattern: "^[A-Za-z0-9_-]{1,80}$" },
        },
        required: ["operation_id"],
        additionalProperties: false,
      }),
    },
    async (args: any) => result(runtime.get(args.operation_id)),
  );
  server.registerTool(
    "lab_get_job",
    {
      description:
        "Inspect a durable background-job receipt. Settled means the handler returned, not persistence/render verification. Queued/running jobs from other processes are never automatically replayed.",
      inputSchema: fromJsonSchema({
        type: "object",
        properties: {
          job_id: { type: "string", pattern: "^[A-Za-z0-9_-]{1,80}$" },
        },
        required: ["job_id"],
        additionalProperties: false,
      }),
    },
    async (args: any) => {
      try {
        return result(jobs.get(args.job_id));
      } catch (error) {
        return {
          isError: true,
          ...result({ status: "unknown", error: String(error) }),
        };
      }
    },
  );
  server.registerTool('lab_reconcile_unchanged_assembly',{description:'Resolve one original unknown assembly attempt only when complete stable native project state equals its original project baseline. Never imports or edits. Exact original fingerprint, live lease and newest attempt required.',inputSchema:fromJsonSchema({type:'object',additionalProperties:false,required:['operation_id','args','guard'],properties:{operation_id:{type:'string',pattern:'^[A-Za-z0-9_-]{1,80}$'},args:{type:'object'},guard:guardSchema}})},async(input:any)=>{try{return result(await runtime.reconcileUnchangedAssembly(input,async project=>{const r:any=await getLabProjectStateTools(bridgeOptions).inspect_project_sequences.handler({project_path:project,paged_digest:true});if(!r.success)throw Error(r.error);return r.data;}));}catch(e){return {isError:true,...result({status:'refused',error:String(e)})};}});
  for (const [name, tool] of Object.entries(tools)) {
    if (!isToolPermitted(name, resolveCapabilities())) continue;
    const schema = labToolSchema(tool.parameters);
    server.registerTool(
      name,
      {
        description:
          tool.description +
          " [Premiere Agent: inspect per-operation evidence; mutations require _lab and exclusive exact-project stage scope or disposable-research ownership.]",
        inputSchema: fromJsonSchema(schema as JsonSchemaType),
      },
      async (input: any) => {
        const { _lab, _lab_async, ...args } = input;
        try {
          const value: any = _lab_async
            ? jobs.submit(name, args, _lab as Guard)
            : await runtime.call(name, args, _lab as Guard);
          return {
            ...result(value),
            ...(value?.success === false ||
            ["failed", "unknown", "running"].includes(value?.status) ||
            ["failed", "unknown"].includes(value?.outcome)
              ? { isError: true }
              : {}),
          };
        } catch (e) {
          return {
            isError: true,
            ...result({
              schema: "premiere-agent-lab/v1",
              status: "refused",
              error: String(e),
            }),
          };
        }
      },
    );
  }
  return { server, runtime, jobs, inventory };
}

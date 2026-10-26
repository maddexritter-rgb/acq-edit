import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  renameSync,
  openSync,
  closeSync,
  unlinkSync,
  realpathSync,
  readdirSync,
} from "node:fs";
import path from "node:path";
import type { ToolDef } from "../server.js";
import {
  capabilitiesForToolInvocation,
  resolveCapabilities,
  isToolPermitted,
} from "../security/capabilities.js";
import { deriveToolOperationalCapability } from "../tool-capability-report.js";
import { labContext } from "./context.js";

export const LAB_SCHEMA = "premiere-agent-lab/v1";
export function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}
export interface Snapshot {
  projectPath: string;
  sequenceId: string | null;
  tracks: unknown[];
}
export interface Guard {
  operation_id: string;
  expected_revision: string;
  project_path: string;
  sequence_id: string | null;
  snapshot_mode?: "media_repair" | "paged";
}
export interface Evidence {
  execution: string;
  readback: string;
  persistence: string;
  rendered: string;
}
export interface RecordEntry {
  schema: string;
  operationId: string;
  tool: string;
  fingerprint: string;
  status: string;
  evidence: Evidence;
  result?: unknown;
  error?: string;
  startedAt: string;
  finishedAt?: string;
}
export const guardSchema = {
  type: "object",
  additionalProperties: false,
  required: [
    "operation_id",
    "expected_revision",
    "project_path",
    "sequence_id",
  ],
  properties: {
    snapshot_mode: { type: "string", enum: ["media_repair", "paged"], description: "Paged uses complete bounded component snapshots for assembly stages; media_repair remains relinking only." },
    operation_id: {
      type: "string",
      pattern: "^[A-Za-z0-9_-]{1,80}$",
      description:
        "Unique durable lab operation ID; never reuse for another request.",
    },
    expected_revision: {
      type: "string",
      pattern: "^[a-f0-9]{64}$",
      description: "Revision returned by lab_snapshot.",
    },
    project_path: {
      type: "string",
      description: "Exact current project path from lab_snapshot; stage scope or disposable lease required.",
    },
    sequence_id: {
      type: ["string", "null"],
      description: "Exact active sequence ID from lab_snapshot.",
    },
  },
};

export function labToolSchema(parameters: Record<string, unknown>) {
  return {
    ...parameters,
    type: "object",
    properties: {
      ...((parameters.properties as object) ?? {}),
      _lab_async: {
        type: "boolean",
        description:
          "Return a durable job ID promptly; inspect lab_get_job. Requires _lab even for inspection. Never auto-replayed after restart.",
      },
      _lab: {
        ...guardSchema,
        description:
          "Mandatory for effects or async submission. Operation-specific expected target fields remain required.",
      },
    },
  };
}

export function requiresNewerHost(version: string | null): boolean {
  if (!version) return false;
  const match = /^(\d+)(?:\.(\d+))?(?:\.(\d+))?/.exec(version);
  if (!match) return true;
  const parts = [
    Number(match[1]),
    Number(match[2] || 0),
    Number(match[3] || 0),
  ];
  // Upstream CEP minimums use marketing years (2020); UXP uses API versions.
  if (parts[0] >= 2000) return parts[0] > 2026;
  for (let i = 0; i < 3; i++) {
    if (parts[i] !== [26, 3, 0][i]) return parts[i] > [26, 3, 0][i];
  }
  return false;
}

export const LAB_BLOCKED_MUTATIONS =
  /^(create_project|open_project|close_project|save_project_as|close_all|quit|set_scratch.*|set_project_scratch_disk|set_preferences|set_workspace|manage_project_sessions_uxp|manage_app_preferences_uxp|manage_storage_uxp|set_project_panel|delete_preview|consolidate_and_transfer|create_project_backup|manage_media_watch|.*after_effects.*|create_mogrt_recipe|create_mogrt_batch|publish_mogrt_to_library|enqueue_after_effects_render)$/;

export class LabRuntime {
  private tail: Promise<unknown> = Promise.resolve();
  readonly journal: string;
  constructor(
    readonly root: string,
    readonly tools: Record<string, ToolDef>,
    readonly snapshot: (mode?: "media_repair" | "paged") => Promise<Snapshot>,
    readonly cachedPagedBaseline?: (revision:string) => Promise<Snapshot|undefined>,
  ) {
    mkdirSync(root, { recursive: true, mode: 0o700 });
    this.journal = path.join(root, "operations");
    mkdirSync(this.journal, { recursive: true, mode: 0o700 });
  }
  private file(id: string) {
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(id))
      throw new Error("Invalid operation ID");
    return path.join(this.journal, id + ".json");
  }
  get(id: string): RecordEntry | null {
    const f = this.file(id);
    return existsSync(f) ? JSON.parse(readFileSync(f, "utf8")) : null;
  }
  private put(r: RecordEntry) {
    const f = this.file(r.operationId),
      stage = f + ".staged";
    writeFileSync(stage, JSON.stringify(r, null, 2) + "\n", { mode: 0o600 });
    renameSync(stage, f);
  }
  async reconcileUnchangedAssembly(input:{operation_id:string;args:Record<string,unknown>;guard:Guard},readProject:(project:string)=>Promise<any>){
    const record=this.get(input.operation_id);
    if(!record||record.status!=='unknown'||record.tool!=='lab_import_compiled_assembly'||input.guard.operation_id!==input.operation_id||digest({name:record.tool,args:input.args,guard:input.guard})!==record.fingerprint)throw Error('ORIGINAL_UNKNOWN_ASSEMBLY_REQUEST_REQUIRED');
    this.assertLease(input.guard.project_path,record.tool);
    const expectedRevision=input.args.expected_project_revision;
    if(typeof expectedRevision!=='string'||!/^[a-f0-9]{64}$/.test(expectedRevision))throw Error('ORIGINAL_PROJECT_BASELINE_REQUIRED');
    const lock=path.join(this.root,'writer.lock'),reconcile=path.join(this.root,'reconcile.lock');
    if(!existsSync(lock))throw Error('ORIGINAL_UNKNOWN_WRITER_LOCK_REQUIRED');
    const fd=openSync(reconcile,'wx',0o600);
    try{
      const entries=readdirSync(this.journal).filter(x=>x.endsWith('.json')&&!x.endsWith('.baseline.json')).map(x=>JSON.parse(readFileSync(path.join(this.journal,x),'utf8')));
      if(entries.some(x=>x.operationId!==record.operationId&&x.startedAt>=record.startedAt))throw Error('MORE_RECENT_OPERATION_REQUIRES_RECONCILIATION');
      const state=await readProject(input.guard.project_path);
      if(state?.revision!==expectedRevision||state.active_sequence_id!==input.guard.sequence_id)throw Error('NATIVE_PROJECT_NOT_UNCHANGED');
      const current=this.get(input.operation_id);if(current?.status!=='unknown'||current.fingerprint!==record.fingerprint)throw Error('OPERATION_CHANGED_DURING_RECONCILIATION');
      record.status='reconciled_no_native_change';record.evidence.readback='complete_stable_all_sequence_state_matches_original_project_baseline';
      (record as any).reconciliation={at:new Date().toISOString(),project_revision:expectedRevision,sequence_count:state.sequences.length,host_edit:'none',original_result_retained:true};
      this.put(record);unlinkSync(lock);return record;
    }finally{closeSync(fd);unlinkSync(reconcile);}
  }
  policy(name: string, args: Record<string, unknown>) {
    const tool = this.tools[name];
    if (!tool) throw new Error("Unknown tool");
    const required = capabilitiesForToolInvocation(name, args);
    return {
      mutation: required.some((v) => v !== "inspect"),
      operational: deriveToolOperationalCapability(
        name,
        tool,
        resolveCapabilities(),
      ),
    };
  }
  async call(
    name: string,
    args: Record<string, unknown>,
    guard?: Guard,
  ): Promise<unknown> {
    // Capture before the queue yields: neither a caller nor a later request may
    // change the payload/target whose fingerprint and preconditions we check.
    const request = JSON.parse(JSON.stringify({ name, args, guard })) as {
      name: string;
      args: Record<string, unknown>;
      guard?: Guard;
    };
    const run = () => this.execute(request.name, request.args, request.guard);
    const next = this.tail.then(run, run);
    this.tail = next.catch(() => {});
    return next;
  }
  private async execute(
    name: string,
    args: Record<string, unknown>,
    guard?: Guard,
  ) {
    const tool = this.tools[name];
    if (!tool || !isToolPermitted(name, resolveCapabilities()))
      throw new Error("Tool unavailable under lab authority");
    const policy = this.policy(name, args);
    // Operations that reach outside the current project need their own fixture contract.
    if (policy.mutation && LAB_BLOCKED_MUTATIONS.test(name))
      throw new Error(
        "LAB_SCOPE_UNSUPPORTED: global/lifecycle/cross-app operation has no disposable-project contract",
      );
    if (requiresNewerHost(policy.operational.minimumPremiereVersion))
      throw new Error(
        "LAB_VERSION_GATE: operation requires a separately validated newer host",
      );
    if (policy.operational.status === "unsupported")
      throw new Error(
        "UPSTREAM_UNSUPPORTED: " + policy.operational.notes.join(" "),
      );
    if (!policy.mutation) return tool.handler(args);
    if (!guard) throw new Error("LAB_GUARD_REQUIRED: call lab_snapshot first");
    if (guard.snapshot_mode && guard.snapshot_mode !== 'paged' && (guard.snapshot_mode !== 'media_repair' || name !== 'lab_relink_media_batch')) throw new Error('MEDIA_REPAIR_GUARD_TOOL_MISMATCH');
    if (name === 'lab_relink_media_batch' && guard.snapshot_mode !== 'media_repair') throw new Error('MEDIA_REPAIR_GUARD_REQUIRED');
    this.file(guard.operation_id);
    const fingerprint = digest({ name, args, guard });
    const previous = this.get(guard.operation_id);
    if (previous) {
      if (previous.fingerprint !== fingerprint)
        throw new Error("OPERATION_ID_CONFLICT");
      return previous;
    }
    const lock = path.join(this.root, "writer.lock");
    let fd: number;
    try {
      fd = openSync(lock, "wx", 0o600);
    } catch {
      throw new Error(
        "LAB_WRITER_BUSY: another writer or unresolved restart lock",
      );
    }
    let record: RecordEntry | undefined;
    let dispatched = false;
    let completionRecorded = false;
    try {
      // Recheck inside the cross-process writer lock: another process may have
      // finished this ID after the earlier journal read but before we acquired it.
      const completedWhileWaiting = this.get(guard.operation_id);
      if (completedWhileWaiting) {
        if (completedWhileWaiting.fingerprint !== fingerprint)
          throw new Error("OPERATION_ID_CONFLICT");
        return completedWhileWaiting;
      }
      const jobFile = path.join(
        this.root,
        "jobs",
        guard.operation_id + ".json",
      );
      if (existsSync(jobFile + ".claim")) {
        if (!existsSync(jobFile))
          throw new Error(
            "LAB_JOB_UNCERTAIN: operation ID is reserved by an incomplete job submission",
          );
        if (
          JSON.parse(readFileSync(jobFile, "utf8")).fingerprint !== fingerprint
        )
          throw new Error("OPERATION_ID_CONFLICT");
      }
      this.assertLease(guard.project_path, name);
      // These CEP handlers always pass through the complete native page guard.
      // UXP, media repair and other handlers continue to use fresh preflight reads.
      const cached = guard.snapshot_mode === 'paged' && ['set_active_sequence','lab_import_compiled_assembly','lab_import_prepared_caption_sequence'].includes(name) ? await this.cachedPagedBaseline?.(guard.expected_revision) : undefined;
      const before = cached || await this.snapshot(guard.snapshot_mode);
      if (
        before.projectPath !== guard.project_path ||
        before.sequenceId !== guard.sequence_id
      )
        throw new Error("LAB_TARGET_CHANGED");
      if (digest(before) !== guard.expected_revision)
        throw new Error("LAB_STALE_STATE");
      this.assertPaths(args);
      record = {
        schema: LAB_SCHEMA,
        operationId: guard.operation_id,
        tool: name,
        fingerprint,
        status: "running",
        startedAt: new Date().toISOString(),
        evidence: {
          execution: "pending",
          readback: "not_run",
          persistence: "not_run",
          rendered: "not_run",
        },
      };
      this.put(record);
      const expectedSnapshotPath = path.join(this.journal, guard.operation_id + '.baseline.json');
      writeFileSync(expectedSnapshotPath, JSON.stringify(before), {mode:0o600, flag:'wx'});
      const ctx = {
        snapshotMode: guard.snapshot_mode,
        expectedSnapshotPath,
        operationId: guard.operation_id,
        projectPath: guard.project_path,
        sequenceId: guard.sequence_id,
        expectedSnapshot: JSON.stringify(before),
        dispatched: false,
        allowNoSequence: name === "import_media" || name === "save_project" || name === "lab_import_compiled_assembly" || name === "set_active_sequence" || name === "create_sequence" || name === "create_sequence_from_preset" || name === "create_sequence_from_clips",
      };
      try {
        const result = await labContext.run(ctx, () => tool.handler(args));
        record.result = result;
        // A successful wrapper is not evidence of correct host postconditions.
        record.status = result.success
          ? "committed_unverified"
          : ctx.dispatched
            ? "unknown"
            : "failed";
        record.evidence.execution = result.success
          ? "reported_success"
          : ctx.dispatched
            ? "unknown"
            : "failed";
        if (result.success) {
          try {
            const after = await this.snapshot(guard.snapshot_mode);
            record.evidence.readback =
              after.projectPath === guard.project_path
                ? "snapshot_captured"
                : "target_changed";
            if (name === 'lab_relink_media_batch') {
              const data = result.data as any, state = after as any;
              const targets = (args as any).items as Array<{new_path:string}>;
              if (data?.verified === true && data.projectPath === (args as any).output_path &&
                  after.projectPath === data.projectPath && after.sequenceId === guard.sequence_id &&
                  data.persistence === 'saved_closed_reopened_media_and_structural_state_verified' &&
                  targets.every(target => state.media?.filter((m:any) => m.path === target.new_path && m.offline === false).length === 1)) {
                record.status = 'verified';
                record.evidence.readback = 'media_paths_online_and_structural_state_verified';
                record.evidence.persistence = data.persistence;
              }
            }
          } catch {
            record.evidence.readback = "unavailable";
          }
        }
      } catch (error) {
        record.status = ctx.dispatched ? "unknown" : "failed";
        record.error = String(error);
        record.evidence.execution = record.status;
      } finally {
        dispatched = ctx.dispatched;
      }
      record.finishedAt = new Date().toISOString();
      this.put(record);
      completionRecorded = true;
      return record;
    } finally {
      closeSync(fd!);
      // A host response held only in memory cannot release the durable writer
      // quarantine. A failed final receipt write leaves a running receipt for
      // restart reconciliation, even if the wrapper reported success.
      if ((!record || record.status !== "unknown") &&
          (!dispatched || completionRecorded)) unlinkSync(lock);
    }
  }
  private assertLease(project: string, tool: string) {
    const leasePath = path.join(this.root, "lease.json");
    if (!existsSync(leasePath))
      throw new Error(
        "LAB_LEASE_REQUIRED: production bridge must be stopped and fixture ownership recorded",
      );
    const lease = JSON.parse(readFileSync(leasePath, "utf8"));
    if (
      lease.productionBridgeStopped !== true ||
      lease.projectPath !== project ||
      Date.parse(lease.expiresAt) <= Date.now() ||
      !Number.isFinite(Date.parse(lease.expiresAt))
    )
      throw new Error("LAB_LEASE_INVALID");
    const authorized = this.productionAuthorization(project);
    if (authorized) {
      if (!authorized.tools.includes(tool)) throw new Error('PRODUCTION_TOOL_NOT_AUTHORIZED');
      return;
    }
    if (process.env.PREMIERE_AGENT_MODE === "scoped-edit") throw new Error("EDIT_PROJECT_SCOPE_REQUIRED");
    const fixtures = realpathSync(path.join(this.root, "fixtures")),
      actual = realpathSync(project);
    if (!actual.startsWith(fixtures + path.sep) || !actual.endsWith(".prproj"))
      throw new Error("LAB_FIXTURE_REQUIRED");
  }
  private productionAuthorization(project: string): {tools:string[],readPaths:string[],writeRoot:string} | null {
    const edit=path.join(this.root,'edit-project-authorization.json');
    const f=existsSync(edit)?edit:path.join(this.root,'reframe-project-authorization.json');
    if(!existsSync(f))return null;
    const a=JSON.parse(readFileSync(f,'utf8'));
    if(!['premiere-agent/reframe-project-authorization-v1','premiere-agent/edit-project-authorization-v1','premiere-agent/media-repair-project-authorization-v1'].includes(a.schema)||a.projectPath!==project)return null;
    if(!Number.isFinite(Date.parse(a.expiresAt))||Date.parse(a.expiresAt)<=Date.now())throw new Error('PRODUCTION_AUTHORIZATION_EXPIRED');
    const allowed=['lab_update_static_panel_geometry','lab_export_reframe_frames','lab_reframe_embedded_panels','lab_split_reframe_shots','lab_duplicate_vertical_sequence','lab_apply_reframe_motion','lab_repair_anchor_x_keys','save_project','set_active_sequence','export_frame'];
    if(a.schema==='premiere-agent/edit-project-authorization-v1')allowed.push('lab_apply_camera_visibility','lab_prepare_sequence_name','lab_import_compiled_assembly','lab_import_prepared_caption_sequence','lab_place_graphic_asset','lab_prepare_music_source','lab_place_music_item','lab_apply_music_envelope','lab_apply_assembly_audio_edges','export_sequence','lab_export_exact_range');
    if(a.schema==='premiere-agent/media-repair-project-authorization-v1') { allowed.length=0; allowed.push('lab_relink_media_batch'); }
    if(!Array.isArray(a.tools)||a.tools.some((t:string)=>!allowed.includes(t)))throw new Error('INVALID_PRODUCTION_TOOL_SCOPE');
    if(!path.isAbsolute(a.writeRoot)||!Array.isArray(a.readPaths)||a.readPaths.some((p:string)=>!path.isAbsolute(p)))throw new Error('INVALID_PRODUCTION_PATH_SCOPE');
    return a;
  }
  private assertPaths(args: unknown, key = "") {
    if (typeof args === "string") {
      const isPathField =
        /(?:path|directory|folder|file)$/i.test(key) &&
        !/(?:profile|file_name)$/i.test(key);
      if (isPathField && !path.isAbsolute(args))
        throw new Error("LAB_ABSOLUTE_PATH_REQUIRED: " + key);
      if (!path.isAbsolute(args)) return;
      if (
        key.includes("preset") &&
        existsSync(args) &&
        /\.(?:epr|sqpreset)$/i.test(args)
      )
        return;
      const ctxProject=JSON.parse(readFileSync(path.join(this.root,'lease.json'),'utf8')).projectPath;
      const auth=this.productionAuthorization(ctxProject);
      if(auth&&['project','project_path'].includes(key)&&args===ctxProject)return;
      if(auth&&['path','media_path','xml_path','expected_path','resolved_path','prepared_path','new_path','coverage_path'].includes(key)&&existsSync(args)&&auth.readPaths.includes(realpathSync(args)))return;
      // Expected old offline paths are target preconditions, never file access.
      if(auth&&auth.tools.includes('lab_relink_media_batch')&&key==='expected_current_path')return;
      if(auth&&(/(?:output_path|output_dir|file_path)$/.test(key))) {
        let parent=args;while(!existsSync(parent)&&path.dirname(parent)!==parent)parent=path.dirname(parent);
        const resolved=path.resolve(realpathSync(parent),path.relative(parent,args));
        if(resolved===realpathSync(auth.writeRoot)||resolved.startsWith(realpathSync(auth.writeRoot)+path.sep))return;
      }
      const base = realpathSync(this.root);
      let parent = args;
      while (!existsSync(parent) && path.dirname(parent) !== parent)
        parent = path.dirname(parent);
      const resolved = path.resolve(
        realpathSync(parent),
        path.relative(parent, args),
      );
      if (resolved !== base && !resolved.startsWith(base + path.sep))
        throw new Error("LAB_EXTERNAL_PATH_REFUSED: " + key);
    } else if (Array.isArray(args)) {
      for (const a of args) this.assertPaths(a, key);
    } else if (args && typeof args === "object") {
      for (const [k, v] of Object.entries(args)) this.assertPaths(v, k);
    }
  }
}

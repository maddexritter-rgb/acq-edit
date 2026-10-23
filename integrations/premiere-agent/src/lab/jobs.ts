import {
  existsSync,
  mkdirSync,
  openSync,
  closeSync,
  readFileSync,
  writeFileSync,
  renameSync,
} from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { LabRuntime, digest, type Guard } from "./runtime.js";

export interface LabJob {
  schema: "premiere-agent-lab/job-v1";
  jobId: string;
  operationId: string;
  tool: string;
  fingerprint: string;
  state: "queued" | "running" | "settled";
  outcome:
    | "pending"
    | "failed"
    | "unknown"
    | "reported_success"
    | "committed_unverified";
  completionScope: "handler_only";
  submittedAt: string;
  startedAt?: string;
  finishedAt?: string;
  result?: unknown;
  error?: string;
  verification: { persistence: "not_run"; rendered: "not_run" };
}

/** Durable one-shot submission. Restarted processes never replay saved jobs. */
export class LabJobs {
  private tail: Promise<unknown> = Promise.resolve();
  private readonly active = new Set<string>();
  private readonly directory: string;
  constructor(readonly runtime: LabRuntime) {
    this.directory = path.join(runtime.root, "jobs");
    mkdirSync(this.directory, { recursive: true, mode: 0o700 });
  }
  private file(id: string) {
    if (!/^[A-Za-z0-9_-]{1,80}$/.test(id)) throw new Error("Invalid job ID");
    return path.join(this.directory, id + ".json");
  }
  get(id: string) {
    const f = this.file(id);
    if (!existsSync(f)) {
      if (existsSync(f + ".claim"))
        throw new Error(
          "LAB_JOB_UNCERTAIN: submission claim exists without a receipt; never replay automatically",
        );
      return null;
    }
    const job = JSON.parse(readFileSync(f, "utf8")) as LabJob;
    return {
      ...job,
      observedInThisProcess: this.active.has(id),
      recoveryPolicy: "never_auto_replay",
    };
  }
  private put(job: LabJob) {
    const file = this.file(job.jobId),
      staged = file + "." + randomUUID() + ".staged";
    writeFileSync(staged, JSON.stringify(job, null, 2) + "\n", { mode: 0o600 });
    renameSync(staged, file);
  }
  submit(name: string, args: Record<string, unknown>, guard?: Guard) {
    if (!guard)
      throw new Error(
        "LAB_GUARD_REQUIRED: async jobs require a unique operation ID and exact snapshot guard",
      );
    // Freeze caller input before returning; callers cannot change a queued request.
    const request = JSON.parse(JSON.stringify({ name, args, guard })) as {
      name: string;
      args: Record<string, unknown>;
      guard: Guard;
    };
    const file = this.file(request.guard.operation_id),
      fingerprint = digest(request);
    this.runtime.policy(name, args); // Reject unknown tools before reserving the ID.
    const existing = this.get(request.guard.operation_id);
    if (existing) {
      if (existing.fingerprint !== fingerprint)
        throw new Error("OPERATION_ID_CONFLICT");
      return existing;
    }
    // A persistent exclusive claim protects against two server processes submitting the same job.
    let fd: number;
    try {
      fd = openSync(file + ".claim", "wx", 0o600);
    } catch {
      const raced = this.get(request.guard.operation_id);
      if (raced && raced.fingerprint === fingerprint) return raced;
      throw new Error(
        "LAB_JOB_CLAIM_CONFLICT: inspect the existing job; do not retry with a new ID",
      );
    }
    closeSync(fd);
    const job: LabJob = {
      schema: "premiere-agent-lab/job-v1",
      jobId: request.guard.operation_id,
      operationId: request.guard.operation_id,
      tool: name,
      fingerprint,
      state: "queued",
      outcome: "pending",
      completionScope: "handler_only",
      submittedAt: new Date().toISOString(),
      verification: { persistence: "not_run", rendered: "not_run" },
    };
    this.put(job);
    this.active.add(job.jobId);
    const run = async () => {
      job.state = "running";
      job.startedAt = new Date().toISOString();
      this.put(job);
      try {
        // Mutations get the runtime's same-invocation guard. Inspection jobs also
        // check their queued target/revision before calling the read handler.
        if (!this.runtime.policy(name, request.args).mutation) {
          const before = await this.runtime.snapshot();
          if (
            before.projectPath !== request.guard.project_path ||
            before.sequenceId !== request.guard.sequence_id
          )
            throw new Error("LAB_TARGET_CHANGED");
          if (digest(before) !== request.guard.expected_revision)
            throw new Error("LAB_STALE_STATE");
        }
        const result: any = await this.runtime.call(
          name,
          request.args,
          request.guard,
        );
        job.result = result;
        if (result?.status === "unknown" || result?.status === "running")
          job.outcome = "unknown";
        else if (result?.status === "failed" || result?.success === false)
          job.outcome = "failed";
        else if (result?.status === "committed_unverified")
          job.outcome = "committed_unverified";
        else
          job.outcome =
            result?.success === true ? "reported_success" : "unknown";
      } catch (error) {
        const receipt = this.runtime.get(job.operationId);
        job.outcome =
          receipt?.status === "running" || receipt?.status === "unknown"
            ? "unknown"
            : "failed";
        job.error = String(error);
      }
      job.state = "settled";
      job.finishedAt = new Date().toISOString();
      this.put(job);
    };
    const next = this.tail.then(run, run);
    // Receipt-write errors leave the last durable queued/running state intact.
    // They never dispatch a replacement attempt or become successful completion.
    this.tail = next
      .catch(() => {})
      .finally(() => this.active.delete(job.jobId));
    return {
      ...job,
      observedInThisProcess: true,
      recoveryPolicy: "never_auto_replay",
    };
  }
  async drain() {
    await this.tail;
  }
}

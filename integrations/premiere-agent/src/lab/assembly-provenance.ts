import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { realpath, stat } from "node:fs/promises";
import { mediaHash } from "./music-placement.js";

const run = promisify(execFile);
export type AssemblyRequest = {
  xml_path: string; xml_sha256: string; expected_path: string; expected_sha256: string;
  resolved_path: string; resolved_sha256: string; gap_frames: number; expected_project_revision: string;
};
export type CompilerProof = {
  expectation: { sequence_name: string; frame_ticks: string; duration_ticks: string; width: number; height: number;
    items: { clip_id: string; media_path: string; start_ticks: string; end_ticks: string; source_in_ticks: string; source_out_ticks: string }[];
    markers: { name: string; comments: string; start_ticks: string }[] };
  provenance: { schema: string; verification: string; artifacts: { path: string; sha256: string }[];
    canonical_code: { path: string; sha256: string }[]; media: { path: string; size: string; mtime_ns: string }[];
    gap_frames: number; media_identity_scope: string; editorial_review: string };
};
export async function checkCompilerArtifacts(proof: CompilerProof) {
  for (const row of [...proof.provenance.artifacts, ...proof.provenance.canonical_code])
    if (await mediaHash(row.path) !== row.sha256) throw Error("COMPILER_ARTIFACT_CHANGED");
  for (const row of proof.provenance.media) {
    const info = await stat(row.path, { bigint: true });
    if (!info.isFile() || await realpath(row.path) !== row.path || info.size.toString() !== row.size || info.mtimeNs.toString() !== row.mtime_ns) throw Error("COMPILER_MEDIA_IDENTITY_CHANGED");
  }
}
export async function validateCompiledAssembly(args: AssemblyRequest, fixtureRoot: string): Promise<CompilerProof> {
  const script = fileURLToPath(new URL("../../scripts/validate-assembly-import.py", import.meta.url));
  const { stdout } = await run("python3", [script, "--compiled", args.xml_path, args.xml_sha256, args.expected_path, args.expected_sha256,
    fixtureRoot, args.resolved_path, args.resolved_sha256, String(args.gap_frames)], { timeout: 300000, maxBuffer: 4 * 1024 * 1024 });
  const proof = JSON.parse(stdout) as CompilerProof;
  if (proof?.provenance?.schema !== "edit.assembly-compiler-provenance/v1" || proof.provenance.verification !== "canonical_v2_selection_recompiled_and_exact_xml_reproduced" || !proof.expectation?.items?.length) throw Error("COMPILER_PROVENANCE_INVALID");
  await checkCompilerArtifacts(proof);
  return proof;
}

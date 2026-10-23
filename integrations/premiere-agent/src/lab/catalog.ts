import {
  LAB_BLOCKED_MUTATIONS,
  requiresNewerHost,
  labToolSchema,
} from "./runtime.js";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { ToolDef } from "../server.js";
import { deriveToolOperationalCapability } from "../tool-capability-report.js";
import {
  resolveCapabilities,
  isToolPermitted,
} from "../security/capabilities.js";
export function catalog(root: string, tools: Record<string, ToolDef>) {
  const read = (file: string) =>
    JSON.parse(readFileSync(path.join(root, "src/resources", file), "utf8"));
  const coverage = read("adobe-uxp-coverage.json"),
    inventory = read("adobe-api-inventory.json");
  const evidenceFile = path.join(root, "reports/evidence-index.json");
  const evidence = existsSync(evidenceFile)
    ? JSON.parse(readFileSync(evidenceFile, "utf8"))
    : { operations: {} };
  const operations = Object.entries(tools)
    .map(([name, tool]) => {
      const operational = deriveToolOperationalCapability(
        name,
        tool,
        resolveCapabilities(),
      );
      const entries = coverage.entries.filter((e: any) =>
        (e.mcpTools ?? []).includes(name),
      );
      return {
        description: tool.description,
        inputSchema: labToolSchema(tool.parameters),
        ...operational,
        supportStatusSource: "pinned_static_metadata_not_host_proof",
        routingScope: "isolated_lab_only",
        authorityPermitted: isToolPermitted(name, resolveCapabilities()),
        labMutationPolicy: LAB_BLOCKED_MUTATIONS.test(name)
          ? "blocked_pending_fixture_contract"
          : "action_dependent_guard_required_for_effects",
        targetVersionEligible: !requiresNewerHost(
          operational.minimumPremiereVersion,
        ),
        apiMappings: entries.map((e: any) => ({
          id: e.id,
          apis: e.adobeApi,
          minimumVersion: e.minimumPremiereVersion,
          command: e.uxpCommand,
        })),
        implementation: name.startsWith("lab_") || ["inspect_reframe_state", "inspect_music_state", "inspect_project_sequences", "inspect_assembly_links"].includes(name)
          ? "lab_wrapper_present"
          : "upstream_wrapper_present",
        hostTest: evidence.operations[name]?.hostTest ?? "not_run",
        persistenceTest:
          evidence.operations[name]?.persistenceTest ?? "not_run",
        visualTest: evidence.operations[name]?.visualTest ?? "not_run",
        localEvidence: evidence.operations[name] ?? null,
        limitation:
          operational.status === "unsupported"
            ? operational.notes.join(" ")
            : evidence.operations[name]
              ? "Local evidence is limited to the recorded fixture invocation; inspect its scope."
              : "No local licensed-host verification yet.",
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
  const declarations = inventory.entries.map((entry: any) => {
    const mappings = coverage.entries.filter((e: any) =>
      (e.adobeApi ?? []).includes(entry.symbol),
    );
    return {
      ...entry,
      classification: mappings.length
        ? "mapped_to_workflow"
        : entry.kind !== "method"
          ? "supporting_declaration_review"
          : "unmapped_callable_review",
      tools: [...new Set(mappings.flatMap((e: any) => e.mcpTools ?? []))],
      hostTest: "not_run",
    };
  });
  return {
    schema: "premiere-agent-lab/catalog-v1",
    upstreamCommit: "254ee051f657df9d44c6b2fd8f2e3bb14098a776",
    targetHost: "26.3.0",
    generatedAt: new Date().toISOString(),
    counts: {
      operations: operations.length,
      defaultAuthorityOperations: operations.filter((t) => t.authorityPermitted)
        .length,
      uxpOperations: operations.filter((t) => t.backends.includes("uxp"))
        .length,
      experimentalQe: operations.filter((t) => t.backends.includes("qe"))
        .length,
      adobeDeclarations: declarations.length,
      unmappedDeclarations: declarations.filter(
        (d: any) => d.coverage === "unmapped",
      ).length,
      hostVerifiedOperations: operations.filter(
        (t) => t.hostTest === "postcondition_passed",
      ).length,
      hostObservedOperations: operations.filter(
        (t) => t.hostTest === "read_succeeded",
      ).length,
      hostFailedOperations: operations.filter((t) => t.hostTest === "failed")
        .length,
    },
    operations,
    declarations,
    extendscript: read("extendscript-api-inventory.json"),
    surfaces: read("premiere-surface-registry.json"),
    limitations: [
      {
        area: "Native SDK",
        status: "externally_gated",
        reason:
          "No authorized PrSDK or UXP Hybrid SDK headers found locally. Header inventory tooling exists upstream; native interface feasibility remains unverified.",
      },
      {
        area: "Native caption tracks",
        status: "limited",
        reason:
          "Inspect documented capabilities separately from editable Graphics/MOGRT layers. No generic UXP caption creation/text/timing/delete APIs in this pinned implementation.",
      },
      {
        area: "Newer APIs",
        status: "version_gated",
        reason: "26.5 operations remain unavailable on the pinned 26.3 host.",
      },
      {
        area: "UI-only controls",
        status: "excluded_by_user",
        reason:
          "No keyboard, mouse, menu automation or private binary patching.",
      },
    ],
  };
}

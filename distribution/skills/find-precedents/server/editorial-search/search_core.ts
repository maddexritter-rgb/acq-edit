export type SearchRequest = {
  brand?: string;
  productionType?: string;
  stage?: string | null;
  problem: string;
  format: "q_and_a" | "monologue" | "podcast" | "story" | null;
  limit: number;
  includeDevelopment: boolean;
  currentProjectPrefix: string | null;
  heldOutSourcePrefixes: string[];
  includeRequiredReading: boolean;
  readingOverlays: Array<"l1" | "workshop">;
};

const FORMATS = new Set(["q_and_a", "monologue", "podcast", "story"]);

export function parseSearchRequest(value: unknown): SearchRequest {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("expected a JSON object");
  }
  const body = value as Record<string, unknown>;
  if (typeof body.problem !== "string") throw new Error("problem must be text");
  const problem = body.problem.trim();
  if (problem.length < 3 || problem.length > 240) throw new Error("problem must be 3–240 characters");
  const format = body.format == null ? null : body.format;
  if (format !== null && (typeof format !== "string" || !FORMATS.has(format))) {
    throw new Error("unsupported format");
  }
  const limit = body.limit === undefined ? 4 : body.limit;
  if (!Number.isInteger(limit) || (limit as number) < 1 || (limit as number) > 5) {
    throw new Error("limit must be an integer from 1 to 5");
  }
  const includeDevelopment = body.include_development === undefined ? false : body.include_development;
  if (typeof includeDevelopment !== "boolean") throw new Error("include_development must be boolean");
  const currentProjectPrefix = body.current_project_prefix == null ? null : body.current_project_prefix;
  if (currentProjectPrefix !== null && (typeof currentProjectPrefix !== "string" || currentProjectPrefix.length > 500)) {
    throw new Error("invalid current_project_prefix");
  }
  const heldOutSourcePrefixes = body.held_out_source_prefixes === undefined ? [] : body.held_out_source_prefixes;
  if (!Array.isArray(heldOutSourcePrefixes) || heldOutSourcePrefixes.length > 20 ||
      heldOutSourcePrefixes.some((value) => typeof value !== "string" || value.length > 500)) {
    throw new Error("invalid held_out_source_prefixes");
  }
  const includeRequiredReading = body.include_required_reading === undefined ? false : body.include_required_reading;
  if (typeof includeRequiredReading !== "boolean") throw new Error("include_required_reading must be boolean");
  const readingOverlays = body.reading_overlays === undefined ? [] : body.reading_overlays;
  if (!Array.isArray(readingOverlays) || readingOverlays.length > 2 ||
      readingOverlays.some((item) => item !== "l1" && item !== "workshop") ||
      new Set(readingOverlays).size !== readingOverlays.length) {
    throw new Error("invalid reading_overlays");
  }
  if ((includeRequiredReading && format === null) ||
      (readingOverlays.length > 0 && !includeRequiredReading) ||
      (readingOverlays.includes("l1") && format !== "q_and_a")) {
    throw new Error("reading profile does not match the requested format");
  }
  const hasScope = body.brand != null || body.production_type != null || body.stage != null;
  let scope = {};
  if (hasScope) {
    const slug = /^[a-z0-9][a-z0-9_-]{0,63}$/;
    if (typeof body.brand !== "string" || !slug.test(body.brand) ||
        typeof body.production_type !== "string" || !slug.test(body.production_type)) {
      throw new Error("brand and production_type must be supplied together as slugs");
    }
    const stages = ["orchestration","assembly","reframe","audio","captions","delivery","publishing"];
    const stage = body.stage == null ? null : body.stage;
    if (stage !== null && (typeof stage !== "string" || !stages.includes(stage))) {
      throw new Error("unsupported policy stage");
    }
    scope = { brand: body.brand, productionType: body.production_type, stage };
  }
  return {
    ...scope,
    problem, format: format as SearchRequest["format"], limit: limit as number,
    includeDevelopment, currentProjectPrefix: currentProjectPrefix as string | null,
    heldOutSourcePrefixes: heldOutSourcePrefixes as string[],
    includeRequiredReading,
    readingOverlays: readingOverlays as SearchRequest["readingOverlays"],
  };
}


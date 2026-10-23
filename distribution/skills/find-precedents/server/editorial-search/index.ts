import { parseSearchRequest } from "./search_core.ts";
import { validateRequiredReading } from "./required_reading_core.ts";

// A dedicated function-only token gives callers read access to this endpoint,
// never service-role access to Supabase's wider Data API. The service-role key
// stays inside the Edge Function. Deploy with verify_jwt=false because this
// handler performs its own authentication before any database call.
async function authorized(req: Request): Promise<boolean> {
  // Supabase's secret form can preserve a pasted trailing newline. Normalize
  // surrounding whitespace on the configured value, matching the local client.
  const configured = (Deno.env.get("EDITORIAL_BRAIN_READ_TOKEN") || "").trim();
  const supplied = req.headers.get("Authorization")?.replace(/^Bearer\s+/i, "") || "";
  if (configured.length < 32 || !supplied) return false;
  const encode = new TextEncoder();
  const [expected, actual] = await Promise.all([
    crypto.subtle.digest("SHA-256", encode.encode(configured)),
    crypto.subtle.digest("SHA-256", encode.encode(supplied)),
  ]);
  const a = new Uint8Array(expected);
  const b = new Uint8Array(actual);
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export default {
  fetch: async (req: Request) => {
    if (req.method !== "POST") {
      return Response.json({ error: "method_not_allowed" }, { status: 405, headers: { Allow: "POST" } });
    }
    if (!await authorized(req)) {
      return Response.json({ error: "unauthorized" }, { status: 401 });
    }

    const rawBody = await req.text();
    if (rawBody.length > 4096) {
      return Response.json({ error: "request_too_large" }, { status: 413 });
    }

    let input;
    try {
      input = parseSearchRequest(JSON.parse(rawBody));
    } catch (error) {
      return Response.json({ error: "invalid_request", detail: String(error) }, { status: 400 });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!supabaseUrl || !serviceKey) {
      return Response.json({ error: "database_unavailable" }, { status: 503 });
    }

    try {
      const dbResponse = await fetch(`${supabaseUrl}/rest/v1/rpc/editorial_context_search`, {
        method: "POST",
        headers: { "Content-Type": "application/json", apikey: serviceKey, Authorization: `Bearer ${serviceKey}` },
        body: JSON.stringify({
          p_problem: input.problem,
          p_format: input.format,
          p_limit: input.limit,
          p_include_development: input.includeDevelopment,
          p_current_project_prefix: input.currentProjectPrefix,
          p_held_out_source_prefixes: input.heldOutSourcePrefixes,
        }),
      });
      if (!dbResponse.ok) {
        console.error("editorial-search RPC failure", dbResponse.status);
        return Response.json({ error: "search_failed" }, { status: 500 });
      }
      const data = await dbResponse.json();
      const playbooks = (data.playbooks || []) as Array<{ format: string }>;
      const requiredFormats = input.format ? ["universal", input.format] : ["universal"];
      if (playbooks.length !== requiredFormats.length ||
          requiredFormats.some((fmt) => !playbooks.some((row) => row.format === fmt))) {
        return Response.json({ error: "active_playbook_missing", required_formats: requiredFormats }, { status: 503 });
      }
      let requiredReading = null;
      if (input.includeRequiredReading) {
        const readingResponse = await fetch(`${supabaseUrl}/rest/v1/rpc/editorial_required_reading`, {
          method: "POST",
          headers: { "Content-Type": "application/json", apikey: serviceKey, Authorization: `Bearer ${serviceKey}` },
          body: JSON.stringify({ p_format: input.format, p_overlays: input.readingOverlays }),
        });
        if (!readingResponse.ok) {
          console.error("editorial-search required-reading RPC failure", readingResponse.status);
          return Response.json({ error: "required_reading_unavailable" }, { status: 503 });
        }
        try {
          requiredReading = await validateRequiredReading(
            await readingResponse.json(), ["universal", input.format!, ...input.readingOverlays]);
        } catch {
          return Response.json({ error: "required_reading_missing" }, { status: 503 });
        }
      }
      // Scoped guidance is additive. Its availability never creates a new quality gate
      // or takes down the existing format playbooks/required-reading route.
      let scopedPolicy = null;
      if (input.brand) {
        try {
          const response = await fetch(`${supabaseUrl}/rest/v1/rpc/editorial_scoped_policy`, {
            method: "POST",
            headers: { "Content-Type": "application/json", apikey: serviceKey, Authorization: `Bearer ${serviceKey}` },
            body: JSON.stringify({ p_brand: input.brand, p_production_type: input.productionType, p_stage: input.stage }),
          });
          if (!response.ok) throw new Error("scoped lookup unavailable");
          const result = await response.json();
          if (!result || !Array.isArray(result.policies)) throw new Error("invalid scoped result");
          scopedPolicy = { ...result, status: result.policies.length ? "available" : "no_match" };
        } catch {
          scopedPolicy = { policies: [], status: "unavailable",
            note: "Scoped guidance unavailable; record the limitation in the existing handoff. No new editorial/export gate." };
        }
      }
      const projectRef = new URL(supabaseUrl).hostname.split(".")[0];
      return Response.json({
        schema: "editorial-brain.context/v1", project_ref: projectRef,
        query: input, playbooks, cards: data.cards || [],
        ...(input.brand ? { scoped_policy: scopedPolicy } : {}),
        ...(input.includeRequiredReading ? { required_reading: requiredReading } : {}),
      },
        { headers: { "Cache-Control": "no-store" } });
    } catch (error) {
      console.error("editorial-search database failure", error);
      return Response.json({ error: "search_failed" }, { status: 500 });
    }
  },
};


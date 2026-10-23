export type RequiredReadingPolicy = {
  policy_id: string;
  version: number;
  format: string;
  priority_note: string;
  documents: Array<{
    ordinal: number;
    source_id: string;
    source_title: string;
    source_sha256: string;
    source_body: string;
  }>;
};

export type RequiredReading = { policies: RequiredReadingPolicy[] };

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

// A Workshop batch may include source-word examples, but never the whole library.
const MAX_DOCUMENTS = 32;
const MAX_BODY_BYTES = 256_000;

export async function validateRequiredReading(value: unknown, expectedFormats: string[]): Promise<RequiredReading> {
  if (!isRecord(value) || !Array.isArray(value.policies) ||
      value.policies.length !== expectedFormats.length || expectedFormats.length < 2) {
    throw new Error("required reading policies are missing or incomplete");
  }
  let totalDocuments = 0;
  let totalBytes = 0;
  const seenSources = new Set<string>();
  for (let policyIndex = 0; policyIndex < expectedFormats.length; policyIndex++) {
    const policy = value.policies[policyIndex];
    if (!isRecord(policy) || policy.format !== expectedFormats[policyIndex] ||
        typeof policy.policy_id !== "string" || !policy.policy_id ||
        typeof policy.version !== "number" || !Number.isInteger(policy.version) || policy.version < 1 ||
        typeof policy.priority_note !== "string" || !policy.priority_note ||
        !Array.isArray(policy.documents) || policy.documents.length < 1) {
      throw new Error("required reading policy is missing or incomplete");
    }
    totalDocuments += policy.documents.length;
    if (totalDocuments > MAX_DOCUMENTS) throw new Error("required reading exceeds document limit");
    for (let index = 0; index < policy.documents.length; index++) {
      const document = policy.documents[index];
      if (!isRecord(document) || document.ordinal !== index + 1 ||
          typeof document.source_id !== "string" || !document.source_id || seenSources.has(document.source_id) ||
          typeof document.source_title !== "string" || !document.source_title ||
          typeof document.source_body !== "string" || !document.source_body ||
          typeof document.source_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(document.source_sha256)) {
        throw new Error("required reading document is missing, repeated, or out of order");
      }
      seenSources.add(document.source_id);
      const bytes = new TextEncoder().encode(document.source_body);
      totalBytes += bytes.byteLength;
      if (totalBytes > MAX_BODY_BYTES) throw new Error("required reading exceeds body limit");
      const hash = await crypto.subtle.digest("SHA-256", bytes);
      const actual = Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, "0")).join("");
      if (actual !== document.source_sha256) throw new Error("required reading source hash mismatch");
    }
  }
  return value as RequiredReading;
}


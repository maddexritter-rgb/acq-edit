import type { UxpWebSocketBridge } from "../bridge/uxp-websocket-bridge.js";

type EffectParameterCatalogArgs = {
  media_type: "video" | "audio";
  track_index?: number;
  clip_index?: number;
  project_item_id?: string;
  expected_project_guid?: string;
  component_index: number;
  expected_sequence_guid?: string;
  expected_component_id?: string;
};

function invoke(bridge: UxpWebSocketBridge, args: Record<string, unknown>) {
  return bridge.request("parameters.catalog.inspect", args)
    .then((result) => ({ success: true, data: { backend: "uxp", result } }))
    .catch((error: unknown) => ({
      success: false,
      error: error instanceof Error ? error.message : String(error),
    }));
}

/** Bounded component-parameter discovery without reading raw parameter values. */
export function getUxpEffectParameterCatalogWorkflowTools(bridge: UxpWebSocketBridge) {
  return {
    inspect_effect_parameter_catalog_uxp: {
      description: "Inspect the bounded native descriptor catalog for one effect component on an audio/video timeline clip or source project item. Supply track_index and clip_index for the active sequence, or project_item_id for source effects; never combine these targets. Source inspection checks native project ownership and needs no active sequence. It returns only animation capability/state, never raw parameter values (including Color or PointF), media paths, rendered pixels, or playback results. The bridge reads the catalog twice and rejects changed project, component identity or parameter descriptors. Source parameter indexes must not be passed to timeline-only automation tools.",
      parameters: {
        type: "object" as const,
        additionalProperties: false,
        properties: {
          media_type: { type: "string", enum: ["video", "audio"], description: "Native audio or video component chain to inspect." },
          track_index: { type: "integer", minimum: 0, maximum: 511, description: "Timeline track index; required with clip_index when project_item_id is omitted." },
          clip_index: { type: "integer", minimum: 0, maximum: 511, description: "Timeline clip index; required with track_index when project_item_id is omitted." },
          project_item_id: { type: "string", minLength: 1, maxLength: 512, description: "Exact source project item ID; excludes timeline coordinates and expected_sequence_guid. No selection or name fallback." },
          expected_project_guid: { type: "string", minLength: 1, maxLength: 512, description: "Optional active-project identity from prior inspection; mismatches are rejected." },
          component_index: { type: "integer", minimum: 0, maximum: 511, description: "Component index within the chosen source or timeline chain." },
          expected_sequence_guid: { type: "string", minLength: 1, maxLength: 512, description: "Optional active-sequence GUID from a prior catalog inspection. A changed sequence is rejected." },
          expected_component_id: { type: "string", minLength: 1, maxLength: 512, description: "Optional component match or display name returned by a prior catalog inspection. A changed component is rejected." },
        },
        required: ["media_type", "component_index"],
        oneOf: [
          { required: ["project_item_id"], not: { anyOf: [{ required: ["track_index"] }, { required: ["clip_index"] }, { required: ["expected_sequence_guid"] }] } },
          { required: ["track_index", "clip_index"], not: { required: ["project_item_id"] } },
        ],
      },
      operationalCapability: {
        backend: "UXP" as const,
        backends: ["uxp" as const],
        minimumPremiereVersion: "25.6",
        verificationBoundary: "structured_uxp_readback" as const,
        hostVerificationRequired: true,
        notes: ["Requires an authenticated UXP bridge whose capability handshake advertises parameters.catalog.inspect.", "Contract tests do not prove a licensed Premiere host, parameter values, editability, rendered output, playback, persistence, or Undo behavior."],
      },
      handler: async (args: EffectParameterCatalogArgs) => invoke(bridge, {
        mediaType: args.media_type,
        ...(args.track_index === undefined ? {} : { trackIndex: args.track_index }),
        ...(args.clip_index === undefined ? {} : { clipIndex: args.clip_index }),
        ...(args.project_item_id === undefined ? {} : { projectItemId: args.project_item_id }),
        ...(args.expected_project_guid === undefined ? {} : { expectedProjectGuid: args.expected_project_guid }),
        componentIndex: args.component_index,
        ...(args.expected_sequence_guid === undefined ? {} : { expectedSequenceGuid: args.expected_sequence_guid }),
        ...(args.expected_component_id === undefined ? {} : { expectedComponentId: args.expected_component_id }),
      }),
    },
  };
}

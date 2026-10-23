(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.PremiereMcpEffectParameterCatalogWorkflows = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  // A caller can already inspect a known parameter through the automation
  // workflow. This catalog fills the discovery gap without returning parameter
  // values, which may be arbitrary PointF/Color objects or user content.
  function createEffectParameterCatalogWorkflowDefinitions(deps) {
    const ppro = deps.ppro;
    const sourceClip = createSourceEffectTargetResolver(ppro);
    const MAX_TRACK_ITEMS = 512;
    const MAX_COMPONENTS = 512;
    const MAX_PARAMETERS = 64;
    const definitions = {
      "parameters.catalog.inspect": {
        readOnly: true,
        targetCapabilityProbe: true,
        minHostVersion: "25.6.0",
        probe: canInspectParameterCatalog,
        handler: inspectParameterCatalog
      }
    };

    function canInspectParameterCatalog() {
      return !!(ppro && ppro.Project && typeof ppro.Project.getActiveProject === "function");
    }

    async function inspectParameterCatalog(args) {
      assertOnlyKeys(args, ["mediaType", "trackIndex", "clipIndex", "projectItemId", "expectedProjectGuid", "componentIndex", "expectedSequenceGuid", "expectedComponentId"]);
      const input = coordinateInput(args);
      const first = await catalogSnapshot(input);
      assertExpected(input.expectedProjectGuid, first.projectGuid, "UXP_STALE_PARAMETER_CATALOG", "Active project GUID");
      assertExpected(input.expectedSequenceGuid, first.sequenceGuid, "UXP_STALE_PARAMETER_CATALOG", "Active sequence GUID");
      assertExpected(input.expectedComponentId, first.component.id, "UXP_STALE_PARAMETER_CATALOG", "Component identity");
      const second = await catalogSnapshot(input);
      if (!sameSnapshot(first, second)) {
        throw commandError("UXP_STALE_PARAMETER_CATALOG", "The project, active sequence, component, or parameter descriptors changed while being inspected; retry the catalog inspection");
      }
      return {
        ...(input.projectItemId ? { targetKind: "source", projectItemId: input.projectItemId } : {}),
        projectGuid: first.projectGuid,
        sequenceGuid: first.sequenceGuid,
        mediaType: input.mediaType,
        trackIndex: input.trackIndex,
        clipIndex: input.clipIndex,
        componentIndex: input.componentIndex,
        component: first.component,
        parameterCount: first.parameters.length,
        parameters: first.parameters,
        verificationBoundary: "bounded_effect_parameter_catalog_double_readback"
      };
    }

    function coordinateInput(args) {
      const source = args.projectItemId != null;
      if (source && (args.trackIndex != null || args.clipIndex != null || args.expectedSequenceGuid != null)) {
        throw commandError("UXP_INVALID_ARGUMENT", "Source projectItemId cannot be combined with timeline coordinates or a sequence precondition");
      }
      if (source && (typeof args.projectItemId !== "string" || !args.projectItemId || args.projectItemId.length > 512 || args.projectItemId.includes("\u0000"))) {
        throw commandError("UXP_INVALID_ARGUMENT", "projectItemId must be a bounded non-empty ID");
      }
      return {
        projectItemId: source ? boundedText(args.projectItemId, "projectItemId", 512, false) : null,
        expectedProjectGuid: args.expectedProjectGuid == null ? null : requestedGuid(args.expectedProjectGuid, "expectedProjectGuid"),
        mediaType: enumValue(args.mediaType, "mediaType", ["video", "audio"]),
        trackIndex: source ? null : boundedIndex(args.trackIndex, "trackIndex"),
        clipIndex: source ? null : boundedIndex(args.clipIndex, "clipIndex"),
        componentIndex: boundedIndex(args.componentIndex, "componentIndex"),
        expectedSequenceGuid: args.expectedSequenceGuid == null ? null : requestedGuid(args.expectedSequenceGuid, "expectedSequenceGuid"),
        expectedComponentId: args.expectedComponentId == null ? null : boundedText(args.expectedComponentId, "expectedComponentId", 512, false)
      };
    }

    async function catalogSnapshot(input) {
      const project = await activeProject();
      const projectGuid = requiredGuid(project.guid, "active project GUID");
      assertExpected(input.expectedProjectGuid, projectGuid, "UXP_STALE_PARAMETER_CATALOG", "Active project GUID");
      let sequenceGuid = null, item;
      if (input.projectItemId) {
        item = await sourceClip(project, input.projectItemId, projectGuid);
      } else {
        if (typeof project.getActiveSequence !== "function") {
          throw commandError("UXP_COMMAND_UNAVAILABLE", "Premiere does not expose the active sequence for parameter catalog inspection");
        }
        const sequence = await project.getActiveSequence();
        if (!sequence) throw commandError("UXP_NO_ACTIVE_SEQUENCE", "No active sequence");
        sequenceGuid = requiredGuid(sequence.guid, "active sequence GUID");
        item = await trackItemAt(sequence, input.mediaType, input.trackIndex, input.clipIndex);
      }
      const component = await componentAt(item, input.componentIndex, input.projectItemId ? input.mediaType : null);
      const componentSnapshot = await componentDescriptor(component);
      const parameterCount = boundedCount(component.getParamCount && component.getParamCount(), "component parameter count", MAX_PARAMETERS);
      if (typeof component.getParam !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "Premiere does not expose component parameter lookup");
      }
      const parameters = [];
      for (let index = 0; index < parameterCount; index += 1) {
        parameters.push(await parameterDescriptor(component.getParam(index), index));
      }
      return { projectGuid, sequenceGuid, component: componentSnapshot, parameters };
    }

    async function activeProject() {
      const project = await ppro.Project.getActiveProject();
      if (!project) throw commandError("UXP_NO_ACTIVE_PROJECT", "No active project");
      return project;
    }

    async function trackItemAt(sequence, mediaType, trackIndex, clipIndex) {
      const countMethod = mediaType === "video" ? "getVideoTrackCount" : "getAudioTrackCount";
      const trackMethod = mediaType === "video" ? "getVideoTrack" : "getAudioTrack";
      if (typeof sequence[countMethod] !== "function" || typeof sequence[trackMethod] !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "Premiere does not expose documented " + mediaType + " track access");
      }
      const count = boundedCount(await sequence[countMethod](), mediaType + " track count", MAX_TRACK_ITEMS);
      if (trackIndex >= count) throw commandError("UXP_TARGET_NOT_FOUND", "trackIndex is out of range");
      const track = await sequence[trackMethod](trackIndex);
      const itemType = ppro.Constants && ppro.Constants.TrackItemType;
      if (!track || !itemType || itemType.CLIP == null || typeof track.getTrackItems !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "Premiere does not expose documented clip-item access on the requested track");
      }
      const items = Array.from(await track.getTrackItems(itemType.CLIP, false) || []);
      if (items.length > MAX_TRACK_ITEMS) {
        throw commandError("UXP_TARGET_TOO_LARGE", "The requested track has more than " + MAX_TRACK_ITEMS + " clip items");
      }
      if (!items[clipIndex]) throw commandError("UXP_TARGET_NOT_FOUND", "clipIndex is out of range");
      return items[clipIndex];
    }

    async function componentAt(item, componentIndex, sourceMediaType) {
      if (!item || typeof item.getComponentChain !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "The requested clip does not expose a documented component chain");
      }
      let chain;
      if (sourceMediaType) {
        const types = ppro.Constants && ppro.Constants.MediaType;
        const nativeType = types && types[sourceMediaType.toUpperCase()];
        if (nativeType == null) throw commandError("UXP_COMMAND_UNAVAILABLE", "Native source media-type constants are unavailable");
        // The pinned 26.3 declaration says string; current Adobe docs say chain|null.
        // Validate the actual object and never parse or invent a chain from a string.
        chain = await item.getComponentChain(nativeType);
      } else chain = await item.getComponentChain();
      if (!chain || typeof chain.getComponentCount !== "function" || typeof chain.getComponentAtIndex !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "Premiere did not return a documented component chain");
      }
      const count = boundedCount(chain.getComponentCount(), "component count", MAX_COMPONENTS);
      if (componentIndex >= count) throw commandError("UXP_TARGET_NOT_FOUND", "componentIndex is out of range");
      const component = chain.getComponentAtIndex(componentIndex);
      if (!component) throw commandError("UXP_TARGET_NOT_FOUND", "Premiere did not return the requested component");
      return component;
    }

    async function componentDescriptor(component) {
      if (typeof component.getMatchName !== "function" || typeof component.getDisplayName !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "Premiere does not expose documented component identity getters");
      }
      const matchName = boundedText(await component.getMatchName(), "component match name", 512, true);
      const displayName = boundedText(await component.getDisplayName(), "component display name", 512, true);
      const id = matchName || displayName;
      if (!id) throw commandError("UXP_VERIFICATION_FAILED", "Premiere returned a component without a match or display name");
      return { id, matchName, displayName };
    }

    async function parameterDescriptor(parameter, index) {
      if (!parameter || typeof parameter.displayName !== "string" || typeof parameter.areKeyframesSupported !== "function" || typeof parameter.isTimeVarying !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "Premiere did not expose documented parameter descriptor access");
      }
      const displayName = boundedText(parameter.displayName, "parameter display name", 512, true);
      const keyframesSupported = await parameter.areKeyframesSupported();
      const timeVarying = parameter.isTimeVarying();
      if (typeof keyframesSupported !== "boolean" || typeof timeVarying !== "boolean") {
        throw commandError("UXP_VERIFICATION_FAILED", "Premiere returned an invalid parameter animation descriptor");
      }
      return { index, displayName, keyframesSupported, timeVarying };
    }

    function sameSnapshot(left, right) {
      if (!left || !right || left.projectGuid !== right.projectGuid || left.sequenceGuid !== right.sequenceGuid ||
        left.component.id !== right.component.id || left.component.matchName !== right.component.matchName ||
        left.component.displayName !== right.component.displayName || left.parameters.length !== right.parameters.length) return false;
      return left.parameters.every(function (parameter, index) {
        const other = right.parameters[index];
        return other && parameter.index === other.index && parameter.displayName === other.displayName &&
          parameter.keyframesSupported === other.keyframesSupported && parameter.timeVarying === other.timeVarying;
      });
    }

    return definitions;
  }

  function createSourceEffectTargetResolver(ppro) {
    async function itemId(item) {
      let identity = item;
      if (identity && typeof identity.getId !== "function" && ppro.ProjectItem && typeof ppro.ProjectItem.cast === "function") {
        try { identity = ppro.ProjectItem.cast(item); } catch (_) { return null; }
      }
      if (!identity || typeof identity.getId !== "function") return null;
      // Roots/bins may not expose readable IDs. Traverse them, but never accept
      // an unreadable ID as the requested source or as post-cast identity proof.
      try {
        const value = await identity.getId();
        return typeof value === "string" && value.length > 0 && value.length <= 512 && !value.includes("\u0000") ? value : null;
      } catch (_) { return null; }
    }

    async function sourceClip(project, wanted, projectGuid) {
      if (typeof project.getRootItem !== "function" || !ppro.ClipProjectItem || typeof ppro.ClipProjectItem.cast !== "function") {
        throw commandError("UXP_COMMAND_UNAVAILABLE", "Source clip lookup APIs are unavailable");
      }
      const pending = [await project.getRootItem()], visited = new Set();
      while (pending.length) {
        const candidate = pending.shift();
        if (!candidate || visited.has(candidate)) continue;
        visited.add(candidate);
        if (visited.size > 4096) throw commandError("UXP_TARGET_TOO_LARGE", "Source lookup exceeded 4096 items");
        if (await itemId(candidate) === wanted) {
          let clip;
          try { clip = ppro.ClipProjectItem.cast(candidate); } catch (_) {}
          if (!clip || typeof clip.getProject !== "function") throw commandError("UXP_TARGET_UNSUPPORTED", "The requested source is not a clip with project ownership access");
          const owner = await clip.getProject();
          if (!owner || requiredGuid(owner.guid, "source owner GUID") !== projectGuid || await itemId(candidate) !== wanted || await itemId(clip) !== wanted) {
            throw commandError("UXP_STALE_PARAMETER_CATALOG", "Source identity or owning project changed");
          }
          return clip;
        }
        let folder = candidate;
        if (typeof folder.getItems !== "function" && ppro.FolderItem && typeof ppro.FolderItem.cast === "function") {
          try { folder = ppro.FolderItem.cast(candidate); } catch (_) { folder = null; }
        }
        if (!folder || typeof folder.getItems !== "function") continue;
        const children = await folder.getItems();
        if (!Array.isArray(children)) throw commandError("UXP_VERIFICATION_FAILED", "Invalid project folder collection");
        if (pending.length + visited.size + children.length > 4096) throw commandError("UXP_TARGET_TOO_LARGE", "Source lookup exceeded 4096 items");
        pending.push(...children);
      }
      throw commandError("UXP_TARGET_NOT_FOUND", "Source project item ID was not found in the active project");
    }

    return sourceClip;
  }

  function assertOnlyKeys(value, allowed) {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw commandError("UXP_INVALID_ARGUMENT", "arguments must be an object");
    const unknown = Object.keys(value).find(function (key) { return !allowed.includes(key); });
    if (unknown) throw commandError("UXP_INVALID_ARGUMENT", "Unknown argument: " + unknown);
  }

  function enumValue(value, name, values) {
    if (typeof value !== "string" || !values.includes(value)) throw commandError("UXP_INVALID_ARGUMENT", name + " must be " + values.join(" or "));
    return value;
  }

  function boundedIndex(value, name) {
    if (!Number.isInteger(value) || value < 0 || value > 511) throw commandError("UXP_INVALID_ARGUMENT", name + " must be an integer from 0 through 511");
    return value;
  }

  function boundedCount(value, name, maximum) {
    const count = Number(value);
    if (!Number.isInteger(count) || count < 0) throw commandError("UXP_VERIFICATION_FAILED", "Premiere returned an invalid " + name);
    if (count > maximum) throw commandError("UXP_TARGET_TOO_LARGE", "The " + name + " exceeds the " + maximum + " entry limit");
    return count;
  }

  function requiredGuid(value, name) {
    const guid = boundedGuid(value, name);
    if (!guid) throw commandError("UXP_VERIFICATION_FAILED", name + " must be a bounded non-empty GUID");
    return guid;
  }

  function boundedGuid(value, name) {
    let text = "";
    try { text = String(value && typeof value.toString === "function" ? value.toString() : value || ""); } catch (_) {}
    if (!text || text.length > 512) throw commandError("UXP_VERIFICATION_FAILED", name + " must be a bounded non-empty GUID");
    return text;
  }

  function requestedGuid(value, name) {
    let text = "";
    try { text = String(value && typeof value.toString === "function" ? value.toString() : value || ""); } catch (_) {}
    if (!text || text.length > 512) throw commandError("UXP_INVALID_ARGUMENT", name + " must be a bounded non-empty GUID");
    return text;
  }

  function boundedText(value, name, maximum, allowEmpty) {
    if (typeof value !== "string" || value.length > maximum || (!allowEmpty && !value)) {
      throw commandError("UXP_VERIFICATION_FAILED", name + " must be a bounded " + (allowEmpty ? "string" : "non-empty string"));
    }
    return value;
  }

  function assertExpected(expected, actual, code, name) {
    if (expected != null && expected !== actual) throw commandError(code, name + " differs from the inspected value; retry the catalog inspection");
  }

  function commandError(code, message) {
    const error = new Error(message);
    error.code = code;
    return error;
  }

  return { createEffectParameterCatalogWorkflowDefinitions, createSourceEffectTargetResolver };
});

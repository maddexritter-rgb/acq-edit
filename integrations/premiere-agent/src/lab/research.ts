import type { ToolOperationalOverride } from "../tool-capability-report.js";
import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import { buildToolScript } from "../bridge/script-builder.js";
export function getLabResearchTools(options: BridgeOptions) {
  return {
    lab_probe_qe_surface: {
      operationalCapability: {
        backend: "CEP/ExtendScript + QE",
        backends: ["cep", "extendscript", "qe"],
        status: "experimental",
        minimumPremiereVersion: "26.3.0",
        hostVerificationRequired: true,
        notes: ["Isolated research; reflection is not method behavior proof."],
      } satisfies ToolOperationalOverride,
      description:
        "Experimental QE research: reflect method names on a disposable project, sequence or first video track. Does not invoke the reflected methods or establish that they work. Requires a lab mutation guard because QE is enabled.",
      parameters: {
        type: "object",
        additionalProperties: false,
        properties: {
          surface: {
            type: "string",
            enum: ["project", "sequence", "video_track"],
            description:
              "Bounded QE object whose method names should be inspected.",
          },
        },
        required: ["surface"],
      },
      handler: async (args: { surface: string }) => {
        if (!["project", "sequence", "video_track"].includes(args.surface))
          return { success: false, error: "Unsupported QE surface" };
        const expression =
          args.surface === "project"
            ? "qe.project"
            : args.surface === "sequence"
              ? "qe.project.getActiveSequence()"
              : "qe.project.getActiveSequence().getVideoTrackAt(0)";
        return sendCommand(
          buildToolScript(`
    app.enableQE();
    var target=${expression};
    if(!target||!target.reflect)return __error('QE reflection is unavailable');
    var methods=[],properties=[],reflection=target.reflect;
    for(var i=0;i<reflection.methods.length&&i<500;i++)methods.push(String(reflection.methods[i].name));
    for(var j=0;j<reflection.properties.length&&j<500;j++)properties.push(String(reflection.properties[j].name));
    return __result({surface:'${args.surface}',methods:methods,properties:properties,verification:'reflection_only',methodBehavior:'not_tested'});
   `),
          options,
        );
      },
    },
  };
}

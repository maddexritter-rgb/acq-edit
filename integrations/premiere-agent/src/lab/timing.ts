import type { ToolOperationalOverride } from "../tool-capability-report.js";
import { sendCommand, type BridgeOptions } from "../bridge/file-bridge.js";
import {
  buildToolScript,
  escapeForExtendScript,
} from "../bridge/script-builder.js";
const TICKS_PER_SECOND = 254016000000n;
export function frameToTicks(
  frame: string,
  numerator: number,
  denominator: number,
): string {
  if (
    !/^\d+$/.test(frame) ||
    !Number.isSafeInteger(numerator) ||
    !Number.isSafeInteger(denominator) ||
    numerator <= 0 ||
    denominator <= 0
  )
    throw new Error("Invalid rational frame position");
  const ticks = BigInt(frame) * TICKS_PER_SECOND * BigInt(denominator);
  if (ticks % BigInt(numerator))
    throw new Error("Frame position is not representable in Premiere ticks");
  return String(ticks / BigInt(numerator));
}
export function getLabTimingTools(options: BridgeOptions) {
  return {
    lab_move_clip_ticks: {
      operationalCapability: {
        backend: "CEP/ExtendScript",
        backends: ["cep", "extendscript"],
        status: "experimental",
        minimumPremiereVersion: "26.3.0",
        hostVerificationRequired: true,
        notes: [
          "Exact tick implementation; live-host behavior and persistence remain unverified.",
        ],
      } satisfies ToolOperationalOverride,
      description:
        "Move one timeline item on its current track using exact decimal tick strings. Requires explicit old timeline/source ranges and ticks per frame; refuses collisions across the whole swept range, locked tracks, retiming and non-frame-aligned spans. No implicit linked-item movement, rollback or rendered claim.",
      parameters: {
        type: "object",
        additionalProperties: false,
        properties: {
          node_id: { type: "string", minLength: 1, maxLength: 512 },
          start_ticks: { type: "string", pattern: "^[0-9]+$" },
          end_ticks: { type: "string", pattern: "^[0-9]+$" },
          in_ticks: { type: "string", pattern: "^[0-9]+$" },
          out_ticks: { type: "string", pattern: "^[0-9]+$" },
          new_start_ticks: { type: "string", pattern: "^[0-9]+$" },
          ticks_per_frame: { type: "string", pattern: "^[0-9]+$" },
        },
        required: [
          "node_id",
          "start_ticks",
          "end_ticks",
          "in_ticks",
          "out_ticks",
          "new_start_ticks",
          "ticks_per_frame",
        ],
      },
      handler: async (args: Record<string, string>) => {
        let values: Record<string, bigint> = {};
        try {
          for (const key of [
            "start_ticks",
            "end_ticks",
            "in_ticks",
            "out_ticks",
            "new_start_ticks",
            "ticks_per_frame",
          ]) {
            if (!/^\d{1,19}$/.test(args[key]))
              throw new Error("Invalid tick string");
            values[key] = BigInt(args[key]);
            if (values[key] > 9223372036854775807n)
              throw new Error("Tick range exceeds signed 64-bit time");
          }
          const v = values,
            span = v.end_ticks - v.start_ticks;
          if (
            v.ticks_per_frame <= 0n ||
            span <= 0n ||
            v.out_ticks - v.in_ticks !== span
          )
            throw new Error(
              "Only positive normal-speed source spans are supported",
            );
          for (const key of ["start_ticks", "end_ticks", "new_start_ticks"])
            if (v[key] % v.ticks_per_frame)
              throw new Error("Timeline positions must be frame-aligned");
          values.new_end_ticks = v.new_start_ticks + span;
          if (values.new_end_ticks > 9223372036854775807n)
            throw new Error("End exceeds signed 64-bit time");
        } catch (error) {
          return { success: false, error: String(error) };
        }
        const q = (s: string) => '"' + escapeForExtendScript(s) + '"';
        const v = Object.fromEntries(
          Object.entries(values).map(([k, n]) => [k, String(n)]),
        );
        return sendCommand(
          buildToolScript(`
          function cmp(a,b){a=String(a);b=String(b);if(a.length!==b.length)return a.length>b.length?1:-1;return a===b?0:a>b?1:-1;}
          var f=__findClip(${q(args.node_id)}),s=app.project.activeSequence;
          if(!f||!s)return __error('Clip or sequence unavailable');
          var c=f.clip,track=f.trackType==='video'?s.videoTracks[f.trackIndex]:s.audioTracks[f.trackIndex];
          if(String(s.timebase)!==${q(v.ticks_per_frame)})return __error('Frame rate changed');
          if(__isTrackLocked(track)||c.getSpeed()!==1)return __error('Locked track or retimed clip');
          if(String(c.start.ticks)!==${q(v.start_ticks)}||String(c.end.ticks)!==${q(v.end_ticks)}||String(c.inPoint.ticks)!==${q(v.in_ticks)}||String(c.outPoint.ticks)!==${q(v.out_ticks)})return __error('Clip range precondition changed');
          var sweepStart=cmp(${q(v.start_ticks)},${q(v.new_start_ticks)})<0?${q(v.start_ticks)}:${q(v.new_start_ticks)},sweepEnd=cmp(${q(v.end_ticks)},${q(v.new_end_ticks)})>0?${q(v.end_ticks)}:${q(v.new_end_ticks)};
          for(var i=0;i<track.clips.numItems;i++){var other=track.clips[i];if(String(other.nodeId)===${q(args.node_id)})continue;if(cmp(other.start.ticks,sweepEnd)<0&&cmp(other.end.ticks,sweepStart)>0)return __error('Move range crosses another item');}
          if(cmp(${q(v.new_start_ticks)},${q(v.start_ticks)})>0){c.end=${q(v.new_end_ticks)};c.start=${q(v.new_start_ticks)};}else{c.start=${q(v.new_start_ticks)};c.end=${q(v.new_end_ticks)};}
          f=__findClip(${q(args.node_id)});if(!f)return __error('Item disappeared after write; inspect fixture');c=f.clip;
          var observed={start:String(c.start.ticks),end:String(c.end.ticks),inPoint:String(c.inPoint.ticks),outPoint:String(c.outPoint.ticks)};
          if(observed.start!==${q(v.new_start_ticks)}||observed.end!==${q(v.new_end_ticks)}||observed.inPoint!==${q(v.in_ticks)}||observed.outPoint!==${q(v.out_ticks)})return __error('Exact move postcondition failed; partial execution possible, no rollback claimed');
          return __result({observed:observed,verification:'exact_item_timing_only',persistence:'not_run',rendered:'not_run',linkedItems:'not_moved_by_this_tool'});
        `),
          options,
        );
      },
    },
  };
}

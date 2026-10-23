#!/bin/bash
# LEGACY 2026-06-08 — kept only because shortform/pipeline.py + qa_detect_speaker.py still import it. NEW CODE: use qa_reframe_v2.py --preset <name> (Y-LOCK + xcenter box). This script is NOT the canonical face-tracker.
# horizontal-to-vertical — CANONICAL 16:9 -> 9:16 reframe + face tracking (locked 2026-06-04).
# THE single reframe+facetrack entry point for the workflow.
#   per-frame multi-cascade Haar detect -> box-car smooth 51 -> crop's X follows the nose
#   to a fixed center (540 in 1080-ref), Y locked at the eye line; zoom 1.15 (86% crop).
# Reframe + facetrack ONLY -- captions / color grade / music are SEPARATE workflow steps.
#
# Usage: reframe.sh INPUT [OUTPUT] [--res auto|1080|4k] [--zoom 1.15]
#   INPUT   horizontal clip (any res, single angle)
#   OUTPUT  defaults to <input>_9x16.mp4
#   --res   auto (default): 4K source -> 2160x3840, else 1080x1920
#   --zoom  1.15 locked default (= 86% crop height)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IN="${1:?need input video}"; shift || true
OUT=""; RES="auto"; ZOOM="1.15"; NOSEY="719"; LOCKX=""; SMOOTH="51"; EYEARGS=""   # nose Y in the 1080x1920 ref (lower value = subject higher)
while [ $# -gt 0 ]; do
  case "$1" in
    --res)    RES="$2"; shift 2;;
    --zoom)   ZOOM="$2"; shift 2;;
    --nose-y) NOSEY="$2"; shift 2;;
    --smooth) SMOOTH="$2"; shift 2;;
    --lock-x) LOCKX="--lock-x"; shift 1;;
    --eye-y-src) EYEARGS="$EYEARGS --eye-y-src $2"; shift 2;;
    --eye-y-out) EYEARGS="$EYEARGS --eye-y-out $2"; shift 2;;
    --*) echo "unknown flag: $1" >&2; exit 1;;
    *) OUT="$1"; shift;;
  esac
done
[ -z "$OUT" ] && OUT="${IN%.*}_9x16.mp4"

# Source height -> choose output resolution
SH=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$IN")
case "$RES" in
  4k)   OW=2160; OH=3840;;
  1080) OW=1080; OH=1920;;
  auto) if [ "${SH:-0}" -ge 2160 ]; then OW=2160; OH=3840; else OW=1080; OH=1920; fi;;
  *) echo "bad --res: $RES (use auto|1080|4k)" >&2; exit 1;;
esac

# Multi-angle warning: single-median X loses the subject on hard angle cuts
NCUTS=$(ffmpeg -i "$IN" -vf "select='gt(scene,0.3)',showinfo" -an -f null - 2>&1 \
  | grep -oE "pts_time:[0-9.]+" | sed 's/pts_time://' | awk '$1>0.5' | wc -l | tr -d ' ' || true)
NCUTS=${NCUTS:-0}
[ "$NCUTS" -gt 0 ] && echo "WARN: $NCUTS hard cut(s) detected -- looks multi-angle. Single-median X-track may lose the subject on angle switches; handle per-segment (see SKILL.md multi-angle note)." >&2

WORK="$(mktemp -d)"
echo "> [1/2] dense face detect (per-frame multi-cascade Haar)"
python3 "$DIR/detect_face_dense.py" "$IN" "$WORK/face.json"
echo "> [2/2] reframe ${OW}x${OH}  zoom $ZOOM  smooth 51  (X->nose@540,${NOSEY}  Y-locked)"
python3 "$DIR/reframe_h2v.py" --video "$IN" --face-json "$WORK/face.json" --output "$OUT" \
  --out-w "$OW" --out-h "$OH" --zoom "$ZOOM" --smooth "$SMOOTH" --nose-x-1080 540 --nose-y-1080 "$NOSEY" $LOCKX $EYEARGS
echo "OK $OUT"
echo "   verify framing by EYE (extract frames) -- the audit centering flag false-negatives on weak detection."

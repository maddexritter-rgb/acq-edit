#!/usr/bin/env bash
# make_matte.sh — subject alpha matte for headline-behind-subject, via MatAnyone.
#
#   ./make_matte.sh <reframed_9x16.mp4> <outdir>
#
# Produces <outdir>/mat_frames_pha.mp4 — feed it to render_ad.py as "matte_video".
#
# MatAnyone needs a first-frame mask. On a dark set we generate that automatically
# with a luma key; on a lit set, hand it a mask you made yourself (arg 3).
#
# NOTE ON LICENSING: MatAnyone ships under S-Lab License 1.0, which permits
# non-commercial use only. Using it on paid creative is a call for whoever owns
# licensing at your org — not a default. Commercially-clean alternatives if you
# need one: Apple Vision person segmentation (built into macOS), BiRefNet (MIT),
# SAM 2 (Apache-2.0). The renderer's built-in luma key needs no third-party code
# at all and is the better choice on a black set.
set -euo pipefail

SRC="${1:?usage: make_matte.sh <reframed.mp4> <outdir> [first_frame_mask.png]}"
OUT="${2:?}"
MASK="${3:-}"

ROOT="${MATANYONE_ROOT:-$HOME/ai ads/_TOOLS/matanyone}"
PY="${MATANYONE_PY:-$HOME/ai ads/_TOOLS/matte-env/bin/python}"
WORK="$(mktemp -d)"

[ -x "$PY" ] || { echo "MatAnyone venv not found at $PY"; exit 1; }

# torchvision >= 0.28 dropped io.read_video, so feed MatAnyone a frame FOLDER.
# 720p keeps the tensor in memory; the alpha is upscaled at composite time.
mkdir -p "$WORK/frames"
ffmpeg -nostdin -v error -y -i "$SRC" -vf "scale=720:1280" "$WORK/frames/f%05d.png"

if [ -z "$MASK" ]; then
  MASK="$WORK/seed.png"
  ffmpeg -nostdin -v error -y -i "$SRC" -frames:v 1 "$WORK/f0.png"
  python3 - "$WORK/f0.png" "$MASK" <<'PY'
import sys
from PIL import Image, ImageFilter
im = Image.open(sys.argv[1]).convert("L")
m = (im.point(lambda v: 255 if v > 26 else 0)
       .filter(ImageFilter.MaxFilter(7))
       .filter(ImageFilter.MinFilter(5)))
m.resize((720, 1280), Image.NEAREST).save(sys.argv[2])
PY
  echo "  seed mask: luma key (dark set)"
else
  python3 -c "
from PIL import Image; import sys
Image.open('$MASK').convert('L').resize((720,1280), Image.NEAREST).save('$WORK/seed.png')"
  MASK="$WORK/seed.png"
  echo "  seed mask: supplied"
fi

mkdir -p "$OUT"
( cd "$ROOT" && PYTORCH_ENABLE_MPS_FALLBACK=1 \
    "$PY" inference_matanyone.py -i "$WORK/frames" -m "$MASK" -o "$OUT" >/dev/null 2>&1 )

PHA="$OUT/frames_pha.mp4"
[ -f "$PHA" ] || PHA="$(find "$OUT" -name '*_pha.mp4' | head -1)"
echo "  alpha -> $PHA"
rm -rf "$WORK"

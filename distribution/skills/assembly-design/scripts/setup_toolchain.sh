#!/usr/bin/env bash
# Install the script-cut toolchain to a PERSISTENT location (the working build lives in /tmp and
# vanishes on reboot). Idempotent: re-running skips anything already present.
#
# Installs:
#   - micromamba                -> $ROOT/bin/micromamba
#   - MFA conda env + models    -> $ROOT/mfa_env   (montreal-forced-aligner + english_us_arpa acoustic+dict)
#   - python venv               -> $ROOT/venv      (numpy, num2words, soundfile, matplotlib)
#
# After running, export these (the engine reads them; defaults point at /tmp):
#   export MFA_MAMBA="$ROOT/bin/micromamba"
#   export MFA_ENV="$ROOT/mfa_env"
#   run scripts with: "$ROOT/venv/bin/python"
set -euo pipefail
ROOT="${SCRIPT_CUT_ROOT:-$HOME/.local/share/script-cut}"
mkdir -p "$ROOT/bin"
echo "==> script-cut toolchain root: $ROOT"

# 1) micromamba ---------------------------------------------------------------
if [ ! -x "$ROOT/bin/micromamba" ]; then
  echo "==> installing micromamba"
  case "$(uname -m)" in
    arm64|aarch64) MARCH="osx-arm64" ;;
    *)             MARCH="osx-64" ;;
  esac
  curl -Ls "https://micro.mamba.pm/api/micromamba/${MARCH}/latest" | tar -xvj -C "$ROOT" bin/micromamba
fi
MAMBA="$ROOT/bin/micromamba"

# 2) MFA conda env + english_us_arpa models -----------------------------------
if [ ! -d "$ROOT/mfa_env" ]; then
  echo "==> creating MFA env (montreal-forced-aligner)"
  "$MAMBA" create -y -p "$ROOT/mfa_env" -c conda-forge montreal-forced-aligner
fi
echo "==> ensuring english_us_arpa acoustic + dictionary models"
"$MAMBA" run -p "$ROOT/mfa_env" mfa model download acoustic   english_us_arpa || true
"$MAMBA" run -p "$ROOT/mfa_env" mfa model download dictionary english_us_arpa || true

# 3) python venv (engine + QC deps) -------------------------------------------
if [ ! -d "$ROOT/venv" ]; then
  echo "==> creating python venv"
  python3 -m venv --system-site-packages "$ROOT/venv"
fi
"$ROOT/venv/bin/pip" install -q --upgrade pip
"$ROOT/venv/bin/pip" install -q numpy num2words soundfile matplotlib

command -v ffmpeg >/dev/null 2>&1 || echo "!! ffmpeg not found on PATH — install it (brew install ffmpeg)"

cat <<EOF

==> done. add to your shell / pass to the engine:
    export MFA_MAMBA="$ROOT/bin/micromamba"
    export MFA_ENV="$ROOT/mfa_env"
    PY="$ROOT/venv/bin/python"

    \$PY __ACQ_SKILLS__/assembly-design/scripts/script_cut.py --source ... --transcript ... --spec ... --out ...
EOF

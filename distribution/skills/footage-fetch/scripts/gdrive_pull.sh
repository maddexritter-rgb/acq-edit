#!/bin/bash
# Delegate Drive intake to the toolkit's existing project and durable transfer owner.
set -euo pipefail
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo 'Usage: gdrive_pull.sh PROJECT_ID DRIVE_URL [RCLONE_REMOTE]' >&2
  exit 2
fi
PROJECT_ID="$1"
URL="$2"
TOOLKIT="__ACQ_TOOLKIT__"
case "$URL" in
  https://drive.google.com/drive/folders/*) COMMAND=drive-folder ;;
  https://drive.google.com/file/d/*|https://drive.google.com/open\?*) COMMAND=drive ;;
  *) echo 'Provide an explicit Google Drive file or folder URL; bare IDs are ambiguous.' >&2; exit 2 ;;
esac
ARGS=("$TOOLKIT/dist/cli.js" "$COMMAND" "$PROJECT_ID" "$URL")
if [[ $# -eq 3 ]]; then ARGS+=("$3"); fi
exec node "${ARGS[@]}"

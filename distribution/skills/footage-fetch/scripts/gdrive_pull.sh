#!/bin/bash
# gdrive_pull.sh <client> <drive-url-or-id> [slug]
# Download ONE Google Drive folder OR single file into its OWN scaffolded project, verified.
# Folder link  -> whole folder into one project.   File link -> that file into its own project.
# Run detached for big pulls:  nohup bash gdrive_pull.sh ... >/tmp/x.log 2>&1 & disown
set -u

CLIENT="${1:?usage: gdrive_pull.sh <client> <drive-url-or-id> [slug]}"
URL="${2:?need a drive url or id}"
SLUG="${3:-}"
NP="$HOME/Downloads/cluade/scripts/new_project.sh"
MIN_FREE_G=15          # never start a download with less than this free

# --- parse ID + type from the URL (or bare ID) ---
if [[ "$URL" == *"/folders/"* ]]; then
  TYPE=folder; ID=$(printf '%s' "$URL" | sed -E 's#.*/folders/([^/?]+).*#\1#')
elif [[ "$URL" == *"/file/d/"* ]]; then
  TYPE=file;   ID=$(printf '%s' "$URL" | sed -E 's#.*/file/d/([^/?]+).*#\1#')
elif [[ "$URL" == *"id="* ]]; then
  TYPE=file;   ID=$(printf '%s' "$URL" | sed -E 's#.*[?&]id=([^&]+).*#\1#')
else
  ID="$URL"; TYPE=file        # bare ID: assume file (copyid is the universal fetch)
fi
echo "[gdrive_pull] client=$CLIENT type=$TYPE id=$ID"

# --- disk gate ---
FREE_G=$(df -g "$HOME/Downloads" | awk 'NR==2{print $4}')
echo "[gdrive_pull] free=${FREE_G}G"
if [[ "$TYPE" == folder ]]; then
  SIZE_B=$(rclone size gdrive: --drive-root-folder-id="$ID" --json 2>/dev/null | sed -E 's/.*"bytes":([0-9]+).*/\1/')
  NEED_G=$(( (${SIZE_B:-0} / 1073741824) + 5 ))
  echo "[gdrive_pull] folder ~${NEED_G}G needed"
  if [ "$NEED_G" -gt 5 ] && [ "${FREE_G:-0}" -lt "$NEED_G" ]; then
    echo "[gdrive_pull] ABORT: need ~${NEED_G}G, have ${FREE_G}G — free space or use an external SSD"; exit 3
  fi
fi
if [ "${FREE_G:-0}" -lt "$MIN_FREE_G" ]; then
  echo "[gdrive_pull] ABORT: only ${FREE_G}G free (<${MIN_FREE_G}G) — free space first"; exit 3
fi

# --- slug + its own project ---
if [ -z "$SLUG" ]; then
  if [[ "$TYPE" == folder ]]; then SLUG="Drive-${ID:0:8}"; else SLUG="Clip-${ID:0:8}"; fi
fi
bash "$NP" "$CLIENT" "$SLUG" >/dev/null 2>&1
PROJ=$(ls -d "$HOME"/Downloads/"$CLIENT"/*_"$SLUG" 2>/dev/null | head -1)
if [ -z "$PROJ" ]; then echo "[gdrive_pull] ABORT: project scaffold failed for $SLUG"; exit 4; fi
DEST="$PROJ/00_SOURCE"
LOG="/tmp/fetch_${SLUG}.log"; : > "$LOG"
echo "[gdrive_pull] project=$PROJ"

# --- download (flags INLINE on purpose — a $VAR of flags fails to word-split under zsh) ---
if [[ "$TYPE" == folder ]]; then
  rclone copy gdrive: "$DEST" --drive-root-folder-id="$ID" \
    --transfers=8 --multi-thread-streams=8 --multi-thread-cutoff=100M \
    --drive-acknowledge-abuse --stats=10s --stats-one-line -v --log-file="$LOG"
  RC=$?
else
  rclone backend copyid gdrive: "$ID" "$DEST/" --multi-thread-streams=8 \
    --drive-acknowledge-abuse --stats=10s --stats-one-line -v --log-file="$LOG"
  RC=$?
fi
echo "[gdrive_pull] download rc=$RC"

# --- rename an auto Clip-<id> project to the real filename ---
if [[ "$TYPE" == file && "$SLUG" == Clip-* ]]; then
  RF=$(ls "$DEST" 2>/dev/null | grep -iE '\.(mp4|mov|wav|mxf|mp3)$' | head -1)
  if [ -n "$RF" ]; then
    NEW="${RF%.*}"
    NEWPROJ="$(dirname "$PROJ")/$(basename "$PROJ" | sed "s/${SLUG}\$/${NEW}/")"
    mv "$PROJ" "$NEWPROJ" 2>/dev/null && { PROJ="$NEWPROJ"; DEST="$PROJ/00_SOURCE"; echo "[gdrive_pull] renamed project -> $(basename "$NEWPROJ")"; }
  fi
fi

# --- verify ---
if [[ "$TYPE" == folder ]]; then
  echo "[gdrive_pull] MD5 check:"; rclone check gdrive: "$DEST" --drive-root-folder-id="$ID" --one-way 2>&1 | tail -2
else
  echo "[gdrive_pull] landed:"; ls -lh "$DEST"
fi
echo "[gdrive_pull] DONE $SLUG -> $PROJ"

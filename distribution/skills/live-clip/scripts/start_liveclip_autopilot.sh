#!/bin/bash
# /live-clip — THE one command to run before walking away from the Mac.
# Keeps the machine awake (lid must stay OPEN + plugged in), watches the channel,
# and runs the full autonomous clip pipeline when the live starts.
#
#   bash start_liveclip_autopilot.sh [channel_url] [until_HH:MM]
#
# Logs: __ACQ_ASSETS__/logs/liveclip_watch_<date>.log
set -euo pipefail
CHANNEL="${1:-https://www.youtube.com/@AlexHormozi}"
UNTIL="${2:-22:00}"
LOGDIR="$HOME/Downloads/cluade/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/liveclip_watch_$(date +%Y-%m-%d).log"
SKILL="$HOME/.agents/skills/live-clip/scripts"

# load keys the detached process won't otherwise have
source "$HOME/.zshrc" >/dev/null 2>&1 || true

# PREFLIGHT — refuse to arm with dead pieces (better to fail NOW, while a human is here)
echo "preflight: checking headless claude auth (the supervisor brain)..."
if ! claude -p "Reply with exactly: OK" 2>&1 | grep -q "OK"; then
    echo "❌ headless claude auth is DEAD — run:  claude login   then re-arm. NOT armed."
    exit 1
fi
for k in ASSEMBLYAI_API_KEY GROQ_API_KEY; do
    [ -n "${!k:-}" ] || { echo "❌ $k missing from environment. NOT armed."; exit 1; }
done
python3 -c "import json,datetime,sys; d=json.load(open('$HOME/Downloads/cluade/config/banned_guests.json')); s=datetime.date.fromisoformat(d['synced']); sys.exit(0 if (datetime.date.today()-s).days<=14 else 1)" \
    || { echo "❌ banned-guest registry stale (>14d) — re-sync it first. NOT armed."; exit 1; }
echo "preflight: all green ✅"

echo "== live-clip autopilot armed $(date) — channel: $CHANNEL, until $UNTIL ==" | tee -a "$LOG"
echo "   REMINDERS: lid OPEN, power connected, wifi on. Log: $LOG"

nohup caffeinate -dimsu python3 "$SKILL/live_watch.py" \
    --channel "$CHANNEL" --until "$UNTIL" >>"$LOG" 2>&1 &
echo "   armed (pid $!). Safe to lock the screen — do NOT close the lid."

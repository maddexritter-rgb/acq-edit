#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v python3.11 >/dev/null || { echo 'Install Python 3.11 first (for example, brew install python@3.11).'; exit 1; }
python3.11 scripts/media_prerequisites.py
python3.11 -m venv .local/venv
python3.11 scripts/runtime_environment.py .local/venv/bin/python -m pip install -r requirements-core.txt
.local/venv/bin/python python/check_framing_dependencies.py
echo 'Shared helpers installed locally. For remote intake, install yt-dlp and rclone and configure your own Drive remote.'

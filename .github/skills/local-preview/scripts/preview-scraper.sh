#!/usr/bin/env bash
# preview-scraper.sh — Dry-run the scraper (no DB writes, JSON to stdout).
# Usage:
#   bash preview-scraper.sh                       # all sources
#   bash preview-scraper.sh taiwan_cultural_center # one source
#   bash preview-scraper.sh peatix

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SCRAPER_DIR="$REPO_ROOT/scraper"
VENV_ACTIVATE="$REPO_ROOT/venv/bin/activate"

if [[ ! -f "$VENV_ACTIVATE" ]]; then
  echo "ERROR: venv not found at $VENV_ACTIVATE" >&2
  echo "Setup: cd $REPO_ROOT && python3 -m venv venv && source venv/bin/activate && pip install -r scraper/requirements.txt" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$VENV_ACTIVATE"

cd "$SCRAPER_DIR"

if [[ $# -ge 1 ]]; then
  echo "=== Dry-run: $1 (no DB writes) ===" >&2
  python main.py --dry-run --source "$1"
else
  echo "=== Dry-run: all sources (no DB writes) ===" >&2
  python main.py --dry-run
fi

#!/usr/bin/env bash
# test-source.sh — Run a single scraper source in dry-run mode (no DB writes).
# Usage:
#   bash test-source.sh <source_name>   # test one source
#   bash test-source.sh                 # test all sources
#
# Output: JSON printed to stdout; logs to stderr.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SCRAPER_DIR="$REPO_ROOT/scraper"
VENV_ACTIVATE="$REPO_ROOT/venv/bin/activate"

if [[ ! -f "$VENV_ACTIVATE" ]]; then
  echo "ERROR: venv not found at $VENV_ACTIVATE" >&2
  echo "Run: cd $REPO_ROOT && python3 -m venv venv && source venv/bin/activate && pip install -r scraper/requirements.txt" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$VENV_ACTIVATE"

cd "$SCRAPER_DIR"

if [[ $# -ge 1 ]]; then
  SOURCE="$1"
  echo "=== Dry-run: $SOURCE ===" >&2
  python main.py --dry-run --source "$SOURCE"
else
  echo "=== Dry-run: all sources ===" >&2
  python main.py --dry-run
fi

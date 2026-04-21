#!/usr/bin/env bash
# preview-web.sh — Start the Next.js dev server for local UI preview.
# Usage:
#   bash preview-web.sh
# Then open: http://localhost:3000

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
WEB_DIR="$REPO_ROOT/web"

if [[ ! -f "$WEB_DIR/.env.local" ]]; then
  echo "WARNING: web/.env.local not found." >&2
  echo "Copy web/.env.local.example to web/.env.local and fill in Supabase credentials." >&2
fi

if [[ ! -d "$WEB_DIR/node_modules" ]]; then
  echo "Installing web dependencies..." >&2
  cd "$WEB_DIR" && npm install
fi

cd "$WEB_DIR"
echo "Starting Next.js dev server at http://localhost:3000 ..." >&2
npm run dev

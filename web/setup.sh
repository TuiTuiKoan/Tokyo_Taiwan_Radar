#!/usr/bin/env bash
# web/setup.sh — 換機器或新環境時一鍵重建 web 開發環境
# Usage: bash web/setup.sh
set -euo pipefail

REQUIRED_NODE_MAJOR=22
REQUIRED_PNPM="10.33.3"

echo "==> Checking Node.js..."
if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js not found. Install via https://nodejs.org/ or nvm."
  exit 1
fi
NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
if [[ "$NODE_MAJOR" -lt "$REQUIRED_NODE_MAJOR" ]]; then
  echo "ERROR: Node.js >= ${REQUIRED_NODE_MAJOR} required (found $(node --version))"
  exit 1
fi
echo "    Node $(node --version) ✓"

echo "==> Checking pnpm..."
if ! command -v pnpm &>/dev/null; then
  echo "    Installing pnpm ${REQUIRED_PNPM}..."
  npm install -g "pnpm@${REQUIRED_PNPM}"
fi
echo "    pnpm $(pnpm --version) ✓"

echo "==> Installing dependencies..."
cd "$(dirname "$0")"
pnpm install

echo "==> Checking .env.local..."
if [[ ! -f .env.local ]]; then
  cp .env.local.example .env.local
  echo ""
  echo "  ⚠️  .env.local created from example."
  echo "  Fill in these values before running dev:"
  echo "    NEXT_PUBLIC_SUPABASE_URL"
  echo "    NEXT_PUBLIC_SUPABASE_ANON_KEY"
  echo "    SUPABASE_SERVICE_ROLE_KEY"
  echo ""
else
  echo "    .env.local already exists ✓"
fi

echo ""
echo "==> Setup complete. Run: pnpm dev"

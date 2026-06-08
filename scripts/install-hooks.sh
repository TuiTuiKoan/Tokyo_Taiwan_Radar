#!/usr/bin/env bash
# install-hooks.sh — sets up tracked git hooks from .githooks/
#
# Run once after cloning: bash scripts/install-hooks.sh
# Idempotent: safe to re-run.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "=== Installing git hooks ==="

# 1. Set core.hooksPath
git config core.hooksPath .githooks
echo "OK git config core.hooksPath = .githooks"

# 2. Make hooks executable
chmod +x .githooks/pre-commit .githooks/pre-push
echo "OK .githooks/pre-commit and .githooks/pre-push are executable"

# 3. Back up existing .git/hooks/pre-commit if present (and not already backed up)
if [[ -f ".git/hooks/pre-commit" && ! -f ".git/hooks/pre-commit.local.bak" ]]; then
  cp ".git/hooks/pre-commit" ".git/hooks/pre-commit.local.bak"
  echo "OK Backed up .git/hooks/pre-commit to .git/hooks/pre-commit.local.bak"
fi

# 4. Scan for other non-sample hooks in .git/hooks/ and warn
OTHER_HOOKS=$(find .git/hooks -maxdepth 1 -type f ! -name "*.sample" ! -name "pre-commit" ! -name "pre-commit.local.bak" 2>/dev/null || true)
if [[ -n "$OTHER_HOOKS" ]]; then
  echo ""
  echo "WARNING: Found other hooks in .git/hooks/ not covered by .githooks/:"
  echo "$OTHER_HOOKS"
  echo "   These hooks will NOT run after core.hooksPath is set to .githooks/."
  echo "   Consider copying them to .githooks/ manually."
fi

echo ""
echo "=== Hook installation complete ==="
echo "   pre-commit: .githooks/pre-commit (i18n guard + agent tools cleanup + migration rename)"
echo "   pre-push:   .githooks/pre-push   (i18n parity range check)"
echo ""
echo "To verify: git config core.hooksPath"

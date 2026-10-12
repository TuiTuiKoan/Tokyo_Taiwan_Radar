#!/usr/bin/env bash
# Fail-closed launcher for the Claude Code PreToolUse guards (see AGENTS.md).
#
# Usage (from .claude/settings.json): run_hook.sh bash|file  < hook payload
# Exit 0 allows; stdout is forwarded only when it is the exact decision JSON
# accepted by _policy.py --validate-output. Exit 2 blocks. Every other guard
# outcome (crash, import error, unknown exit code, invalid output, missing
# python3) is converted to exit 2 with a fixed message.

set -u

readonly INTERNAL_ERROR='ttr-hook: internal error, blocked'

fail() {
  printf '%s\n' "${1:-$INTERNAL_ERROR}" >&2
  exit 2
}

case "${1:-}" in
  bash) guard=pretooluse_bash_guard.py ;;
  file) guard=pretooluse_file_guard.py ;;
  *) fail ;;
esac

here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || fail
command -v python3 >/dev/null 2>&1 || fail 'ttr-hook: python3 not found, blocked'
errfile=$(mktemp "${TMPDIR:-/tmp}/ttr-hook.XXXXXX") || fail
trap 'rm -f "$errfile"' EXIT

out=$(python3 -B -E -s "$here/$guard" 2>"$errfile")
status=$?

case "$status" in
  0)
    [ -z "$out" ] && exit 0
    printf '%s' "$out" | python3 -B -E -s "$here/_policy.py" --validate-output >/dev/null 2>&1 || fail
    printf '%s\n' "$out"
    exit 0
    ;;
  2)
    cat -- "$errfile" >&2
    exit 2
    ;;
  *)
    fail
    ;;
esac

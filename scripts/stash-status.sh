#!/usr/bin/env bash
# scripts/stash-status.sh — Multi-session stash status tracker
#
# Usage:
#   ./scripts/stash-status.sh list              # 依狀態分組列出所有 stash
#   ./scripts/stash-status.sh ready             # 僅列出 [READY] stash
#   ./scripts/stash-status.sh promote <N>       # pop stash@{N} → 互動式 commit 流程
#
# Stash naming convention:
#   [WIP]     草稿，禁止合併      git stash push -m "[WIP] area: summary"
#   [READY]   驗證完，可合併      git stash push -m "[READY] area: summary"
#   [REVIEW]  等人工確認          git stash push -m "[REVIEW] area: summary"
#   [BLOCKED] 有外部依賴未就緒    git stash push -m "[BLOCKED] area: summary"
#   (無標籤)  舊 stash / 未分類   git stash push -m "area: summary"

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ────────────────────────────────────────────────────────────
# Color codes
# ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
GRAY='\033[0;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────
stash_age() {
  local ref="$1"
  local ts
  ts=$(git stash show --format="%ct" -s "$ref" 2>/dev/null || echo "0")
  local now
  now=$(date +%s)
  local diff=$(( now - ts ))
  if   (( diff < 3600 ));   then echo "${diff}s ago"
  elif (( diff < 86400 ));  then echo "$(( diff / 3600 ))h ago"
  elif (( diff < 604800 )); then echo "$(( diff / 86400 ))d ago"
  else                           echo "$(( diff / 604800 ))w ago"
  fi
}

stash_file_count() {
  local ref="$1"
  git stash show "$ref" 2>/dev/null | tail -1 | awk '{print $1}' || echo "?"
}

stash_is_stale() {
  local ref="$1"
  local ts
  ts=$(git stash show --format="%ct" -s "$ref" 2>/dev/null || echo "0")
  local now
  now=$(date +%s)
  local days=$(( (now - ts) / 86400 ))
  (( days >= 3 ))
}

get_state_from_message() {
  local msg="$1"
  if   [[ "$msg" =~ ^\[READY\]   ]]; then echo "READY"
  elif [[ "$msg" =~ ^\[REVIEW\]  ]]; then echo "REVIEW"
  elif [[ "$msg" =~ ^\[BLOCKED\] ]]; then echo "BLOCKED"
  elif [[ "$msg" =~ ^\[WIP\]     ]]; then echo "WIP"
  else                                    echo "UNLABELED"
  fi
}

strip_state_prefix() {
  local msg="$1"
  # Remove [STATE] prefix if present
  echo "$msg" | sed 's/^\[[A-Z]*\] //'
}

# ────────────────────────────────────────────────────────────
# cmd: list
# ────────────────────────────────────────────────────────────
cmd_list() {
  local stash_list
  stash_list=$(git stash list 2>/dev/null)

  if [[ -z "$stash_list" ]]; then
    echo "📭 No stashes found."
    return 0
  fi

  declare -a ready_lines review_lines wip_lines blocked_lines unlabeled_lines

  while IFS= read -r line; do
    # Parse: stash@{N}: On <branch>: <message>
    local ref desc
    ref=$(echo "$line" | awk -F': ' '{print $1}')           # stash@{N}
    desc=$(echo "$line" | sed 's/^[^:]*: On [^:]*: //' \
                        | sed 's/^[^:]*: WIP on [^:]*: //')  # the message

    local state
    state=$(get_state_from_message "$desc")
    local short_desc
    short_desc=$(strip_state_prefix "$desc")
    local age
    age=$(stash_age "$ref")
    local files
    files=$(stash_file_count "$ref")
    local stale_marker=""
    if stash_is_stale "$ref" && [[ "$state" == "READY" ]]; then
      stale_marker=" ${YELLOW}⚠ STALE${NC}"
    fi

    local entry
    printf -v entry "  %-12s  %-45s  %-10s  %s files%b" \
      "$ref" "$short_desc" "($age)" "$files" "$stale_marker"

    case "$state" in
      READY)     ready_lines+=("$entry") ;;
      REVIEW)    review_lines+=("$entry") ;;
      WIP)       wip_lines+=("$entry") ;;
      BLOCKED)   blocked_lines+=("$entry") ;;
      UNLABELED) unlabeled_lines+=("$entry") ;;
    esac
  done <<< "$stash_list"

  # Print sections
  if (( ${#ready_lines[@]} > 0 )); then
    echo -e "${GREEN}${BOLD}🟢 READY (可合併):${NC}"
    for l in "${ready_lines[@]}"; do echo -e "$l"; done
    echo
  fi

  if (( ${#review_lines[@]} > 0 )); then
    echo -e "${YELLOW}${BOLD}🟡 REVIEW (待人工確認):${NC}"
    for l in "${review_lines[@]}"; do echo -e "$l"; done
    echo
  fi

  if (( ${#blocked_lines[@]} > 0 )); then
    echo -e "${RED}${BOLD}🚫 BLOCKED (有外部依賴):${NC}"
    for l in "${blocked_lines[@]}"; do echo -e "$l"; done
    echo
  fi

  if (( ${#wip_lines[@]} > 0 )); then
    echo -e "${GRAY}${BOLD}🔴 WIP (勿動):${NC}"
    for l in "${wip_lines[@]}"; do echo -e "$l"; done
    echo
  fi

  if (( ${#unlabeled_lines[@]} > 0 )); then
    echo -e "${GRAY}${BOLD}⚪ UNLABELED (未分類):${NC}"
    for l in "${unlabeled_lines[@]}"; do echo -e "$l"; done
    echo
  fi

  # Promote hints
  if (( ${#ready_lines[@]} > 0 )); then
    echo -e "${BOLD}提示 — 一鍵合併:${NC}"
    for l in "${ready_lines[@]}"; do
      local ref
      ref=$(echo "$l" | awk '{print $1}')
      local n
      n=$(echo "$ref" | grep -o '[0-9]*')
      echo -e "  ${BLUE}./scripts/stash-status.sh promote $n${NC}"
    done
  fi
}

# ────────────────────────────────────────────────────────────
# cmd: ready
# ────────────────────────────────────────────────────────────
cmd_ready() {
  local stash_list
  stash_list=$(git stash list 2>/dev/null)

  if [[ -z "$stash_list" ]]; then
    echo "📭 No stashes found."
    return 0
  fi

  local found=0
  while IFS= read -r line; do
    local ref desc
    ref=$(echo "$line" | awk -F': ' '{print $1}')
    desc=$(echo "$line" | sed 's/^[^:]*: On [^:]*: //' \
                        | sed 's/^[^:]*: WIP on [^:]*: //')
    local state
    state=$(get_state_from_message "$desc")
    if [[ "$state" == "READY" ]]; then
      local short_desc age files n stale_marker=""
      short_desc=$(strip_state_prefix "$desc")
      age=$(stash_age "$ref")
      files=$(stash_file_count "$ref")
      n=$(echo "$ref" | grep -o '[0-9]*')
      stash_is_stale "$ref" && stale_marker=" ${YELLOW}⚠ STALE${NC}"
      echo -e "  ${GREEN}$ref${NC}  $short_desc  ($age)  $files files${stale_marker}"
      echo -e "         → ${BLUE}./scripts/stash-status.sh promote $n${NC}"
      found=1
    fi
  done <<< "$stash_list"

  if (( found == 0 )); then
    echo "📭 No [READY] stashes found."
  fi
}

# ────────────────────────────────────────────────────────────
# cmd: promote <N>
# ────────────────────────────────────────────────────────────
cmd_promote() {
  local n="${1:-}"
  if [[ -z "$n" ]]; then
    echo "Usage: $0 promote <N>   # e.g. promote 0" >&2
    exit 1
  fi

  local ref="stash@{$n}"

  # ── Step 1: working tree must be clean ─────────────────────
  if ! git diff --quiet || ! git diff --cached --quiet; then
    echo -e "${RED}❌ Working tree is dirty. Stash or commit your current changes first.${NC}" >&2
    git status --short
    exit 1
  fi

  # ── Step 2: fetch + check rebase need ──────────────────────
  echo "⏳ Fetching origin/main…"
  git fetch origin main --quiet
  local behind
  behind=$(git log HEAD..origin/main --oneline | wc -l | tr -d ' ')
  if (( behind > 0 )); then
    echo -e "${YELLOW}⚠ origin/main is $behind commit(s) ahead. Rebasing…${NC}"
    git rebase origin/main
    echo "✅ Rebase complete."
  else
    echo "✅ Already up-to-date with origin/main."
  fi

  # ── Step 3: show what we're about to pop ──────────────────
  echo ""
  echo -e "${BOLD}Stash to promote:${NC}"
  git stash show "$ref" 2>/dev/null || true
  echo ""
  echo -e "${YELLOW}About to pop ${ref}. Press Enter to continue, Ctrl-C to abort.${NC}"
  read -r

  # ── Step 4: pop ────────────────────────────────────────────
  if ! git stash pop "$ref"; then
    echo -e "${RED}❌ Stash pop failed (likely conflict). Resolve conflicts then commit manually.${NC}" >&2
    exit 1
  fi
  echo "✅ Stash popped."

  # ── Step 5: show diff ──────────────────────────────────────
  echo ""
  git status --short
  echo ""
  git diff --stat HEAD
  echo ""

  # ── Step 6: suggest commit message ─────────────────────────
  local orig_msg
  orig_msg=$(git stash list 2>/dev/null | grep -E "^stash@\{" | head -1 || true)
  # stash was already popped, so get message from reflog
  local stash_msg
  stash_msg=$(git log -g stash --format="%gs" 2>/dev/null | head -1 \
    | sed 's/^On [^:]*: //' | sed 's/^\[READY\] //' | sed 's/^\[WIP\] //' || true)

  echo -e "${BOLD}Suggested commit message (edit as needed):${NC}"
  echo -e "${BLUE}${stash_msg:-"feat: <describe your change>"}${NC}"
  echo ""
  printf "Commit message: "
  read -r commit_msg
  if [[ -z "$commit_msg" ]]; then
    commit_msg="${stash_msg:-"chore: promote stash@{$n}"}"
  fi

  # ── Step 7: commit ─────────────────────────────────────────
  git add -A
  git commit -m "$commit_msg"
  echo "✅ Committed."

  # ── Step 8: push prompt ────────────────────────────────────
  echo ""
  printf "Push to origin/main? [y/N] "
  read -r push_confirm
  if [[ "$push_confirm" =~ ^[Yy]$ ]]; then
    git push origin main
    echo "✅ Pushed to origin/main."
    echo ""
    echo -e "${GREEN}${BOLD}🚀 Done! 現在點 VMD agent 完成 Vercel 驗證。${NC}"
  else
    echo "⏸  Skipped push. Run 'git push origin main' when ready."
  fi
}

# ────────────────────────────────────────────────────────────
# Main dispatcher
# ────────────────────────────────────────────────────────────
CMD="${1:-list}"
case "$CMD" in
  list)    cmd_list ;;
  ready)   cmd_ready ;;
  promote) cmd_promote "${2:-}" ;;
  *)
    echo "Usage: $0 {list|ready|promote <N>}" >&2
    exit 1
    ;;
esac

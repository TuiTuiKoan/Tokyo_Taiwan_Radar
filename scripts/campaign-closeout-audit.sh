#!/usr/bin/env bash
#
# campaign-closeout-audit.sh — Phase A of a campaign close-out, automated.
#
# This is a SINGLE-WORKTREE PROBE, not an inventory. It answers one question
# about one named worktree: may this worktree be retired right now. The single
# authority for which worktrees exist is the `workstream-tracking` spec; this
# script never builds a second inventory and never writes one.
#
# The authoritative definitions of path class, the six freshness values and the
# cleanup order live in docs/evaluation/campaigns/README.md, sections Identity,
# Freshness and Cleanup checklist. When this script and that document disagree,
# the document wins and this script is the defect.
#
# READ-ONLY. It creates no file, mutates no ref, and never fetches. Ahead and
# behind are measured against the local `origin/main` ref exactly as it stands,
# so the caller must fetch immediately before running:
#
#     git -C '<worktree>' fetch origin main --quiet
#
# Exit codes
#   0   RETIRE_CANDIDATE  every gate passed
#   10  HOLD              at least one hard blocker
#   20  UNDETERMINED      no hard blocker, but something could not be checked
#   2   usage error
#
# Parsing note: every path in this repository contains spaces. Fields are cut
# with sed and every expansion is quoted. awk is not used anywhere, because a
# field-splitting parser truncates each path at its first space.

set -u

WT=""
SLUG=""
BASE=""
HEAD_SHA=""
SELF_SESSION=""
STATE_DIR="$HOME/.copilot/session-state"
IDLE_THRESHOLD=900
SKIP_ISSUES=0

usage() {
  cat <<'EOF'
Usage: scripts/campaign-closeout-audit.sh --worktree <registered-path> [options]

  --worktree <path>        registered or physical path of the worktree to audit
  --slug <slug>            campaign slug; without it the spec and issue sources
                           report not_checked rather than a false zero
  --base <sha>             campaign base SHA, the origin/main tip before the
                           V-M-D push; start of the TODO commit range
  --head <sha>             pushed HEAD SHA; end of the TODO commit range
  --self-session <id>      this session's id, excluded from contention
  --session-state-dir <d>  default ~/.copilot/session-state
  --idle-threshold <secs>  default 900; a lock older than this is UNDETERMINED,
                           never SOLE_OWNER
  --skip-issues            do not query GitHub; that source reports not_checked
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --worktree)           WT="${2:-}"; shift 2 ;;
    --slug)               SLUG="${2:-}"; shift 2 ;;
    --base)               BASE="${2:-}"; shift 2 ;;
    --head)               HEAD_SHA="${2:-}"; shift 2 ;;
    --self-session)       SELF_SESSION="${2:-}"; shift 2 ;;
    --session-state-dir)  STATE_DIR="${2:-}"; shift 2 ;;
    --idle-threshold)     IDLE_THRESHOLD="${2:-}"; shift 2 ;;
    --skip-issues)        SKIP_ISSUES=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$WT" ]; then
  echo "--worktree is required" >&2
  usage >&2
  exit 2
fi
if [ ! -d "$WT" ]; then
  echo "not a directory: $WT" >&2
  exit 2
fi

# Hard blockers and unknowns are collected separately. A hard blocker decides
# the verdict on its own; unknowns only decide it when no blocker was found.
HOLD_REASONS=""
UNDET_REASONS=""

add_hold() {
  if [ -z "$HOLD_REASONS" ]; then HOLD_REASONS="$1"; else HOLD_REASONS="$HOLD_REASONS,$1"; fi
}
add_undet() {
  case ",$UNDET_REASONS," in
    *",$1,"*) return 0 ;;
  esac
  if [ -z "$UNDET_REASONS" ]; then UNDET_REASONS="$1"; else UNDET_REASONS="$UNDET_REASONS,$1"; fi
}

# trim() removes ALL whitespace and is only safe for numeric output such as the
# leading padding BSD wc emits. It must never touch a path: this repository's
# own directory name contains spaces.
trim() { printf '%s' "$1" | tr -d '[:space:]'; }

# trim_edges() removes only leading and trailing blanks, and is the one to use
# on a value that may legitimately contain interior spaces.
trim_edges() { printf '%s' "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'; }

mtime_of() {
  if stat -f %m "$1" >/dev/null 2>&1; then
    stat -f %m "$1"
  else
    stat -c %Y "$1" 2>/dev/null
  fi
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

OBSERVED_AT=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

echo "# Campaign close-out audit (Phase A, read-only)"
echo
echo "observed_at=$OBSERVED_AT"
echo "probe_scope=single_worktree  (inventory authority: docs/specs/active/workstream-tracking)"
echo "fetch=not_performed  (read-only; ahead/behind are relative to the local origin/main ref)"
echo

# ── A1 Identity ──────────────────────────────────────────────────────────────
# Placement is decided first, then lexical divergence. Registered paths are cut
# with sed; /bin/pwd -P is the external binary, because a shell builtin hands
# back the string that was typed and so reports a divergent worktree external.

echo "## A1 Identity"
echo

if ! git -C "$WT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "identity=NOT_A_WORKTREE"
  echo
  echo "## A5 Verdict"
  echo
  echo "verdict=HOLD:not_a_worktree"
  exit 10
fi

MAIN_WT=$( git -C "$WT" worktree list --porcelain | sed -n '1s/^worktree //p' )
ROOT=$( cd "$MAIN_WT" && /bin/pwd -P )
PHYS=$( cd "$WT" && /bin/pwd -P )
# Directory name of the target, used only by the A3 unparseable-value guard.
PHYS_BASE=$( basename "$PHYS" )

REGISTERED=""
while IFS= read -r line; do
  [ -n "$line" ] || continue
  [ -d "$line" ] || continue
  cand=$( cd "$line" && /bin/pwd -P )
  if [ "$cand" = "$PHYS" ]; then
    REGISTERED="$line"
    break
  fi
done <<EOF
$( git -C "$WT" worktree list --porcelain | sed -n 's/^worktree //p' )
EOF

if [ -z "$REGISTERED" ]; then
  echo "registered=UNREGISTERED"
  add_hold "unregistered"
else
  echo "registered=\"$REGISTERED\""
fi

case "$PHYS" in
  "$ROOT"|"$ROOT"/*)
    if [ "$REGISTERED" = "$PHYS" ]; then PATH_CLASS="canonical"; else PATH_CLASS="divergent"; fi ;;
  *)
    PATH_CLASS="external" ;;
esac

BRANCH=$( git -C "$WT" rev-parse --abbrev-ref HEAD )
DIRNAME=$( basename "$PHYS" )

echo "physical=\"$PHYS\""
echo "path_class=$PATH_CLASS"
echo "directory=$DIRNAME"
echo "branch=$BRANCH"
if [ "$PATH_CLASS" = "external" ]; then
  echo "note=external: the repository .git/info/exclude entry does not apply, and a"
  echo "note=root-relative residue check would report directory=gone while the"
  echo "note=directory still exists. Point both at the external path explicitly."
fi
if [ "$PATH_CLASS" = "divergent" ]; then
  echo "note=divergent: one directory under two names. Quote both strings; never"
  echo "note=normalize one away, because automation keyed on the registered string"
  echo "note=splits from automation keyed on the physical one."
fi
echo

# ── A2 Unhandled work ────────────────────────────────────────────────────────
# Five sources. A source that could not be consulted reports not_checked. It is
# never reported as zero: "not checked" and "checked, found nothing" are
# different claims and only one of them supports retirement.

echo "## A2 Unhandled work"
echo

UNHANDLED_TOTAL=0
NOT_CHECKED=0

count_or_zero() { # prints an integer, never empty
  c=$( trim "${1:-0}" )
  [ -n "$c" ] || c=0
  printf '%s' "$c"
}

# 0. Resolve the spec directory ONCE, before any spec-derived source reads it.
#    A slug that does not resolve to a real spec directory is an unanswered
#    question, not an answer of zero: a single mistyped letter would otherwise
#    turn every unhandled task into "spec_tasks=0" and silently open the gate.
#    Sources 1 and 2 therefore report not_checked whenever SPEC_DIR is empty.
SPEC_DIR=""
if [ -n "$SLUG" ]; then
  for cand in "$WT/docs/specs/active/$SLUG" "$WT/docs/specs/archive/$SLUG"; do
    if [ -d "$cand" ]; then
      SPEC_DIR="$cand"
      break
    fi
  done
fi

# 1. spec tasks.md unchecked boxes
if [ -z "$SLUG" ]; then
  echo "spec_tasks=not_checked  (reason: --slug not supplied; the slug is never"
  echo "spec_tasks=not_checked  guessed from the directory or branch name)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "spec_tasks_not_checked"
elif [ -z "$SPEC_DIR" ]; then
  echo "spec_tasks=not_checked  (reason: slug '$SLUG' does not resolve to an"
  echo "spec_tasks=not_checked  existing docs/specs/active/ or docs/specs/archive/"
  echo "spec_tasks=not_checked  directory; a typo must never be reported as 0)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "spec_dir_unresolved"
else
  TASKS_FILE="$SPEC_DIR/tasks.md"
  if [ -f "$TASKS_FILE" ]; then
    n=$( grep -cE '^[[:space:]]*[-*] \[ \]' "$TASKS_FILE" 2>/dev/null )
    n=$( count_or_zero "$n" )
    echo "spec_tasks=$n  (${SPEC_DIR#"$WT"/}/tasks.md)"
    UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + n ))
  else
    echo "spec_tasks=0  (spec directory ${SPEC_DIR#"$WT"/} exists but has no tasks.md)"
  fi
fi

# 2. Deferred markers in the spec narrative
if [ -z "$SLUG" ]; then
  echo "deferred_markers=not_checked  (reason: --slug not supplied)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "deferred_not_checked"
elif [ -z "$SPEC_DIR" ]; then
  echo "deferred_markers=not_checked  (reason: slug '$SLUG' does not resolve to an"
  echo "deferred_markers=not_checked  existing spec directory)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "spec_dir_unresolved"
else
  DEF=0
  DEF_SEEN=0
  for f in "$SPEC_DIR/changes-log.md" "$SPEC_DIR/proposal.md"; do
    [ -f "$f" ] || continue
    DEF_SEEN=1
    n=$( grep -Ei 'deferred|not executed' "$f" 2>/dev/null \
         | grep -viE 'deferred[[:space:]]*(work)?[[:space:]]*:?[[:space:]]*(none|n/a)' \
         | grep -c . )
    n=$( count_or_zero "$n" )
    DEF=$(( DEF + n ))
  done
  if [ "$DEF_SEEN" -eq 0 ]; then
    echo "deferred_markers=0  (spec directory ${SPEC_DIR#"$WT"/} has no changes-log.md or proposal.md)"
  else
    echo "deferred_markers=$DEF  (changes-log.md + proposal.md; 'None' and 'n/a' excluded)"
    UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + DEF ))
  fi
fi

# 3. .copilot-tracking plans (gitignored scratch space, lives inside the worktree)
PLAN_DIR="$WT/.copilot-tracking/plans"
if [ -d "$PLAN_DIR" ]; then
  n2=0
  while IFS= read -r c; do
    c=$( count_or_zero "$c" )
    n2=$(( n2 + c ))
  done <<EOF
$( grep -rhcE '^[[:space:]]*[-*] \[ \]' "$PLAN_DIR" 2>/dev/null )
EOF
  echo "tracking_plans=$n2  (.copilot-tracking/plans/*.md unchecked items)"
  UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + n2 ))
else
  echo "tracking_plans=0  (no .copilot-tracking/plans directory)"
fi

# 4. TODO / FIXME introduced by the campaign's own commits.
#    The range is <base>..<head>, never origin/main...HEAD: after the V-M-D push
#    HEAD equals origin/main, so the three-dot form is always empty and would
#    report a false zero for every campaign that shipped.
if [ -z "$BASE" ]; then
  echo "range_todo=not_checked  (reason: --base not supplied by the V-M-D handoff;"
  echo "range_todo=not_checked  origin/main...HEAD is refused because it is empty"
  echo "range_todo=not_checked  after the push and would report a false zero)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "range_todo_not_checked"
else
  END="$HEAD_SHA"
  [ -n "$END" ] || END="HEAD"
  if git -C "$WT" rev-parse --verify --quiet "$BASE" >/dev/null 2>&1 \
     && git -C "$WT" rev-parse --verify --quiet "$END" >/dev/null 2>&1; then
    n=$( git -C "$WT" log --format='' -p "$BASE..$END" 2>/dev/null \
         | grep -E '^\+' \
         | grep -cE 'TODO|FIXME' )
    n=$( count_or_zero "$n" )
    echo "range_todo=$n  (added lines matching TODO|FIXME in $BASE..$END)"
    UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + n ))
  else
    echo "range_todo=not_checked  (reason: --base or --head does not resolve here)"
    NOT_CHECKED=$(( NOT_CHECKED + 1 ))
    add_undet "range_todo_unresolvable"
  fi
fi

# 5. open GitHub issues naming the slug
if [ "$SKIP_ISSUES" -eq 1 ]; then
  echo "open_issues=not_checked  (reason: --skip-issues)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "issues_not_checked"
elif [ -z "$SLUG" ]; then
  echo "open_issues=not_checked  (reason: --slug not supplied)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "issues_not_checked"
elif ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
  echo "open_issues=not_checked  (reason: no authenticated gh; a token is required)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "issues_not_checked"
else
  if issues=$( cd "$WT" && gh issue list --state open --search "$SLUG" --limit 100 --json number 2>/dev/null ); then
    n=$( printf '%s' "$issues" | grep -o '"number"' | grep -c . )
    n=$( count_or_zero "$n" )
    echo "open_issues=$n  (open issues matching '$SLUG')"
    UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + n ))
  else
    echo "open_issues=not_checked  (reason: gh query failed)"
    NOT_CHECKED=$(( NOT_CHECKED + 1 ))
    add_undet "issues_not_checked"
  fi
fi

echo "unhandled_total=$UNHANDLED_TOTAL"
echo "not_checked_sources=$NOT_CHECKED"
if [ "$UNHANDLED_TOTAL" -gt 0 ]; then
  add_hold "unhandled_work"
fi
echo

# ── A3 Session contention ────────────────────────────────────────────────────
# Deterministic and conservative, one level deep.
#
# A process id is NEVER a liveness signal here. Copilot CLI sessions share a
# Code Helper process, so distinct sessions legitimately record the same pid;
# treating that pid as proof of life would mark unrelated sessions as alive.
#
# The idle threshold only raises doubt. It never grants permission: a lock whose
# transcript has gone quiet yields UNDETERMINED, never SOLE_OWNER.

echo "## A3 Session contention"
echo

CONTENDED=0
A3_UNDET=0

if [ ! -d "$STATE_DIR" ]; then
  echo "session_state=absent  (\"$STATE_DIR\")"
  A3_UNDET=1
  add_undet "session_state_absent"
elif [ -z "$SELF_SESSION" ]; then
  echo "self_session=unknown  (this session cannot be excluded from its own audit)"
  A3_UNDET=1
  add_undet "self_session_unknown"
fi

NOW=$( date -u '+%s' )

if [ -d "$STATE_DIR" ]; then
  for d in "$STATE_DIR"/*/; do
    [ -d "$d" ] || continue
    id=$( basename "$d" )
    [ "$id" = "$SELF_SESSION" ] && continue

    have_lock=0
    # Both the pid-qualified and the bare lock name are accepted. The lock file
    # name is an external format contract; a name this probe fails to match
    # would silently skip a live session, so the match is kept deliberately wide.
    for lock in "$d"inuse.*.lock "$d"inuse.lock; do
      [ -e "$lock" ] || continue
      have_lock=1
      break
    done
    [ "$have_lock" -eq 1 ] || continue

    yaml="$d/workspace.yaml"
    sroot=""
    if [ -f "$yaml" ]; then
      # [[:space:]]* so that any amount of padding after the colon is consumed
      # at the source. Do not rely on the later trim alone: the two defences
      # cover different inputs and the first version of this parse shipped with
      # only half of them.
      sroot=$( sed -n 's/^git_root:[[:space:]]*//p' "$yaml" | sed -n '1p' )
      if [ -z "$sroot" ]; then
        sroot=$( sed -n 's/^cwd:[[:space:]]*//p' "$yaml" | sed -n '1p' )
      fi
      # Order matters: trim FIRST, strip quotes SECOND. The quote-stripping
      # expressions are anchored at ^ and $, so any surviving padding makes the
      # anchor fail and the quotes stay on, which then fails both the directory
      # test and the string compare and silently skips a live session.
      sroot=$( trim_edges "$sroot" )
      # Strip one wrapping quote pair. Interior spaces are meaningful (this
      # repository's own path contains them) and are never touched.
      sroot=$( printf '%s' "$sroot" | sed -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/" )
    fi

    if [ -z "$sroot" ]; then
      echo "session=${id%%-*} lock=yes root=unrecorded verdict=UNDETERMINED"
      A3_UNDET=1
      add_undet "session_root_unrecorded"
      continue
    fi

    matched=0
    resolved=1
    if [ -d "$sroot" ]; then
      srp=$( cd "$sroot" && /bin/pwd -P )
      [ "$srp" = "$PHYS" ] && matched=1
    else
      # Unresolvable path. Fall back to a case-insensitive comparison of the raw
      # strings, which is what the Development/development split actually is on a
      # case-insensitive filesystem. A match that could not be resolved is a
      # doubt, not a clearance.
      resolved=0
      if [ "$( lower "$sroot" )" = "$( lower "$PHYS" )" ]; then matched=1; fi
    fi

    [ "$matched" -eq 1 ] || {
      # Class-level guard for a value this probe could neither resolve nor
      # match. The contract is "malformed but still pointing at the target is a
      # doubt, not a skip", so an unresolvable string that still mentions the
      # target directory name is escalated rather than dropped. This catches
      # every malformed shape at once (unpaired quote, ~ or other unexpanded
      # relative form, a form not invented yet) instead of one regex per shape.
      #
      # Deliberately restricted to resolved=0. A path that DID resolve and
      # points somewhere else is a genuine clearance; escalating those would
      # drag every unrelated session with a similar name into UNDETERMINED and
      # make the gate unusable.
      if [ "$resolved" -eq 0 ] && [ -n "$PHYS_BASE" ] \
         && printf '%s' "$( lower "$sroot" )" | grep -qF "$( lower "$PHYS_BASE" )"; then
        echo "session=${id%%-*} lock=yes root=unparseable_but_names_target verdict=UNDETERMINED"
        A3_UNDET=1
        add_undet "session_root_unparseable"
      fi
      continue
    }

    if [ "$resolved" -eq 0 ]; then
      echo "session=${id%%-*} lock=yes root=unresolvable verdict=UNDETERMINED"
      A3_UNDET=1
      add_undet "session_root_unresolvable"
      continue
    fi

    ev="$d/events.jsonl"
    if [ -f "$ev" ]; then
      m=$( mtime_of "$ev" )
      m=$( count_or_zero "$m" )
      age=$(( NOW - m ))
      if [ "$age" -le "$IDLE_THRESHOLD" ]; then
        echo "session=${id%%-*} lock=yes transcript_age_s=$age verdict=CONTENDED"
        CONTENDED=1
      else
        echo "session=${id%%-*} lock=yes transcript_age_s=$age verdict=UNDETERMINED  (idle but open)"
        A3_UNDET=1
        add_undet "idle_lock"
      fi
    else
      echo "session=${id%%-*} lock=yes transcript=absent verdict=UNDETERMINED"
      A3_UNDET=1
      add_undet "transcript_absent"
    fi
  done
fi

if [ "$CONTENDED" -eq 1 ]; then
  A3_VERDICT="CONTENDED"
  add_hold "contended"
elif [ "$A3_UNDET" -eq 1 ]; then
  A3_VERDICT="UNDETERMINED"
else
  A3_VERDICT="SOLE_OWNER (CLI-scope)"
fi

echo "contention=$A3_VERDICT"
echo "coverage=Copilot CLI sessions only. VS Code chat sessions are not"
echo "coverage=detectable: every workspaceStorage entry pointing at this project"
echo "coverage=resolves to the repository root, not to a worktree. SOLE_OWNER is"
echo "coverage=therefore CLI-scoped, and the user confirmation gate is the backstop."
echo "coverage=Process ids are not used as a liveness signal; sessions share one"
echo "coverage=Code Helper process and legitimately report the same pid."
echo

# ── A4 Freshness ─────────────────────────────────────────────────────────────

echo "## A4 Freshness"
echo

TIP=$( git -C "$WT" rev-parse HEAD )
COUNTS=$( git -C "$WT" rev-list --left-right --count HEAD...origin/main 2>/dev/null )
AHEAD=$( printf '%s' "$COUNTS" | sed -n 's/^\([0-9][0-9]*\)[[:space:]].*$/\1/p' )
BEHIND=$( printf '%s' "$COUNTS" | sed -n 's/^[0-9][0-9]*[[:space:]]*\([0-9][0-9]*\)$/\1/p' )
AHEAD=$( count_or_zero "$AHEAD" )
BEHIND=$( count_or_zero "$BEHIND" )
DIRTY=$( git -C "$WT" status --porcelain | grep -c . )
DIRTY=$( count_or_zero "$DIRTY" )
IGNORED=$( git -C "$WT" status --porcelain --ignored 2>/dev/null | grep -c '^!!' )
IGNORED=$( count_or_zero "$IGNORED" )
ORIGIN_MAIN=$( git -C "$WT" rev-parse origin/main 2>/dev/null )
[ -n "$ORIGIN_MAIN" ] || ORIGIN_MAIN="unresolved"

echo "branch_tip=$TIP"
echo "ahead=$AHEAD"
echo "behind=$BEHIND"
echo "dirty_count=$DIRTY"
echo "ignored_artifacts=$IGNORED"
echo "path_identity=$PATH_CLASS, directory $DIRNAME, branch $BRANCH"
echo "origin_main_ref=$ORIGIN_MAIN  (local ref; not refreshed by this script)"

GITDIR=$( git -C "$WT" rev-parse --git-dir )
case "$GITDIR" in
  /*) ABS_GITDIR="$GITDIR" ;;
  *)  ABS_GITDIR="$WT/$GITDIR" ;;
esac
IN_PROGRESS="none"
if [ -d "$ABS_GITDIR/rebase-merge" ] || [ -d "$ABS_GITDIR/rebase-apply" ]; then
  IN_PROGRESS="rebase"
elif [ -f "$ABS_GITDIR/MERGE_HEAD" ]; then
  IN_PROGRESS="merge"
elif [ -f "$ABS_GITDIR/CHERRY_PICK_HEAD" ]; then
  IN_PROGRESS="cherry-pick"
fi
echo "in_progress=$IN_PROGRESS"

[ "$DIRTY" -gt 0 ] && add_hold "dirty"
[ "$AHEAD" -gt 0 ] && add_hold "ahead"
[ "$IN_PROGRESS" = "none" ] || add_hold "in_progress"
echo

# ── A5 Verdict ───────────────────────────────────────────────────────────────
# A hard blocker decides on its own. Unknowns decide only when nothing is
# blocking, so an unreadable source can never be mistaken for a clean pass.

echo "## A5 Verdict"
echo

if [ -n "$HOLD_REASONS" ]; then
  echo "verdict=HOLD:$HOLD_REASONS"
  [ -n "$UNDET_REASONS" ] && echo "also_undetermined=$UNDET_REASONS"
  echo "next=Resolve every blocker, then re-run. Do not enter Phase B."
  exit 10
fi

if [ -n "$UNDET_REASONS" ]; then
  echo "verdict=UNDETERMINED:$UNDET_REASONS"
  echo "next=Stop and ask the user. UNDETERMINED is neither a pass nor a permanent"
  echo "next=block: supply the missing input, or have the user confirm, then re-run."
  exit 20
fi

echo "verdict=RETIRE_CANDIDATE"
echo "next=Phase B. Every freshness value above must be re-observed immediately"
echo "next=before any removal; an earlier PASS is never carried forward."
exit 0

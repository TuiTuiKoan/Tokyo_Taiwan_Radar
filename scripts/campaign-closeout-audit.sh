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
RANGES=""
SELF_SESSION=""
STATE_DIR="$HOME/.copilot/session-state"
IDLE_THRESHOLD=900
SKIP_ISSUES=0

# Issues carrying this label are reminders the repository generates on its own
# every day, and their body lists commit subjects, so any slug that appears in a
# subject matches them. They are not work, and they are excluded from source 5.
ISSUE_EXCLUDE_LABEL="daily-review"

# The two marker words counted by source 4, assembled from halves on purpose.
# The audit counts them on ADDED lines, so a script that spelled them out would
# flag any campaign that merely edited it. The words are named in the heading
# comment of source 4 below.
MARKER_PATTERN='TO''DO|FIX''ME'

usage() {
  cat <<'EOF'
Usage: scripts/campaign-closeout-audit.sh --worktree <registered-path> [options]

  --worktree <path>        registered or physical path of the worktree to audit
  --slug <slug>            campaign slug; without it the spec and issue sources
                           report not_checked rather than a false zero. The spec
                           is docs/specs/active/<slug>, else the one directory
                           under docs/specs/archive/ named <slug> or
                           <YYYY-MM>-<slug>. Two or more archived matches are
                           spec_dir_ambiguous (not_checked), never guessed
  --range <base>..<head>   one pushed segment of the campaign's commit range;
                           repeatable. base is the origin/main tip before that
                           push, head is the HEAD that push delivered. Give one
                           per push: a campaign pushed in several rounds has
                           other campaigns' commits between its rounds, and one
                           span over all of them counts those commits' added
                           lines as this campaign's. Each segment is counted and
                           printed with its first and last commit, and range_todo
                           is the total over the DISTINCT commits of all segments
                           (a commit inside two segments counts once). A segment
                           that does not resolve here, or holds no commit (base
                           and head swapped, or equal), makes range_todo
                           not_checked, never 0. The three-dot form a...b is
                           refused.
  --base <sha>             alone: the single-segment form, kept for
                           compatibility, with the output it always had. With
                           --range: the start of the campaign's FULL range,
                           normally the first push's base.
  --head <sha>             end of that range, default HEAD; with --range it needs
                           --base. The full range lets the audit see the commits
                           that no segment covers, which range_todo cannot:
                           range_todo_uncovered_commits and _hits count them, and
                           every uncovered commit that adds a marker line is
                           listed (short sha, date, author, subject, files, the
                           line itself, and a hint whether the slug appears in
                           its subject or paths; the hint is not a verdict).
                           They may belong to another campaign, so they are not
                           added to unhandled_total, but they keep the verdict
                           at UNDETERMINED until a person attributes them. With
                           --range and no full range the figures are not_checked,
                           because a segment left out could not be noticed.
  --self-session <id>      this session's id, excluded from contention
  --session-state-dir <d>  default ~/.copilot/session-state
  --idle-threshold <secs>  default 900; a lock older than this is UNDETERMINED,
                           never SOLE_OWNER
  --skip-issues            do not query GitHub; that source reports not_checked
EOF
}

# add_range appends one validated <base>..<head> segment to RANGES. It exits the
# script directly, so it must never be called inside a command substitution.
add_range() {
  r="$1"
  case "$r" in
    *...*)
      echo "--range refuses the three-dot form '$r': after the push HEAD equals" >&2
      echo "origin/main and that form is empty, which would report a false zero" >&2
      usage >&2
      exit 2 ;;
    *..*) ;;
    *)
      echo "--range expects <base>..<head>, got '$r'" >&2
      usage >&2
      exit 2 ;;
  esac
  rb="${r%%..*}"
  rh="${r#*..}"
  if [ -z "$rb" ] || [ -z "$rh" ]; then
    echo "--range needs both a base and a head, got '$r'" >&2
    usage >&2
    exit 2
  fi
  if [ -z "$RANGES" ]; then
    RANGES="$r"
  else
    RANGES="$RANGES
$r"
  fi
}

while [ $# -gt 0 ]; do
  # A value flag with nothing after it must stop the parse. Without this guard
  # `shift 2` fails on the last argument, leaves $# unchanged, and the loop never
  # ends.
  case "$1" in
    --worktree|--slug|--base|--head|--range|--self-session|--session-state-dir|--idle-threshold)
      if [ $# -lt 2 ]; then
        echo "$1 requires a value" >&2
        usage >&2
        exit 2
      fi ;;
  esac
  case "$1" in
    --worktree)           WT="${2:-}"; shift 2 ;;
    --slug)               SLUG="${2:-}"; shift 2 ;;
    --base)               BASE="${2:-}"; shift 2 ;;
    --head)               HEAD_SHA="${2:-}"; shift 2 ;;
    --range)              add_range "${2:-}"; shift 2 ;;
    --self-session)       SELF_SESSION="${2:-}"; shift 2 ;;
    --session-state-dir)  STATE_DIR="${2:-}"; shift 2 ;;
    --idle-threshold)     IDLE_THRESHOLD="${2:-}"; shift 2 ;;
    --skip-issues)        SKIP_ISSUES=1; shift ;;
    -h|--help)            usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -n "$RANGES" ] && [ -n "$HEAD_SHA" ] && [ -z "$BASE" ]; then
  echo "--head needs --base when --range is used: together they are the full range" >&2
  usage >&2
  exit 2
fi

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
#
#    Resolution order. docs/specs/README names an archived directory
#    <YYYY-MM>-<slug>, so a bare archive/<slug> is only the legacy spelling.
#      1. active/<slug> exists: use it. A live spec is unique, so archive is not
#         consulted and ambiguity cannot arise.
#      2. Otherwise compare every directory name under archive/ with the slug:
#         the name itself, or the name without a leading <YYYY-MM>- (month
#         01-12), must EQUAL the slug. The slug is data, never a glob: it is only
#         ever compared with [ = ], so 'demo-*' cannot widen the match.
#         0 hits -> unresolved, 1 hit -> use it, 2 or more -> ambiguous.
#    Ambiguity is its own reason: a typo needs a new slug, a duplicate archive
#    needs one of the directories removed, and a person must tell them apart.
#    Several hits are reported, never narrowed to the newest month by guessing.
SPEC_DIR=""
SPEC_AMBIGUOUS=0
SPEC_HIT_LIST=""
if [ -n "$SLUG" ]; then
  if [ -d "$WT/docs/specs/active/$SLUG" ]; then
    SPEC_DIR="$WT/docs/specs/active/$SLUG"
  else
    SPEC_HITS=0
    for cand in "$WT"/docs/specs/archive/*/; do
      [ -d "$cand" ] || continue   # an unmatched glob stays literal and is skipped here
      name=${cand%/}
      name=${name##*/}
      case "$name" in
        [0-9][0-9][0-9][0-9]-0[1-9]-*|[0-9][0-9][0-9][0-9]-1[0-2]-*) stem=${name#????-??-} ;;
        *) stem=$name ;;
      esac
      if [ "$name" = "$SLUG" ] || [ "$stem" = "$SLUG" ]; then
        SPEC_HITS=$(( SPEC_HITS + 1 ))
        SPEC_DIR=${cand%/}
        rel=${cand%/}
        rel=${rel#"$WT"/}
        if [ -z "$SPEC_HIT_LIST" ]; then SPEC_HIT_LIST="$rel"; else SPEC_HIT_LIST="$SPEC_HIT_LIST
$rel"; fi
      fi
    done
    if [ "$SPEC_HITS" -gt 1 ]; then
      SPEC_DIR=""
      SPEC_AMBIGUOUS=1
    fi
  fi
fi

# 1. spec tasks.md unchecked boxes
if [ -z "$SLUG" ]; then
  echo "spec_tasks=not_checked  (reason: --slug not supplied; the slug is never"
  echo "spec_tasks=not_checked  guessed from the directory or branch name)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "spec_tasks_not_checked"
elif [ "$SPEC_AMBIGUOUS" -eq 1 ]; then
  echo "spec_tasks=not_checked  (reason: slug '$SLUG' matches more than one archived"
  echo "spec_tasks=not_checked  spec directory; remove the duplicate, never guess:"
  printf '%s\n' "$SPEC_HIT_LIST" | while IFS= read -r hit; do
    echo "spec_tasks=not_checked    candidate: $hit"
  done
  echo "spec_tasks=not_checked  )"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "spec_dir_ambiguous"
elif [ -z "$SPEC_DIR" ]; then
  echo "spec_tasks=not_checked  (reason: slug '$SLUG' does not resolve to an existing"
  echo "spec_tasks=not_checked  docs/specs/active/<slug> or docs/specs/archive/ directory"
  echo "spec_tasks=not_checked  named <slug> or <YYYY-MM>-<slug>; a typo must never be"
  echo "spec_tasks=not_checked  reported as 0)"
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
elif [ "$SPEC_AMBIGUOUS" -eq 1 ]; then
  echo "deferred_markers=not_checked  (reason: slug '$SLUG' matches more than one"
  echo "deferred_markers=not_checked  archived spec directory; see spec_tasks above)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "spec_dir_ambiguous"
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

# 3. Legacy .copilot-tracking plans: old Copilot scratch (gitignored, inside the
#    worktree). Read-only check; nothing new is written there, and new work is
#    tracked in the spec's tasks.md (source 1).
PLAN_DIR="$WT/.copilot-tracking/plans"
if [ -d "$PLAN_DIR" ]; then
  n2=0
  while IFS= read -r c; do
    c=$( count_or_zero "$c" )
    n2=$(( n2 + c ))
  done <<EOF
$( grep -rhcE '^[[:space:]]*[-*] \[ \]' "$PLAN_DIR" 2>/dev/null )
EOF
  echo "legacy_tracking_plans=$n2  (legacy .copilot-tracking/plans/*.md unchecked items; read-only)"
  UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + n2 ))
else
  echo "legacy_tracking_plans=0  (no legacy .copilot-tracking/plans directory)"
fi

# 4. TODO / FIXME introduced by the campaign's own commits.
#    The range is <base>..<head>, never origin/main...HEAD: after the V-M-D push
#    HEAD equals origin/main, so the three-dot form is always empty and would
#    report a false zero for every campaign that shipped.
#
#    A campaign pushed in several rounds has other campaigns' commits between its
#    rounds. One span from the first base to the last head would count those
#    commits' added lines as this campaign's, so the range is given per push with
#    --range. Together with --base/--head, which then names the FULL range, the
#    audit can also list the commits that no segment covers instead of silently
#    dropping them: another campaign's work, or a push the caller left out.
#    --base/--head alone is exactly one segment, kept for compatibility.
#
#    Every figure below comes from one routine. The commits of each range are
#    listed with rev-list and their diffs are read in a single log pass, so a
#    commit that sits in two segments is counted once, and the lines a person is
#    shown are the very lines the totals were made from.

NL='
'
TAB=$( printf '\t' )

# resolve_range <base> <end> sets SEG_STATUS (ok|unresolved), SEG_LIST (the full
# SHAs of base..end, newest first, one per line) and SEG_N. Both ends are peeled
# to a commit, so a tree or a blob cannot pass for a range. git's own exit
# status is checked as well: counting through a pipe alone would turn a failed
# command into a clean zero, which is the one answer this gate must never invent.
resolve_range() {
  SEG_STATUS="unresolved"
  SEG_LIST=""
  SEG_N=0
  git -C "$WT" rev-parse --verify --quiet "${1}^{commit}" >/dev/null 2>&1 || return 0
  git -C "$WT" rev-parse --verify --quiet "${2}^{commit}" >/dev/null 2>&1 || return 0
  SEG_LIST=$( git -C "$WT" rev-list --topo-order "$1..$2" -- 2>/dev/null ) || { SEG_LIST=""; return 0; }
  SEG_N=$( printf '%s\n' "$SEG_LIST" | grep -c . )
  SEG_N=$( count_or_zero "$SEG_N" )
  SEG_STATUS="ok"
}

# collect_hits <shas> sets HITS to one "sha<TAB>path<TAB>line" record per added
# marker line in those commits, and HITS_OK to 0 when git could not be read. The
# match is the one the totals have always used: a line that starts with '+' and
# carries a marker word. --no-walk lists each commit exactly once.
collect_hits() {
  HITS=""
  HITS_OK=1
  [ -n "$1" ] || return 0
  hits_raw=$( printf '%s\n' "$1" | git -C "$WT" -c core.quotePath=false log \
      --no-walk=unsorted --stdin --no-ext-diff --no-textconv \
      --src-prefix=a/ --dst-prefix=b/ --format='@@COMMIT %H' -p 2>/dev/null ) \
    || { HITS_OK=0; return 0; }
  hits_stream=$( printf '%s\n' "$hits_raw" \
    | grep -E "^(@@COMMIT |\+\+\+ b/|\+.*($MARKER_PATTERN))" )
  hits_cur_sha=""
  hits_cur_path=""
  while IFS= read -r hits_line; do
    case "$hits_line" in
      "@@COMMIT "*)
        hits_cur_sha="${hits_line#@@COMMIT }"
        hits_cur_path=""
        continue ;;
      "+++ b/"*)
        hits_cur_path="${hits_line#+++ b/}" ;;
    esac
    if [[ "$hits_line" =~ $MARKER_PATTERN ]]; then
      HITS="${HITS}${hits_cur_sha}${TAB}${hits_cur_path}${TAB}${hits_line#+}${NL}"
    fi
  done <<EOF
$hits_stream
EOF
}

# hits_in <shas> prints how many records in HITS belong to the given commits.
hits_in() {
  hi_n=0
  while IFS="$TAB" read -r hi_sha _; do
    [ -n "$hi_sha" ] || continue
    case "${NL}${1}${NL}" in
      *"${NL}${hi_sha}${NL}"*) hi_n=$(( hi_n + 1 )) ;;
    esac
  done <<EOF
$HITS
EOF
  printf '%s' "$hi_n"
}

# commit_meta <sha> sets CM_SHORT, CM_DATE, CM_AUTHOR and CM_SUBJECT.
commit_meta() {
  cm_raw=$( git -C "$WT" -c core.quotePath=false log -1 \
      --format='%h%x09%ad%x09%an%x09%s' --date='format:%Y-%m-%d %H:%M %z' "$1" -- 2>/dev/null ) \
    || cm_raw=""
  CM_SHORT="${cm_raw%%"$TAB"*}"
  cm_rest="${cm_raw#*"$TAB"}"
  CM_DATE="${cm_rest%%"$TAB"*}"
  cm_rest="${cm_rest#*"$TAB"}"
  CM_AUTHOR="${cm_rest%%"$TAB"*}"
  CM_SUBJECT="${cm_rest#*"$TAB"}"
  if [ -z "$CM_SHORT" ]; then
    CM_SHORT=$( printf '%.8s' "$1" )
    CM_DATE="date unavailable"
    CM_AUTHOR="author unavailable"
    CM_SUBJECT="(subject unavailable)"
  fi
}

# commit_label <sha> prints "<short-sha>  <date>  <subject>". A bare SHA tells a
# reader nothing, so no line of this report carries one without its subject.
commit_label() {
  commit_meta "$1"
  printf '%s  %s  %s' "$CM_SHORT" "$CM_DATE" "$CM_SUBJECT"
}

# describe_uncovered <sha> prints the block a person needs to decide who a
# commit belongs to: subject, author, date, files, the added lines themselves,
# and a hint. The hint only says whether the slug appears in the subject or a
# path. It is not a verdict; the decision stays with a person.
describe_uncovered() {
  commit_meta "$1"
  printf 'uncovered_commit=%s  %s  %s  %s\n' "$CM_SHORT" "$CM_DATE" "$CM_AUTHOR" "$CM_SUBJECT"
  du_subject="$CM_SUBJECT"
  du_files=$( git -C "$WT" -c core.quotePath=false diff-tree --no-commit-id --name-only -r --root "$1" 2>/dev/null )
  du_total=$( printf '%s\n' "$du_files" | grep -c . )
  du_total=$( count_or_zero "$du_total" )
  du_list=""
  du_i=0
  while IFS= read -r du_f; do
    [ -n "$du_f" ] || continue
    du_i=$(( du_i + 1 ))
    [ "$du_i" -le 5 ] || continue
    if [ -z "$du_list" ]; then du_list="$du_f"; else du_list="$du_list, $du_f"; fi
  done <<EOF
$du_files
EOF
  if [ "$du_total" -gt 5 ]; then du_list="$du_list, +$(( du_total - 5 ))"; fi
  printf '  files(%s): %s\n' "$du_total" "$du_list"
  while IFS= read -r du_rec; do
    case "$du_rec" in
      "$1$TAB"*) ;;
      *) continue ;;
    esac
    du_rest="${du_rec#"$1$TAB"}"
    du_path="${du_rest%%"$TAB"*}"
    du_text="${du_rest#*"$TAB"}"
    du_text="${du_text#"${du_text%%[![:space:]]*}"}"
    if [ "${#du_text}" -gt 150 ]; then du_text="${du_text:0:150}..."; fi
    [ -n "$du_path" ] || du_path="(file unknown)"
    printf '  hit: %s: %s\n' "$du_path" "$du_text"
  done <<EOF
$HITS
EOF
  if [ -z "$SLUG" ]; then
    echo "  attribution_hint: unavailable (--slug not supplied); a hint only, not a verdict"
  else
    du_in_subject="no"
    du_in_paths="no"
    printf '%s' "$du_subject" | grep -qiF -e "$SLUG" && du_in_subject="yes"
    printf '%s\n' "$du_files" | grep -qiF -e "$SLUG" && du_in_paths="yes"
    echo "  attribution_hint: slug '$SLUG' in subject=$du_in_subject, in paths=$du_in_paths; a hint only, not a verdict"
  fi
}

if [ -n "$RANGES" ]; then
  # 4a. The full range, when --base/--head came with --range.
  FULL_STATUS="not_supplied"
  FULL_LIST=""
  FULL_N=0
  FULL_END=""
  if [ -n "$BASE" ]; then
    FULL_END="$HEAD_SHA"
    [ -n "$FULL_END" ] || FULL_END="HEAD"
    resolve_range "$BASE" "$FULL_END"
    if [ "$SEG_STATUS" != "ok" ]; then
      FULL_STATUS="unresolved"
    elif [ "$SEG_N" -eq 0 ]; then
      FULL_STATUS="empty"
    else
      FULL_STATUS="ok"
      FULL_LIST="$SEG_LIST"
      FULL_N="$SEG_N"
    fi
  fi

  # 4b. Which segments are usable, and the distinct commits they cover.
  RT_N=0
  RT_UNRESOLVED=0
  RT_EMPTY=0
  RT_LISTED=0
  UNION=""
  UNION_N=0
  while IFS= read -r seg; do
    [ -n "$seg" ] || continue
    RT_N=$(( RT_N + 1 ))
    resolve_range "${seg%%..*}" "${seg#*..}"
    if [ "$SEG_STATUS" != "ok" ]; then
      RT_UNRESOLVED=$(( RT_UNRESOLVED + 1 ))
      continue
    fi
    if [ "$SEG_N" -eq 0 ]; then
      # One push always delivers at least one commit, so a segment holding none
      # is a base and head written the wrong way round (or equal), not a clean
      # campaign. There is deliberately no ancestry test: a base that is not an
      # ancestor of head is a legitimate diverged range and must still count.
      RT_EMPTY=$(( RT_EMPTY + 1 ))
      continue
    fi
    RT_LISTED=$(( RT_LISTED + SEG_N ))
    while IFS= read -r sha; do
      [ -n "$sha" ] || continue
      case "${NL}${UNION}${NL}" in
        *"${NL}${sha}${NL}"*) ;;
        *) UNION="${UNION}${sha}${NL}"; UNION_N=$(( UNION_N + 1 )) ;;
      esac
    done <<EOF
$SEG_LIST
EOF
  done <<EOF
$RANGES
EOF
  RT_BAD=$(( RT_UNRESOLVED + RT_EMPTY ))

  # 4c. One pass over the diffs of every commit that matters.
  RT_SCOPE="$UNION"
  if [ "$FULL_STATUS" = "ok" ]; then RT_SCOPE="${RT_SCOPE}${FULL_LIST}${NL}"; fi
  collect_hits "$RT_SCOPE"

  if [ "$HITS_OK" -ne 1 ]; then
    echo "range_todo=not_checked  (reason: git could not read the diffs of the commits in range)"
    NOT_CHECKED=$(( NOT_CHECKED + 1 ))
    add_undet "range_todo_unresolvable"
  else
    # 4d. Per-segment lines, then the total.
    RT_LINES=""
    RT_I=0
    while IFS= read -r seg; do
      [ -n "$seg" ] || continue
      RT_I=$(( RT_I + 1 ))
      resolve_range "${seg%%..*}" "${seg#*..}"
      if [ "$SEG_STATUS" != "ok" ]; then
        RT_LINES="${RT_LINES}range_todo_segment_${RT_I}=not_checked  (${seg}; reason: base or head does not resolve here)${NL}"
      elif [ "$SEG_N" -eq 0 ]; then
        RT_LINES="${RT_LINES}range_todo_segment_${RT_I}=not_checked  (${seg}; reason: holds no commit, base and head may be swapped or equal)${NL}"
      else
        seg_hits=$( hits_in "$SEG_LIST" )
        seg_detail="commits=${SEG_N}"
        if [ "$FULL_STATUS" = "ok" ]; then
          seg_outside=0
          while IFS= read -r sha; do
            [ -n "$sha" ] || continue
            case "${NL}${FULL_LIST}${NL}" in
              *"${NL}${sha}${NL}"*) ;;
              *) seg_outside=$(( seg_outside + 1 )) ;;
            esac
          done <<EOF
$SEG_LIST
EOF
          seg_detail="${seg_detail}; outside_full_range=${seg_outside}"
        fi
        seg_first=$( printf '%s\n' "$SEG_LIST" | sed -n '$p' )
        seg_last=$( printf '%s\n' "$SEG_LIST" | sed -n '1p' )
        RT_LINES="${RT_LINES}range_todo_segment_${RT_I}=${seg_hits}  (${seg}; ${seg_detail})${NL}"
        RT_LINES="${RT_LINES}range_todo_segment_${RT_I}_first=$( commit_label "$seg_first" )${NL}"
        RT_LINES="${RT_LINES}range_todo_segment_${RT_I}_last=$( commit_label "$seg_last" )${NL}"
      fi
    done <<EOF
$RANGES
EOF
    RT_SUM=$( hits_in "$UNION" )
    if [ "$RT_BAD" -eq 0 ]; then
      echo "range_todo=$RT_SUM  (added lines matching $MARKER_PATTERN, summed over $RT_N segment(s), $UNION_N distinct commit(s))"
    else
      # A known blocker is still a blocker: the lines already found in the
      # usable segments stay in unhandled_total, so a clearly dirty campaign is
      # not downgraded to "ask the user" by an unrelated unusable segment.
      echo "range_todo=not_checked  (reason: $RT_BAD of $RT_N segment(s) cannot be used:"
      echo "range_todo=not_checked  $RT_UNRESOLVED do not resolve here, $RT_EMPTY hold no commit;"
      echo "range_todo=not_checked  $RT_SUM matching line(s) in the usable segments stay in"
      echo "range_todo=not_checked  unhandled_total, but the total is incomplete)"
      NOT_CHECKED=$(( NOT_CHECKED + 1 ))
      [ "$RT_UNRESOLVED" -eq 0 ] || add_undet "range_todo_unresolvable"
      [ "$RT_EMPTY" -eq 0 ] || add_undet "range_todo_empty_segment"
    fi
    printf '%s' "$RT_LINES"
    RT_OVERLAP=$(( RT_LISTED - UNION_N ))
    if [ "$RT_OVERLAP" -gt 0 ]; then
      echo "range_todo_segments_overlap=$RT_OVERLAP  (commit(s) inside more than one segment, counted once)"
    fi
    UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + RT_SUM ))

    # 4e. What the segments left uncovered. Those lines are NOT added to
    #     unhandled_total: they may belong to another campaign. They still keep
    #     the verdict at UNDETERMINED until a person has attributed them.
    if [ "$FULL_STATUS" = "not_supplied" ]; then
      echo "range_todo_uncovered_commits=not_checked  (reason: no full range; give --base/--head with --range"
      echo "range_todo_uncovered_commits=not_checked  so that a segment left out can be detected)"
      echo "range_todo_uncovered_hits=not_checked"
      [ "$RT_BAD" -gt 0 ] || NOT_CHECKED=$(( NOT_CHECKED + 1 ))
      add_undet "range_todo_uncovered_not_checked"
    elif [ "$FULL_STATUS" != "ok" ]; then
      echo "range_todo_full_range=$BASE..$FULL_END  (reason: $FULL_STATUS; it does not resolve here or holds no commit)"
      echo "range_todo_uncovered_commits=not_checked  (reason: the full range cannot be used)"
      echo "range_todo_uncovered_hits=not_checked"
      [ "$RT_BAD" -gt 0 ] || NOT_CHECKED=$(( NOT_CHECKED + 1 ))
      add_undet "range_todo_full_range_unusable"
    elif [ "$RT_BAD" -gt 0 ]; then
      echo "range_todo_full_range=$BASE..$FULL_END  (commits=$FULL_N)"
      echo "range_todo_uncovered_commits=not_checked  (reason: $RT_BAD segment(s) cannot be used, so coverage"
      echo "range_todo_uncovered_commits=not_checked  cannot be computed)"
      echo "range_todo_uncovered_hits=not_checked"
    else
      UNCOV=""
      UNCOV_N=0
      while IFS= read -r sha; do
        [ -n "$sha" ] || continue
        case "${NL}${UNION}${NL}" in
          *"${NL}${sha}${NL}"*) ;;
          *) UNCOV="${sha}${NL}${UNCOV}"; UNCOV_N=$(( UNCOV_N + 1 )) ;;
        esac
      done <<EOF
$FULL_LIST
EOF
      UNCOV_HITS=$( hits_in "$UNCOV" )
      UNCOV_HIT_COMMITS=0
      while IFS= read -r sha; do
        [ -n "$sha" ] || continue
        [ "$( hits_in "$sha" )" -gt 0 ] && UNCOV_HIT_COMMITS=$(( UNCOV_HIT_COMMITS + 1 ))
      done <<EOF
$UNCOV
EOF
      echo "range_todo_full_range=$BASE..$FULL_END  (commits=$FULL_N)"
      echo "range_todo_uncovered_commits=$UNCOV_N  (commits in the full range that no segment covers)"
      echo "range_todo_uncovered_hits=$UNCOV_HITS  (added marker lines in $UNCOV_HIT_COMMITS of them; not counted in unhandled_total)"
      if [ "$UNCOV_HITS" -gt 0 ]; then
        add_undet "range_todo_uncovered_hits"
        while IFS= read -r sha; do
          [ -n "$sha" ] || continue
          if [ "$( hits_in "$sha" )" -gt 0 ]; then describe_uncovered "$sha"; fi
        done <<EOF
$UNCOV
EOF
      fi
    fi
  fi
elif [ -z "$BASE" ]; then
  echo "range_todo=not_checked  (reason: neither --range nor --base supplied by the V-M-D handoff;"
  echo "range_todo=not_checked  origin/main...HEAD is refused because it is empty"
  echo "range_todo=not_checked  after the push and would report a false zero)"
  NOT_CHECKED=$(( NOT_CHECKED + 1 ))
  add_undet "range_todo_not_checked"
else
  END="$HEAD_SHA"
  [ -n "$END" ] || END="HEAD"
  resolve_range "$BASE" "$END"
  if [ "$SEG_STATUS" != "ok" ]; then
    echo "range_todo=not_checked  (reason: --base or --head does not resolve here)"
    NOT_CHECKED=$(( NOT_CHECKED + 1 ))
    add_undet "range_todo_unresolvable"
  else
    collect_hits "$SEG_LIST"
    if [ "$HITS_OK" -eq 1 ]; then
      n=$( hits_in "$SEG_LIST" )
      echo "range_todo=$n  (added lines matching $MARKER_PATTERN in $BASE..$END)"
      UNHANDLED_TOTAL=$(( UNHANDLED_TOTAL + n ))
    else
      echo "range_todo=not_checked  (reason: git could not read the diffs of the commits in range)"
      NOT_CHECKED=$(( NOT_CHECKED + 1 ))
      add_undet "range_todo_unresolvable"
    fi
  fi
fi

# 5. open GitHub issues naming the slug, minus the auto-generated daily reminders
#    (ISSUE_EXCLUDE_LABEL, defined with the other settings above).
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
  if issues=$( cd "$WT" && gh issue list --state open --search "$SLUG -label:$ISSUE_EXCLUDE_LABEL" --limit 100 --json number 2>/dev/null ); then
    n=$( printf '%s' "$issues" | grep -o '"number"' | grep -c . )
    n=$( count_or_zero "$n" )
    echo "open_issues=$n  (open issues matching '$SLUG', excluding label:$ISSUE_EXCLUDE_LABEL)"
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

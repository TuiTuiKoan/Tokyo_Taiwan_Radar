"""Behaviour tests for scripts/campaign-closeout-audit.sh, source 4 and source 5.

Every test builds a throwaway git repository whose history interleaves a
campaign's own commits with upstream commits, one of which carries work markers,
then runs the real script against it. Nothing here touches the network or
~/.copilot: GitHub is skipped or replaced by a stub on PATH, and the session
state directory is an empty temporary one.

The audit counts two marker words on ADDED lines. They are assembled from halves
below so that this file's own added lines never contain them.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "campaign-closeout-audit.sh"

MARK_A = "TO" + "DO"
MARK_B = "FIX" + "ME"
PATTERN = f"{MARK_A}|{MARK_B}"

SLUG = "demo-campaign"
RUN_TIMEOUT = 60
HANG_TIMEOUT = 15
MISSING_SHA = "0" * 40
LONG_FILLER = "x" * 300
UPSTREAM_EXTRA_FILES = 6
UPSTREAM_SUBJECT = "another campaign lands"
QUIET_SUBJECT = "another campaign tidies up"
DATE_RE = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} [+-]\d{4}"


def git_env(home: Path) -> dict[str, str]:
    """Environment that cannot see the developer's git config or any outer repo."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Audit Test",
        GIT_AUTHOR_EMAIL="audit@example.invalid",
        GIT_COMMITTER_NAME="Audit Test",
        GIT_COMMITTER_EMAIL="audit@example.invalid",
    )
    return env


def git(repo: Path, env: dict[str, str], *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return done.stdout.strip()


def marker_lines(word: str, count: int) -> str:
    return "".join(f"note {word} {i}\n" for i in range(count))


@dataclass(frozen=True)
class History:
    repo: Path
    base: str  # origin/main tip before the first push
    first: str  # head of the campaign's first push
    upstream: str  # another campaign's commit that adds marker lines
    quiet: str  # another campaign's later commit, adding none; the second push's base
    second: str  # head of the campaign's second push, also HEAD
    side: str  # a commit forked from base that is not reachable from second
    foreign: int  # marker lines the upstream commit adds
    own: int  # marker lines the campaign's two segments add together

    def short(self, sha: str) -> str:
        return sha[:7]


def build_history(root: Path, env: dict[str, str], own_first: int, own_second: int) -> History:
    """base -> campaign(first) -> upstream -> quiet -> campaign(second), all linear."""
    repo = root / "audit repo"  # a space in the path, as in this project
    spec = repo / "docs" / "specs" / "active" / SLUG
    spec.mkdir(parents=True)
    git(repo, env, "init", "-q")
    (spec / "tasks.md").write_text("- [x] everything finished\n")

    def commit(message: str) -> str:
        git(repo, env, "add", "-A")
        git(repo, env, "commit", "-q", "-m", message)
        return git(repo, env, "rev-parse", "HEAD")

    base = commit("base")

    with (repo / "campaign.md").open("a") as handle:
        handle.write("plain campaign note\n" + marker_lines(MARK_A, own_first))
    first = commit("campaign first push")

    # Three marker lines, one of them long enough to be cut for display, spread
    # over a commit that touches seven files so the file list has to be cut too.
    with (repo / "upstream.md").open("a") as handle:
        handle.write(marker_lines(MARK_A, 1) + marker_lines(MARK_B, 1))
        handle.write(f"padding {MARK_A} {LONG_FILLER}\n")
        handle.write("plain upstream note\n")
    for index in range(1, UPSTREAM_EXTRA_FILES + 1):
        (repo / f"extra_{index}.md").write_text("plain extra file\n")
    upstream = commit(UPSTREAM_SUBJECT)

    (repo / "quiet.md").write_text("nothing to see\n")
    quiet = commit(QUIET_SUBJECT)

    with (repo / "campaign.md").open("a") as handle:
        handle.write("another plain note\n" + marker_lines(MARK_B, own_second))
    second = commit("campaign second push")

    # A commit forked from base, so it is not reachable from `second`. It makes a
    # diverged range (second..side) whose base is not an ancestor of its head.
    branch = git(repo, env, "rev-parse", "--abbrev-ref", "HEAD")
    git(repo, env, "checkout", "-q", "--detach", base)
    (repo / "side.md").write_text(marker_lines(MARK_A, 1))
    side = commit("work forked from base")
    git(repo, env, "checkout", "-q", branch)

    return History(
        repo, base, first, upstream, quiet, second, side,
        foreign=3, own=own_first + own_second,
    )


@pytest.fixture(scope="module")
def env(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    return git_env(tmp_path_factory.mktemp("home"))


@pytest.fixture(scope="module")
def state_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("session-state")


@pytest.fixture(scope="module")
def clean(tmp_path_factory: pytest.TempPathFactory, env: dict[str, str]) -> History:
    """The campaign's own segments hold no marker; only the upstream commit does."""
    return build_history(tmp_path_factory.mktemp("clean"), env, 0, 0)


@pytest.fixture(scope="module")
def dirty(tmp_path_factory: pytest.TempPathFactory, env: dict[str, str]) -> History:
    """The campaign itself adds one marker in its first push and two in its second."""
    return build_history(tmp_path_factory.mktemp("dirty"), env, 1, 2)


@dataclass(frozen=True)
class Audit:
    code: int
    out: str
    err: str

    def field(self, key: str) -> str | None:
        """First value of a `key=value` line, or None when the key is absent."""
        match = re.search(rf"^{re.escape(key)}=(\S+)", self.out, re.MULTILINE)
        return match.group(1) if match else None

    def line(self, key: str) -> str:
        match = re.search(rf"^{re.escape(key)}=.*$", self.out, re.MULTILINE)
        assert match, f"{key} missing from output:\n{self.out}"
        return match.group(0)

    def lines(self, key: str) -> list[str]:
        return re.findall(rf"^{re.escape(key)}=.*$", self.out, re.MULTILINE)

    @property
    def verdict(self) -> str:
        return self.field("verdict") or ""


def run_script(args: list[str], env: dict[str, str], timeout: int = RUN_TIMEOUT) -> Audit:
    done = subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    return Audit(done.returncode, done.stdout, done.stderr)


def audit(
    history: History,
    state_dir: Path,
    env: dict[str, str],
    *extra: str,
    skip_issues: bool = True,
    slug: str | None = SLUG,
) -> Audit:
    args = ["--worktree", str(history.repo)]
    if slug is not None:
        args += ["--slug", slug]
    args += [
        "--self-session", "test-session",
        "--session-state-dir", str(state_dir),
        *extra,
    ]
    if skip_issues:
        args.append("--skip-issues")
    return run_script(args, env)


def segments(history: History) -> list[str]:
    """The campaign's two pushes, exactly as a V-M-D handoff would carry them."""
    return [
        "--range", f"{history.base}..{history.first}",
        "--range", f"{history.quiet}..{history.second}",
    ]


def full_range(history: History) -> list[str]:
    return ["--base", history.base, "--head", history.second]


# --- source 4: segments ------------------------------------------------------


def test_segments_alone_report_zero_but_leave_coverage_unchecked(clean, state_dir, env):
    result = audit(clean, state_dir, env, *segments(clean))

    assert result.field("range_todo") == "0"
    assert result.field("range_todo_segment_1") == "0"
    assert result.field("range_todo_segment_2") == "0"
    assert "commits=1" in result.line("range_todo_segment_1")
    assert "commits=1" in result.line("range_todo_segment_2")
    assert result.field("unhandled_total") == "0"
    # Without a full range a segment that was left out could not be noticed.
    assert result.field("range_todo_uncovered_commits") == "not_checked"
    assert result.field("range_todo_uncovered_hits") == "not_checked"
    assert "range_todo_uncovered_not_checked" in result.verdict
    assert result.code == 20
    assert git(clean.repo, env, "status", "--porcelain") == ""


def test_segments_that_cover_the_full_range_leave_only_the_skipped_source(clean, state_dir, env):
    result = audit(
        clean, state_dir, env,
        "--base", clean.base, "--head", clean.first,
        "--range", f"{clean.base}..{clean.first}",
    )

    assert result.field("range_todo") == "0"
    assert result.field("range_todo_uncovered_commits") == "0"
    assert result.field("range_todo_uncovered_hits") == "0"
    assert result.verdict == "UNDETERMINED:issues_not_checked"
    assert result.code == 20


def test_one_span_over_an_upstream_commit_counts_its_markers(clean, state_dir, env):
    result = audit(clean, state_dir, env, "--base", clean.base, "--head", clean.second)

    assert result.field("range_todo") == str(clean.foreign)
    # Single-segment output keeps its original shape and adds nothing to it.
    assert result.line("range_todo") == (
        f"range_todo={clean.foreign}  (added lines matching {PATTERN} "
        f"in {clean.base}..{clean.second})"
    )
    assert "range_todo_uncovered" not in result.out
    assert "range_todo_segment" not in result.out
    assert result.verdict == "HOLD:unhandled_work"
    assert result.code == 10


def test_single_range_flag_over_the_same_span_is_also_positive(clean, state_dir, env):
    """The contamination comes from the span, not from which flag carries it."""
    result = audit(clean, state_dir, env, "--range", f"{clean.base}..{clean.second}")

    assert result.field("range_todo") == str(clean.foreign)
    assert result.field("range_todo_segment_1") == str(clean.foreign)
    assert "commits=4" in result.line("range_todo_segment_1")
    assert result.code == 10


def test_segments_sum_the_campaigns_own_markers_and_leave_out_the_upstream(dirty, state_dir, env):
    result = audit(dirty, state_dir, env, *full_range(dirty), *segments(dirty))
    span = audit(dirty, state_dir, env, *full_range(dirty))

    assert result.field("range_todo_segment_1") == "1"
    assert result.field("range_todo_segment_2") == "2"
    assert result.field("range_todo") == str(dirty.own)
    assert result.field("unhandled_total") == str(dirty.own)
    # The upstream lines are reported, but they are not this campaign's total.
    assert result.field("range_todo_uncovered_hits") == str(dirty.foreign)
    assert result.verdict.startswith("HOLD:unhandled_work")
    assert "range_todo_uncovered_hits" in (result.field("also_undetermined") or "")
    # The single span is exactly the sum plus what the upstream commit brought.
    assert span.field("range_todo") == str(dirty.own + dirty.foreign)


def test_each_segment_names_its_first_and_last_commit(clean, state_dir, env):
    result = audit(clean, state_dir, env, "--range", f"{clean.base}..{clean.second}")

    first = result.line("range_todo_segment_1_first")
    last = result.line("range_todo_segment_1_last")
    assert clean.short(clean.first) in first
    assert "campaign first push" in first
    assert clean.short(clean.second) in last
    assert "campaign second push" in last
    for label in (first, last):
        assert re.search(DATE_RE, label)


def test_a_commit_in_two_segments_is_counted_once(dirty, state_dir, env):
    wide = f"{dirty.base}..{dirty.second}"
    narrow = f"{dirty.base}..{dirty.first}"  # entirely inside the wide one

    result = audit(dirty, state_dir, env, "--range", wide, "--range", narrow)

    assert result.field("range_todo") == str(dirty.own + dirty.foreign)
    assert result.field("range_todo_segment_1") == str(dirty.own + dirty.foreign)
    assert result.field("range_todo_segment_2") == "1"
    assert result.field("range_todo_segments_overlap") == "1"
    assert "4 distinct commit(s)" in result.line("range_todo")


@pytest.mark.parametrize("missing_first", [True, False], ids=["first-missing", "second-missing"])
def test_an_unresolvable_segment_is_not_checked_never_zero(clean, state_dir, env, missing_first):
    good = f"{clean.base}..{clean.first}"
    bad = f"{MISSING_SHA}..{clean.second}"
    ranges = [bad, good] if missing_first else [good, bad]
    args: list[str] = []
    for value in ranges:
        args += ["--range", value]

    result = audit(clean, state_dir, env, *args)

    assert result.field("range_todo") == "not_checked"
    assert not re.search(r"^range_todo=0\b", result.out, re.MULTILINE)
    assert result.field("range_todo_segment_1") == ("not_checked" if missing_first else "0")
    assert result.field("range_todo_segment_2") == ("0" if missing_first else "not_checked")
    assert "range_todo_unresolvable" in result.verdict
    assert result.code == 20


def test_an_unresolvable_segment_does_not_hide_a_confirmed_blocker(dirty, state_dir, env):
    result = audit(
        dirty, state_dir, env,
        "--range", f"{dirty.base}..{dirty.first}",
        "--range", f"{MISSING_SHA}..{dirty.second}",
    )

    assert result.field("range_todo") == "not_checked"
    assert result.field("unhandled_total") == "1"
    # A hard blocker decides on its own; the unknown is reported beside it.
    assert result.verdict.startswith("HOLD:unhandled_work")
    assert "range_todo_unresolvable" in (result.field("also_undetermined") or "")
    assert result.code == 10


@pytest.mark.parametrize("shape", ["swapped", "equal"])
def test_a_segment_holding_no_commit_is_not_checked_never_zero(clean, state_dir, env, shape):
    """One push delivers at least one commit, so an empty segment is a mistake."""
    good = f"{clean.base}..{clean.first}"
    empty = f"{clean.second}..{clean.base}" if shape == "swapped" else f"{clean.first}..{clean.first}"

    result = audit(clean, state_dir, env, "--range", good, "--range", empty)

    assert result.field("range_todo") == "not_checked"
    assert not re.search(r"^range_todo=0\b", result.out, re.MULTILINE)
    assert result.field("range_todo_segment_1") == "0"
    assert result.field("range_todo_segment_2") == "not_checked"
    assert "holds no commit" in result.line("range_todo_segment_2")
    assert "range_todo_empty_segment" in result.verdict
    assert result.code == 20


def test_a_diverged_range_is_not_mistaken_for_an_empty_one(clean, state_dir, env):
    """The base is not an ancestor of the head here, and the range still counts."""
    result = audit(clean, state_dir, env, "--range", f"{clean.second}..{clean.side}")

    assert result.field("range_todo") == "1"
    assert "commits=1" in result.line("range_todo_segment_1")
    assert result.verdict.startswith("HOLD:unhandled_work")


def test_the_single_segment_form_keeps_reporting_zero_for_an_empty_range(clean, state_dir, env):
    """The empty-segment rule belongs to --range; --base/--head stays as it was."""
    result = audit(clean, state_dir, env, "--base", clean.first, "--head", clean.first)

    assert result.field("range_todo") == "0"


def test_without_any_range_the_source_is_not_checked(clean, state_dir, env):
    result = audit(clean, state_dir, env)

    assert result.field("range_todo") == "not_checked"
    assert "range_todo_not_checked" in result.verdict


@pytest.mark.parametrize(
    ("which", "expected"),
    [("quiet", "0"), ("base", "3")],
    ids=["after-upstream", "before-upstream"],
)
def test_base_alone_ends_at_the_checkout_head(clean, state_dir, env, which, expected):
    start = getattr(clean, which)

    result = audit(clean, state_dir, env, "--base", start)

    assert result.field("range_todo") == expected


@pytest.mark.parametrize("end", ["base", "head"])
@pytest.mark.parametrize("spelling", ["tree", "blob"])
def test_an_object_that_is_not_a_commit_is_not_a_range(clean, state_dir, env, end, spelling):
    """A tree or blob end must never produce a number.

    Passed straight to git log, a non-commit base is ignored and the whole
    history is counted, while a non-commit head makes the log fail and leaves a
    clean-looking zero. Peeling both ends to a commit turns both into not_checked.
    """
    odd = "HEAD^{tree}" if spelling == "tree" else f"HEAD:docs/specs/active/{SLUG}/tasks.md"
    base, head = (odd, "HEAD") if end == "base" else (clean.base, odd)

    single = audit(clean, state_dir, env, "--base", base, "--head", head)
    multi = audit(clean, state_dir, env, "--range", f"{base}..{head}")

    assert single.field("range_todo") == "not_checked"
    assert multi.field("range_todo") == "not_checked"
    assert multi.field("range_todo_segment_1") == "not_checked"


# --- source 4: what the segments leave uncovered -----------------------------


def test_uncovered_commits_are_listed_with_what_a_person_needs(clean, state_dir, env):
    result = audit(clean, state_dir, env, *full_range(clean), *segments(clean))

    assert result.field("range_todo") == "0"
    assert result.field("range_todo_uncovered_commits") == "2"
    assert result.field("range_todo_uncovered_hits") == str(clean.foreign)
    assert "in 1 of them" in result.line("range_todo_uncovered_hits")
    assert f"commits=4" in result.line("range_todo_full_range")
    # Not this campaign's total, but never a clean pass either.
    assert result.field("unhandled_total") == "0"
    assert result.verdict == "UNDETERMINED:range_todo_uncovered_hits,issues_not_checked"
    assert result.code == 20

    # Only the commit that adds marker lines is described; the quiet one is
    # counted above and has nothing to attribute.
    blocks = result.lines("uncovered_commit")
    assert len(blocks) == 1
    assert clean.short(clean.upstream) in blocks[0]
    assert UPSTREAM_SUBJECT in blocks[0]
    assert "Audit Test" in blocks[0]
    assert re.search(DATE_RE, blocks[0])
    assert QUIET_SUBJECT not in result.out

    # Files are cut after five, with the remainder counted.
    files = re.search(r"^  files\((\d+)\): (.*)$", result.out, re.MULTILINE)
    assert files, result.out
    assert files.group(1) == str(UPSTREAM_EXTRA_FILES + 1)
    assert files.group(2).endswith(", +2")
    assert files.group(2).count(",") == 5

    # Every added marker line is shown, with the path it was added to.
    hits = re.findall(r"^  hit: (.*?): (.*)$", result.out, re.MULTILINE)
    assert len(hits) == clean.foreign
    assert {path for path, _ in hits} == {"upstream.md"}
    texts = [text for _, text in hits]
    assert f"note {MARK_A} 0" in texts
    assert f"note {MARK_B} 0" in texts
    long_text = next(text for text in texts if LONG_FILLER[:20] in text)
    assert long_text.endswith("...")
    assert len(long_text) <= 153


@pytest.mark.parametrize(
    ("slug", "in_subject", "in_paths"),
    [("another", "yes", "no"), ("EXTRA_3", "no", "yes"), ("unrelated-slug", "no", "no")],
    ids=["subject", "path-case-insensitive", "neither"],
)
def test_the_attribution_hint_reports_where_the_slug_appears(
    clean, state_dir, env, slug, in_subject, in_paths
):
    result = audit(clean, state_dir, env, *full_range(clean), *segments(clean), slug=slug)

    assert (
        f"attribution_hint: slug '{slug}' in subject={in_subject}, in paths={in_paths}; "
        "a hint only, not a verdict"
    ) in result.out
    # A hint never changes the verdict.
    assert "range_todo_uncovered_hits" in result.verdict
    assert not result.verdict.startswith("HOLD")


def test_the_attribution_hint_says_so_when_no_slug_was_given(clean, state_dir, env):
    result = audit(clean, state_dir, env, *full_range(clean), *segments(clean), slug=None)

    assert "attribution_hint: unavailable (--slug not supplied)" in result.out


def test_a_segment_reaching_outside_the_full_range_is_only_counted(clean, state_dir, env):
    result = audit(
        clean, state_dir, env,
        "--base", clean.quiet, "--head", clean.second,
        "--range", f"{clean.base}..{clean.first}",
        "--range", f"{clean.quiet}..{clean.second}",
    )

    assert "outside_full_range=1" in result.line("range_todo_segment_1")
    assert "outside_full_range=0" in result.line("range_todo_segment_2")
    assert result.field("range_todo") == "0"
    assert result.field("range_todo_uncovered_commits") == "0"
    assert not result.verdict.startswith("HOLD")


def test_an_unresolvable_full_range_makes_coverage_not_checked(clean, state_dir, env):
    result = audit(
        clean, state_dir, env,
        "--base", MISSING_SHA, "--head", clean.second,
        *segments(clean),
    )

    assert result.field("range_todo") == "0"
    assert result.field("range_todo_uncovered_commits") == "not_checked"
    assert result.field("range_todo_uncovered_hits") == "not_checked"
    assert "range_todo_full_range_unusable" in result.verdict
    assert result.lines("uncovered_commit") == []
    assert result.code == 20


def test_an_empty_full_range_makes_coverage_not_checked(clean, state_dir, env):
    result = audit(
        clean, state_dir, env,
        "--base", clean.second, "--head", clean.second,
        *segments(clean),
    )

    assert result.field("range_todo_uncovered_commits") == "not_checked"
    assert "range_todo_full_range_unusable" in result.verdict


def test_coverage_is_not_computed_when_a_segment_is_unusable(clean, state_dir, env):
    result = audit(
        clean, state_dir, env,
        *full_range(clean),
        "--range", f"{clean.base}..{clean.first}",
        "--range", f"{MISSING_SHA}..{clean.second}",
    )

    assert result.field("range_todo") == "not_checked"
    assert result.field("range_todo_uncovered_commits") == "not_checked"
    assert result.lines("uncovered_commit") == []
    assert "range_todo_unresolvable" in result.verdict


# --- argument handling -------------------------------------------------------


def test_base_and_head_with_range_are_the_full_range(clean, state_dir, env):
    result = audit(clean, state_dir, env, *full_range(clean), *segments(clean))

    assert result.code != 2
    assert f"{clean.base}..{clean.second}" in result.line("range_todo_full_range")


def test_head_without_base_is_refused_when_range_is_used(clean, state_dir, env):
    result = audit(clean, state_dir, env, "--range", f"{clean.base}..{clean.first}", "--head", clean.second)

    assert result.code == 2
    assert "--head needs --base" in result.err
    assert result.out == ""


@pytest.mark.parametrize(
    "value",
    ["abc", "abc...def", "..HEAD", "HEAD.."],
    ids=["no-separator", "three-dot", "empty-base", "empty-head"],
)
def test_a_malformed_range_is_a_usage_error(clean, state_dir, env, value):
    result = audit(clean, state_dir, env, "--range", value)

    assert result.code == 2
    assert "--range" in result.err
    assert "range_todo" not in result.out


@pytest.mark.parametrize(
    "flag",
    [
        "--worktree", "--slug", "--base", "--head", "--range",
        "--self-session", "--session-state-dir", "--idle-threshold",
    ],
)
def test_a_value_flag_without_its_value_stops_instead_of_hanging(env, flag):
    try:
        result = run_script([flag], env, timeout=HANG_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{flag} with no value left the argument loop spinning")

    assert result.code == 2
    assert "requires a value" in result.err


# --- source 5: open issues ---------------------------------------------------


@pytest.fixture
def stub_gh(tmp_path: Path, env: dict[str, str]):
    """A `gh` on PATH that records its arguments and prints canned JSON."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "gh-args.txt"
    stub = bin_dir / "gh"
    stub.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "auth" ]; then exit 0; fi\n'
        'printf \'%s\\n\' "$@" > "$GH_STUB_LOG"\n'
        'printf \'%s\\n\' "$GH_STUB_JSON"\n'
    )
    stub.chmod(0o755)

    def configure(payload: str) -> tuple[dict[str, str], Path]:
        stubbed = dict(env)
        stubbed["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
        stubbed["GH_STUB_LOG"] = str(log)
        stubbed["GH_STUB_JSON"] = payload
        return stubbed, log

    return configure


@pytest.mark.parametrize(
    ("payload", "expected"),
    [("[]", "0"), ('[{"number": 4}, {"number": 9}]', "2")],
    ids=["no-issues", "two-issues"],
)
def test_open_issue_search_excludes_the_daily_review_label(
    clean, state_dir, stub_gh, payload, expected
):
    stubbed, log = stub_gh(payload)

    result = audit(
        clean, state_dir, stubbed,
        "--range", f"{clean.base}..{clean.first}",
        skip_issues=False,
    )

    assert log.exists(), "the stub gh was never called"
    sent = log.read_text().splitlines()
    assert sent[sent.index("--search") + 1] == f"{SLUG} -label:daily-review"
    assert sent[sent.index("--state") + 1] == "open"
    assert result.field("open_issues") == expected
    assert "excluding label:daily-review" in result.line("open_issues")


# --- spec directory resolution (source 0, read by sources 1 and 2) ----------

OPEN_TASK = "- [ ] still open\n- [ ] also open\n"


def build_spec_repo(
    root: Path, env: dict[str, str], dirs: list[str], files: list[str] | None = None
) -> Path:
    """A repo whose docs/specs tree holds the given spec directories, each with
    two unchecked tasks, and the given single-file entries."""
    repo = root / "spec repo"  # a space in the path, as in this project
    for rel in dirs:
        (repo / "docs" / "specs" / rel).mkdir(parents=True)
        (repo / "docs" / "specs" / rel / "tasks.md").write_text(OPEN_TASK)
    for rel in files or []:
        path = repo / "docs" / "specs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(OPEN_TASK)
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, env, "init", "-q")
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-q", "-m", "specs")
    return repo


def spec_audit(repo: Path, state_dir: Path, env: dict[str, str], slug: str) -> Audit:
    return run_script(
        [
            "--worktree", str(repo), "--slug", slug,
            "--self-session", "test-session",
            "--session-state-dir", str(state_dir),
            "--skip-issues",
        ],
        env,
    )


def undetermined_reasons(result: Audit) -> list[str]:
    match = re.search(r"^verdict=UNDETERMINED:(\S+)", result.out, re.MULTILINE)
    return match.group(1).split(",") if match else []


def assert_resolved(result: Audit, rel: str) -> None:
    assert result.field("spec_tasks") == "2", result.out
    assert f"({rel}/tasks.md)" in result.line("spec_tasks")
    assert "spec_dir_unresolved" not in result.out
    assert "spec_dir_ambiguous" not in result.out


def assert_unresolved(result: Audit) -> None:
    assert result.field("spec_tasks") == "not_checked", result.out
    assert result.field("deferred_markers") == "not_checked", result.out
    assert "spec_dir_unresolved" in undetermined_reasons(result)
    assert "spec_dir_ambiguous" not in undetermined_reasons(result)


def test_a_date_prefixed_archive_directory_resolves_by_its_bare_slug(
    tmp_path, state_dir, env
):
    repo = build_spec_repo(tmp_path, env, ["archive/2026-10-demo-campaign"])

    result = spec_audit(repo, state_dir, env, SLUG)

    assert_resolved(result, "docs/specs/archive/2026-10-demo-campaign")


def test_a_bare_archive_directory_still_resolves(tmp_path, state_dir, env):
    repo = build_spec_repo(tmp_path, env, ["archive/demo-campaign"])

    result = spec_audit(repo, state_dir, env, SLUG)

    assert_resolved(result, "docs/specs/archive/demo-campaign")


def test_the_full_dated_name_given_as_the_slug_resolves_too(tmp_path, state_dir, env):
    repo = build_spec_repo(tmp_path, env, ["archive/2026-10-demo-campaign"])

    result = spec_audit(repo, state_dir, env, "2026-10-demo-campaign")

    assert_resolved(result, "docs/specs/archive/2026-10-demo-campaign")


@pytest.mark.parametrize("prefix", ["2026-13-", "2026-00-", "2026-1-", "26-10-"])
def test_an_invalid_month_prefix_is_not_stripped(tmp_path, state_dir, env, prefix):
    repo = build_spec_repo(tmp_path, env, [f"archive/{prefix}demo-campaign"])

    result = spec_audit(repo, state_dir, env, SLUG)

    assert_unresolved(result)


def test_a_source_name_that_only_ends_with_the_slug_does_not_match(
    tmp_path, state_dir, env
):
    """archive/2026-04-source-prtimes must not answer for the slug 'prtimes'."""
    repo = build_spec_repo(tmp_path, env, ["archive/2026-04-source-prtimes"])

    result = spec_audit(repo, state_dir, env, "prtimes")

    assert_unresolved(result)


def test_a_glob_character_in_the_slug_never_widens_the_match(tmp_path, state_dir, env):
    repo = build_spec_repo(
        tmp_path, env,
        ["archive/2026-10-demo-one", "archive/2026-10-demo-two", "archive/demo-three"],
    )

    result = spec_audit(repo, state_dir, env, "demo-*")

    assert_unresolved(result)


def test_a_glob_character_in_the_slug_still_matches_a_literal_directory(
    tmp_path, state_dir, env
):
    repo = build_spec_repo(tmp_path, env, ["archive/2026-10-demo-*", "archive/2026-10-demo-x"])

    result = spec_audit(repo, state_dir, env, "demo-*")

    assert_resolved(result, "docs/specs/archive/2026-10-demo-*")


def test_two_archive_matches_are_ambiguous_and_list_every_candidate(
    tmp_path, state_dir, env
):
    repo = build_spec_repo(
        tmp_path, env, ["archive/2026-09-demo-campaign", "archive/2026-10-demo-campaign"]
    )

    result = spec_audit(repo, state_dir, env, SLUG)

    assert result.field("spec_tasks") == "not_checked", result.out
    assert result.field("deferred_markers") == "not_checked", result.out
    reasons = undetermined_reasons(result)
    assert "spec_dir_ambiguous" in reasons
    assert "spec_dir_unresolved" not in reasons
    assert "docs/specs/archive/2026-09-demo-campaign" in result.out
    assert "docs/specs/archive/2026-10-demo-campaign" in result.out
    candidates = re.findall(r"candidate: (\S.*)$", result.out, re.MULTILINE)
    assert sorted(candidates) == [
        "docs/specs/archive/2026-09-demo-campaign",
        "docs/specs/archive/2026-10-demo-campaign",
    ]


def test_a_dated_and_a_bare_archive_directory_together_are_ambiguous(
    tmp_path, state_dir, env
):
    repo = build_spec_repo(
        tmp_path, env, ["archive/demo-campaign", "archive/2026-10-demo-campaign"]
    )

    result = spec_audit(repo, state_dir, env, SLUG)

    assert "spec_dir_ambiguous" in undetermined_reasons(result)
    assert result.field("spec_tasks") == "not_checked"


def test_an_active_spec_wins_over_archive_matches_without_ambiguity(
    tmp_path, state_dir, env
):
    repo = build_spec_repo(
        tmp_path, env,
        [
            f"active/{SLUG}",
            "archive/2026-09-demo-campaign",
            "archive/2026-10-demo-campaign",
        ],
    )

    result = spec_audit(repo, state_dir, env, SLUG)

    assert_resolved(result, f"docs/specs/active/{SLUG}")


def test_a_single_file_archive_spec_is_not_resolved(tmp_path, state_dir, env):
    repo = build_spec_repo(tmp_path, env, [], files=["archive/2026-10-demo-campaign.md"])

    result = spec_audit(repo, state_dir, env, SLUG)

    assert_unresolved(result)


# --- struck-out tasks and label-only issues (#445) ---------------------------


def test_struck_out_tasks_are_listed_but_not_counted(tmp_path, state_dir, env):
    repo = build_spec_repo(tmp_path, env, ["active/demo"])
    tasks = repo / "docs" / "specs" / "active" / "demo" / "tasks.md"
    tasks.write_text(
        "- [ ] real one\n- [ ] ~~dropped~~ - decided not to do\n- [ ] ~~later~~ - deferred\n"
    )

    result = spec_audit(repo, state_dir, env, "demo")

    assert result.field("spec_tasks") == "1", result.out
    assert result.field("struck_out") == "2", result.out
    assert result.field("unhandled_total") == "1", result.out


def test_label_query_is_listed_apart_from_the_literal_slug_search(
    clean, state_dir, stub_gh
):
    stubbed, log = stub_gh('[{"number": 4}, {"number": 9}]')

    result = audit(
        clean, state_dir, stubbed,
        "--range", f"{clean.base}..{clean.first}",
        skip_issues=False,
    )

    assert result.field("open_issues_by_label") == "2", result.out
    assert result.line("open_issues_label_numbers").split("=")[1].split() == ["4", "9"]
    assert result.line("open_issues_slug_numbers").split("=")[1].split() == ["4", "9"]
    assert result.field("open_issues_label_only") == "0", result.out

"""Behaviour tests for scripts/campaign-closeout-audit.sh, source 4 and source 5.

Every test builds a throwaway git repository whose history interleaves a
campaign's own commits with an upstream commit that carries work markers, then
runs the real script against it. Nothing here touches the network or
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
    upstream: str  # another campaign's commit that landed between the pushes
    second: str  # head of the campaign's second push, also HEAD
    foreign: int  # marker lines the upstream commit adds
    own: int  # marker lines the campaign's two segments add together


def build_history(root: Path, env: dict[str, str], own_first: int, own_second: int) -> History:
    """base -> campaign(first) -> upstream -> campaign(second), all linear."""
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

    with (repo / "upstream.md").open("a") as handle:
        handle.write(marker_lines(MARK_A, 1) + marker_lines(MARK_B, 1) + "plain upstream note\n")
    upstream = commit("another campaign lands")

    with (repo / "campaign.md").open("a") as handle:
        handle.write("another plain note\n" + marker_lines(MARK_B, own_second))
    second = commit("campaign second push")

    return History(repo, base, first, upstream, second, foreign=2, own=own_first + own_second)


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
) -> Audit:
    args = [
        "--worktree", str(history.repo),
        "--slug", SLUG,
        "--self-session", "test-session",
        "--session-state-dir", str(state_dir),
        *extra,
    ]
    if skip_issues:
        args.append("--skip-issues")
    return run_script(args, env)


# --- source 4: commit range --------------------------------------------------


def test_segments_around_an_upstream_commit_report_zero(clean, state_dir, env):
    result = audit(
        clean, state_dir, env,
        "--range", f"{clean.base}..{clean.first}",
        "--range", f"{clean.upstream}..{clean.second}",
    )

    assert result.field("range_todo") == "0"
    assert result.field("range_todo_segment_1") == "0"
    assert result.field("range_todo_segment_2") == "0"
    assert "commits=1" in result.line("range_todo_segment_1")
    assert "commits=1" in result.line("range_todo_segment_2")
    assert result.field("unhandled_total") == "0"
    # The skipped GitHub source is the only open question left.
    assert result.field("verdict") == "UNDETERMINED:issues_not_checked"
    assert result.code == 20
    assert git(clean.repo, env, "status", "--porcelain") == ""


def test_one_span_over_an_upstream_commit_counts_its_markers(clean, state_dir, env):
    result = audit(clean, state_dir, env, "--base", clean.base, "--head", clean.second)

    assert result.field("range_todo") == str(clean.foreign)
    assert result.field("range_todo") != "0"
    # Single-segment output keeps its original shape.
    assert result.line("range_todo") == (
        f"range_todo={clean.foreign}  (added lines matching {PATTERN} "
        f"in {clean.base}..{clean.second})"
    )
    assert result.field("verdict") == "HOLD:unhandled_work"
    assert result.code == 10


def test_single_range_flag_over_the_same_span_is_also_positive(clean, state_dir, env):
    """The contamination comes from the span, not from which flag carries it."""
    result = audit(clean, state_dir, env, "--range", f"{clean.base}..{clean.second}")

    assert result.field("range_todo") == str(clean.foreign)
    assert result.field("range_todo_segment_1") == str(clean.foreign)
    assert "commits=3" in result.line("range_todo_segment_1")
    assert result.code == 10


def test_segments_sum_the_campaigns_own_markers_and_leave_out_the_upstream(dirty, state_dir, env):
    segments = audit(
        dirty, state_dir, env,
        "--range", f"{dirty.base}..{dirty.first}",
        "--range", f"{dirty.upstream}..{dirty.second}",
    )
    span = audit(dirty, state_dir, env, "--base", dirty.base, "--head", dirty.second)

    assert segments.field("range_todo_segment_1") == "1"
    assert segments.field("range_todo_segment_2") == "2"
    assert segments.field("range_todo") == str(dirty.own)
    assert segments.field("unhandled_total") == str(dirty.own)
    assert segments.field("verdict") == "HOLD:unhandled_work"
    # The single span is exactly the sum plus what the upstream commit brought.
    assert span.field("range_todo") == str(dirty.own + dirty.foreign)


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
    assert "range_todo_unresolvable" in (result.field("verdict") or "")
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
    assert result.field("verdict") == "HOLD:unhandled_work"
    assert "range_todo_unresolvable" in (result.field("also_undetermined") or "")
    assert result.code == 10


def test_without_any_range_the_source_is_not_checked(clean, state_dir, env):
    result = audit(clean, state_dir, env)

    assert result.field("range_todo") == "not_checked"
    assert "range_todo_not_checked" in (result.field("verdict") or "")


@pytest.mark.parametrize(
    ("which", "expected"),
    [("upstream", "0"), ("base", "2")],
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


# --- argument handling -------------------------------------------------------


@pytest.mark.parametrize("flag", ["--base", "--head"])
def test_range_cannot_be_combined_with_base_or_head(clean, state_dir, env, flag):
    result = audit(
        clean, state_dir, env,
        "--range", f"{clean.base}..{clean.first}",
        flag, clean.first,
    )

    assert result.code == 2
    assert "cannot be combined" in result.err
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

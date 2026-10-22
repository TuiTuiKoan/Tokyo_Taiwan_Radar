"""Behaviour tests for scripts/campaign-disposition-backfill.py.

The synthetic record reproduces the shape of a real close-out record: the pending
disposition section is copied from the first version of
docs/evaluation/campaigns/2026-10-14-ai-portability.md (commit ca569d8d), and the
applied section from the backfilled version on main. Text outside the section
contains the word `pending` on purpose, as real records do.

The section ends at the first heading after `## Worktree disposition`: a `###`
subsection such as `### Gates at the close-out audit`, or the next `## `
(user decision, 2026-10-22). Subsections are kept as they are and never rewritten.

The committed records under docs/evaluation/campaigns/ are also verified directly.
Committed records are not rewritten (README § Correction), so they are stable
fixtures for the real formats: backticked and bare values, annotated `behind`
cells, a `###` subsection after the section, and no backticks around the time.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "campaign-disposition-backfill.py"
CAMPAIGNS = ROOT / "docs" / "evaluation" / "campaigns"
RECORD_REL = "docs/evaluation/campaigns/2026-10-22-demo.md"

HEAD = """\
---
title: Demo Close-out
description: Fixture shaped like a real close-out record
ms.date: 2026-10-22
ms.topic: reference
---

## Outcome

The demo campaign is in production.

## Spec disposition

`archive` for `docs/specs/active/demo/`. The admin queue still lists 3 pending
reports; they belong to another campaign.

"""

PENDING_SECTION = """\
## Worktree disposition

`pending`, decided at `pending`.

The owner answered `remove` at the Phase B reply, after reading the audit output.
That is an intention, not a disposition: no removal has happened and no decision
time exists yet.

| Freshness value | Observed at the decision |
|-----------------|--------------------------|
| branch tip | `pending` |
| ahead of `origin/main` | `pending` |
| behind `origin/main` | `pending` |
| dirty count | `pending` |
| ignored artifact set | `pending` |
| path identity | `pending` |

"""

APPLIED_SECTION = """\
## Worktree disposition

`remove`, decided at `2026-10-13T18:32:07Z`.

The six values cannot be observed again after removal. This section was
backfilled from the recovery capsule, which holds the values recorded at the
decision:

| Freshness value | Observed at the decision |
|-----------------|--------------------------|
| branch tip | `ca569d8d7e21abf85c6e0418df2393437cfc001f` |
| ahead of `origin/main` | `0` |
| behind `origin/main` | `1`; `origin/main` advanced to `1c5abfb9` after the branch tip, which is not a branch change |
| dirty count | `0` |
| ignored artifact set | `6`, the entries listed under Ignored artifacts and handling |
| path identity | `canonical`, directory `ttr-ai-portability-worktree`, branch `feat/ai-portability` |
"""

GATES = """\
### Gates at the close-out audit

| Unhandled-work source | Script result | Final result |
|-----------------------|---------------|--------------|
| `tasks.md` unchecked items | 0 | 0 |
| Open GitHub issues naming the slug | 0 | 0 |

"""

TAIL = """\
## Ignored artifacts and handling

| Artifact | Handling | SHA-256 |
|----------|----------|---------|
| `web/node_modules/` | `disposable` | not applicable (directory) |

## Evidence anchors

* Ledger upload for the last slice is still pending.
"""

PENDING_RECORD = HEAD + PENDING_SECTION + GATES + TAIL
APPLIED_RECORD = HEAD + APPLIED_SECTION + "\n" + GATES + TAIL

CAPSULE = {
    "decided_at": "2026-10-13T18:32:07Z",
    "branch_tip": "ca569d8d7e21abf85c6e0418df2393437cfc001f",
    "ahead": "0",
    "behind": "1",
    "dirty_count": "0",
    "ignored_artifact_set": "6",
    "path_identity": "canonical, directory ttr-ai-portability-worktree, branch feat/ai-portability",
    "record": RECORD_REL,
}

EXTRA_CAPSULE_LINES = """\
# recovery capsule, closer-auto-retire key names
consented_at: 2026-10-13T18:20:00Z
registered_path: /repo copy/ttr-ai-portability-worktree
branch: feat/ai-portability
ignored_artifact: web/node_modules/ disposable not applicable (directory)
ignored_artifact: scripts/__pycache__/ disposable not applicable (directory)
t_c: ca569d8d7e21abf85c6e0418df2393437cfc001f
b_c: 1c5abfb9
"""


@pytest.fixture(scope="session")
def backfill():
    spec = importlib.util.spec_from_file_location("campaign_disposition_backfill", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capsule_text(values: dict[str, str], extra: str = EXTRA_CAPSULE_LINES) -> str:
    return extra + "".join(f"{key}: {value}\n" for key, value in values.items())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repository-shaped directory whose path contains a space."""
    dest = tmp_path / "repo copy"
    (dest / "docs" / "evaluation" / "campaigns").mkdir(parents=True)
    return dest


@pytest.fixture
def files(repo: Path, tmp_path: Path):
    def make(record: str, block: str = APPLIED_SECTION, capsule: dict[str, str] | None = None,
             capsule_raw: str | None = None) -> tuple[Path, Path, Path]:
        record_path = repo / RECORD_REL
        record_path.write_bytes(record.encode("utf-8"))
        block_path = tmp_path / "scratch" / "block.md"
        block_path.parent.mkdir(exist_ok=True)
        block_path.write_text(block, encoding="utf-8")
        capsule_path = tmp_path / "capsules" / "2026-10-22-demo.md"
        capsule_path.parent.mkdir(exist_ok=True)
        raw = capsule_raw if capsule_raw is not None else capsule_text(capsule or CAPSULE)
        capsule_path.write_text(raw, encoding="utf-8")
        return record_path, block_path, capsule_path

    return make


def run(backfill, capsys, *args: str, stdin: str | None = None) -> tuple[int, str, str]:
    code = backfill.main([str(a) for a in args], stdin=stdin)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def apply(backfill, capsys, record: Path, block: Path, capsule: Path) -> tuple[int, str, str]:
    return run(backfill, capsys, "--record", record, "--block", block, "--capsule", capsule)


def verify(backfill, capsys, capsule: Path, text: str) -> tuple[int, str, str]:
    return run(backfill, capsys, "--verify", "--capsule", capsule, stdin=text)


# --- apply -----------------------------------------------------------------


def test_pending_section_is_replaced(backfill, capsys, files):
    record, block, capsule = files(PENDING_RECORD)
    code, out, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    assert out.splitlines()[-1] == "result=applied"
    assert "-`pending`, decided at `pending`." in out
    assert "+`remove`, decided at `2026-10-13T18:32:07Z`." in out
    assert "### Gates" not in out
    assert record.read_text(encoding="utf-8") == APPLIED_RECORD


def test_text_outside_section_is_byte_identical(backfill, capsys, files):
    head = HEAD.replace("\n", "\r\n") + "trailing spaces   \n\n"
    tail = TAIL.replace("## Evidence anchors\n", "## Evidence anchors\r\n﻿non-ASCII 台灣 \t\n")
    assert tail != TAIL
    record, block, capsule = files(head + PENDING_SECTION + GATES + tail)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    data = record.read_bytes()
    assert data.startswith(head.encode("utf-8"))
    assert data.endswith((GATES + tail).encode("utf-8"))


def test_gates_subsection_is_kept_byte_for_byte(backfill, capsys, files):
    gates = (
        "### Gates at the close-out audit\r\n\n"
        "Run 1 stopped at a pending GitHub check, 台灣 \t\n"
        "| Source | Result |\n|---|---|\n| issues | `not_checked` |\n\n"
        "#### Detail\n\nUnchanged.\n\n"
    )
    record, block, capsule = files(HEAD + PENDING_SECTION + gates + TAIL)
    code, out, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    assert "not_checked" not in out
    expected = HEAD + APPLIED_SECTION + "\n" + gates + TAIL
    assert record.read_bytes() == expected.encode("utf-8")
    # `pending` inside the subsection is outside the checked section.
    assert apply(backfill, capsys, record, block, capsule)[1].startswith("result=already_applied")
    assert record.read_bytes() == expected.encode("utf-8")


def test_rerun_is_already_applied_and_leaves_file_untouched(backfill, capsys, files):
    record, block, capsule = files(PENDING_RECORD)
    assert apply(backfill, capsys, record, block, capsule)[0] == 0
    first = record.read_bytes()
    code, out, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    assert out.splitlines() == ["result=already_applied", "block_identical=yes"]
    assert record.read_bytes() == first


def test_already_applied_with_different_wording_is_reported(backfill, capsys, files):
    reworded = APPLIED_SECTION.replace("This section was\nbackfilled", "It was\nbackfilled")
    record, block, capsule = files(HEAD + reworded + "\n" + GATES + TAIL)
    code, out, _ = apply(backfill, capsys, record, block, capsule)
    assert code == 0
    assert out.splitlines() == ["result=already_applied", "block_identical=no"]


@pytest.mark.parametrize(
    "old, new",
    [
        ("`remove`, decided at `2026-10-13T18:32:07Z`.", "`retain`, decided at `2026-10-13T18:32:07Z`."),
        ("2026-10-13T18:32:07Z", "2026-10-13T18:40:00Z"),
        ("| dirty count | `0` |", "| dirty count | `2` |"),
        ("| behind `origin/main` | `1`;", "| behind `origin/main` | `12`;"),
    ],
)
def test_edited_section_is_unexpected_state(backfill, capsys, files, old, new):
    edited = APPLIED_SECTION.replace(old, new)
    assert edited != APPLIED_SECTION
    original = HEAD + edited + "\n" + GATES + TAIL
    record, block, capsule = files(original)
    code, out, _ = apply(backfill, capsys, record, block, capsule)
    assert code == 3
    assert out.splitlines()[0] == "result=unexpected_state"
    assert any(line.startswith("reason=") for line in out.splitlines()[1:])
    assert record.read_text(encoding="utf-8") == original


def test_missing_heading_is_an_error(backfill, capsys, files):
    original = HEAD + TAIL
    record, block, capsule = files(original)
    code, out, err = apply(backfill, capsys, record, block, capsule)
    assert code == 2
    assert out == ""
    assert "no `## Worktree disposition` heading" in err
    assert record.read_text(encoding="utf-8") == original


def test_duplicated_heading_is_an_error(backfill, capsys, files):
    record, block, capsule = files(HEAD + PENDING_SECTION + GATES + PENDING_SECTION + TAIL)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 2
    assert "2 `## Worktree disposition` headings" in err


def test_section_at_end_of_file(backfill, capsys, files):
    record, block, capsule = files(TAIL + "\n" + PENDING_SECTION.rstrip("\n") + "\n")
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    assert record.read_text(encoding="utf-8") == TAIL + "\n" + APPLIED_SECTION
    assert apply(backfill, capsys, record, block, capsule)[1].startswith("result=already_applied")


def test_section_without_subsection_ends_at_next_h2(backfill, capsys, files):
    record, block, capsule = files(HEAD + PENDING_SECTION + TAIL)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    assert record.read_text(encoding="utf-8") == HEAD + APPLIED_SECTION + "\n" + TAIL


def test_headings_inside_code_fence_are_ignored(backfill, capsys, files):
    fenced = "## Notes\n\n```markdown\n## Worktree disposition\n\n`pending`\n## Other\n```\n\n"
    in_section = "~~~text\n### not a subsection\n~~~\n\n"
    pending = PENDING_SECTION.replace("time exists yet.\n\n", "time exists yet.\n\n" + in_section)
    assert pending != PENDING_SECTION
    record, block, capsule = files(HEAD + fenced + pending + GATES + TAIL)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    assert record.read_text(encoding="utf-8") == HEAD + fenced + APPLIED_SECTION + "\n" + GATES + TAIL


def test_block_that_fails_verification_writes_nothing(backfill, capsys, files):
    bad_block = APPLIED_SECTION.replace("| dirty count | `0` |", "| dirty count | `pending` |")
    record, block, capsule = files(PENDING_RECORD, block=bad_block)
    code, out, err = apply(backfill, capsys, record, block, capsule)
    assert code == 2
    assert out == ""
    assert "does not pass verification" in err
    assert record.read_text(encoding="utf-8") == PENDING_RECORD


@pytest.mark.parametrize(
    "bad_block, message",
    [
        (APPLIED_SECTION.split("\n", 1)[1], "must start with the line"),
        (APPLIED_SECTION + "\n## Ignored artifacts and handling\n", "another `## ` heading"),
        (APPLIED_SECTION + "\n" + GATES, "`###` subsection heading"),
        (APPLIED_SECTION + "\n#### Detail\n", "`###` subsection heading"),
    ],
)
def test_invalid_block_file_is_an_error(backfill, capsys, files, bad_block, message):
    record, block, capsule = files(PENDING_RECORD, block=bad_block)
    code, out, err = apply(backfill, capsys, record, block, capsule)
    assert code == 2
    assert out == ""
    assert message in err
    assert record.read_text(encoding="utf-8") == PENDING_RECORD


def test_block_with_fenced_subsection_text_is_accepted(backfill, capsys, files):
    fenced_block = APPLIED_SECTION + "\n```text\n### quoted, not a heading\n```\n"
    record, block, capsule = files(PENDING_RECORD, block=fenced_block)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 0, err
    assert record.read_text(encoding="utf-8") == HEAD + fenced_block + "\n" + GATES + TAIL


def test_record_path_must_match_capsule(backfill, capsys, files):
    other = dict(CAPSULE, record="docs/evaluation/campaigns/2026-10-21-other.md")
    record, block, capsule = files(PENDING_RECORD, capsule=other)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 2
    assert "does not end with capsule record" in err
    assert record.read_text(encoding="utf-8") == PENDING_RECORD


# --- capsule ---------------------------------------------------------------


@pytest.mark.parametrize("missing", ["decided_at", "branch_tip", "path_identity", "record"])
def test_capsule_missing_key_is_an_error(backfill, capsys, files, missing):
    values = {k: v for k, v in CAPSULE.items() if k != missing}
    record, block, capsule = files(PENDING_RECORD, capsule=values)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 2
    assert f"capsule is missing key `{missing}`" in err
    assert record.read_text(encoding="utf-8") == PENDING_RECORD


@pytest.mark.parametrize(
    "raw, message",
    [
        (capsule_text(CAPSULE) + "this line has no key\n", "is not `key: value`"),
        (capsule_text(CAPSULE) + "ahead: 3\n", "`ahead` appears 2 times"),
        (capsule_text(dict(CAPSULE, behind="")), "`behind` is empty"),
        (capsule_text(dict(CAPSULE, decided_at="2026-10-13 18:32")), "decided_at is not"),
    ],
)
def test_malformed_capsule_is_an_error(backfill, capsys, files, raw, message):
    record, block, capsule = files(PENDING_RECORD, capsule_raw=raw)
    code, _, err = apply(backfill, capsys, record, block, capsule)
    assert code == 2
    assert message in err


def test_verify_does_not_need_record_key(backfill, capsys, files):
    values = {k: v for k, v in CAPSULE.items() if k != "record"}
    _, _, capsule = files(PENDING_RECORD, capsule=values)
    code, out, err = verify(backfill, capsys, capsule, APPLIED_RECORD)
    assert code == 0, err
    assert out == "verify=pass\n"


def test_verify_capsule_missing_key_is_an_error(backfill, capsys, files):
    values = {k: v for k, v in CAPSULE.items() if k != "dirty_count"}
    _, _, capsule = files(PENDING_RECORD, capsule=values)
    code, _, err = verify(backfill, capsys, capsule, APPLIED_RECORD)
    assert code == 2
    assert "capsule is missing key `dirty_count`" in err


# --- verify ----------------------------------------------------------------


def test_verify_ignores_pending_outside_section(backfill, capsys, files):
    _, _, capsule = files(PENDING_RECORD)
    text = APPLIED_RECORD.replace("| 0 | 0 |\n\n## Ignored", "| 0 | pending |\n\n## Ignored")
    assert text.count("pending") == 3
    code, out, _ = verify(backfill, capsys, capsule, text)
    assert code == 0
    assert out == "verify=pass\n"


def test_verify_fails_on_pending_section(backfill, capsys, files):
    _, _, capsule = files(PENDING_RECORD)
    code, out, _ = verify(backfill, capsys, capsule, PENDING_RECORD)
    assert code == 1
    lines = out.splitlines()
    assert lines[0] == "verify=fail"
    assert "reason=section contains `pending`" in lines


@pytest.mark.parametrize(
    "old, new, reason",
    [
        ("`remove`, decided", "`already_removed`, decided", "disposition is not `remove`"),
        ("2026-10-13T18:32:07Z", "2026-10-13T18:32:08Z", "decided at 2026-10-13T18:32:08Z != capsule"),
        ("ca569d8d7e21abf85c6e0418df2393437cfc001f", "ca569d8d", "row `branch tip`"),
        ("| ignored artifact set | `6`,", "| ignored artifact set | `7`,", "row `ignored artifact set`"),
        ("`canonical`, directory", "`divergent`, directory", "row `path identity`"),
        ("| ahead of `origin/main` | `0` |\n", "", "row `ahead of origin/main` appears 0 times"),
    ],
)
def test_verify_fails_on_mismatch(backfill, capsys, files, old, new, reason):
    _, _, capsule = files(PENDING_RECORD)
    edited = APPLIED_SECTION.replace(old, new)
    assert edited != APPLIED_SECTION
    code, out, _ = verify(backfill, capsys, capsule, HEAD + edited + "\n" + GATES + TAIL)
    assert code == 1
    assert any(line.startswith(f"reason={reason}") for line in out.splitlines()), out


def test_verify_fails_on_duplicated_freshness_table(backfill, capsys, files):
    _, _, capsule = files(PENDING_RECORD)
    table = APPLIED_SECTION[APPLIED_SECTION.index("| Freshness"):]
    doubled = APPLIED_SECTION + "\n" + table
    code, out, _ = verify(backfill, capsys, capsule, HEAD + doubled + "\n" + GATES + TAIL)
    assert code == 1
    assert "reason=row `branch tip` appears 2 times" in out.splitlines()


def test_verify_does_not_read_freshness_table_after_subsection(backfill, capsys, files):
    """The shape of the 2026-10-13 senses-taxonomy record: table after `### Gates`."""
    _, _, capsule = files(PENDING_RECORD)
    split = APPLIED_SECTION.index("| Freshness")
    before, table = APPLIED_SECTION[:split], APPLIED_SECTION[split:]
    text = HEAD + before + GATES + table + "\n" + TAIL
    code, out, _ = verify(backfill, capsys, capsule, text)
    assert code == 1
    assert "reason=row `branch tip` appears 0 times" in out.splitlines()


def test_verify_missing_heading_is_an_error(backfill, capsys, files):
    _, _, capsule = files(PENDING_RECORD)
    code, _, err = verify(backfill, capsys, capsule, HEAD + TAIL)
    assert code == 2
    assert "no `## Worktree disposition` heading" in err


def test_verify_reads_stdin_through_a_pipe(files, tmp_path):
    record, _, capsule = files(APPLIED_RECORD)
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--verify", "--capsule", str(capsule)],
        stdin=record.open("rb"),
        capture_output=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == b"verify=pass\n"


@pytest.mark.parametrize(
    "args",
    [
        ["--verify", "--record", "x.md"],
        ["--verify", "--block", "b.md"],
        ["--record", "x.md"],
        ["--block", "b.md"],
    ],
)
def test_mode_arguments_are_exclusive(backfill, capsys, files, args):
    _, _, capsule = files(PENDING_RECORD)
    with pytest.raises(SystemExit) as exc:
        backfill.main([*args, "--capsule", str(capsule)])
    assert exc.value.code == 2
    capsys.readouterr()


# --- committed records -----------------------------------------------------

REAL_RECORDS = {
    "2026-10-14-ai-portability.md": {k: v for k, v in CAPSULE.items() if k != "record"},
    "2026-10-14-closeout-audit-multirange.md": {
        "decided_at": "2026-10-14T04:05:23Z",
        "branch_tip": "13d8798b7585cd27f82893c9b743a5827093de8c",
        "ahead": "0", "behind": "0", "dirty_count": "0",
        "ignored_artifact_set": "5 entries, 15 files",
        "path_identity": "canonical, directory ttr-closeout-audit-multirange-worktree, "
                         "branch feat/closeout-audit-multirange",
    },
    "2026-10-14-event-intake-wizard.md": {
        "decided_at": "2026-10-14T05:14:32Z",
        "branch_tip": "4c994ce072c947312f4beb63ce997bed32dc813e",
        "ahead": "0", "behind": "1", "dirty_count": "0",
        "ignored_artifact_set": "7",
        "path_identity": "divergent, directory ttr-v8-worktree, branch feat/event-intake-wizard",
    },
    "2026-10-20-iwafu-taiwan-relevance-gate.md": {
        "decided_at": "2026-10-20T09:33:06Z",
        "branch_tip": "f1a519fed22c583ed1ba3c253b84fba4f70702f3",
        "ahead": "0", "behind": "4", "dirty_count": "0",
        "ignored_artifact_set": "3 directories, 134 files",
        "path_identity": "canonical, directory ttr-iwafu-gate-worktree, branch fix/iwafu-taiwan-relevance-gate",
    },
    "2026-10-20-vmd-summary-ai-scope.md": {
        "decided_at": "2026-10-20T13:01:30Z",
        "branch_tip": "b5eaa35ac814636837e81e91ee09999142dafe1c",
        "ahead": "0", "behind": "1", "dirty_count": "0",
        "ignored_artifact_set": "none",
        "path_identity": "canonical, directory ttr-vmd-summary-ai-scope-worktree, branch feat/vmd-summary-ai-scope",
    },
}

# Legacy format, accepted as an exception (user decision, 2026-10-22): the
# freshness table sits after `### Gates at the close-out audit`, so it is outside
# the checked section and this record does not verify even with the right capsule.
LEGACY_RECORD = "2026-10-13-senses-taxonomy.md"
LEGACY_CAPSULE = {
    "decided_at": "2026-10-12T22:39:21Z",
    "branch_tip": "6acae937667954af2dcd1a10e9c69b18397b1be8",
    "ahead": "0", "behind": "0", "dirty_count": "0",
    "ignored_artifact_set": "11",
    "path_identity": "canonical, directory ttr-senses-taxonomy-worktree, branch feat/senses-taxonomy",
}


def verify_committed(backfill, capsys, tmp_path, name: str, values: dict[str, str]) -> tuple[int, str]:
    capsule = tmp_path / "capsule.md"
    capsule.write_text(capsule_text(values, extra=""), encoding="utf-8")
    text = (CAMPAIGNS / name).read_text(encoding="utf-8")
    code, out, err = verify(backfill, capsys, capsule, text)
    return code, out + err


@pytest.mark.parametrize("name", sorted(REAL_RECORDS))
def test_committed_records_verify(backfill, capsys, tmp_path, name):
    code, out = verify_committed(backfill, capsys, tmp_path, name, REAL_RECORDS[name])
    assert code == 0, out
    assert out == "verify=pass\n"


@pytest.mark.parametrize("name", sorted(REAL_RECORDS))
def test_committed_records_reject_wrong_capsule(backfill, capsys, tmp_path, name):
    wrong = dict(REAL_RECORDS[name], dirty_count="9")
    code, out = verify_committed(backfill, capsys, tmp_path, name, wrong)
    assert code == 1
    assert any(line.startswith("reason=row `dirty count`") for line in out.splitlines())


def test_legacy_record_with_table_after_subsection_does_not_verify(backfill, capsys, tmp_path):
    code, out = verify_committed(backfill, capsys, tmp_path, LEGACY_RECORD, LEGACY_CAPSULE)
    assert code == 1
    lines = out.splitlines()
    assert lines[0] == "verify=fail"
    assert lines[1:] == [f"reason=row `{label}` appears 0 times" for label in (
        "branch tip", "ahead of origin/main", "behind origin/main",
        "dirty count", "ignored artifact set", "path identity",
    )]

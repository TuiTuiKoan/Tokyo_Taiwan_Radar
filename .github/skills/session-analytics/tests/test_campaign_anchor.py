"""Contract tests for ``oneoff_campaign_anchor.py``.

All transcripts are synthetic and every git assertion runs inside a throwaway
repository. Nothing here reads a real Copilot transcript.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import sys

import pytest

from conftest import (
    CAMPAIGN,
    GIT_ENV,
    SESSION_ID,
    anchor,
    canonical_events,
    detectors,
    event,
    git,
    load_generator,
    render_transcript,
    uid,
)

SLICE = f"{SESSION_ID}:{uid(2)}:{uid(10)}"

GOLDEN_RECORD = """---
campaign_slug: "2026-08-03-fixture-campaign"
description: "Process telemetry for campaign 2026-08-03-fixture-campaign; all metrics recomputable from docs/evaluation/campaigns/ledger/2026-08-03-fixture-campaign-b7d78691c336.jsonl."
generator_blobs:
  ".github/skills/session-analytics/oneoff_campaign_anchor.py": "git-blob-sha1:__BLOB__"
ledger_digest: "sha256:b7d78691c336142a1a71a785582f2c2ecd768226152ac8d92fe46c002717487b"
ledger_path: "docs/evaluation/campaigns/ledger/2026-08-03-fixture-campaign-b7d78691c336.jsonl"
owning_spec_slug: "evaluation-framework"
record_kind: "process_telemetry"
schema_version: 1
title: "Campaign close-out: 2026-08-03-fixture-campaign"
---

## Process

| Metric | Value |
| --- | --- |
| user_turns | 2 |
| assistant_turns | 2 |
| tool_calls | 4 |
| avg_tools_per_turn | 2.0 |
| wall_span_hours | 1.0 |

### Tool top 8

| Tool | Count |
| --- | --- |
| read_file | 2 |
| grep_search | 1 |
| run_in_terminal | 1 |

## Session

| Field | Value |
| --- | --- |
| session_id | 11111111-1111-4111-8111-111111111111 |
| start_event_id | 00000000-0000-4000-8000-000000000002 |
| end_event_id_exclusive | 00000000-0000-4000-8000-000000000010 |
| selected_events | 8 |
| first_timestamp | 2026-08-03T00:00:01Z |
| last_timestamp | 2026-08-03T01:00:02Z |
| slice_digest | sha256:73831e4879b84b10b59cf18ce34603d4cdd63a776b6b696c8d2188db0fcf94de |

## Outcome references

- __OUTCOME_REF__

## Recompute

1. Read the ledger named by `ledger_path`. Every line is one selected event with the keys `session_id`, `i`, `event_id`, `timestamp`, `type`, `tool_name` and `turn_index`.
2. Recompute `## Process`: `user_turns` counts rows whose `type` is `user.message`; `assistant_turns` counts `assistant.turn_start`; `tool_calls` counts `tool.execution_start`; `avg_tools_per_turn` is `tool_calls / user_turns` rounded to one decimal, or `0` when `user_turns` is zero; `wall_span_hours` is the span between the smallest and the largest `timestamp` expressed in hours and rounded to two decimals; the tool table ranks `tool_name` over `tool.execution_start` rows by count descending, then by name ascending, keeping the first eight.
3. Recompute `selected_events` as the ledger row count, and `first_timestamp` / `last_timestamp` as the smallest / largest `timestamp` value.
4. Recompute `ledger_digest` by hashing the whole ledger file with SHA-256 and prefixing the hex digest with `sha256:`. It must equal `ledger_digest`, and its first twelve hex characters must equal the suffix in the ledger file name.
5. Recompute `slice_digest` from the original transcript alone: take the raw bytes of every selected line with its line terminator removed, join them with a single line feed, hash with SHA-256 and prefix with `sha256:`.
"""


# ── helpers ───────────────────────────────────────────────────────────────────

def ledger_rows(workspace):
    ledgers = workspace.ledgers()
    assert len(ledgers) == 1, ledgers
    text = ledgers[0].read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def record_field(workspace, field: str) -> str:
    match = re.search(rf"^\| {re.escape(field)} \| (.+) \|$", workspace.record.read_text(encoding="utf-8"), re.M)
    assert match, f"{field} missing from the record"
    return match.group(1)


def assert_nothing_written(workspace):
    assert not workspace.record.exists()
    assert workspace.ledgers() == []
    assert workspace.stray_temp_files() == []


def expect_failure(workspace, **kwargs):
    proc = workspace.run(**kwargs)
    assert proc.returncode != 0, proc.stdout
    assert proc.stderr.startswith("error:") or "error:" in proc.stderr
    return proc


# ── 1. boundary ───────────────────────────────────────────────────────────────

def test_slice_is_half_open_on_both_ends(workspace):
    assert workspace.run().returncode == 0
    rows = ledger_rows(workspace)
    assert [row["event_id"] for row in rows] == [uid(n) for n in range(2, 10)]
    assert rows[0]["event_id"] == uid(2)
    assert rows[-1]["event_id"] == uid(9)
    assert uid(1) not in {row["event_id"] for row in rows}
    assert uid(10) not in {row["event_id"] for row in rows}
    assert record_field(workspace, "selected_events") == "8"


def test_identical_adjacent_timestamps_still_split_at_the_anchor(workspace):
    events = canonical_events()
    for item in events:
        if item["id"] in {uid(9), uid(10)}:
            item["timestamp"] = "2026-08-03T01:00:02Z"
    workspace.write_transcript(render_transcript(events))
    assert workspace.run().returncode == 0
    rows = ledger_rows(workspace)
    assert [row["event_id"] for row in rows] == [uid(n) for n in range(2, 10)]


def test_start_equal_to_end_fails_closed(workspace):
    expect_failure(workspace, slices=[f"{SESSION_ID}:{uid(2)}:{uid(2)}"])
    assert_nothing_written(workspace)


@pytest.mark.parametrize("slice_value", [
    f"{SESSION_ID}:{uid(2)}:{uid(999)}",
    f"{SESSION_ID}:{uid(999)}:{uid(10)}",
])
def test_missing_anchor_fails_closed(workspace, slice_value):
    expect_failure(workspace, slices=[slice_value])
    assert_nothing_written(workspace)


def test_start_after_end_fails_closed(workspace):
    expect_failure(workspace, slices=[f"{SESSION_ID}:{uid(9)}:{uid(3)}"])
    assert_nothing_written(workspace)


@pytest.mark.parametrize("sentinel", ["EOF", "eof"])
def test_eof_sentinel_is_refused(workspace, sentinel):
    proc = expect_failure(workspace, slices=[f"{SESSION_ID}:{uid(2)}:{sentinel}"])
    assert "EOF" in proc.stderr
    assert_nothing_written(workspace)


def test_session_slice_may_be_given_only_once(workspace):
    proc = expect_failure(workspace, slices=[SLICE, f"{SESSION_ID}:{uid(3)}:{uid(9)}"])
    assert "exactly once" in proc.stderr
    assert_nothing_written(workspace)


def test_malformed_slice_spec_fails_closed(workspace):
    expect_failure(workspace, slices=[f"{SESSION_ID}:{uid(2)}"])
    assert_nothing_written(workspace)


# ── 2. append invariance ──────────────────────────────────────────────────────

APPENDED = {
    "legal_event": '{"id":"00000000-0000-4000-8000-000000000900","timestamp":"2026-08-03T05:00:00Z","type":"user.message"}',
    "malformed_json": "{not json at all",
    "duplicate_id": '{"id":"00000000-0000-4000-8000-000000000002","timestamp":"2026-08-03T06:00:00Z","type":"user.message"}',
    "naive_timestamp": '{"id":"00000000-0000-4000-8000-000000000901","timestamp":"2026-08-03T07:00:00","type":"user.message"}',
    "tool_without_name": '{"id":"00000000-0000-4000-8000-000000000902","timestamp":"2026-08-03T08:00:00Z","type":"tool.execution_start","data":{}}',
}


@pytest.mark.parametrize("kind", sorted(APPENDED))
def test_appending_after_the_end_anchor_changes_nothing(workspace, kind):
    assert workspace.run().returncode == 0
    baseline_ledger = workspace.ledgers()[0].read_bytes()
    baseline_record = workspace.record.read_bytes()

    transcript = workspace.transcripts / f"{SESSION_ID}.jsonl"
    transcript.write_bytes(transcript.read_bytes() + APPENDED[kind].encode("utf-8") + b"\n")

    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert workspace.ledgers()[0].read_bytes() == baseline_ledger
    assert workspace.record.read_bytes() == baseline_record


# ── 3. strictness inside prefix + slice ───────────────────────────────────────

def _corrupt(events, target_uid, mutate):
    return [mutate(dict(item)) if item["id"] == target_uid else item for item in events]


@pytest.mark.parametrize("target", [uid(1), uid(4), uid(10)])
def test_malformed_json_inside_the_validated_range_fails_closed(workspace, target):
    raw = render_transcript(canonical_events()).decode("utf-8").splitlines()
    raw = ["{broken" if target in line else line for line in raw]
    workspace.write_transcript(("\n".join(raw) + "\n").encode("utf-8"))
    expect_failure(workspace)
    assert_nothing_written(workspace)


@pytest.mark.parametrize("target", [uid(1), uid(5)])
def test_missing_id_inside_the_validated_range_fails_closed(workspace, target):
    def drop_id(item):
        item.pop("id")
        return item

    workspace.write_transcript(render_transcript(_corrupt(canonical_events(), target, drop_id)))
    expect_failure(workspace)
    assert_nothing_written(workspace)


@pytest.mark.parametrize("target", [uid(1), uid(6)])
def test_naive_timestamp_inside_the_validated_range_fails_closed(workspace, target):
    def strip_zone(item):
        item["timestamp"] = "2026-08-03T00:00:05"
        return item

    workspace.write_transcript(render_transcript(_corrupt(canonical_events(), target, strip_zone)))
    proc = expect_failure(workspace)
    assert "naive timestamp" in proc.stderr
    assert_nothing_written(workspace)


def test_duplicate_id_inside_the_validated_range_fails_closed(workspace):
    events = canonical_events()
    events[5]["id"] = uid(4)
    workspace.write_transcript(render_transcript(events))
    proc = expect_failure(workspace)
    assert "duplicate id" in proc.stderr
    assert_nothing_written(workspace)


def test_missing_timestamp_inside_the_validated_range_fails_closed(workspace):
    def drop_timestamp(item):
        item.pop("timestamp")
        return item

    workspace.write_transcript(render_transcript(_corrupt(canonical_events(), uid(4), drop_timestamp)))
    expect_failure(workspace)
    assert_nothing_written(workspace)


@pytest.mark.parametrize("target", [uid(4), uid(9)])
def test_tool_start_without_tool_name_fails_closed(workspace, target):
    def drop_tool_name(item):
        item["data"] = {}
        return item

    workspace.write_transcript(render_transcript(_corrupt(canonical_events(), target, drop_tool_name)))
    proc = expect_failure(workspace)
    assert "toolName" in proc.stderr
    assert_nothing_written(workspace)


# ── 4. non-monotonic timestamps are tolerated ─────────────────────────────────

def test_reversed_timestamps_only_emit_a_diagnostic(workspace):
    events = canonical_events()
    events[5]["timestamp"] = "2026-08-02T23:00:00Z"
    workspace.write_transcript(render_transcript(events))

    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert "non-monotonic" in proc.stderr
    assert record_field(workspace, "first_timestamp") == "2026-08-02T23:00:00Z"
    assert record_field(workspace, "last_timestamp") == "2026-08-03T01:00:02Z"


# ── 5. line-ending contract ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "newline,trailing",
    [("\n", True), ("\r\n", True), ("\n", False), ("\r\n", False)],
)
def test_line_endings_do_not_change_the_slice_digest(workspace, newline, trailing):
    workspace.write_transcript(render_transcript(canonical_events(), newline, trailing))
    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert record_field(workspace, "slice_digest") == (
        "sha256:73831e4879b84b10b59cf18ce34603d4cdd63a776b6b696c8d2188db0fcf94de"
    )


# ── 6. timestamp canonicalization ─────────────────────────────────────────────

def test_timestamp_canonicalization(workspace):
    events = canonical_events()
    events[1]["timestamp"] = "2026-08-03T00:00:01.0Z"
    events[2]["timestamp"] = "2026-08-03T00:00:02.1Z"
    events[3]["timestamp"] = "2026-08-03T00:00:03.123456Z"
    events[4]["timestamp"] = "2026-08-03T09:00:04+09:00"
    workspace.write_transcript(render_transcript(events))
    assert workspace.run().returncode == 0

    rows = ledger_rows(workspace)
    assert rows[0]["timestamp"] == "2026-08-03T00:00:01Z"
    assert rows[1]["timestamp"] == "2026-08-03T00:00:02.100000Z"
    assert rows[2]["timestamp"] == "2026-08-03T00:00:03.123456Z"
    assert rows[3]["timestamp"] == "2026-08-03T00:00:04Z"


# ── 7. independent recompute and tamper detection ─────────────────────────────

def test_every_number_is_recomputable_from_the_ledger(workspace):
    assert workspace.run().returncode == 0
    rows = ledger_rows(workspace)

    recomputed = anchor.compute_process(rows)
    assert str(recomputed["user_turns"]) == record_field(workspace, "user_turns")
    assert str(recomputed["assistant_turns"]) == record_field(workspace, "assistant_turns")
    assert str(recomputed["tool_calls"]) == record_field(workspace, "tool_calls")
    assert str(recomputed["avg_tools_per_turn"]) == record_field(workspace, "avg_tools_per_turn")
    assert str(recomputed["wall_span_hours"]) == record_field(workspace, "wall_span_hours")

    first, last = anchor.compute_span(rows)
    assert first == record_field(workspace, "first_timestamp")
    assert last == record_field(workspace, "last_timestamp")
    assert str(len(rows)) == record_field(workspace, "selected_events")

    digest = anchor.sha256_field(workspace.ledgers()[0].read_bytes())
    assert digest.split(":", 1)[1][:12] in workspace.ledgers()[0].name
    assert digest in workspace.record.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "before,after",
    [
        ('"turn_index":2', '"turn_index":3'),
        ('"type":"user.message"', '"type":"assistant.message"'),
        ('"i":5', '"i":50'),
        ('"tool_name":"grep_search"', '"tool_name":"read_file"'),
    ],
)
def test_a_tampered_ledger_row_is_rejected_before_any_write(workspace, before, after, monkeypatch):
    module = load_generator(workspace)
    original = module.render_ledger

    def tampered(rows):
        data = original(rows)
        assert before.encode() in data
        return data.replace(before.encode(), after.encode(), 1)

    monkeypatch.setattr(module, "render_ledger", tampered)
    with pytest.raises(module.AnchorError):
        module.run(workspace.argv())
    assert_nothing_written(workspace)


# ── 8. turn indices agree with the shared detector ────────────────────────────

def test_turn_index_matches_detectors(workspace):
    assert workspace.run().returncode == 0
    rows = ledger_rows(workspace)
    slice_events = canonical_events()[1:9]
    assert [row["event_id"] for row in rows] == [item["id"] for item in slice_events]
    for index, row in enumerate(rows):
        assert row["turn_index"] == detectors._turn_index_at(slice_events, index)


# ── 9. golden record and tie-breaking ─────────────────────────────────────────

def test_golden_record_is_byte_identical(workspace):
    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    blob = subprocess.run(
        ["git", "-C", str(workspace.root), "hash-object", "--", str(workspace.generator)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    expected = (
        GOLDEN_RECORD
        .replace("__OUTCOME_REF__", workspace.head)
        .replace("__BLOB__", blob)
    )
    assert workspace.record.read_bytes() == expected.encode("utf-8")


def _tie_break_events():
    plan = [
        ("t_a", 5), ("t_b", 4), ("t_c", 3), ("t_d", 3),
        ("t_e", 2), ("t_f", 2), ("t_g", 2), ("t_h", 1),
        ("t_i", 1), ("zzz_late", 6),
    ]
    events = [
        event(1, "2026-08-03T00:00:00Z", "session.start"),
        event(2, "2026-08-03T00:00:01Z", "user.message"),
    ]
    counter = 100
    minute = 0
    for name, count in plan:
        for _ in range(count):
            minute += 1
            events.append(
                event(counter, f"2026-08-03T00:{minute:02d}:00Z", "tool.execution_start", name)
            )
            counter += 1
    events.append(event(10, "2026-08-03T23:00:00Z", "user.message"))
    return events


def test_tool_ranking_breaks_ties_by_name(workspace):
    workspace.write_transcript(render_transcript(_tie_break_events()))
    assert workspace.run().returncode == 0

    table = re.search(r"### Tool top 8\n\n(.*?)\n\n## Session", workspace.record.read_text("utf-8"), re.S)
    ranked = [line.split("|")[1].strip() for line in table.group(1).splitlines()[2:]]
    assert ranked == ["zzz_late", "t_a", "t_b", "t_c", "t_d", "t_e", "t_f", "t_g"]
    assert "t_h" not in ranked and "t_i" not in ranked


def test_tool_ranking_is_independent_of_row_order(workspace):
    workspace.write_transcript(render_transcript(_tie_break_events()))
    assert workspace.run().returncode == 0
    rows = ledger_rows(workspace)
    shuffled = list(rows)
    random.Random(20260804).shuffle(shuffled)
    assert anchor.compute_process(shuffled) == anchor.compute_process(rows)


# ── 10. immutability and idempotency ──────────────────────────────────────────

def test_second_run_is_a_byte_identical_no_op(workspace):
    assert workspace.run().returncode == 0
    ledger = workspace.ledgers()[0]
    before = (ledger.read_bytes(), workspace.record.read_bytes())

    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert "unchanged" in proc.stdout
    assert (ledger.read_bytes(), workspace.record.read_bytes()) == before
    assert workspace.stray_temp_files() == []


def test_a_different_ledger_at_the_same_path_is_never_overwritten(workspace):
    assert workspace.run().returncode == 0
    ledger = workspace.ledgers()[0]
    ledger.write_bytes(b'{"session_id":"tampered"}\n')
    record_before = workspace.record.read_bytes()

    proc = workspace.run()
    assert proc.returncode != 0
    assert "refusing to overwrite" in proc.stderr
    assert ledger.read_bytes() == b'{"session_id":"tampered"}\n'
    assert workspace.record.read_bytes() == record_before
    assert workspace.stray_temp_files() == []


def test_a_record_conflict_leaves_the_ledger_untouched(workspace):
    assert workspace.run().returncode == 0
    ledger_before = workspace.ledgers()[0].read_bytes()
    workspace.record.write_text("hand edited\n", encoding="utf-8")

    proc = workspace.run()
    assert proc.returncode != 0
    assert "refusing to overwrite" in proc.stderr
    assert workspace.ledgers()[0].read_bytes() == ledger_before
    assert workspace.record.read_text(encoding="utf-8") == "hand edited\n"
    assert workspace.stray_temp_files() == []


# ── 11. provenance pinned to the generator, and the final gate ────────────────

def test_uncommitted_generator_fails_closed(workspace):
    with workspace.generator.open("a", encoding="utf-8") as handle:
        handle.write("# drift\n")
    proc = expect_failure(workspace)
    assert "differs from its committed blob" in proc.stderr
    assert_nothing_written(workspace)


def test_a_generator_no_commit_ever_touched_fails_closed(workspace):
    twin = workspace.generator.with_name("oneoff_campaign_anchor_twin.py")
    shutil.copy2(workspace.generator, twin)
    proc = subprocess.run(
        [sys.executable, str(twin), *workspace.argv()],
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    assert proc.returncode != 0, proc.stdout
    assert "no commit touches" in proc.stderr
    assert_nothing_written(workspace)


def test_the_record_carries_no_commit_sha_outside_outcome_refs(workspace):
    (workspace.root / "unrelated.txt").write_text("parallel session\n", encoding="utf-8")
    git(workspace.root, "add", "unrelated.txt")
    git(workspace.root, "commit", "-qm", "unrelated work")
    moved_head = git(workspace.root, "rev-parse", "HEAD")
    git(workspace.root, "update-ref", "refs/remotes/origin/main", moved_head)
    generator_commit = workspace.generator_commit
    assert moved_head != generator_commit

    assert workspace.run(outcome_refs=[moved_head]).returncode == 0
    text = workspace.record.read_text(encoding="utf-8")
    blob = git(workspace.root, "hash-object", "--", str(workspace.generator))

    assert f'"git-blob-sha1:{blob}"' in text
    assert "generator_source_commit" not in text
    assert generator_commit not in text

    quoted = {line[2:].split(":", 1)[0] for line in text.splitlines() if line.startswith("- ")}
    assert quoted == {moved_head}
    for sha in re.findall(r"\b[0-9a-f]{40}\b", text):
        if sha in quoted:
            continue
        assert git(workspace.root, "cat-file", "-t", sha) == "blob", sha


def test_unrelated_dirty_files_do_not_block_the_run(workspace):
    (workspace.root / "README.md").write_text("locally edited\n", encoding="utf-8")
    (workspace.root / "untracked-wip.txt").write_text("parallel session\n", encoding="utf-8")
    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert workspace.record.exists()


def test_an_unrelated_commit_neither_aborts_the_run_nor_changes_the_output(workspace):
    assert workspace.run().returncode == 0
    before = (workspace.ledgers()[0].read_bytes(), workspace.record.read_bytes())

    (workspace.root / "unrelated.txt").write_text("parallel session\n", encoding="utf-8")
    git(workspace.root, "add", "unrelated.txt")
    git(workspace.root, "commit", "-qm", "unrelated work")
    assert git(workspace.root, "rev-parse", "HEAD") != workspace.head
    assert workspace.generator_commit == workspace.head

    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("unchanged: ") == 2
    assert (workspace.ledgers()[0].read_bytes(), workspace.record.read_bytes()) == before
    assert workspace.stray_temp_files() == []


def test_rerunning_after_the_artifacts_are_committed_is_a_no_op(workspace):
    assert workspace.run().returncode == 0
    ledger = workspace.ledgers()[0]
    before = (ledger.read_bytes(), workspace.record.read_bytes())

    git(workspace.root, "add", "docs/evaluation/campaigns")
    git(workspace.root, "commit", "-qm", "freeze the campaign anchor")
    assert git(workspace.root, "rev-parse", "HEAD") != workspace.head

    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("unchanged: ") == 2
    assert (ledger.read_bytes(), workspace.record.read_bytes()) == before
    assert workspace.stray_temp_files() == []


def test_a_generator_history_rewrite_keeps_the_rerun_a_no_op(workspace):
    pristine = workspace.generator.read_bytes()
    workspace.generator.write_bytes(pristine + b"# temporary drift\n")
    git(workspace.root, "add", "--", str(workspace.generator))
    git(workspace.root, "commit", "-qm", "drift the generator")
    workspace.generator.write_bytes(pristine)
    git(workspace.root, "add", "--", str(workspace.generator))
    git(workspace.root, "commit", "-qm", "restore the generator")

    assert workspace.run().returncode == 0
    ledger = workspace.ledgers()[0]
    before = (ledger.read_bytes(), workspace.record.read_bytes())
    commit_before = workspace.generator_commit
    blob = git(workspace.root, "hash-object", "--", str(workspace.generator))

    git(workspace.root, "commit", "-q", "--amend", "-m", "restore the generator, reworded")
    assert workspace.generator_commit != commit_before
    assert git(workspace.root, "hash-object", "--", str(workspace.generator)) == blob

    proc = workspace.run()
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("unchanged: ") == 2
    assert (ledger.read_bytes(), workspace.record.read_bytes()) == before
    assert workspace.stray_temp_files() == []


def test_generator_drift_before_the_final_gate_writes_nothing(workspace, monkeypatch):
    module = load_generator(workspace)
    original = module._git
    seen = {"count": 0}

    def drifting(repo_root, *args):
        if args[:2] == ("log", "-1"):
            seen["count"] += 1
            if seen["count"] > 1:
                return "0" * 40
        return original(repo_root, *args)

    monkeypatch.setattr(module, "_git", drifting)
    with pytest.raises(module.AnchorError, match="generator changed during the run"):
        module.run(workspace.argv())
    assert_nothing_written(workspace)


# ── 12. outcome references ────────────────────────────────────────────────────

def test_reachable_commit_and_commit_path_are_accepted(workspace):
    proc = workspace.run(outcome_refs=[workspace.head, f"{workspace.head}:README.md"])
    assert proc.returncode == 0, proc.stderr
    body = workspace.record.read_text(encoding="utf-8")
    assert f"- {workspace.head}\n" in body
    assert f"- {workspace.head}:README.md\n" in body


def test_commit_unreachable_from_origin_main_is_refused(workspace):
    from conftest import git

    git(workspace.root, "commit", "-q", "--allow-empty", "-m", "not on origin/main")
    unreachable = git(workspace.root, "rev-parse", "HEAD")
    assert unreachable != workspace.head
    proc = expect_failure(workspace, outcome_refs=[unreachable])
    assert "not durable" in proc.stderr
    assert_nothing_written(workspace)


def test_dangling_commit_is_refused(workspace):
    from conftest import git

    tree = git(workspace.root, "rev-parse", "HEAD^{tree}")
    dangling = git(workspace.root, "commit-tree", tree, "-m", "dangling")
    assert git(workspace.root, "cat-file", "-t", dangling) == "commit"
    proc = expect_failure(workspace, outcome_refs=[dangling])
    assert "not durable" in proc.stderr
    assert_nothing_written(workspace)


@pytest.mark.parametrize("ref", [
    "0" * 40,
    "main",
    "v1.0.0",
    "bee1038",
    "scraper/organizer_registry.py",
    "/memories/session/plan.md",
    "",
])
def test_non_durable_outcome_reference_shapes_are_refused(workspace, ref):
    expect_failure(workspace, outcome_refs=[ref])
    assert_nothing_written(workspace)


def test_path_absent_from_the_commit_is_refused(workspace):
    proc = expect_failure(workspace, outcome_refs=[f"{workspace.head}:does/not/exist.md"])
    assert "not readable" in proc.stderr
    assert_nothing_written(workspace)


def test_outcome_refs_are_mandatory(workspace):
    proc = expect_failure(workspace, outcome_refs=[])
    assert "outcome-ref" in proc.stderr
    assert_nothing_written(workspace)


# ── privacy boundary ──────────────────────────────────────────────────────────

def test_ledger_rows_carry_only_the_seven_agreed_keys(workspace):
    events = canonical_events()
    for item in events:
        item.setdefault("data", {})
        item["data"]["content"] = "SECRET user prompt text"
        item["data"]["arguments"] = {"filePath": "/Users/private/secret.py"}
    workspace.write_transcript(render_transcript(events))
    assert workspace.run().returncode == 0

    text = workspace.ledgers()[0].read_text(encoding="utf-8")
    record = workspace.record.read_text(encoding="utf-8")
    for line in text.splitlines():
        assert tuple(json.loads(line)) == anchor.LEDGER_KEYS
    for leak in ("SECRET", "arguments", "filePath", "/Users/", "content"):
        assert leak not in text
        assert leak not in record


def test_record_obeys_the_output_format_rules(workspace):
    assert workspace.run().returncode == 0
    raw = workspace.record.read_bytes()
    text = raw.decode("utf-8")

    assert b"\r" not in raw
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert all(line == line.rstrip() for line in text.split("\n"))

    head, frontmatter, body = text.split("---\n", 2)
    assert head == ""
    keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if not line.startswith(" ")]
    assert keys == sorted(keys)
    assert "title" in keys and "description" in keys
    assert not any(line.startswith("# ") for line in body.splitlines())

    headings = [line for line in body.splitlines() if line.startswith("## ")]
    assert headings == ["## Process", "## Session", "## Outcome references", "## Recompute"]
    assert "\n".join(anchor.RECOMPUTE_SECTION) in body


def test_forbidden_fields_never_reach_the_record(workspace):
    assert workspace.run().returncode == 0
    text = workspace.record.read_text(encoding="utf-8")
    for field in (
        "copilot_version",
        "start_time",
        "duration_minutes",
        "generated_at",
        "analyzer_dirty",
        "lessons",
        "plan_quality",
        "anomalies",
        "production",
        "slice_index",
    ):
        assert field not in text


def test_module_imports_nothing_from_this_repository():
    source = anchor.__file__
    with open(source, encoding="utf-8") as handle:
        body = handle.read()
    for forbidden in ("import analyze", "import detectors", "from analyze", "from detectors"):
        assert forbidden not in body


def test_generator_never_touches_the_network_or_database():
    with open(anchor.__file__, encoding="utf-8") as handle:
        body = handle.read()
    for forbidden in ("requests", "urllib", "http.client", "supabase", "socket"):
        assert forbidden not in body


def test_python_version_guard():
    assert sys.version_info >= (3, 11)

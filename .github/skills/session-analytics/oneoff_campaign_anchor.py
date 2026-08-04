#!/usr/bin/env python3
"""One-off campaign close-out anchor generator.

Freezes the process telemetry of exactly one contiguous slice of exactly one
Copilot transcript into two committed artifacts:

* a canonical JSONL ledger (one row per selected event, no message content), and
* a markdown close-out record whose every number is recomputable from the ledger.

Boundary contract
-----------------
``--session-slice <session-uuid>:<start-uuid>:<end-uuid>`` selects the events
from the line carrying ``start-uuid`` (inclusive) up to, but not including, the
line carrying ``end-uuid``.  Selection follows *file order*; timestamps never
participate.  ``EOF`` is not accepted as a boundary because an appended
transcript would silently move it.

Append invariance
-----------------
Only the prefix and the slice (file head through the exclusive anchor line,
that line included) are parsed and validated.  Anything after the exclusive
anchor is never read, so appending to a live transcript cannot change the
digests, the ledger or the record.

Strictness
----------
Inside the validated range the script fails closed on malformed JSON, a missing
``id``, a missing or naive ``timestamp``, a duplicate ``id`` and a
``tool.execution_start`` without ``toolName``.  Non-monotonic timestamps are
legal transcript data and only raise a stderr diagnostic.

Privacy
-------
The ledger stores identifiers, timestamps, event types, tool names and turn
indices only.  Message content, tool arguments, prompts, file paths and raw
``data`` payloads are never written.

This module is self-contained: it imports nothing from this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
RECORD_KIND = "process_telemetry"
OWNING_SPEC_SLUG = "evaluation-framework"
DEFAULT_LEDGER_DIR = "docs/evaluation/campaigns/ledger"

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
BLOB_RE = re.compile(r"^git-blob-sha1:[0-9a-f]{40}$")
PLACEHOLDER_RE = re.compile(r"<[^<>]*>")
OUTCOME_RE = re.compile(r"^([0-9a-f]{40})(?::(.+))?$")

TOP_LEVEL_FIELDS = frozenset(
    {
        "title",
        "description",
        "schema_version",
        "record_kind",
        "campaign_slug",
        "owning_spec_slug",
        "generator_source_commit",
        "generator_blobs",
        "ledger_path",
        "ledger_digest",
        "session",
        "process",
        "outcome_refs",
    }
)
SESSION_FIELDS = (
    "session_id",
    "start_event_id",
    "end_event_id_exclusive",
    "selected_events",
    "first_timestamp",
    "last_timestamp",
    "slice_digest",
)
PROCESS_FIELDS = (
    "user_turns",
    "assistant_turns",
    "tool_calls",
    "avg_tools_per_turn",
    "wall_span_hours",
    "tool_top8",
)
LEDGER_KEYS = ("session_id", "i", "event_id", "timestamp", "type", "tool_name", "turn_index")
BODY_SECTIONS = ("process", "session", "outcome_refs")

RECOMPUTE_SECTION = (
    "1. Read the ledger named by `ledger_path`. Every line is one selected event with the keys "
    "`session_id`, `i`, `event_id`, `timestamp`, `type`, `tool_name` and `turn_index`.",
    "2. Recompute `## Process`: `user_turns` counts rows whose `type` is `user.message`; "
    "`assistant_turns` counts `assistant.turn_start`; `tool_calls` counts `tool.execution_start`; "
    "`avg_tools_per_turn` is `tool_calls / user_turns` rounded to one decimal, or `0` when "
    "`user_turns` is zero; `wall_span_hours` is the span between the smallest and the largest "
    "`timestamp` expressed in hours and rounded to two decimals; the tool table ranks `tool_name` "
    "over `tool.execution_start` rows by count descending, then by name ascending, keeping the "
    "first eight.",
    "3. Recompute `selected_events` as the ledger row count, and `first_timestamp` / "
    "`last_timestamp` as the smallest / largest `timestamp` value.",
    "4. Recompute `ledger_digest` by hashing the whole ledger file with SHA-256 and prefixing the "
    "hex digest with `sha256:`. It must equal `ledger_digest`, and its first twelve hex characters "
    "must equal the suffix in the ledger file name.",
    "5. Recompute `slice_digest` from the original transcript alone: take the raw bytes of every "
    "selected line with its line terminator removed, join them with a single line feed, hash with "
    "SHA-256 and prefix with `sha256:`.",
)


class AnchorError(RuntimeError):
    """Any condition that must abort the run without touching the filesystem."""


@dataclass(frozen=True)
class SliceEvent:
    event_id: str
    timestamp: datetime
    type: str | None
    tool_name: str | None
    raw_line: bytes


# ── git ───────────────────────────────────────────────────────────────────────

def _git(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AnchorError(f"git {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip()


def _git_ok(repo_root: Path, *args: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


# ── timestamps ────────────────────────────────────────────────────────────────

def _parse_timestamp(value: str, line_number: int) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AnchorError(f"line {line_number}: unparsable timestamp {value!r}: {exc}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnchorError(f"line {line_number}: naive timestamp {value!r}")
    return parsed


def canonical_timestamp(value: datetime) -> str:
    text = value.astimezone(timezone.utc).isoformat()
    return text[:-6] + "Z" if text.endswith("+00:00") else text


# ── transcript ────────────────────────────────────────────────────────────────

def read_raw_lines(path: Path) -> list[bytes]:
    data = path.read_bytes()
    if not data:
        return []
    parts = data.split(b"\n")
    if parts and parts[-1] == b"":
        parts.pop()
    return [part[:-1] if part.endswith(b"\r") else part for part in parts]


def locate_transcript(transcripts_dir: Path, session_id: str) -> Path:
    if not transcripts_dir.is_dir():
        raise AnchorError(f"transcripts dir not found: {transcripts_dir}")
    matches = sorted(p for p in transcripts_dir.rglob("*.jsonl") if p.stem == session_id)
    if not matches:
        raise AnchorError(f"no transcript named {session_id}.jsonl under {transcripts_dir}")
    if len(matches) > 1:
        raise AnchorError(f"ambiguous transcript for {session_id}: {[str(m) for m in matches]}")
    return matches[0]


def extract_slice(lines: list[bytes], start_id: str, end_id: str) -> list[SliceEvent]:
    if start_id == end_id:
        raise AnchorError("start_event_id equals end_event_id_exclusive; the slice would be empty")

    scanned: list[SliceEvent] = []
    seen_ids: set[str] = set()
    end_index: int | None = None

    for index, raw in enumerate(lines):
        line_number = index + 1
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AnchorError(f"line {line_number}: invalid UTF-8: {exc}") from exc
        try:
            event = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AnchorError(f"line {line_number}: malformed JSON: {exc}") from exc
        if not isinstance(event, dict):
            raise AnchorError(f"line {line_number}: event is not a JSON object")

        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise AnchorError(f"line {line_number}: missing 'id'")
        if event_id in seen_ids:
            raise AnchorError(f"line {line_number}: duplicate id {event_id}")
        seen_ids.add(event_id)

        raw_timestamp = event.get("timestamp")
        if not isinstance(raw_timestamp, str) or not raw_timestamp:
            raise AnchorError(f"line {line_number}: missing 'timestamp'")
        timestamp = _parse_timestamp(raw_timestamp, line_number)

        raw_type = event.get("type")
        event_type = raw_type if isinstance(raw_type, str) else None

        tool_name: str | None = None
        if event_type == "tool.execution_start":
            data = event.get("data")
            candidate = data.get("toolName") if isinstance(data, dict) else None
            if not isinstance(candidate, str) or not candidate:
                raise AnchorError(f"line {line_number}: tool.execution_start without 'toolName'")
            tool_name = candidate

        scanned.append(SliceEvent(event_id, timestamp, event_type, tool_name, raw))

        if event_id == end_id:
            end_index = index
            break

    if end_index is None:
        raise AnchorError(
            f"end_event_id_exclusive {end_id} not found in the transcript; "
            "an unbounded slice is refused"
        )

    start_index = next((i for i, ev in enumerate(scanned) if ev.event_id == start_id), None)
    if start_index is None:
        raise AnchorError(f"start_event_id {start_id} not found before {end_id}")
    if start_index >= end_index:
        raise AnchorError("start_event_id is not before end_event_id_exclusive")

    return scanned[start_index:end_index]


def report_non_monotonic(events: list[SliceEvent], stream: Any) -> int:
    reversals = 0
    for index in range(1, len(events)):
        if events[index].timestamp < events[index - 1].timestamp:
            reversals += 1
            print(
                f"diagnostic: non-monotonic timestamp at slice index {index} "
                f"({events[index].event_id})",
                file=stream,
            )
    return reversals


# ── ledger ────────────────────────────────────────────────────────────────────

def build_ledger_rows(session_id: str, events: list[SliceEvent]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    turn_index = 0
    for index, event in enumerate(events):
        if event.type == "user.message":
            turn_index += 1
        rows.append(
            {
                "session_id": session_id,
                "i": index,
                "event_id": event.event_id,
                "timestamp": canonical_timestamp(event.timestamp),
                "type": event.type,
                "tool_name": event.tool_name,
                "turn_index": turn_index,
            }
        )
    return rows


def render_ledger(rows: list[dict[str, Any]]) -> bytes:
    chunks = []
    for row in rows:
        ordered = {key: row[key] for key in LEDGER_KEYS}
        chunks.append(json.dumps(ordered, separators=(",", ":"), ensure_ascii=False))
    return ("\n".join(chunks) + "\n").encode("utf-8")


def sha256_field(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def slice_digest(events: list[SliceEvent]) -> str:
    return sha256_field(b"\n".join(event.raw_line for event in events))


# ── derived metrics ───────────────────────────────────────────────────────────

def compute_process(rows: list[dict[str, Any]]) -> dict[str, Any]:
    user_turns = sum(1 for row in rows if row["type"] == "user.message")
    assistant_turns = sum(1 for row in rows if row["type"] == "assistant.turn_start")
    tool_rows = [row for row in rows if row["type"] == "tool.execution_start"]
    tool_calls = len(tool_rows)
    counts = Counter(row["tool_name"] for row in tool_rows)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    timestamps = [row["timestamp"] for row in rows]
    first = min(timestamps)
    last = max(timestamps)
    span = _parse_timestamp(last, 0) - _parse_timestamp(first, 0)
    return {
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "tool_calls": tool_calls,
        "avg_tools_per_turn": round(tool_calls / user_turns, 1) if user_turns else 0,
        "wall_span_hours": round(span.total_seconds() / 3600, 2),
        "tool_top8": [[name, count] for name, count in ranked[:8]],
    }


def compute_span(rows: list[dict[str, Any]]) -> tuple[str, str]:
    timestamps = [row["timestamp"] for row in rows]
    ordered = sorted(timestamps, key=lambda value: _parse_timestamp(value, 0))
    return ordered[0], ordered[-1]


def recompute_turn_indices(rows: list[dict[str, Any]]) -> list[int]:
    indices: list[int] = []
    turn_index = 0
    for row in rows:
        if row["type"] == "user.message":
            turn_index += 1
        indices.append(turn_index)
    return indices


# ── record rendering ──────────────────────────────────────────────────────────

def _yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _number(value: Any) -> str:
    return str(value)


def render_record(payload: dict[str, Any]) -> str:
    lines = ["---"]
    for key in sorted(k for k in payload if k not in BODY_SECTIONS):
        value = payload[key]
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key in sorted(value):
                lines.append(f"  {_yaml_scalar(sub_key)}: {_yaml_scalar(value[sub_key])}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")

    process = payload["process"]
    lines += ["", "## Process", "", "| Metric | Value |", "| --- | --- |"]
    for field in PROCESS_FIELDS:
        if field == "tool_top8":
            continue
        lines.append(f"| {field} | {_number(process[field])} |")

    lines += ["", "### Tool top 8", ""]
    if process["tool_top8"]:
        lines += ["| Tool | Count |", "| --- | --- |"]
        for name, count in process["tool_top8"]:
            lines.append(f"| {name} | {count} |")
    else:
        lines.append("_No tool call was selected by this slice._")

    session = payload["session"]
    lines += ["", "## Session", "", "| Field | Value |", "| --- | --- |"]
    for field in SESSION_FIELDS:
        lines.append(f"| {field} | {_number(session[field])} |")

    lines += ["", "## Outcome references", ""]
    for ref in payload["outcome_refs"]:
        lines.append(f"- {ref}")

    lines += ["", "## Recompute", ""]
    lines += list(RECOMPUTE_SECTION)

    return "\n".join(lines) + "\n"


def assert_output_shape(text: str) -> None:
    if "\r" in text:
        raise AnchorError("record contains a carriage return")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise AnchorError("record must end with exactly one line feed")
    for number, line in enumerate(text.split("\n")[:-1], start=1):
        if line != line.rstrip():
            raise AnchorError(f"record line {number} has trailing whitespace")
        if line.startswith("# "):
            raise AnchorError(f"record line {number} is an H1 while frontmatter carries the title")


# ── validation ────────────────────────────────────────────────────────────────

def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        found: list[str] = []
        for key, item in value.items():
            found += _walk_strings(key) + _walk_strings(item)
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found += _walk_strings(item)
        return found
    return []


def validate_outcome_ref(repo_root: Path, ref: str) -> None:
    match = OUTCOME_RE.match(ref)
    if not match:
        raise AnchorError(
            f"outcome_ref {ref!r} must be a lowercase 40-hex commit sha, optionally '<sha>:<path>'"
        )
    sha, path = match.group(1), match.group(2)
    object_type = _git(repo_root, "cat-file", "-t", sha)
    if object_type != "commit":
        raise AnchorError(f"outcome_ref {ref!r} points at a {object_type}, not a commit")
    if path is not None and not _git_ok(repo_root, "cat-file", "-e", f"{sha}:{path}"):
        raise AnchorError(f"outcome_ref {ref!r}: path is not readable in that commit")
    if not _git_ok(repo_root, "merge-base", "--is-ancestor", sha, "origin/main"):
        raise AnchorError(f"outcome_ref {ref!r} is not an ancestor of origin/main; it is not durable")


def validate_payload(
    payload: dict[str, Any],
    ledger_bytes: bytes,
    slice_events: list[SliceEvent],
    cli_end_event_id: str,
    repo_root: Path,
) -> None:
    if set(payload) != TOP_LEVEL_FIELDS:
        missing = sorted(TOP_LEVEL_FIELDS - set(payload))
        extra = sorted(set(payload) - TOP_LEVEL_FIELDS)
        raise AnchorError(f"record fields off contract (missing={missing}, extra={extra})")

    session = payload["session"]
    if set(session) != set(SESSION_FIELDS):
        raise AnchorError("session map off contract")
    process = payload["process"]
    if set(process) != set(PROCESS_FIELDS):
        raise AnchorError("process map off contract")

    for text in _walk_strings(payload):
        if PLACEHOLDER_RE.search(text):
            raise AnchorError(f"unresolved placeholder in {text!r}")

    if payload["schema_version"] != SCHEMA_VERSION:
        raise AnchorError("schema_version must be the constant 1")
    if payload["record_kind"] != RECORD_KIND:
        raise AnchorError(f"record_kind must be the constant {RECORD_KIND}")
    if payload["owning_spec_slug"] != OWNING_SPEC_SLUG:
        raise AnchorError(f"owning_spec_slug must be the constant {OWNING_SPEC_SLUG}")
    if not SLUG_RE.match(payload["campaign_slug"]):
        raise AnchorError("campaign_slug is not a lowercase hyphenated slug")
    if not SHA1_RE.match(payload["generator_source_commit"]):
        raise AnchorError("generator_source_commit is not a 40-hex sha")
    if not payload["generator_blobs"]:
        raise AnchorError("generator_blobs must not be empty")
    for blob_path, blob_value in payload["generator_blobs"].items():
        if blob_path.startswith("/") or ".." in Path(blob_path).parts:
            raise AnchorError(f"generator_blobs key {blob_path!r} is not repo-relative")
        if not BLOB_RE.match(blob_value):
            raise AnchorError(f"generator_blobs value {blob_value!r} is not 'git-blob-sha1:<40hex>'")
    if not DIGEST_RE.match(payload["ledger_digest"]):
        raise AnchorError("ledger_digest is not 'sha256:<64hex>'")
    if not DIGEST_RE.match(session["slice_digest"]):
        raise AnchorError("slice_digest is not 'sha256:<64hex>'")
    for field in ("session_id", "start_event_id", "end_event_id_exclusive"):
        if not UUID_RE.match(session[field]):
            raise AnchorError(f"session.{field} is not a lowercase UUID")
    if session["end_event_id_exclusive"] != cli_end_event_id:
        raise AnchorError("session.end_event_id_exclusive does not match the requested boundary")

    ledger_path = payload["ledger_path"]
    if ledger_path.startswith("/") or "\\" in ledger_path or ".." in Path(ledger_path).parts:
        raise AnchorError(f"ledger_path {ledger_path!r} is not a repo-relative POSIX path")
    if sha256_field(ledger_bytes) != payload["ledger_digest"]:
        raise AnchorError("ledger_digest does not match the ledger bytes")
    hex12 = payload["ledger_digest"].split(":", 1)[1][:12]
    if not Path(ledger_path).name.endswith(f"-{hex12}.jsonl"):
        raise AnchorError("ledger file name does not carry the first 12 hex characters of its digest")

    rows = _parse_ledger(ledger_bytes)
    if not rows:
        raise AnchorError("ledger is empty")
    if len(rows) != session["selected_events"]:
        raise AnchorError("selected_events does not match the ledger row count")
    if session["selected_events"] < 1:
        raise AnchorError("selected_events must be at least 1")
    if any(row["session_id"] != session["session_id"] for row in rows):
        raise AnchorError("a ledger row carries a foreign session_id")
    if [row["i"] for row in rows] != list(range(len(rows))):
        raise AnchorError("ledger index column is not a dense 0-based sequence")
    if [row["turn_index"] for row in rows] != recompute_turn_indices(rows):
        raise AnchorError("ledger turn_index column does not match the recomputed turn sequence")
    if rows[0]["event_id"] != session["start_event_id"]:
        raise AnchorError("first ledger row is not the start anchor")

    recomputed_process = compute_process(rows)
    if recomputed_process != process:
        raise AnchorError(f"process recomputed from the ledger differs: {recomputed_process} != {process}")
    first_timestamp, last_timestamp = compute_span(rows)
    if (first_timestamp, last_timestamp) != (session["first_timestamp"], session["last_timestamp"]):
        raise AnchorError("first/last timestamp recomputed from the ledger differs")

    if slice_digest(slice_events) != session["slice_digest"]:
        raise AnchorError("slice_digest does not match the raw transcript lines")

    refs = payload["outcome_refs"]
    if not isinstance(refs, list) or not refs:
        raise AnchorError("outcome_refs must hold at least one reference")
    for ref in refs:
        validate_outcome_ref(repo_root, ref)


def _parse_ledger(ledger_bytes: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    text = ledger_bytes.decode("utf-8")
    if not text.endswith("\n"):
        raise AnchorError("ledger must end with a line feed")
    for number, line in enumerate(text.split("\n")[:-1], start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnchorError(f"ledger line {number}: malformed JSON: {exc}") from exc
        if not isinstance(row, dict) or tuple(row) != LEDGER_KEYS:
            raise AnchorError(f"ledger line {number}: key set or order off contract")
        rows.append(row)
    return rows


# ── publication ───────────────────────────────────────────────────────────────

def _decide(path: Path, data: bytes) -> bool:
    """Return True when the file still has to be written."""
    if not path.exists():
        return True
    if path.read_bytes() == data:
        return False
    raise AnchorError(f"{path} already exists with different content; refusing to overwrite")


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campaign", required=True, help="campaign slug, also the ledger file stem")
    parser.add_argument(
        "--session-slice",
        action="append",
        metavar="SESSION:START:END_EXCLUSIVE",
        help="exactly one slice of exactly one session; the end anchor is excluded",
    )
    parser.add_argument("--outcome-ref", action="append", metavar="SHA[:PATH]", help="durable outcome reference")
    parser.add_argument("--record-output", required=True, help="path of the close-out record")
    parser.add_argument("--ledger-dir", default=DEFAULT_LEDGER_DIR, help="directory holding the ledger")
    parser.add_argument("--transcripts-dir", required=True, help="directory scanned for '<session>.jsonl'")
    parser.add_argument("--repo-root", default=None, help="repository root; defaults to this file's repository")
    return parser


def _parse_slice(values: list[str] | None) -> tuple[str, str, str]:
    if not values:
        raise AnchorError("--session-slice is required")
    if len(values) != 1:
        raise AnchorError("--session-slice may be given exactly once; a campaign is a single slice")
    parts = values[0].split(":")
    if len(parts) != 3:
        raise AnchorError("--session-slice must be '<session-uuid>:<start-uuid>:<end-uuid>'")
    for part in parts:
        if part.strip().upper() == "EOF":
            raise AnchorError("the EOF sentinel is refused; an appended transcript would move it")
        if not UUID_RE.match(part):
            raise AnchorError(f"{part!r} is not a lowercase UUID")
    return parts[0], parts[1], parts[2]


def _resolve_repo_root(explicit: str | None) -> Path:
    base = Path(explicit).resolve() if explicit else Path(__file__).resolve().parents[3]
    top = _git(base, "rev-parse", "--show-toplevel")
    return Path(top).resolve()


def _relative_to_repo(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError as exc:
        raise AnchorError(f"{path} is outside the repository at {repo_root}") from exc


def run(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    campaign_slug = args.campaign
    if not SLUG_RE.match(campaign_slug):
        raise AnchorError(f"--campaign {campaign_slug!r} is not a lowercase hyphenated slug")
    session_id, start_event_id, end_event_id = _parse_slice(args.session_slice)
    outcome_refs = list(args.outcome_ref or [])
    if not outcome_refs:
        raise AnchorError("at least one --outcome-ref is required")

    repo_root = _resolve_repo_root(args.repo_root)
    generator_source_commit = _git(repo_root, "rev-parse", "HEAD")
    if not SHA1_RE.match(generator_source_commit):
        raise AnchorError(f"unexpected HEAD {generator_source_commit!r}")

    generator_path = Path(__file__).resolve()
    generator_rel = _relative_to_repo(repo_root, generator_path)
    working_blob = _git(repo_root, "hash-object", "--", str(generator_path))
    committed_blob = _git(repo_root, "rev-parse", f"{generator_source_commit}:{generator_rel}")
    if working_blob != committed_blob:
        raise AnchorError(
            f"{generator_rel} differs from its committed blob at {generator_source_commit}; "
            "commit the generator before freezing an anchor"
        )

    transcript = locate_transcript(Path(args.transcripts_dir).expanduser(), session_id)
    events = extract_slice(read_raw_lines(transcript), start_event_id, end_event_id)
    report_non_monotonic(events, sys.stderr)

    rows = build_ledger_rows(session_id, events)
    ledger_bytes = render_ledger(rows)
    ledger_digest = sha256_field(ledger_bytes)
    hex12 = ledger_digest.split(":", 1)[1][:12]

    ledger_dir = Path(args.ledger_dir)
    ledger_file = (ledger_dir if ledger_dir.is_absolute() else repo_root / ledger_dir) / f"{campaign_slug}-{hex12}.jsonl"
    ledger_rel = _relative_to_repo(repo_root, ledger_file)
    record_path = Path(args.record_output)
    record_file = record_path if record_path.is_absolute() else repo_root / record_path
    _relative_to_repo(repo_root, record_file)

    first_timestamp, last_timestamp = compute_span(rows)
    payload = {
        "title": f"Campaign close-out: {campaign_slug}",
        "description": (
            f"Process telemetry for campaign {campaign_slug}; "
            f"all metrics recomputable from {ledger_rel}."
        ),
        "schema_version": SCHEMA_VERSION,
        "record_kind": RECORD_KIND,
        "campaign_slug": campaign_slug,
        "owning_spec_slug": OWNING_SPEC_SLUG,
        "generator_source_commit": generator_source_commit,
        "generator_blobs": {generator_rel: f"git-blob-sha1:{working_blob}"},
        "ledger_path": ledger_rel,
        "ledger_digest": ledger_digest,
        "session": {
            "session_id": session_id,
            "start_event_id": start_event_id,
            "end_event_id_exclusive": end_event_id,
            "selected_events": len(rows),
            "first_timestamp": first_timestamp,
            "last_timestamp": last_timestamp,
            "slice_digest": slice_digest(events),
        },
        "process": compute_process(rows),
        "outcome_refs": outcome_refs,
    }

    validate_payload(payload, ledger_bytes, events, end_event_id, repo_root)
    record_text = render_record(payload)
    assert_output_shape(record_text)
    record_bytes = record_text.encode("utf-8")

    ledger_pending = _decide(ledger_file, ledger_bytes)
    record_pending = _decide(record_file, record_bytes)

    if _git(repo_root, "rev-parse", "HEAD") != generator_source_commit:
        raise AnchorError("HEAD moved during the run; nothing was written")

    if ledger_pending:
        _write_atomic(ledger_file, ledger_bytes)
    if record_pending:
        _write_atomic(record_file, record_bytes)

    if ledger_file.read_bytes() != ledger_bytes:
        raise AnchorError("ledger read-back mismatch")
    if record_file.read_bytes() != record_bytes:
        raise AnchorError("record read-back mismatch")

    state = "written" if (ledger_pending or record_pending) else "unchanged"
    print(f"{state}: {ledger_rel}")
    print(f"{state}: {_relative_to_repo(repo_root, record_file)}")


def main(argv: list[str] | None = None) -> int:
    try:
        run(argv)
    except AnchorError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

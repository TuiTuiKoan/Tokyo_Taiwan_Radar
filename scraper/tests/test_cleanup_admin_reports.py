from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

import _oneoff_cleanup_admin_reports as cleanup


REAL_POLICY_LOADER = cleanup._load_auto_qa_policy
R1 = "10000000-0000-4000-8000-000000000001"
R2 = "10000000-0000-4000-8000-000000000002"
R3 = "10000000-0000-4000-8000-000000000003"
R4 = "10000000-0000-4000-8000-000000000004"
R5 = "10000000-0000-4000-8000-000000000005"
R6 = "10000000-0000-4000-8000-000000000006"
R7 = "10000000-0000-4000-8000-000000000007"
E1 = "20000000-0000-4000-8000-000000000001"
E2 = "20000000-0000-4000-8000-000000000002"
E3 = "20000000-0000-4000-8000-000000000003"
E4 = "20000000-0000-4000-8000-000000000004"
E5 = "20000000-0000-4000-8000-000000000005"
E6 = "20000000-0000-4000-8000-000000000006"
E7 = "20000000-0000-4000-8000-000000000007"
HEAD = "a" * 40
AUTO_A = "auto_qa_missing_address"
AUTO_B = "auto_qa_missing_title"


def _test_classifier(report_types):
    tokens = [
        token
        for token in (report_types or [])
        if isinstance(token, str) and token
    ]
    if not tokens:
        return "empty"
    if any(token not in {AUTO_A, AUTO_B} for token in tokens):
        return "manual"
    return "single_auto" if len(tokens) == 1 else "compound_auto"


TEST_POLICY = cleanup.AutoQaPolicy(
    known_auto_qa_types=frozenset({AUTO_A, AUTO_B}),
    classifier=_test_classifier,
    payload_token_predicate=lambda token: token.startswith(
        ("field:", "fieldEdit:", "selectionReason:")
    ),
)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("network access is forbidden in T-A0 core tests")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(cleanup, "_load_auto_qa_policy", lambda: TEST_POLICY)


def _report(report_id: str = R1, event_id: str = E1, report_types=None, **overrides):
    row = {
        "id": report_id,
        "event_id": event_id,
        "report_types": [AUTO_A] if report_types is None else report_types,
        "locale": "ja",
        "status": "pending",
        "admin_notes": None,
        "confirmed_at": None,
        "created_at": "2026-08-11T00:00:00+00:00",
        "suggested_category": None,
        "custom_report_field": {"preserved": True},
    }
    row.update(overrides)
    return row


def _event(event_id: str = E1, **overrides):
    row = {
        "id": event_id,
        "is_active": True,
        "annotation_status": "annotated",
        "source_name": "fixture_source",
        "name_ja": "Fixture",
        "raw_title": "Fixture",
        "location_name": "Venue",
        "location_address": "Address",
        "location_prefectures": ["Tokyo"],
        "category": ["art"],
        "start_date": "2026-08-12T00:00:00+00:00",
        "organizer": "Organizer",
        "business_hours": "10:00-18:00",
        "performers": ["Performer"],
        "performer": "Performer",
        "parent_event_id": None,
        "description_zh": "Description",
        "name_zh": "Fixture",
        "location_name_zh": "Venue",
        "location_address_zh": "Address",
        "business_hours_zh": "10:00-18:00",
        "organizer_zh": "Organizer",
        "selection_reason": "{}",
        "event_form": ["exhibition"],
        "raw_description": "Raw description",
        "source_url": "https://example.test/event",
        "created_at": "2026-08-10T00:00:00+00:00",
        "custom_event_field": {"nested": [1, None, "x"]},
    }
    row.update(overrides)
    return row


class _Result:
    def __init__(self, data, count):
        self.data = data
        self.count = count


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.projection = "*"
        self.count_mode = None
        self.filters = []
        self.ordering = None
        self.window = None

    def select(self, projection="*", *, count=None):
        self.projection = projection
        self.count_mode = count
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def order(self, column, desc=False):
        self.ordering = (column, desc)
        return self

    def range(self, start, end):
        self.window = (start, end)
        return self

    def __getattr__(self, name):
        if name in cleanup.MUTATION_METHODS:
            def blocked(*_args, **_kwargs):
                self.client.mutator_calls.append((self.table, name))
                raise AssertionError(f"mutator called: {name}")

            return blocked
        raise AttributeError(name)

    def execute(self):
        rows = [deepcopy(row) for row in self.client.tables.get(self.table, [])]
        for kind, column, value in self.filters:
            if kind == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif kind == "in":
                wanted = set(value)
                rows = [row for row in rows if row.get(column) in wanted]
        if self.ordering:
            column, desc = self.ordering
            rows.sort(key=lambda row: str(row.get(column) or ""), reverse=desc)
        actual_count = len(rows)
        count_call = self.client.count_calls.setdefault(self.table, 0)
        overrides = self.client.count_overrides.get(self.table, [])
        exact_count = overrides[count_call] if count_call < len(overrides) else actual_count
        self.client.count_calls[self.table] = count_call + 1
        if self.window:
            start, end = self.window
            rows = rows[start : end + 1]
        if self.projection != "*":
            columns = {column.strip() for column in self.projection.split(",") if column.strip()}
            rows = [
                {key: value for key, value in row.items() if key in columns}
                for row in rows
            ]
        self.client.calls.append(
            {
                "table": self.table,
                "projection": self.projection,
                "count": self.count_mode,
                "filters": deepcopy(self.filters),
                "order": self.ordering,
                "range": self.window,
            }
        )
        return _Result(rows, exact_count if self.count_mode == "exact" else None)


class _Client:
    def __init__(self, *, reports=None, events=None, count_overrides=None):
        self.tables = {
            "event_reports": [deepcopy(row) for row in (reports or [])],
            "events": [deepcopy(row) for row in (events or [])],
        }
        self.count_overrides = deepcopy(count_overrides or {})
        self.count_calls = {}
        self.calls = []
        self.mutator_calls = []

    def table(self, name):
        return _Query(self, name)

    def __getattr__(self, name):
        if name in cleanup.MUTATION_METHODS:
            def blocked(*_args, **_kwargs):
                self.mutator_calls.append(("client", name))
                raise AssertionError(f"client mutator called: {name}")

            return blocked
        raise AttributeError(name)


def _three_row_client():
    return _Client(
        reports=[
            _report(R3, E3),
            _report(R1, E1),
            _report(R2, E2),
        ],
        events=[_event(E2), _event(E3), _event(E1)],
    )


def _ledger(client=None, *, page_size=2):
    return cleanup.build_discovery_ledger(
        client or _Client(reports=[_report()], events=[_event()]),
        repository_head=HEAD,
        page_size=page_size,
    )


def _verify_ledger(ledger, *, expected_repository_head=HEAD):
    return cleanup.verify_discovery_ledger(
        ledger,
        expected_repository_head=expected_repository_head,
    )


def _artifact_root(monkeypatch, tmp_path):
    root = tmp_path / "worktree"
    root.mkdir()
    root = root.resolve()
    monkeypatch.setattr(cleanup, "ROOT", root)
    monkeypatch.setattr(cleanup, "_is_git_ignored", lambda _path, *, root: True)
    return root


def _artifact_output(root: Path, name: str = "artifact.json") -> Path:
    return root / "tmp" / "admin-qa-cleanup" / "20260811T120000Z" / name


def _sealed_payload(**overrides):
    return cleanup._seal(
        {
            "schema": {"name": "fixture-artifact", "version": 1},
            "value": "fixture",
            **overrides,
        }
    )


def _assert_failed_publish_is_clean(output: Path):
    assert not output.exists()
    assert not output.is_symlink()
    if output.parent.exists():
        assert list(output.parent.glob(f".{output.name}.*.tmp")) == []


class _FaultyBinaryFile:
    def __init__(self, handle, fault):
        self._handle = handle
        self._fault = fault

    def write(self, content):
        if self._fault == "write":
            raise OSError("injected write failure")
        if self._fault == "short_write":
            return self._handle.write(content[:-1])
        return self._handle.write(content)

    def flush(self):
        if self._fault == "flush":
            raise OSError("injected flush failure")
        return self._handle.flush()

    def fileno(self):
        return self._handle.fileno()

    def close(self):
        self._handle.close()
        if self._fault == "close":
            raise OSError("injected close failure")

    def __getattr__(self, name):
        return getattr(self._handle, name)


class _AfterReadBinaryFile:
    def __init__(self, handle, mutate):
        self._handle = handle
        self._mutate = mutate

    def read(self, *args, **kwargs):
        content = self._handle.read(*args, **kwargs)
        self._mutate()
        return content

    def fileno(self):
        return self._handle.fileno()

    def close(self):
        return self._handle.close()

    def __getattr__(self, name):
        return getattr(self._handle, name)


class _NestedMutator:
    def __init__(self):
        self.deepcopy_calls = 0
        self.update_calls = 0

    def __deepcopy__(self, _memo):
        self.deepcopy_calls += 1
        return self

    def update(self, *_args, **_kwargs):
        self.update_calls += 1


def _replace_staging_with_competitor(output: Path, content: bytes) -> Path:
    staging = next(output.parent.glob(f".{output.name}.*.tmp"))
    staging.unlink()
    staging.write_bytes(content)
    staging.chmod(0o400)
    return staging


def _run_cli_with_side_effect_spies(arguments):
    with TemporaryDirectory() as directory:
        temporary = Path(directory)
        marker = temporary / "side-effects.log"
        (temporary / "sitecustomize.py").write_text(
            """import os
import socket
import sys
import types

def record(label):
    with open(os.environ["T_A0_SIDE_EFFECT_MARKER"], "a", encoding="utf-8") as handle:
        handle.write(label + "\\n")

dotenv = types.ModuleType("dotenv")
dotenv.load_dotenv = lambda *args, **kwargs: record("dotenv")
sys.modules["dotenv"] = dotenv

supabase = types.ModuleType("supabase")
supabase.create_client = lambda *args, **kwargs: record("client")
sys.modules["supabase"] = supabase

def blocked_connection(*args, **kwargs):
    record("network")
    raise AssertionError("network attempted before argparse")

socket.create_connection = blocked_connection
socket.socket.connect = blocked_connection
""",
            encoding="utf-8",
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key
            not in {
                "SUPABASE_URL",
                "SUPABASE_SERVICE_ROLE_KEY",
                "OPENAI_API_KEY",
                "DEEPL_API_KEY",
            }
        }
        environment["PYTHONPATH"] = str(temporary)
        environment["T_A0_SIDE_EFFECT_MARKER"] = str(marker)
        result = subprocess.run(
            [sys.executable, str(Path(cleanup.__file__).resolve()), *arguments],
            cwd=Path(cleanup.__file__).resolve().parent,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        side_effects = marker.read_text(encoding="utf-8").splitlines() if marker.exists() else []
        return result, side_effects



def test_build_discovery_ledger_uses_complete_exact_count_pagination_and_before_images():
    client = _three_row_client()

    ledger = _ledger(client)

    assert [row["report_id"] for row in ledger["reports"]] == [R1, R2, R3]
    assert [row["event_id"] for row in ledger["events"]] == [E1, E2, E3]
    assert ledger["counts"]["pending_reports"] == 3
    assert ledger["counts"]["unique_report_ids"] == 3
    assert ledger["counts"]["referenced_event_ids"] == 3
    assert ledger["counts"]["fetched_events"] == 3
    assert ledger["query"]["reports"]["pagination"]["exact_count"] == 3
    assert ledger["query"]["reports"]["pagination"]["fetched_count"] == 3
    assert ledger["query"]["events"]["pagination"]["exact_count"] == 3
    assert [page["returned"] for page in ledger["query"]["reports"]["pagination"]["pages"]] == [2, 1]
    assert [page["returned"] for page in ledger["query"]["events"]["pagination"]["pages"]] == [2, 1]
    assert ledger["reports"][0]["before_image"]["custom_report_field"] == {"preserved": True}
    assert ledger["events"][0]["before_image"]["custom_event_field"] == {
        "nested": [1, None, "x"]
    }
    assert all(call["count"] == "exact" for call in client.calls)
    assert all(call["projection"] == "*" for call in client.calls)
    assert client.mutator_calls == []


def test_fetch_pending_reports_rejects_duplicate_ids_across_pages():
    client = _Client(
        reports=[_report(R1, E1), _report(R1, E2)],
        events=[_event(E1), _event(E2)],
    )

    with pytest.raises(RuntimeError, match="duplicate report id"):
        cleanup.fetch_pending_reports(client, page_size=1)


def test_fetch_pending_reports_rejects_missing_and_non_full_ids():
    missing = _report()
    missing.pop("id")
    with pytest.raises(RuntimeError, match="projection missing required fields"):
        cleanup.fetch_pending_reports(_Client(reports=[missing]), page_size=1)

    with pytest.raises(RuntimeError, match="full UUID required"):
        cleanup.fetch_pending_reports(
            _Client(reports=[_report(report_id=R1[:8])]),
            page_size=1,
        )


def test_fetch_pending_reports_rejects_exact_count_drift():
    client = _three_row_client()
    client.count_overrides["event_reports"] = [3, 4]

    with pytest.raises(RuntimeError, match="exact count drifted"):
        cleanup.fetch_pending_reports(client, page_size=2)


def test_build_discovery_ledger_rejects_missing_referenced_event():
    client = _Client(reports=[_report(R1, E1)], events=[])

    with pytest.raises(RuntimeError, match="referenced event count mismatch"):
        _ledger(client)


def test_classification_covers_every_class_and_routes_unknown_mixed_payload_and_empty():
    reports = [
        _report(R1, E1, [AUTO_A]),
        _report(R2, E2, [AUTO_A, AUTO_B]),
        _report(R3, E3, ["wrongCategory"]),
        _report(R4, E4, ["mystery_type"]),
        _report(R5, E5, []),
        _report(R6, E6, [AUTO_A, "wrongCategory"]),
        _report(R7, E7, [AUTO_A, "field:name_ja"]),
    ]

    by_id = {
        row["report_id"]: row
        for row in cleanup.classify_pending_reports(reports)
    }

    assert by_id[R1]["classification"] == "single_auto"
    assert by_id[R1]["review_reasons"] == []
    assert by_id[R2]["classification"] == "compound_auto"
    assert by_id[R2]["review_reasons"] == ["compound_auto"]
    assert by_id[R3]["classification"] == "manual"
    assert by_id[R3]["review_reasons"] == ["manual"]
    assert by_id[R3]["manual_tokens"] == ["wrongCategory"]
    assert by_id[R4]["unknown_tokens"] == ["mystery_type"]
    assert by_id[R5]["classification"] == "empty"
    assert by_id[R5]["review_reasons"] == ["empty"]
    assert by_id[R6]["review_reasons"] == ["manual", "mixed"]
    assert by_id[R7]["review_reasons"] == ["manual", "mixed", "payload_token"]
    assert by_id[R7]["payload_tokens"] == ["field:name_ja"]
    assert all(len(report_id) == 36 for report_id in by_id)
    assert all(row["predicate_resolution"] == "not_evaluated" for row in by_id.values())


def test_canonical_discovery_is_deterministic_across_row_and_key_order():
    first_client = _three_row_client()
    second_reports = [
        dict(reversed(list(row.items())))
        for row in reversed(first_client.tables["event_reports"])
    ]
    second_events = [
        dict(reversed(list(row.items())))
        for row in reversed(first_client.tables["events"])
    ]

    first = _ledger(first_client)
    second = _ledger(_Client(reports=second_reports, events=second_events))

    assert cleanup.canonical_json_bytes(first) == cleanup.canonical_json_bytes(second)
    assert first["digest_sha256"] == second["digest_sha256"]


@pytest.mark.parametrize(
    "tamper",
    [
        "missing_reports_query",
        "extra_query_key",
        "report_filter",
        "event_filter",
        "report_projection",
        "event_projection",
        "report_order",
        "event_table",
    ],
)
def test_verifier_rejects_resealed_query_contract_tampering(tamper):
    ledger = deepcopy(_ledger(_three_row_client()))
    query = ledger["query"]
    if tamper == "missing_reports_query":
        query.pop("reports")
    elif tamper == "extra_query_key":
        query["extra"] = {}
    elif tamper == "report_filter":
        query["reports"]["filters"] = {}
    elif tamper == "event_filter":
        query["events"]["filters"]["id"]["values"] = [E1]
    elif tamper == "report_projection":
        query["reports"]["projection"] = "id"
    elif tamper == "event_projection":
        query["events"]["projection"] = "id"
    elif tamper == "report_order":
        query["reports"]["order"][0]["direction"] = "desc"
    else:
        query["events"]["table"] = "event_reports"

    with pytest.raises(RuntimeError):
        _verify_ledger(cleanup._seal(ledger))


@pytest.mark.parametrize(
    "tamper",
    [
        "missing_pages",
        "empty_pages",
        "page_gap",
        "wrong_returned",
        "page_exact_count",
        "reconciled_999",
        "zero_page_size",
    ],
)
def test_verifier_rejects_resealed_pagination_tampering(tamper):
    ledger = deepcopy(_ledger(_three_row_client()))
    pagination = ledger["query"]["reports"]["pagination"]
    if tamper == "missing_pages":
        pagination.pop("pages")
    elif tamper == "empty_pages":
        pagination["pages"] = []
    elif tamper == "page_gap":
        pagination["pages"][1]["page"] = 3
    elif tamper == "wrong_returned":
        pagination["pages"][-1]["returned"] = 2
    elif tamper == "page_exact_count":
        pagination["pages"][0]["exact_count"] = 999
    elif tamper == "reconciled_999":
        pagination["exact_count"] = 999
        pagination["fetched_count"] = 999
    else:
        pagination["page_size"] = 0

    with pytest.raises(RuntimeError):
        _verify_ledger(cleanup._seal(ledger))


def _classification_ledger():
    reports = [
        _report(R1, E1, [AUTO_A]),
        _report(R2, E2, [AUTO_A, AUTO_B]),
        _report(R3, E3, ["wrongCategory"]),
        _report(R4, E4, ["mystery_type"]),
        _report(R5, E5, []),
        _report(R6, E6, [AUTO_A, "wrongCategory"]),
        _report(R7, E7, [AUTO_A, "field:name_ja"]),
    ]
    events = [_event(event_id) for event_id in (E1, E2, E3, E4, E5, E6, E7)]
    return _ledger(_Client(reports=reports, events=events), page_size=3)


@pytest.mark.parametrize(
    "tamper",
    [
        "classification_count",
        "review_reason_count",
        "classification",
        "known_auto_types",
        "manual_tokens",
        "unknown_tokens",
        "payload_tokens",
        "compound_auto_reason",
    ],
)
def test_verifier_rejects_resealed_counts_and_classification_metadata_drift(tamper):
    ledger = deepcopy(_classification_ledger())
    by_id = {row["report_id"]: row for row in ledger["reports"]}
    if tamper == "classification_count":
        ledger["counts"]["classifications"]["single_auto"] = 999
    elif tamper == "review_reason_count":
        ledger["counts"]["review_reasons"]["mixed"] = 999
    elif tamper == "classification":
        by_id[R1]["classification"] = "manual"
    elif tamper == "known_auto_types":
        by_id[R1]["known_auto_types"] = []
    elif tamper == "manual_tokens":
        by_id[R3]["manual_tokens"] = []
    elif tamper == "unknown_tokens":
        by_id[R4]["unknown_tokens"] = []
    elif tamper == "payload_tokens":
        by_id[R7]["payload_tokens"] = []
    else:
        by_id[R2]["review_reasons"] = []

    with pytest.raises(RuntimeError):
        _verify_ledger(cleanup._seal(ledger))


@pytest.mark.parametrize("collection", ["reports", "events"])
def test_verifier_rejects_resealed_noncanonical_entry_order(collection):
    ledger = deepcopy(_ledger(_three_row_client()))
    ledger[collection][0], ledger[collection][1] = ledger[collection][1], ledger[collection][0]

    with pytest.raises(RuntimeError, match="not canonically sorted"):
        _verify_ledger(cleanup._seal(ledger))


@pytest.mark.parametrize(
    "tamper",
    [
        "missing_contract",
        "extra_contract_key",
        "invalid_head",
        "schema_drift",
        "extra_top_level_key",
        "missing_digest",
    ],
)
def test_verifier_rejects_top_level_contract_head_schema_and_digest_drift(tamper):
    ledger = deepcopy(_ledger())
    if tamper == "missing_contract":
        ledger.pop("contract")
    elif tamper == "extra_contract_key":
        ledger["contract"]["extra"] = True
    elif tamper == "invalid_head":
        ledger["repository_head"] = "short"
    elif tamper == "schema_drift":
        ledger["schema"]["version"] = 999
    elif tamper == "extra_top_level_key":
        ledger["extra"] = True
    else:
        ledger.pop("digest_sha256")
        with pytest.raises(RuntimeError):
            _verify_ledger(ledger)
        return

    with pytest.raises(RuntimeError):
        _verify_ledger(cleanup._seal(ledger))


def test_verifier_requires_trusted_head_and_rejects_valid_resealed_head_drift():
    ledger = _ledger()

    with pytest.raises(TypeError, match="expected_repository_head"):
        cleanup.verify_discovery_ledger(ledger)
    with pytest.raises(RuntimeError, match="full repository HEAD required"):
        _verify_ledger(ledger, expected_repository_head="short")

    drifted = deepcopy(ledger)
    drifted["repository_head"] = "b" * 40
    drifted = cleanup._seal(drifted)
    with pytest.raises(RuntimeError, match="repository HEAD mismatch"):
        _verify_ledger(drifted)


def test_build_binds_external_repository_head_to_semantic_verifier(monkeypatch):
    seen = []
    real_verify = cleanup.verify_discovery_ledger

    def recording_verify(ledger, *, expected_repository_head, **kwargs):
        seen.append(expected_repository_head)
        return real_verify(
            ledger,
            expected_repository_head=expected_repository_head,
            **kwargs,
        )

    monkeypatch.setattr(cleanup, "verify_discovery_ledger", recording_verify)

    ledger = cleanup.build_discovery_ledger(
        _Client(reports=[_report()], events=[_event()]),
        repository_head=HEAD,
    )

    assert ledger["repository_head"] == HEAD
    assert seen == [HEAD]


def test_projection_omission_removes_real_fields_and_fails_predicate_contract(monkeypatch):
    projection = ",".join(sorted(cleanup.PREDICATE_EVENT_FIELDS - {"raw_description"}))
    monkeypatch.setattr(cleanup, "EVENT_PROJECTION", projection)
    client = _Client(reports=[_report()], events=[_event()])

    with pytest.raises(RuntimeError, match="raw_description"):
        _ledger(client)

    event_calls = [call for call in client.calls if call["table"] == "events"]
    assert event_calls[0]["projection"] == projection


def test_freeze_requires_two_identical_scans_and_writes_exclusive_mode_0400(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        ledger = _ledger()
        output = (
            root
            / "tmp"
            / "admin-qa-cleanup"
            / "20260811T120000Z"
            / "discovery-freeze.json"
        )

        written = cleanup.freeze_discovery_ledger(
            ledger,
            deepcopy(ledger),
            output,
            frozen_at="2026-08-11T12:00:00Z",
            expected_repository_head=HEAD,
        )

        artifact = cleanup.load_artifact(written)
        assert written == output
        assert stat.S_IMODE(written.stat().st_mode) == 0o400
        assert artifact["scan"]["required_complete_scans"] == 2
        assert artifact["scan"]["byte_identical"] is True
        assert artifact["scan"]["digests_sha256"] == [
            ledger["digest_sha256"],
            ledger["digest_sha256"],
        ]
        assert artifact["query"] == ledger["query"]
        assert artifact["counts"] == ledger["counts"]
        with pytest.raises(FileExistsError, match="already exists"):
            cleanup.freeze_discovery_ledger(
                ledger,
                deepcopy(ledger),
                output,
                frozen_at="2026-08-11T12:00:00Z",
                expected_repository_head=HEAD,
            )


def test_freeze_rejects_scan_digest_drift_without_publishing(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        first = _ledger()
        second = _ledger(
            _Client(
                reports=[_report(admin_notes="drift")],
                events=[_event()],
            )
        )
        output = _artifact_output(root, "freeze.json")

        with pytest.raises(RuntimeError, match="scan digest drift"):
            cleanup.freeze_discovery_ledger(
                first,
                second,
                output,
                frozen_at="2026-08-11T12:00:01Z",
                expected_repository_head=HEAD,
            )

        _assert_failed_publish_is_clean(output)


def test_export_manual_review_includes_all_review_routes_and_full_before_images(
    monkeypatch,
):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        reports = [
            _report(R1, E1, [AUTO_A]),
            _report(R2, E2, [AUTO_A, AUTO_B]),
            _report(R3, E3, ["wrongCategory"]),
            _report(R4, E4, ["mystery_type"]),
            _report(R5, E5, []),
            _report(R6, E6, [AUTO_A, "wrongCategory"]),
            _report(R7, E7, [AUTO_A, "field:name_ja"]),
        ]
        events = [_event(event_id) for event_id in (E1, E2, E3, E4, E5, E6, E7)]
        ledger = _ledger(_Client(reports=reports, events=events), page_size=3)
        output = _artifact_output(root, "manual-review.json")

        written = cleanup.export_manual_review(
            ledger,
            output,
            exported_at="2026-08-11T12:00:02Z",
            expected_repository_head=HEAD,
        )

        artifact = cleanup.load_artifact(written)
        by_id = {row["report_id"]: row for row in artifact["rows"]}
        assert set(by_id) == {R2, R3, R4, R5, R6, R7}
        assert R1 not in by_id
        assert by_id[R4]["review_reasons"] == ["manual", "unknown"]
        assert by_id[R5]["review_reasons"] == ["empty"]
        assert by_id[R6]["review_reasons"] == ["manual", "mixed"]
        assert by_id[R7]["payload_tokens"] == ["field:name_ja"]
        assert by_id[R2]["event_before_image"]["id"] == E2
        assert by_id[R2]["report_before_image"]["id"] == R2
        assert artifact["contract"]["classification_is_apply_allowlist"] is False
        assert artifact["contract"]["known_auto_membership_proves_predicate_resolution"] is False
        assert stat.S_IMODE(written.stat().st_mode) == 0o400


def test_artifacts_require_ignored_timestamp_directory(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        ledger = _ledger()
        bad = root / "tmp" / "admin-qa-cleanup" / "not-a-timestamp" / "freeze.json"

        with pytest.raises(RuntimeError, match="timestamp directory"):
            cleanup.freeze_discovery_ledger(
                ledger,
                deepcopy(ledger),
                bad,
                frozen_at="2026-08-11T12:00:00Z",
                expected_repository_head=HEAD,
            )


def test_freeze_export_and_artifact_ledger_bind_trusted_head(monkeypatch, tmp_path):
    root = _artifact_root(monkeypatch, tmp_path)
    drifted = deepcopy(_ledger())
    drifted["repository_head"] = "b" * 40
    drifted = cleanup._seal(drifted)

    with pytest.raises(RuntimeError, match="repository HEAD mismatch"):
        cleanup.freeze_discovery_ledger(
            drifted,
            deepcopy(drifted),
            _artifact_output(root, "drift-freeze.json"),
            frozen_at="2026-08-11T12:00:03Z",
            expected_repository_head=HEAD,
        )
    with pytest.raises(RuntimeError, match="repository HEAD mismatch"):
        cleanup.export_manual_review(
            drifted,
            _artifact_output(root, "drift-review.json"),
            exported_at="2026-08-11T12:00:04Z",
            expected_repository_head=HEAD,
        )
    with pytest.raises(RuntimeError, match="repository HEAD mismatch"):
        cleanup._ledger_from_artifact(
            drifted,
            expected_repository_head=HEAD,
        )

    freeze_payload = {
        "schema": cleanup.FREEZE_SCHEMA,
        "repository_head": "b" * 40,
        "discovery_ledger": _ledger(),
    }
    with pytest.raises(RuntimeError, match="freeze artifact repository HEAD mismatch"):
        cleanup._ledger_from_artifact(
            freeze_payload,
            expected_repository_head=HEAD,
        )

    assert list(root.rglob("drift-*.json")) == []


def test_core_logic_never_constructs_a_real_client_or_calls_any_mutator(monkeypatch):
    def forbidden_factory():
        raise AssertionError("core logic created a real client")

    monkeypatch.setattr(cleanup, "_create_read_only_client", forbidden_factory)
    client = _three_row_client()

    ledger = _ledger(client)

    assert ledger["complete"] is True
    assert client.mutator_calls == []
    for method in cleanup.MUTATION_METHODS:
        with pytest.raises(AssertionError, match="mutator called"):
            getattr(client.table("event_reports"), method)({})


def test_read_only_proxy_blocks_mutators_on_client_and_query_chain():
    target = SimpleNamespace()
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    target.execute = lambda: SimpleNamespace(data=[], count=0)
    proxy = cleanup.ReadOnlyProxy(target)

    assert proxy.table("event_reports").select("*", count="exact").execute().data == []
    for method in cleanup.MUTATION_METHODS:
        with pytest.raises(RuntimeError, match=f"blocked Supabase client access: {method}"):
            getattr(proxy, method)
        with pytest.raises(RuntimeError, match=f"blocked Supabase query access: {method}"):
            getattr(proxy.table("event_reports"), method)


def test_read_only_proxy_default_denies_storage_functions_auth_and_unknown_surfaces():
    target = SimpleNamespace(
        storage=SimpleNamespace(from_=lambda _bucket: SimpleNamespace(upload=lambda: None)),
        functions=SimpleNamespace(invoke=lambda _name: None),
        auth=SimpleNamespace(sign_out=lambda: None),
    )
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    target.eq = lambda *_args, **_kwargs: target
    target.in_ = lambda *_args, **_kwargs: target
    target.order = lambda *_args, **_kwargs: target
    target.range = lambda *_args, **_kwargs: target
    target.execute = lambda: SimpleNamespace(data=[], count=0)
    proxy = cleanup.ReadOnlyProxy(target)

    assert (
        proxy.table("event_reports")
        .select("*", count="exact")
        .eq("status", "pending")
        .in_("id", [R1])
        .order("id")
        .range(0, 0)
        .execute()
        .data
        == []
    )
    with pytest.raises(RuntimeError, match="blocked Supabase client access: storage"):
        proxy.storage.from_("bucket").upload(b"payload")
    with pytest.raises(RuntimeError, match="blocked Supabase client access: functions"):
        proxy.functions.invoke("function")
    with pytest.raises(RuntimeError, match="blocked Supabase client access: auth"):
        proxy.auth.sign_out()
    with pytest.raises(RuntimeError, match="blocked Supabase client access: unknown"):
        proxy.unknown()
    with pytest.raises(RuntimeError, match="blocked Supabase client access: select"):
        proxy.select("*")
    with pytest.raises(RuntimeError, match="blocked Supabase table access: secrets"):
        proxy.table("secrets")

    query = proxy.table("event_reports")
    for name in (*cleanup.MUTATION_METHODS, "storage", "auth", "table", "unknown"):
        with pytest.raises(RuntimeError, match=f"blocked Supabase query access: {name}"):
            getattr(query, name)


def test_read_only_proxy_exposes_no_raw_target_through_ordinary_attributes():
    target = _Client(reports=[_report()], events=[_event()])
    proxy = cleanup.ReadOnlyProxy(target)
    query = proxy.table("event_reports")
    escape_names = (
        "_target",
        "target",
        "raw",
        "raw_client",
        "client",
        "query",
        "_ReadOnlyProxy__target",
        "_ClientCapability__target",
        "_QueryCapability__target",
        "__dict__",
    )

    for capability, surface in ((proxy, "client"), (query, "query")):
        for name in escape_names:
            with pytest.raises(RuntimeError, match=f"blocked Supabase {surface} access"):
                getattr(capability, name)
        with pytest.raises((RuntimeError, TypeError)):
            vars(capability)

    assert query.select("*", count="exact").execute().data == [_report()]
    assert target.mutator_calls == []


def test_read_only_proxy_execute_never_returns_raw_target_or_non_row_data():
    target = SimpleNamespace()
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    proxy = cleanup.ReadOnlyProxy(target)

    target.execute = lambda: target
    with pytest.raises(RuntimeError, match="malformed response"):
        proxy.table("events").select("*").execute()

    target.execute = lambda: SimpleNamespace(data=[target], count=1)
    with pytest.raises(RuntimeError, match="malformed data"):
        proxy.table("events").select("*").execute()


@pytest.mark.parametrize("depth", ["direct", "deep"])
def test_read_only_proxy_rejects_nested_custom_mutator_without_invoking_it(depth):
    target = SimpleNamespace()
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    mutator = _NestedMutator()
    nested = mutator if depth == "direct" else {"level": [{"value": mutator}]}
    target.execute = lambda: SimpleNamespace(data=[{"nested": nested}], count=1)

    with pytest.raises(RuntimeError, match="malformed data"):
        cleanup.ReadOnlyProxy(target).table("events").select("*").execute()

    assert mutator.deepcopy_calls == 0
    assert mutator.update_calls == 0


def test_read_only_proxy_rejects_nested_non_json_values():
    class DictSubclass(dict):
        pass

    class ListSubclass(list):
        pass

    bad_values = [
        DictSubclass(value=1),
        ListSubclass([1]),
        lambda: None,
        cleanup.datetime.now(cleanup.timezone.utc),
        float("nan"),
        float("inf"),
        float("-inf"),
        {1: "non-string key"},
    ]
    target = SimpleNamespace()
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    proxy = cleanup.ReadOnlyProxy(target)

    for value in bad_values:
        target.execute = lambda value=value: SimpleNamespace(
            data=[{"nested": [value]}],
            count=1,
        )
        with pytest.raises(RuntimeError, match="malformed data"):
            proxy.table("events").select("*").execute()


@pytest.mark.parametrize("count", [True, -1, 1.5, "1"])
def test_read_only_proxy_rejects_invalid_terminal_count(count):
    target = SimpleNamespace()
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    target.execute = lambda: SimpleNamespace(data=[], count=count)

    with pytest.raises(RuntimeError, match="malformed count"):
        cleanup.ReadOnlyProxy(target).table("events").select("*").execute()


def test_read_only_proxy_returns_fresh_builtin_json_graph_in_slots_result():
    raw = [
        {
            "nested": {
                "values": [None, True, False, 1, 2.5, "text"],
                "mapping": {"key": "value"},
            }
        }
    ]
    target = SimpleNamespace()
    target.table = lambda _name: target
    target.select = lambda *_args, **_kwargs: target
    target.execute = lambda: SimpleNamespace(data=raw, count=None)

    result = cleanup.ReadOnlyProxy(target).table("events").select("*").execute()

    assert result.data == raw
    assert result.data is not raw
    assert result.data[0] is not raw[0]
    assert result.data[0]["nested"] is not raw[0]["nested"]
    assert result.data[0]["nested"]["values"] is not raw[0]["nested"]["values"]
    assert result.count is None
    with pytest.raises((AttributeError, TypeError)):
        result.count = 1
    with pytest.raises(TypeError):
        vars(result)


def test_lazy_policy_loader_delegates_to_auto_qa_symbols(monkeypatch):
    module = ModuleType("auto_qa")

    def classifier(_report_types):
        return "delegated"

    def payload_token_predicate(_token):
        return True

    module.KNOWN_AUTO_QA_TYPES = frozenset({"delegated_type"})
    module.classify_report_types = classifier
    module.is_payload_token = payload_token_predicate
    monkeypatch.setitem(sys.modules, "auto_qa", module)

    policy = REAL_POLICY_LOADER()

    assert policy.known_auto_qa_types == frozenset({"delegated_type"})
    assert policy.classifier is classifier
    assert policy.payload_token_predicate is payload_token_predicate


def test_classification_core_accepts_an_injected_classifier():
    calls = []

    def classifier(report_types):
        calls.append(report_types)
        return "manual"

    classified = cleanup.classify_pending_reports(
        [_report()],
        policy=TEST_POLICY,
        classifier=classifier,
    )

    assert calls == [[AUTO_A]]
    assert classified[0]["classification"] == "manual"


@pytest.mark.parametrize(
    ("arguments", "expected_code"),
    [
        (["--help"], 0),
        (["apply"], 2),
        (["rollback"], 2),
        (["settle"], 2),
        (["reset"], 2),
        (["lock"], 2),
        (["gpt"], 2),
        (["dispatch"], 2),
    ],
)
def test_help_and_forbidden_commands_exit_before_dotenv_client_or_network(
    arguments,
    expected_code,
):
    result, side_effects = _run_cli_with_side_effect_spies(arguments)

    assert result.returncode == expected_code
    assert side_effects == []


def test_legal_commands_are_parser_only_in_unit_tests():
    parser = cleanup.build_parser()

    assert parser.parse_args(["discover"]).command == "discover"
    assert parser.parse_args(["freeze"]).command == "freeze"
    assert parser.parse_args(
        ["export-review", "--ledger", "fixture.json"]
    ).command == "export-review"


def test_cli_exposes_only_read_only_commands_and_rejects_mutation_commands_offline(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        cleanup,
        "_create_read_only_client",
        lambda: (_ for _ in ()).throw(AssertionError("client factory called")),
    )
    parser = cleanup.build_parser()
    choices = next(
        action.choices
        for action in parser._actions
        if isinstance(action, __import__("argparse")._SubParsersAction)
    )
    assert set(choices) == {"discover", "freeze", "export-review"}

    with pytest.raises(SystemExit) as help_exit:
        cleanup.main(["--help"])
    assert help_exit.value.code == 0
    assert "{discover,freeze,export-review}" in capsys.readouterr().out

    for command in ("apply", "rollback", "settle", "reset", "lock", "gpt", "dispatch"):
        with pytest.raises(SystemExit) as invalid_exit:
            cleanup.main([command])
        assert invalid_exit.value.code == 2


@pytest.mark.parametrize("fault", ["write", "short_write", "flush", "close"])
def test_atomic_publish_cleans_staging_after_stream_failure(monkeypatch, fault):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output = _artifact_output(root, f"{fault}.json")
        real_fdopen = cleanup.os.fdopen

        def faulty_fdopen(descriptor, *args, **kwargs):
            return _FaultyBinaryFile(
                real_fdopen(descriptor, *args, **kwargs),
                fault,
            )

        monkeypatch.setattr(cleanup.os, "fdopen", faulty_fdopen)

        with pytest.raises((OSError, RuntimeError)):
            cleanup._write_immutable_json(output, _sealed_payload())

        _assert_failed_publish_is_clean(output)


@pytest.mark.parametrize("fault", ["open", "fchmod", "fsync", "link"])
def test_atomic_publish_fails_closed_for_system_operation_failure(monkeypatch, fault):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output = _artifact_output(root, f"{fault}.json")

        if fault == "open":
            monkeypatch.setattr(
                cleanup,
                "_open_staging_file",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    OSError("injected open failure")
                ),
            )
        elif fault == "fchmod":
            monkeypatch.setattr(
                cleanup.os,
                "fchmod",
                lambda *_args: (_ for _ in ()).throw(
                    OSError("injected fchmod failure")
                ),
            )
        elif fault == "fsync":
            monkeypatch.setattr(
                cleanup.os,
                "fsync",
                lambda *_args: (_ for _ in ()).throw(
                    OSError("injected fsync failure")
                ),
            )
        else:
            monkeypatch.setattr(
                cleanup.os,
                "link",
                lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    OSError("injected link failure")
                ),
            )

        with pytest.raises(OSError, match=f"injected {fault} failure"):
            cleanup._write_immutable_json(output, _sealed_payload())

        _assert_failed_publish_is_clean(output)


def test_atomic_publish_rejects_inexact_staging_mode(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output = _artifact_output(root, "wrong-staging-mode.json")
        real_fchmod = cleanup.os.fchmod

        def set_wrong_mode(descriptor, _mode):
            real_fchmod(descriptor, 0o600)

        monkeypatch.setattr(cleanup.os, "fchmod", set_wrong_mode)

        with pytest.raises(RuntimeError, match="mode must be exactly 0400"):
            cleanup._write_immutable_json(output, _sealed_payload())

        _assert_failed_publish_is_clean(output)


def test_atomic_publish_rolls_back_its_final_on_post_link_validation_failure(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output = _artifact_output(root, "post-link.json")
        real_reader = cleanup._read_anchored_artifact_bytes

        def fail_final(directory_descriptor, name, path, **kwargs):
            if name == output.name:
                raise RuntimeError("injected final validation failure")
            return real_reader(directory_descriptor, name, path, **kwargs)

        monkeypatch.setattr(cleanup, "_read_anchored_artifact_bytes", fail_final)

        with pytest.raises(RuntimeError, match="injected final validation failure"):
            cleanup._write_immutable_json(output, _sealed_payload())

        _assert_failed_publish_is_clean(output)


def test_atomic_publish_rolls_back_when_link_raises_after_creating_final(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output = _artifact_output(root, "partial-link.json")
        real_link = cleanup.os.link

        def partial_link(*args, **kwargs):
            real_link(*args, **kwargs)
            raise OSError("injected partial link failure")

        monkeypatch.setattr(cleanup.os, "link", partial_link)

        with pytest.raises(OSError, match="injected partial link failure"):
            cleanup._write_immutable_json(output, _sealed_payload())

        _assert_failed_publish_is_clean(output)


def test_atomic_publish_destination_race_is_nonoverwriting(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output = _artifact_output(root, "race.json")
        winner = b"race winner\n"
        real_link = cleanup.os.link

        def racing_link(*args, **kwargs):
            output.write_bytes(winner)
            output.chmod(0o400)
            return real_link(*args, **kwargs)

        monkeypatch.setattr(cleanup.os, "link", racing_link)

        with pytest.raises(FileExistsError):
            cleanup._write_immutable_json(output, _sealed_payload())

        assert output.read_bytes() == winner
        assert list(output.parent.glob(f".{output.name}.*.tmp")) == []


@pytest.mark.parametrize("layer", ["root", "tmp", "admin-qa-cleanup", "timestamp"])
def test_artifact_rejects_symlink_at_root_or_any_parent_even_when_target_is_in_root(
    monkeypatch,
    tmp_path,
    layer,
):
    real_root = tmp_path / "worktree"
    real_root.mkdir()
    target = real_root / "inside-target"
    target.mkdir()
    if layer == "root":
        root = tmp_path / "worktree-link"
        root.symlink_to(real_root, target_is_directory=True)
    else:
        root = real_root
        current = root
        names = ["tmp", "admin-qa-cleanup", "20260811T120000Z"]
        target_layer = "20260811T120000Z" if layer == "timestamp" else layer
        for name in names:
            candidate = current / name
            if name == target_layer:
                candidate.symlink_to(target, target_is_directory=True)
                break
            candidate.mkdir()
            current = candidate
    monkeypatch.setattr(cleanup, "ROOT", root)
    monkeypatch.setattr(cleanup, "_is_git_ignored", lambda _path, *, root: True)
    output = _artifact_output(root, f"{layer}.json")

    with pytest.raises(RuntimeError, match="symlink"):
        cleanup._write_immutable_json(output, _sealed_payload())

    assert list(target.rglob(f"{layer}.json")) == []


@pytest.mark.parametrize("replacement_scope", ["outside", "inside"])
def test_publish_parent_replacement_after_anchor_never_writes_through_symlink(
    monkeypatch,
    tmp_path,
    replacement_scope,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, f"parent-{replacement_scope}.json")
    replacement = (
        tmp_path / "outside-replacement"
        if replacement_scope == "outside"
        else root / "inside-replacement"
    )
    replacement.mkdir()
    anchored_parent = output.parent.with_name(f"{output.parent.name}-anchored")
    real_open_parent = cleanup._open_artifact_parent

    def replace_parent_after_open(destination, *, create):
        anchors = real_open_parent(destination, create=create)
        destination.parent.rename(anchored_parent)
        destination.parent.symlink_to(replacement, target_is_directory=True)
        return anchors

    monkeypatch.setattr(cleanup, "_open_artifact_parent", replace_parent_after_open)

    with pytest.raises(RuntimeError, match="directory"):
        cleanup._write_immutable_json(output, _sealed_payload())

    assert not (replacement / output.name).exists()
    assert not (anchored_parent / output.name).exists()
    assert list(anchored_parent.glob(f".{output.name}.*.tmp")) == []


@pytest.mark.parametrize("fault", ["write", "fsync", "link", "final_validation"])
def test_failure_cleanup_preserves_replacement_staging_and_removes_owned_final(
    monkeypatch,
    tmp_path,
    fault,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, f"competitor-{fault}.json")
    competitor = f"competitor-{fault}\n".encode()
    competitor_paths = []

    def replace_staging():
        path = _replace_staging_with_competitor(output, competitor)
        competitor_paths.append(path)

    if fault == "write":
        real_fdopen = cleanup.os.fdopen

        class ReplaceOnWrite:
            def __init__(self, handle):
                self._handle = handle

            def write(self, _content):
                replace_staging()
                raise OSError("injected write replacement failure")

            def __getattr__(self, name):
                return getattr(self._handle, name)

        def replacing_fdopen(descriptor, *args, **kwargs):
            handle = real_fdopen(descriptor, *args, **kwargs)
            return ReplaceOnWrite(handle) if args and args[0] == "wb" else handle

        monkeypatch.setattr(cleanup.os, "fdopen", replacing_fdopen)
    elif fault == "fsync":
        def replacing_fsync(_descriptor):
            replace_staging()
            raise OSError("injected fsync replacement failure")

        monkeypatch.setattr(cleanup.os, "fsync", replacing_fsync)
    elif fault == "link":
        def replacing_link(*_args, **_kwargs):
            replace_staging()
            raise OSError("injected link replacement failure")

        monkeypatch.setattr(cleanup.os, "link", replacing_link)
    else:
        real_reader = cleanup._read_anchored_artifact_bytes

        def replacing_final_reader(directory_descriptor, name, path, **kwargs):
            if name == output.name:
                replace_staging()
                raise RuntimeError("injected final validation replacement failure")
            return real_reader(directory_descriptor, name, path, **kwargs)

        monkeypatch.setattr(
            cleanup,
            "_read_anchored_artifact_bytes",
            replacing_final_reader,
        )

    with pytest.raises((OSError, RuntimeError), match="injected"):
        cleanup._write_immutable_json(output, _sealed_payload())

    assert len(competitor_paths) == 1
    assert competitor_paths[0].read_bytes() == competitor
    assert not output.exists()


def test_failure_cleanup_removes_renamed_staging_and_all_owned_hardlinks(
    monkeypatch,
    tmp_path,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, "renamed-staging.json")
    competitor = b"staging competitor\n"
    state = {}

    def rename_staging_and_fail(_descriptor):
        staging = next(output.parent.glob(f".{output.name}.*.tmp"))
        state["identity"] = cleanup._identity(staging.stat())
        renamed = output.parent / "owned-staging-renamed"
        alias_one = output.parent / "owned-staging-alias-one"
        alias_two = output.parent / "owned-staging-alias-two"
        staging.rename(renamed)
        os.link(renamed, alias_one)
        os.link(renamed, alias_two)
        staging.write_bytes(competitor)
        staging.chmod(0o400)
        state["competitor"] = staging
        raise OSError("injected renamed staging failure")

    monkeypatch.setattr(cleanup.os, "fsync", rename_staging_and_fail)

    with pytest.raises(OSError, match="injected renamed staging failure"):
        cleanup._write_immutable_json(output, _sealed_payload())

    matching = [
        path
        for path in output.parent.iterdir()
        if cleanup._identity(path.lstat()) == state["identity"]
    ]
    assert matching == []
    assert state["competitor"].read_bytes() == competitor


def test_failure_cleanup_removes_renamed_final_staging_and_owned_hardlinks(
    monkeypatch,
    tmp_path,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, "renamed-final.json")
    competitor = b"final competitor\n"
    state = {}
    real_reader = cleanup._read_anchored_artifact_bytes

    def rename_final_and_fail(directory_descriptor, name, path, **kwargs):
        if name == output.name:
            state["identity"] = cleanup._identity(output.lstat())
            renamed = output.parent / "owned-final-renamed"
            alias = output.parent / "owned-final-alias"
            output.rename(renamed)
            os.link(renamed, alias)
            output.write_bytes(competitor)
            output.chmod(0o400)
            raise RuntimeError("injected renamed final failure")
        return real_reader(directory_descriptor, name, path, **kwargs)

    monkeypatch.setattr(
        cleanup,
        "_read_anchored_artifact_bytes",
        rename_final_and_fail,
    )

    with pytest.raises(RuntimeError, match="injected renamed final failure"):
        cleanup._write_immutable_json(output, _sealed_payload())

    matching = [
        path
        for path in output.parent.iterdir()
        if cleanup._identity(path.lstat()) == state["identity"]
    ]
    assert matching == []
    assert output.read_bytes() == competitor


def test_success_cleanup_preserves_only_final_owned_link(monkeypatch, tmp_path):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, "success-hardlinks.json")
    real_link = cleanup.os.link
    aliases = []

    def link_with_aliases(source, destination, *args, **kwargs):
        result = real_link(source, destination, *args, **kwargs)
        if destination == output.name:
            directory_descriptor = kwargs["dst_dir_fd"]
            for alias in ("owned-success-alias-one", "owned-success-alias-two"):
                real_link(
                    destination,
                    alias,
                    src_dir_fd=directory_descriptor,
                    dst_dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
                aliases.append(alias)
        return result

    monkeypatch.setattr(cleanup.os, "link", link_with_aliases)

    written = cleanup._write_immutable_json(output, _sealed_payload())
    identity = cleanup._identity(written.lstat())
    matching = [
        path.name
        for path in output.parent.iterdir()
        if cleanup._identity(path.lstat()) == identity
    ]

    assert matching == [output.name]
    assert written.stat().st_nlink == 1
    assert aliases == ["owned-success-alias-one", "owned-success-alias-two"]


def test_cleanup_enumeration_failure_keeps_primary_exception_and_fails_closed(
    monkeypatch,
    tmp_path,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, "cleanup-enumeration.json")
    monkeypatch.setattr(
        cleanup.os,
        "fsync",
        lambda _descriptor: (_ for _ in ()).throw(OSError("primary fsync failure")),
    )
    monkeypatch.setattr(
        cleanup.os,
        "listdir",
        lambda _descriptor: (_ for _ in ()).throw(OSError("cleanup list failure")),
    )

    with pytest.raises(OSError, match="primary fsync failure") as raised:
        cleanup._write_immutable_json(output, _sealed_payload())

    notes = getattr(raised.value, "__notes__", [])
    assert any("cleanup list failure" in note for note in notes)


@pytest.mark.parametrize("existing_kind", ["regular", "symlink"])
def test_atomic_publish_rejects_every_existing_destination(monkeypatch, existing_kind):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output = _artifact_output(root, f"existing-{existing_kind}.json")
        output.parent.mkdir(parents=True)
        preserved = b"preserved\n"
        if existing_kind == "regular":
            output.write_bytes(preserved)
            output.chmod(0o400)
        else:
            target = output.with_name("target.json")
            target.write_bytes(preserved)
            target.chmod(0o400)
            output.symlink_to(target)

        with pytest.raises(FileExistsError, match="already exists"):
            cleanup._write_immutable_json(output, _sealed_payload())

        if existing_kind == "regular":
            assert output.read_bytes() == preserved
        else:
            assert output.is_symlink()
            assert output.resolve().read_bytes() == preserved
        assert list(output.parent.glob(f".{output.name}.*.tmp")) == []


def test_loader_rejects_non_regular_symlink_and_non_0400_files(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        content = cleanup.canonical_json_bytes(_sealed_payload()) + b"\n"

        wrong_mode = _artifact_output(root, "wrong-mode.json")
        wrong_mode.parent.mkdir(parents=True)
        wrong_mode.write_bytes(content)
        wrong_mode.chmod(0o600)
        with pytest.raises(RuntimeError, match="mode must be exactly 0400"):
            cleanup.load_artifact(wrong_mode)

        target = wrong_mode.with_name("target.json")
        target.write_bytes(content)
        target.chmod(0o400)
        symlink = wrong_mode.with_name("symlink.json")
        symlink.symlink_to(target)
        with pytest.raises(RuntimeError, match="symlink is forbidden"):
            cleanup.load_artifact(symlink)

        directory_artifact = wrong_mode.with_name("directory.json")
        directory_artifact.mkdir(mode=0o400)
        directory_artifact.chmod(0o400)
        with pytest.raises(RuntimeError, match="regular file"):
            cleanup.load_artifact(directory_artifact)


def test_loader_rejects_valid_artifact_behind_in_root_symlink_parent(monkeypatch, tmp_path):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, "symlink-parent.json")
    cleanup._write_immutable_json(output, _sealed_payload())
    anchored_parent = output.parent.with_name(f"{output.parent.name}-anchored")
    output.parent.rename(anchored_parent)
    output.parent.symlink_to(anchored_parent, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        cleanup.load_artifact(output)


def test_loader_rejects_post_open_inode_replacement(monkeypatch, tmp_path):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, "post-open-replace.json")
    cleanup._write_immutable_json(output, _sealed_payload())
    original = output.with_name("opened-original.json")
    competitor = b"replacement\n"
    real_open = cleanup.os.open
    replaced = False

    def replacing_open(path, flags, *args, **kwargs):
        nonlocal replaced
        descriptor = real_open(path, flags, *args, **kwargs)
        if path == output.name and not replaced:
            replaced = True
            output.rename(original)
            output.write_bytes(competitor)
            output.chmod(0o600)
        return descriptor

    monkeypatch.setattr(cleanup.os, "open", replacing_open)

    with pytest.raises(RuntimeError):
        cleanup.load_artifact(output)

    assert output.read_bytes() == competitor


@pytest.mark.parametrize("mutation", ["chmod", "unlink"])
def test_loader_rejects_mode_or_path_change_after_full_read(monkeypatch, tmp_path, mutation):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, f"after-read-{mutation}.json")
    cleanup._write_immutable_json(output, _sealed_payload())
    real_fdopen = cleanup.os.fdopen

    def mutate():
        if mutation == "chmod":
            output.chmod(0o600)
        else:
            output.unlink()

    def mutating_fdopen(descriptor, *args, **kwargs):
        return _AfterReadBinaryFile(
            real_fdopen(descriptor, *args, **kwargs),
            mutate,
        )

    monkeypatch.setattr(cleanup.os, "fdopen", mutating_fdopen)

    with pytest.raises(RuntimeError):
        cleanup.load_artifact(output)


@pytest.mark.parametrize("mutation", ["replace", "chmod", "unlink", "symlink"])
def test_loader_rejects_decode_pre_return_path_mutation(
    monkeypatch,
    tmp_path,
    mutation,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, f"decode-{mutation}.json")
    cleanup._write_immutable_json(output, _sealed_payload())
    canonical = output.read_bytes()
    original = output.with_name(f"decode-{mutation}-original.json")
    real_decode = cleanup._decode_artifact_bytes

    def mutate_after_decode(content):
        payload = real_decode(content)
        if mutation == "replace":
            output.rename(original)
            output.write_bytes(canonical)
            output.chmod(0o400)
        elif mutation == "chmod":
            output.chmod(0o600)
        elif mutation == "unlink":
            output.unlink()
        else:
            output.rename(original)
            output.symlink_to(original)
        return payload

    monkeypatch.setattr(cleanup, "_decode_artifact_bytes", mutate_after_decode)

    with pytest.raises(RuntimeError):
        cleanup.load_artifact(output)


def test_loader_rejects_parent_replacement_during_decode_pre_return(
    monkeypatch,
    tmp_path,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, "decode-parent-replacement.json")
    cleanup._write_immutable_json(output, _sealed_payload())
    anchored_parent = output.parent.with_name(f"{output.parent.name}-decode-anchor")
    real_decode = cleanup._decode_artifact_bytes

    def replace_parent_after_decode(content):
        payload = real_decode(content)
        output.parent.rename(anchored_parent)
        output.parent.mkdir()
        return payload

    monkeypatch.setattr(cleanup, "_decode_artifact_bytes", replace_parent_after_decode)

    with pytest.raises(RuntimeError, match="directory path identity changed"):
        cleanup.load_artifact(output)


@pytest.mark.parametrize("replacement_kind", ["directory", "symlink"])
def test_loader_rejects_parent_replacement_while_anchored(
    monkeypatch,
    tmp_path,
    replacement_kind,
):
    root = _artifact_root(monkeypatch, tmp_path)
    output = _artifact_output(root, f"loader-parent-{replacement_kind}.json")
    cleanup._write_immutable_json(output, _sealed_payload())
    anchored_parent = output.parent.with_name(f"{output.parent.name}-read-anchor")
    replacement = root / f"loader-{replacement_kind}-replacement"
    replacement.mkdir()
    real_open_parent = cleanup._open_artifact_parent

    def replace_parent_after_open(destination, *, create):
        anchors = real_open_parent(destination, create=create)
        destination.parent.rename(anchored_parent)
        if replacement_kind == "directory":
            destination.parent.mkdir()
        else:
            destination.parent.symlink_to(replacement, target_is_directory=True)
        return anchors

    monkeypatch.setattr(cleanup, "_open_artifact_parent", replace_parent_after_open)

    with pytest.raises(RuntimeError, match="directory"):
        cleanup.load_artifact(output)

    assert not (replacement / output.name).exists()


@pytest.mark.parametrize(
    "bad_output",
    [
        Path("tmp/admin-qa-cleanup/20260811T120000Z/../escape.json"),
        Path("tmp/admin-qa-cleanup/20260811T120000Z/nested/artifact.json"),
        Path("tmp/admin-qa-cleanup/20260811T120000Z/.."),
    ],
)
def test_artifact_output_requires_single_safe_basename(monkeypatch, tmp_path, bad_output):
    root = _artifact_root(monkeypatch, tmp_path)

    with pytest.raises(RuntimeError):
        cleanup._write_immutable_json(root / bad_output, _sealed_payload())


def test_loader_rejects_partial_noncanonical_and_digest_mismatch(monkeypatch):
    with TemporaryDirectory() as directory:
        root = _artifact_root(monkeypatch, Path(directory))
        output_parent = _artifact_output(root).parent
        output_parent.mkdir(parents=True)
        payload = _sealed_payload()
        cases = {
            "partial.json": (b'{"schema":', "JSON is invalid"),
            "noncanonical.json": (
                json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
                "not canonical",
            ),
            "digest.json": (
                cleanup.canonical_json_bytes({**payload, "value": "tampered"}) + b"\n",
                "digest mismatch",
            ),
            "nan.json": (b'{"value":NaN}\n', "JSON is invalid"),
            "infinity.json": (b'{"value":Infinity}\n', "JSON is invalid"),
        }

        for filename, (content, message) in cases.items():
            artifact = output_parent / filename
            artifact.write_bytes(content)
            artifact.chmod(0o400)
            with pytest.raises(RuntimeError, match=message):
                cleanup.load_artifact(artifact)

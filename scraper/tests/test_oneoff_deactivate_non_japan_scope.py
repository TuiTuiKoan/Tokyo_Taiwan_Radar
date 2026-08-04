from __future__ import annotations

from copy import deepcopy
import json
import stat

import pytest

import _oneoff_deactivate_non_japan_scope as cleanup


@pytest.fixture(autouse=True)
def _fixed_provenance(monkeypatch):
    monkeypatch.setattr(cleanup, "current_git_head", lambda: "test-head")
    monkeypatch.setattr(cleanup, "current_script_sha256", lambda: "a" * 64)


def _event_id(prefix: str, index: int) -> str:
    return f"{prefix}-0000-4000-8000-{index:012x}"


def _target_rows() -> list[dict]:
    rows = []
    for index, spec in enumerate(cleanup.TARGET_SPECS, start=1):
        row = {
            "id": _event_id(spec.prefix, index),
            "source_name": f"source_{index}",
            "raw_title": "",
            "raw_description": "",
            "location_address": "",
            "location_prefectures": ["台北"],
            "is_active": True,
            "annotation_status": "annotated",
            "parent_event_id": None,
            "updated_at": "2026-08-04T00:00:00+00:00",
        }
        for evidence in spec.evidence:
            row[evidence.field] = f"{row.get(evidence.field) or ''} {evidence.contains} verified"
        rows.append(row)
    return rows


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = "select"
        self.patch = None
        self.filters = []
        self.start = None
        self.end = None

    def select(self, _columns="*", *_args, **_kwargs):
        return self

    def update(self, patch):
        if self.client.forbid_mutations:
            raise AssertionError("snapshot attempted a mutation")
        self.operation = "update"
        self.patch = deepcopy(patch)
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def order(self, _column, **_kwargs):
        return self

    def range(self, start, end):
        self.start = start
        self.end = end
        return self

    def _matches(self, row):
        return all(row.get(column) == value for column, value in self.filters)

    def execute(self):
        rows = self.client.tables.setdefault(self.table, [])
        if self.operation == "update":
            matched = [row for row in rows if self._matches(row)]
            self.client.write_attempts.append(
                {
                    "table": self.table,
                    "patch": deepcopy(self.patch),
                    "filters": list(self.filters),
                    "matched": len(matched),
                }
            )
            if self.client.update_results:
                override = self.client.update_results.pop(0)
                if isinstance(override, Exception):
                    raise override
                return _Result(deepcopy(override))
            for row in matched:
                row.update(self.patch)
            return _Result([{"id": row["id"]} for row in matched])
        selected = [deepcopy(row) for row in rows if self._matches(row)]
        if self.start is not None and self.end is not None:
            selected = selected[self.start : self.end + 1]
        return _Result(selected)


class _Client:
    def __init__(self, events, *, forbid_mutations=False):
        self.tables = {"events": deepcopy(events)}
        self.forbid_mutations = forbid_mutations
        self.write_attempts = []
        self.update_results = []

    def table(self, name):
        return _Query(self, name)

    def event(self, event_id):
        return next(row for row in self.tables["events"] if row["id"] == event_id)


def _manifest(rows=None):
    return cleanup.build_manifest_from_rows(
        deepcopy(rows or _target_rows()), created_at_utc="2026-08-04T00:00:00Z"
    )


def _last_journal_statuses(path):
    statuses = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("record_type") == "target":
            statuses[record["id"]] = record["status"]
    return statuses


def test_prefixes_resolve_to_22_unique_full_uuids():
    resolved = cleanup.resolve_target_rows(_target_rows())

    assert len(resolved) == cleanup.TARGET_COUNT
    assert len({row["id"] for _spec, row in resolved}) == cleanup.TARGET_COUNT
    assert [spec.prefix for spec, _row in resolved] == [spec.prefix for spec in cleanup.TARGET_SPECS]


def test_prefix_resolution_rejects_missing_ambiguous_and_duplicate_full_uuid():
    rows = _target_rows()
    with pytest.raises(RuntimeError, match="match_count=0"):
        cleanup.resolve_target_rows(rows[1:])

    ambiguous = deepcopy(rows)
    ambiguous.append({**rows[0], "id": _event_id(cleanup.TARGET_SPECS[0].prefix, 999)})
    with pytest.raises(RuntimeError, match="match_count=2"):
        cleanup.resolve_target_rows(ambiguous)

    duplicate_specs = list(cleanup.TARGET_SPECS)
    duplicate_specs[1] = duplicate_specs[0]
    with pytest.raises(RuntimeError, match="duplicate_full_uuid"):
        cleanup.resolve_target_rows(rows, duplicate_specs)


def test_evidence_contradiction_stops_snapshot():
    rows = _target_rows()
    rows[0]["raw_title"] = "different title"

    with pytest.raises(RuntimeError, match="evidence contradiction"):
        cleanup.build_manifest_from_rows(rows)


def test_canonical_digest_is_deterministic_and_payload_changes_it():
    payload_a = {"z": [1, {"中文": None}], "a": True}
    payload_b = {"a": True, "z": [1, {"中文": None}]}

    assert cleanup.manifest_digest(payload_a) == cleanup.manifest_digest(payload_b)
    changed = deepcopy(payload_a)
    changed["z"][1]["中文"] = "changed"
    assert cleanup.manifest_digest(payload_a) != cleanup.manifest_digest(changed)


def test_embedded_and_expected_digest_mismatches_are_rejected():
    manifest = _manifest()
    with pytest.raises(RuntimeError, match="expected digest mismatch"):
        cleanup.verify_manifest_digest(manifest, "b" * 64)

    tampered = deepcopy(manifest)
    tampered["targets"][0]["reason"] = "changed"
    with pytest.raises(RuntimeError, match="embedded digest mismatch"):
        cleanup.verify_manifest_digest(tampered, manifest["manifest_digest"])


def test_existing_output_is_never_overwritten(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("keep", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already exists"):
        cleanup.write_manifest(path, _manifest())
    assert path.read_text(encoding="utf-8") == "keep"


def test_manifest_publication_race_preserves_competitor_and_removes_temp(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    competitor = b"competitor-won\n"
    real_link = cleanup.os.link

    def race_link(source, destination):
        assert destination == path
        path.write_bytes(competitor)
        return real_link(source, destination)

    monkeypatch.setattr(cleanup.os, "link", race_link)

    with pytest.raises(FileExistsError):
        cleanup.write_manifest(path, _manifest())

    assert path.read_bytes() == competitor
    assert list(tmp_path.glob(f".{path.name}.*.tmp")) == []


def test_manifest_write_is_read_only_and_digest_round_trips(tmp_path):
    path = tmp_path / "nested" / "manifest.json"
    manifest = _manifest()

    cleanup.write_manifest(path, manifest)

    assert stat.S_IMODE(path.stat().st_mode) == stat.S_IRUSR
    loaded = cleanup.load_manifest(path)
    assert cleanup.verify_manifest_digest(loaded, manifest["manifest_digest"]) == manifest["manifest_digest"]


def test_snapshot_uses_only_select_queries():
    client = _Client(_target_rows(), forbid_mutations=True)

    manifest = cleanup.build_snapshot(client, created_at_utc="2026-08-04T00:00:00Z")

    assert manifest["target_count"] == cleanup.TARGET_COUNT
    assert client.write_attempts == []


def test_inactive_child_is_recorded_as_warning_and_manifest_relation():
    rows = _target_rows()
    child = {
        "id": "ffffffff-0000-4000-8000-000000000001",
        "parent_event_id": rows[0]["id"],
        "is_active": False,
    }
    rows.append(child)

    manifest = cleanup.build_manifest_from_rows(rows)

    assert manifest["relations"]["inactive_children"] == [child]
    assert manifest["warnings"] == [f"inactive_child={child['id']} parent={rows[0]['id']}"]


@pytest.mark.parametrize(
    "tamper, expected_error",
    [
        ("category", "category mismatch"),
        ("reason", "reason mismatch"),
        ("evidence_empty", "evidence mismatch"),
        ("evidence_malformed", "evidence mismatch"),
        ("evidence_extra_key", "evidence item"),
        ("evidence_field", "evidence field mismatch"),
        ("evidence_substring", "evidence expected_substring mismatch"),
        ("evidence_excerpt", "evidence observed_excerpt"),
        ("evidence_excerpt_missing_substring", "evidence observed_excerpt"),
        ("before_inactive", "before-image is_active"),
        ("before_missing", "before-image missing fields"),
    ],
)
def test_rebound_digest_does_not_bypass_manifest_contract(tamper, expected_error):
    manifest = _manifest()
    target = manifest["targets"][0]
    if tamper == "category":
        target["category"] = "tampered"
    elif tamper == "reason":
        target["reason"] = "tampered"
    elif tamper == "evidence_empty":
        target["evidence"] = []
    elif tamper == "evidence_malformed":
        target["evidence"] = [{}]
    elif tamper == "evidence_extra_key":
        target["evidence"][0]["extra"] = "tampered"
    elif tamper == "evidence_field":
        target["evidence"][0]["field"] = "raw_description"
    elif tamper == "evidence_substring":
        target["evidence"][0]["expected_substring"] = "tampered"
    elif tamper == "evidence_excerpt":
        target["evidence"][0]["observed_excerpt"] = ""
    elif tamper == "evidence_excerpt_missing_substring":
        target["evidence"][0]["observed_excerpt"] = "unrelated evidence"
    elif tamper == "before_inactive":
        target["before"]["is_active"] = False
    else:
        del target["before"]["source_name"]
    manifest = cleanup.bind_manifest_digest(manifest)

    cleanup.verify_manifest_digest(manifest, manifest["manifest_digest"])
    with pytest.raises(RuntimeError, match=expected_error):
        cleanup.validate_manifest_contract(manifest)


@pytest.mark.parametrize("drift", ["stable", "inactive", "active_child", "target_parent"])
def test_apply_preflight_drift_and_relations_stop_before_writes(tmp_path, drift):
    rows = _target_rows()
    manifest = _manifest(rows)
    client = _Client(rows)
    first_id = rows[0]["id"]
    if drift == "stable":
        client.event(first_id)["location_address"] = "changed"
    elif drift == "inactive":
        client.event(first_id)["is_active"] = False
    elif drift == "active_child":
        client.tables["events"].append(
            {
                "id": "ffffffff-0000-4000-8000-000000000002",
                "parent_event_id": first_id,
                "is_active": True,
            }
        )
    else:
        client.event(first_id)["parent_event_id"] = "eeeeeeee-0000-4000-8000-000000000001"

    with pytest.raises(RuntimeError, match="preflight failed"):
        cleanup.apply_manifest(
            client,
            manifest,
            manifest_path=tmp_path / "manifest.json",
            expected_digest=manifest["manifest_digest"],
        )
    assert client.write_attempts == []


def test_updated_at_only_drift_warns_but_allows_apply(tmp_path):
    rows = _target_rows()
    manifest = _manifest(rows)
    client = _Client(rows)
    first_id = rows[0]["id"]
    client.event(first_id)["updated_at"] = "2026-08-04T01:00:00+00:00"

    report = cleanup.apply_manifest(
        client,
        manifest,
        manifest_path=tmp_path / "manifest.json",
        expected_digest=manifest["manifest_digest"],
        apply_timestamp="2026-08-04T02:00:00Z",
    )

    assert report["warnings"] == [
        f"updated_at_only_drift={first_id} before=2026-08-04T00:00:00+00:00 current=2026-08-04T01:00:00+00:00"
    ]
    assert len(client.write_attempts) == cleanup.TARGET_COUNT


def test_apply_uses_exact_one_cas_and_one_timestamp(tmp_path):
    rows = _target_rows()
    manifest = _manifest(rows)
    client = _Client(rows)
    timestamp = "2026-08-04T02:00:00Z"

    report = cleanup.apply_manifest(
        client,
        manifest,
        manifest_path=tmp_path / "manifest.json",
        expected_digest=manifest["manifest_digest"],
        apply_timestamp=timestamp,
    )

    assert len(report["applied_ids"]) == cleanup.TARGET_COUNT
    assert len(client.write_attempts) == cleanup.TARGET_COUNT
    for target, attempt in zip(manifest["targets"], client.write_attempts, strict=True):
        assert attempt["filters"] == [("id", target["id"]), ("is_active", True)]
        assert attempt["matched"] == 1
        assert attempt["patch"]["is_active"] is False
        assert attempt["patch"]["deactivated_at"] == timestamp
        assert attempt["patch"]["deactivated_by_pass"] == "admin_manual"
        assert attempt["patch"]["deactivated_reason"] == (
            f"out_of_scope: {target['reason']} — not a Japan event"
        )


@pytest.mark.parametrize("override, count", [([], 0), ([{"id": "one"}, {"id": "two"}], 2)])
def test_cas_zero_and_multiple_rows_fail_and_journal_records_error(tmp_path, override, count):
    rows = _target_rows()
    manifest = _manifest(rows)
    client = _Client(rows)
    client.update_results = [override]
    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(RuntimeError, match=f"CAS affected {count} rows"):
        cleanup.apply_manifest(
            client,
            manifest,
            manifest_path=manifest_path,
            expected_digest=manifest["manifest_digest"],
        )

    journal_path = cleanup.journal_path_for(manifest_path)
    statuses = _last_journal_statuses(journal_path)
    assert statuses[rows[0]["id"]] == "error"
    assert statuses[rows[1]["id"]] == "unapplied"
    assert stat.S_IMODE(journal_path.stat().st_mode) == stat.S_IRUSR


def test_partial_failure_journal_distinguishes_applied_error_and_unapplied(tmp_path):
    rows = _target_rows()
    manifest = _manifest(rows)
    client = _Client(rows)
    client.update_results = [[{"id": rows[0]["id"]}], []]
    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(RuntimeError, match="CAS affected 0 rows"):
        cleanup.apply_manifest(
            client,
            manifest,
            manifest_path=manifest_path,
            expected_digest=manifest["manifest_digest"],
        )

    statuses = _last_journal_statuses(cleanup.journal_path_for(manifest_path))
    assert statuses[rows[0]["id"]] == "applied"
    assert statuses[rows[1]["id"]] == "error"
    assert statuses[rows[2]["id"]] == "unapplied"


def test_existing_journal_path_is_rejected_before_any_write(tmp_path):
    rows = _target_rows()
    manifest = _manifest(rows)
    client = _Client(rows)
    manifest_path = tmp_path / "manifest.json"
    journal_path = cleanup.journal_path_for(manifest_path)
    journal_path.write_text("keep\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        cleanup.apply_manifest(
            client,
            manifest,
            manifest_path=manifest_path,
            expected_digest=manifest["manifest_digest"],
        )
    assert client.write_attempts == []
    assert journal_path.read_text(encoding="utf-8") == "keep\n"


def test_cli_requires_complete_apply_contract_and_mutually_exclusive_modes():
    with pytest.raises(SystemExit) as missing_contract:
        cleanup.main(["--apply"])
    assert missing_contract.value.code == 2

    with pytest.raises(SystemExit) as missing_out:
        cleanup.main(["--snapshot"])
    assert missing_out.value.code == 2

    with pytest.raises(SystemExit) as conflicting_modes:
        cleanup.main(["--snapshot", "--apply", "--out", "manifest.json"])
    assert conflicting_modes.value.code == 2
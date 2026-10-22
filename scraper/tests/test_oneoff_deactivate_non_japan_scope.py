from __future__ import annotations

from copy import deepcopy
import json
import stat
import sys

import pytest

import _oneoff_deactivate_non_japan_scope as cleanup

PARENT_PREFIX = "3f693869"
CHILD_PREFIXES = ("7c6c1e7f", "fe47a25c", "a62ce9e1", "47262b02")


@pytest.fixture(autouse=True)
def _fixed_provenance(monkeypatch):
    monkeypatch.setattr(cleanup, "current_git_head", lambda: "test-head")
    monkeypatch.setattr(cleanup, "current_script_sha256", lambda: "a" * 64)
    monkeypatch.setattr(cleanup, "current_migration_sha256", lambda: "b" * 64)


def _event_id(prefix: str, index: int) -> str:
    return f"{prefix}-0000-4000-8000-{index:012x}"


def _target_rows() -> list[dict]:
    rows = []
    for index, spec in enumerate(cleanup.TARGET_SPECS, start=1):
        row = {
            "id": _event_id(spec.prefix, index),
            "source_name": f"source_{index}",
            "raw_title": "",
            "raw_description": f"body {index}",
            "location_address": "",
            "location_prefectures": ["台北"],
            "is_active": True,
            "annotation_status": "annotated",
            "parent_event_id": None,
            "deactivated_at": None,
            "deactivated_reason": None,
            "deactivated_by_pass": None,
            "updated_at": "2026-08-04T00:00:00+00:00",
        }
        for evidence in spec.evidence:
            row[evidence.field] = f"{row.get(evidence.field) or ''} {evidence.contains} verified"
        rows.append(row)
    parent_id = next(row["id"] for row in rows if row["id"].startswith(PARENT_PREFIX))
    for row in rows:
        if row["id"].startswith(CHILD_PREFIXES):
            row["parent_event_id"] = parent_id
    return rows


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []
        self.in_filters = []
        self.start = None
        self.end = None

    def select(self, _columns="*", *_args, **_kwargs):
        return self

    def update(self, _patch):
        raise AssertionError("the CLI must not write through PostgREST")

    insert = upsert = delete = update

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.in_filters.append((column, tuple(values)))
        return self

    def order(self, _column, **_kwargs):
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self):
        rows = self.client.tables.setdefault(self.table, [])
        selected = [
            deepcopy(row)
            for row in rows
            if all(row.get(c) == v for c, v in self.filters)
            and all(row.get(c) in vs for c, vs in self.in_filters)
        ]
        if self.start is not None:
            selected = selected[self.start : self.end + 1]
        return _Result(selected)


class _Rpc:
    def __init__(self, client, name, params):
        self.client, self.name, self.params = client, name, params

    def execute(self):
        self.client.rpc_calls.append((self.name, self.params["p_mode"], deepcopy(self.params["p_manifest"])))
        response = self.client.rpc_responses.get(self.params["p_mode"], {"ok": True, "status": "valid", "target_count": 22})
        if isinstance(response, Exception):
            raise response
        return _Result(deepcopy(response))


class _Client:
    def __init__(self, events, **tables):
        self.tables = {"events": deepcopy(events), **{k: deepcopy(v) for k, v in tables.items()}}
        self.rpc_calls = []
        self.rpc_responses = {}

    def table(self, name):
        return _Query(self, name)

    def rpc(self, name, params):
        return _Rpc(self, name, params)

    def modes(self):
        return [mode for _name, mode, _manifest in self.rpc_calls]


def _snapshot(rows=None, **tables):
    client = _Client(rows or _target_rows(), **tables)
    return client, cleanup.build_snapshot(client, created_at_utc="2026-08-04T00:00:00Z")


def _manifest(rows=None):
    return _snapshot(rows)[1]


def _rebound(manifest, mutate):
    changed = deepcopy(manifest)
    mutate(changed)
    return cleanup.bind_manifest_digest(changed)


# ----------------------------------------------------------- target resolution


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
        cleanup.build_snapshot(_Client(rows))


# ------------------------------------------------------------------- digest


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
    assert cleanup.verified_manifest(loaded, manifest["manifest_digest"]) == manifest


# ---------------------------------------------------------------- snapshot


def test_snapshot_reads_only_and_validates_the_exact_payload_live():
    client, manifest = _snapshot()

    assert client.modes() == ["validate"]
    _name, _mode, sent = client.rpc_calls[0]
    assert sent == cleanup.rpc_payload(manifest)
    assert set(sent) == {"schema_version", "manifest_digest", "target_count", "targets", "external_children"}
    assert sent["schema_version"] == 2
    assert all(set(t) == {"id", "category", "before"} for t in sent["targets"])
    assert all(set(t["before"]) == set(cleanup.BEFORE_FIELDS) for t in sent["targets"])
    assert manifest["project_ref"] == cleanup.PROJECT_REF
    assert manifest["operator"] == {"git_head": "test-head", "script_sha256": "a" * 64, "migration_sha256": "b" * 64}


def test_before_image_hashes_the_description_and_keeps_deactivation_fields():
    manifest = _manifest()
    first = manifest["targets"][0]["before"]

    assert first["raw_description_sha256"] == cleanup.raw_description_sha256("body 1")
    assert first["deactivated_at"] is None and first["deactivated_reason"] is None
    assert cleanup.raw_description_sha256(None) is None


def test_snapshot_records_reference_counts():
    rows = _target_rows()
    first, second = rows[0]["id"], rows[1]["id"]
    client, manifest = _snapshot(
        rows,
        event_reports=[
            {"event_id": first, "status": "pending"},
            {"event_id": first, "status": "confirmed"},
        ],
        saved_events=[{"event_id": second}],
        announcement_events=[{"event_id": second}, {"event_id": second}],
    )

    assert manifest["reference_counts"][first] == {"pending_reports": 1, "saved_events": 0, "announcement_events": 0}
    assert manifest["reference_counts"][second] == {"pending_reports": 0, "saved_events": 1, "announcement_events": 2}


def test_snapshot_fails_closed_when_live_validate_is_not_ok():
    client = _Client(_target_rows())
    client.rpc_responses["validate"] = {"ok": False, "problems": [{"id": "x", "problem": "drift"}]}

    with pytest.raises(RuntimeError, match="live validate failed; zero writes performed"):
        cleanup.build_snapshot(client)


def test_family_with_all_members_in_the_set_is_accepted():
    manifest = _manifest()
    by_prefix = {t["prefix"]: t for t in manifest["targets"]}
    parent_id = by_prefix[PARENT_PREFIX]["id"]

    assert by_prefix[PARENT_PREFIX]["before"]["parent_event_id"] is None
    assert {by_prefix[p]["before"]["parent_event_id"] for p in CHILD_PREFIXES} == {parent_id}
    assert manifest["external_children"] == []


def test_inactive_external_child_is_recorded_active_one_blocks():
    rows = _target_rows()
    parent_id = next(r["id"] for r in rows if r["id"].startswith(PARENT_PREFIX))
    inactive = {"id": "99999999-0000-4000-8000-000000000001", "parent_event_id": parent_id, "is_active": False}
    client = _Client([*rows, inactive])
    manifest = cleanup.build_snapshot(client)
    assert manifest["external_children"] == [{"id": inactive["id"], "parent_event_id": parent_id}]

    active = {**inactive, "is_active": True}
    with pytest.raises(RuntimeError, match="active child"):
        cleanup.build_snapshot(_Client([*rows, active]))


def test_parent_outside_the_set_and_inactive_target_block_the_snapshot():
    rows = _target_rows()
    rows[0]["parent_event_id"] = "88888888-0000-4000-8000-000000000001"
    with pytest.raises(RuntimeError, match="outside the set"):
        cleanup.build_snapshot(_Client(rows))

    rows = _target_rows()
    rows[0]["is_active"] = False
    with pytest.raises(RuntimeError, match="is not active"):
        cleanup.build_snapshot(_Client(rows))


def test_reason_marker_uses_the_first_twelve_digest_characters():
    assert cleanup.reason_for("A4_x", "0123456789abcdef" * 4) == "out_of_scope: A4_x - scope cleanup 0123456789ab"


# ------------------------------------------------------------ contract


@pytest.mark.parametrize("mutate,expected_error", [
    (lambda m: m.update(project_ref="other"), "project_ref mismatch"),
    (lambda m: m.update(schema_version="non-japan-scope-deactivation.v1"), "unsupported manifest schema_version"),
    (lambda m: m.update(extra=1), "manifest keys mismatch"),
    (lambda m: m["targets"][0]["before"].update(is_active=False), "is_active must be true"),
    (lambda m: m["targets"][0]["before"].update(deactivated_reason="x"), "must not be deactivated"),
    (lambda m: m["targets"][0]["before"].pop("updated_at"), "before-image fields mismatch"),
    (lambda m: m["targets"][0]["before"].update(raw_description_sha256="zz"), "raw_description_sha256 invalid"),
    (lambda m: m["targets"][0]["before"].update(parent_event_id="77777777-0000-4000-8000-000000000001"), "parent outside the set"),
    (lambda m: m["targets"][0].update(category="A1_other"), "does not match the reviewed spec"),
    (lambda m: m["targets"][0].update(id=m["targets"][1]["id"]), "UUID/prefix mismatch"),
    (lambda m: m["targets"].pop(), "exactly 22 rows"),
    (lambda m: m["reference_counts"].popitem(), "reference_counts must cover"),
    (lambda m: m["operator"].update(script_sha256="c" * 64), "current script does not match"),
    (lambda m: m["operator"].update(migration_sha256="c" * 64), "current migration does not match"),
    (lambda m: m["external_children"].append({"id": "a" * 8 + "-0000-4000-8000-000000000001", "parent_event_id": "66666666-0000-4000-8000-000000000001"}), "parent is not a target"),
])
def test_rebound_digest_does_not_bypass_manifest_contract(mutate, expected_error):
    manifest = _manifest()
    tampered = _rebound(manifest, mutate)

    with pytest.raises(RuntimeError, match=expected_error):
        cleanup.verified_manifest(tampered, tampered["manifest_digest"])


# --------------------------------------------------------------------- apply


def _apply(client, manifest, tmp_path, confirm=lambda _m: True):
    path = tmp_path / "manifest.json"
    if not path.exists():
        cleanup.write_manifest(path, manifest)
    return cleanup.apply_manifest(
        client, manifest, manifest_path=path, expected_digest=manifest["manifest_digest"], confirm=confirm
    )


def test_apply_validates_then_confirms_then_calls_the_rpc_once(tmp_path):
    client, manifest = _snapshot()
    client.rpc_calls.clear()
    client.rpc_responses["apply"] = {"status": "applied", "applied_count": 22, "targets": []}

    report = _apply(client, manifest, tmp_path)

    assert client.modes() == ["validate", "apply"]
    assert report["status"] == "applied" and report["applied_count"] == 22
    journal = json.loads(report["journal_path"].read_text(encoding="utf-8"))
    assert journal["manifest_digest"] == manifest["manifest_digest"]
    assert journal["result"]["status"] == "applied"
    assert stat.S_IMODE(report["journal_path"].stat().st_mode) == stat.S_IRUSR


def test_apply_without_confirmation_makes_no_apply_call(tmp_path):
    client, manifest = _snapshot()
    client.rpc_calls.clear()

    with pytest.raises(RuntimeError, match="not confirmed; zero writes performed"):
        _apply(client, manifest, tmp_path, confirm=lambda _m: False)

    assert client.modes() == ["validate"]


def test_apply_stops_when_live_validate_fails(tmp_path):
    client, manifest = _snapshot()
    client.rpc_calls.clear()
    client.rpc_responses["validate"] = {"ok": False, "problems": [{"problem": "drift"}]}

    with pytest.raises(RuntimeError, match="live validate failed"):
        _apply(client, manifest, tmp_path)

    assert client.modes() == ["validate"]


def test_apply_checks_digest_and_contract_before_any_database_call(tmp_path):
    client, manifest = _snapshot()
    client.rpc_calls.clear()
    path = tmp_path / "manifest.json"
    cleanup.write_manifest(path, manifest)

    with pytest.raises(RuntimeError, match="expected digest mismatch"):
        cleanup.apply_manifest(client, manifest, manifest_path=path, expected_digest="d" * 64, confirm=lambda _m: True)
    tampered = _rebound(manifest, lambda m: m.update(project_ref="other"))
    with pytest.raises(RuntimeError, match="project_ref mismatch"):
        cleanup.apply_manifest(client, tampered, manifest_path=path,
                               expected_digest=tampered["manifest_digest"], confirm=lambda _m: True)

    assert client.rpc_calls == []


def test_apply_surfaces_rpc_error_code_and_records_no_journal(tmp_path):
    class ApiError(Exception):
        code = "40001"
        message = "scope cleanup preconditions failed"
        details = '[{"problem": "drift"}]'

    client, manifest = _snapshot()
    client.rpc_responses["apply"] = ApiError()

    with pytest.raises(RuntimeError, match=r"code=40001 message=scope cleanup preconditions failed"):
        _apply(client, manifest, tmp_path)

    assert list(tmp_path.glob("*.apply-*.json")) == []


def test_apply_records_a_noop_retry(tmp_path):
    client, manifest = _snapshot()
    client.rpc_responses["apply"] = {"status": "noop", "applied_count": 0}

    assert _apply(client, manifest, tmp_path)["status"] == "noop"


def test_apply_rejects_unexpected_status(tmp_path):
    client, manifest = _snapshot()
    client.rpc_responses["apply"] = {"status": "weird"}

    with pytest.raises(RuntimeError, match="unexpected apply status"):
        _apply(client, manifest, tmp_path)


def test_postgrest_client_is_never_used_to_write():
    client = _Client(_target_rows())
    with pytest.raises(AssertionError):
        client.table("events").update({"is_active": False})


# ------------------------------------------------------------------ readback


def _applied_rows(manifest):
    rows = _target_rows()
    reasons = {t["id"]: cleanup.reason_for(t["category"], manifest["manifest_digest"]) for t in manifest["targets"]}
    for row in rows:
        row.update(is_active=False, deactivated_reason=reasons[row["id"]],
                   deactivated_by_pass="admin_manual", deactivated_at="2026-10-23T00:00:00+00:00")
    return rows


def test_readback_passes_for_a_clean_result_and_reports_each_problem():
    manifest = _manifest()
    assert cleanup.readback(_Client(_applied_rows(manifest)), manifest) == []

    rows = _applied_rows(manifest)
    rows[0]["is_active"] = True
    rows[1]["deactivated_reason"] = "something else"
    rows[2]["deactivated_by_pass"] = "merger"
    rows[3]["deactivated_at"] = "2026-10-23T00:00:09+00:00"
    problems = cleanup.readback(_Client(rows), manifest)
    assert any("still active" in p for p in problems)
    assert any("deactivated_reason" in p for p in problems)
    assert any("deactivated_by_pass" in p for p in problems)
    assert any("deactivated_at differs" in p for p in problems)


def test_readback_flags_an_active_child():
    manifest = _manifest()
    rows = _applied_rows(manifest)
    parent_id = next(r["id"] for r in rows if r["id"].startswith(PARENT_PREFIX))
    rows.append({"id": "99999999-0000-4000-8000-000000000002", "parent_event_id": parent_id, "is_active": True})

    assert any("active child" in p for p in cleanup.readback(_Client(rows), manifest))


# ------------------------------------------------------ rollback and package


def test_rollback_sql_restores_exactly_the_manifest_rows_behind_compare_and_swap():
    manifest = _manifest()
    sql = cleanup.render_rollback_sql(manifest)

    assert sql == cleanup.render_rollback_sql(manifest), "deterministic"
    assert sql.count("::uuid") == 2 * cleanup.TARGET_COUNT
    for target in manifest["targets"]:
        assert target["id"] in sql
        assert cleanup.reason_for(target["category"], manifest["manifest_digest"]) in sql
    assert "lock table public.events in share row exclusive mode" in sql
    assert "e.is_active is false" in sql
    assert "e.deactivated_by_pass = 'admin_manual'" in sql
    assert "e.deactivated_reason = b.expect_reason" in sql
    assert "count(distinct e.deactivated_at)" in sql
    assert f"if n <> {cleanup.TARGET_COUNT} then" in sql
    assert sql.rstrip().endswith("commit;")


def test_sql_literals_escape_quotes():
    assert cleanup.sql_literal("it's") == "'it''s'"
    assert cleanup.sql_literal(None) == "null"
    assert cleanup.sql_literal(False) == "false"


def test_approval_package_lists_every_event_with_a_clickable_link():
    client, manifest = _snapshot(
        event_reports=[{"event_id": _target_rows()[0]["id"], "status": "pending"}],
    )
    text = cleanup.render_approval_package(manifest)

    for target in manifest["targets"]:
        assert f"https://tokyotaiwanradar.com/ja/events/{target['id']}" in text
    assert manifest["manifest_digest"] in text
    assert "rollback SQL sha256" in text
    assert "apply_scope_cleanup('apply'" in text
    assert text.count("| 1 |") >= 1 and "| 22 |" in text


# ----------------------------------------------------------------------- CLI


def test_project_ref_assertion():
    cleanup.assert_project_ref(f"https://{cleanup.PROJECT_REF}.supabase.co")
    for bad in (None, "", "https://other.supabase.co", f"https://{cleanup.PROJECT_REF}.evil.com"):
        with pytest.raises(RuntimeError, match="does not point at project"):
            cleanup.assert_project_ref(bad)


def test_cli_modes_are_mutually_exclusive_and_require_their_inputs(capsys):
    parser = cleanup.build_parser()
    for argv in (
        [],
        ["--snapshot"],
        ["--snapshot", "--out", "x", "--manifest", "m"],
        ["--snapshot", "--apply", "--out", "x"],
        ["--validate"],
        ["--validate", "--manifest", "m"],
        ["--rollback-sql", "--manifest", "m", "--expect-digest", "a" * 64],
        ["--readback", "--manifest", "m", "--expect-digest", "a" * 64, "--out", "x"],
    ):
        with pytest.raises(SystemExit) as exc:
            args = parser.parse_args(argv)
            cleanup.validate_cli_args(parser, args)
        assert exc.value.code == 2, argv


def test_apply_needs_a_terminal_before_any_database_access(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cleanup, "get_supabase", lambda: pytest.fail("database must not be reached"))
    monkeypatch.setattr(cleanup, "load_manifest", lambda _p: pytest.fail("manifest must not be read"))

    with pytest.raises(SystemExit) as exc:
        cleanup.main(["--apply", "--manifest", "m.json", "--expect-digest", "a" * 64])
    assert exc.value.code == 2


def test_typed_confirmation_must_match_the_digest_prefix(monkeypatch, capsys):
    manifest = _manifest()
    digest12 = manifest["manifest_digest"][:12]
    monkeypatch.setattr("builtins.input", lambda _prompt: digest12)
    assert cleanup.confirm_on_terminal(manifest) is True
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    assert cleanup.confirm_on_terminal(manifest) is False


def test_snapshot_cli_refuses_a_dirty_script_before_database_access(monkeypatch):
    monkeypatch.setattr(cleanup, "assert_provenance_clean", lambda: (_ for _ in ()).throw(RuntimeError("dirty")))
    monkeypatch.setattr(cleanup, "get_supabase", lambda: pytest.fail("database must not be reached"))

    with pytest.raises(SystemExit) as exc:
        cleanup.main(["--snapshot", "--out", "unused.json"])
    assert exc.value.code == 2


def test_offline_modes_write_files_without_database_access(tmp_path, monkeypatch, capsys):
    manifest = _manifest()
    path = tmp_path / "manifest.json"
    cleanup.write_manifest(path, manifest)
    monkeypatch.setattr(cleanup, "get_supabase", lambda: pytest.fail("offline modes must not connect"))
    base = ["--manifest", str(path), "--expect-digest", manifest["manifest_digest"]]

    cleanup.main(["--rollback-sql", *base, "--out", str(tmp_path / "rollback.sql")])
    cleanup.main(["--approval-package", *base, "--out", str(tmp_path / "package.md")])
    cleanup.main(["--approval-package", *base])

    assert (tmp_path / "rollback.sql").read_text(encoding="utf-8").startswith("-- Rollback of japan-scope-gate")
    assert "approval package" in (tmp_path / "package.md").read_text(encoding="utf-8")
    assert "approval package" in capsys.readouterr().out

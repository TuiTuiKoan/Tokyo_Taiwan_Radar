"""The v2 CLI against the real apply_scope_cleanup function (throwaway PostgreSQL).

PostgREST reads are served from memory; only the RPC runs in PostgreSQL. This
checks that the payload the CLI builds is accepted by the migration, that the
rollback SQL really restores the rows, and the end-to-end apply path.
Skipped when no local PostgreSQL install is found.
"""

from __future__ import annotations

import json

import pytest

import _oneoff_deactivate_non_japan_scope as cleanup
from test_oneoff_deactivate_non_japan_scope import _Client, _Result, _target_rows
from test_scope_cleanup_rpc import cluster, connect  # noqa: F401  (fixture re-export)


@pytest.fixture(autouse=True)
def _fixed_provenance(monkeypatch):
    monkeypatch.setattr(cleanup, "current_git_head", lambda: "test-head")
    monkeypatch.setattr(cleanup, "current_script_sha256", lambda: "a" * 64)
    monkeypatch.setattr(cleanup, "current_migration_sha256", lambda: "b" * 64)


class _PgRpc:
    def __init__(self, info, params):
        self.info, self.params = info, params

    def execute(self):
        conn = connect(self.info, "service_role")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "select public.apply_scope_cleanup(%s, %s::jsonb)",
                    (self.params["p_mode"], json.dumps(self.params["p_manifest"])),
                )
                data = cur.fetchone()[0]
            conn.commit()
            return _Result(data)
        finally:
            conn.close()


class _PgBackedClient(_Client):
    def __init__(self, info, rows):
        super().__init__(rows)
        self.info = info

    def rpc(self, name, params):
        assert name == cleanup.RPC_NAME
        return _PgRpc(self.info, params)


@pytest.fixture
def seeded(cluster):  # noqa: F811
    rows = _target_rows()
    admin = connect(cluster, autocommit=True)
    with admin.cursor() as cur:
        cur.execute("select pg_terminate_backend(pid) from pg_stat_activity"
                    " where pid <> pg_backend_pid() and datname = current_database()")
        cur.execute("truncate public.events cascade")
        for row in rows:  # parent first: the spec order already lists it before its children
            cur.execute(
                "insert into public.events (id, source_name, raw_title, raw_description, location_address,"
                " location_prefectures, annotation_status, parent_event_id, is_active, updated_at)"
                " values (%s,%s,%s,%s,%s,%s,%s,%s,true,%s)",
                (row["id"], row["source_name"], row["raw_title"], row["raw_description"],
                 row["location_address"], row["location_prefectures"], row["annotation_status"],
                 row["parent_event_id"], row["updated_at"]),
            )
        cur.execute("insert into public.events (raw_title) values ('unrelated active event')")
    yield cluster, rows, admin
    admin.close()


def _states(admin):
    with admin.cursor() as cur:
        cur.execute("select id::text, is_active, deactivated_at, deactivated_reason, deactivated_by_pass"
                    " from public.events order by id")
        return cur.fetchall()


def test_snapshot_payload_is_accepted_by_the_migration_and_apply_round_trips(seeded, tmp_path):
    cluster_info, rows, admin = seeded
    client = _PgBackedClient(cluster_info, rows)

    manifest = cleanup.build_snapshot(client, created_at_utc="2026-08-04T00:00:00Z")
    path = tmp_path / "manifest.json"
    cleanup.write_manifest(path, manifest)
    report = cleanup.apply_manifest(
        client, manifest, manifest_path=path,
        expected_digest=manifest["manifest_digest"], confirm=lambda _m: True,
    )

    assert report["status"] == "applied" and report["applied_count"] == cleanup.TARGET_COUNT
    states = _states(admin)
    inactive = [s for s in states if s[1] is False]
    assert len(inactive) == cleanup.TARGET_COUNT
    assert len(states) == cleanup.TARGET_COUNT + 1 and sum(1 for s in states if s[1]) == 1
    assert {s[4] for s in inactive} == {"admin_manual"}
    assert len({s[2] for s in inactive}) == 1
    reasons = {t["id"]: cleanup.reason_for(t["category"], manifest["manifest_digest"]) for t in manifest["targets"]}
    assert all(reasons[s[0]] == s[3] for s in inactive)

    retry = cleanup.call_rpc(client, "apply", manifest)  # a lost response is safe to retry
    assert retry["status"] == "noop" and retry["applied_count"] == 0
    assert _states(admin) == states


def test_validate_reports_drift_after_a_concurrent_edit(seeded):
    cluster_info, rows, admin = seeded
    client = _PgBackedClient(cluster_info, rows)
    manifest = cleanup.build_snapshot(client)
    with admin.cursor() as cur:
        cur.execute("update public.events set raw_title = raw_title || ' edited' where id = %s", (rows[3]["id"],))

    with pytest.raises(RuntimeError, match="live validate failed"):
        cleanup.validate_live(client, manifest)


def test_rollback_sql_restores_the_applied_rows(seeded, tmp_path):
    cluster_info, rows, admin = seeded
    client = _PgBackedClient(cluster_info, rows)
    manifest = cleanup.build_snapshot(client)
    path = tmp_path / "manifest.json"
    cleanup.write_manifest(path, manifest)
    cleanup.apply_manifest(client, manifest, manifest_path=path,
                           expected_digest=manifest["manifest_digest"], confirm=lambda _m: True)

    with admin.cursor() as cur:
        cur.execute(cleanup.render_rollback_sql(manifest))

    states = _states(admin)
    assert all(s[1] is True and s[2] is None and s[3] is None and s[4] is None for s in states)


def test_rollback_sql_refuses_when_a_row_was_changed_after_the_apply(seeded, tmp_path):
    cluster_info, rows, admin = seeded
    client = _PgBackedClient(cluster_info, rows)
    manifest = cleanup.build_snapshot(client)
    path = tmp_path / "manifest.json"
    cleanup.write_manifest(path, manifest)
    cleanup.apply_manifest(client, manifest, manifest_path=path,
                           expected_digest=manifest["manifest_digest"], confirm=lambda _m: True)
    with admin.cursor() as cur:  # someone re-activates and re-deactivates one row by hand
        cur.execute("update public.events set deactivated_reason = 'manual' where id = %s", (rows[0]["id"],))

    import psycopg2

    with admin.cursor() as cur:
        with pytest.raises(psycopg2.Error, match="matched 21 rows, expected 22"):
            cur.execute(cleanup.render_rollback_sql(manifest))
        cur.execute("rollback")  # the script's own BEGIN is still open after the abort
    still =[s for s in _states(admin) if s[1] is False]
    assert len(still) == cleanup.TARGET_COUNT, "nothing was restored"

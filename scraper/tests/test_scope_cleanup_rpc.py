"""apply_scope_cleanup RPC (migration 103) against a throwaway PostgreSQL.

Starts its own cluster from a local PostgreSQL install (pg_ctl on PATH,
Homebrew, or /usr/lib/postgresql) and skips when there is none. Nothing here
touches Supabase. Run: cd scraper && python -m pytest tests/test_scope_cleanup_rpc.py
"""

from __future__ import annotations

import glob
import json
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import errors, extensions  # noqa: E402

MIGRATION = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "103_scope_cleanup_rpc.sql"
DIGEST = "a" * 12 + "b" * 52
DIGEST12 = DIGEST[:12]

SCHEMA = """
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
grant usage on schema public to anon, authenticated, service_role;
-- Supabase grants EXECUTE on every new public function to these roles.
alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;
alter default privileges in schema public grant all on tables to anon, authenticated, service_role;

create function public.set_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

create table public.events (
  id uuid primary key default gen_random_uuid(),
  source_name text,
  raw_title text,
  raw_description text,
  location_address text,
  location_prefectures text[],
  annotation_status text,
  parent_event_id uuid references public.events(id) on delete set null,
  is_active boolean not null default true,
  deactivated_at timestamptz,
  deactivated_reason text,
  deactivated_by_pass text,
  updated_at timestamptz not null default now()
);
create trigger events_updated_at before update on public.events
  for each row execute function public.set_updated_at();
create table public.saved_events (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null references public.events(id) on delete cascade
);
grant all on all tables in schema public to anon, authenticated, service_role;
"""

BEFORE_SQL = """
select jsonb_build_object(
  'source_name', source_name, 'raw_title', raw_title,
  'location_address', location_address, 'location_prefectures', to_jsonb(location_prefectures),
  'annotation_status', annotation_status, 'parent_event_id', parent_event_id,
  'is_active', is_active, 'deactivated_at', deactivated_at,
  'deactivated_reason', deactivated_reason, 'deactivated_by_pass', deactivated_by_pass,
  'updated_at', updated_at,
  'raw_description_sha256', case when raw_description is null then null
    else encode(sha256(convert_to(raw_description, 'UTF8')), 'hex') end)
from public.events where id = %s
"""


def _pg_bin() -> Path | None:
    found = shutil.which("pg_ctl")
    candidates = [Path(found).parent] if found else []
    candidates += [Path(p) for p in sorted(glob.glob("/opt/homebrew/opt/postgresql@*/bin"), reverse=True)]
    candidates += [Path(p) for p in sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)]
    for c in candidates:
        if (c / "pg_ctl").exists() and (c / "initdb").exists():
            return c
    return None


@pytest.fixture(scope="module")
def cluster():
    bin_dir = _pg_bin()
    if bin_dir is None:
        pytest.skip("no local PostgreSQL install (pg_ctl/initdb) found")
    # Unix socket paths are limited to ~100 bytes, so keep the directory short.
    root = Path(tempfile.mkdtemp(prefix="ttrpg", dir="/tmp"))
    data = root / "data"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    subprocess.run([bin_dir / "initdb", "-D", data, "-U", "postgres", "-A", "trust", "-E", "UTF8", "--locale=C"],
                   check=True, capture_output=True)
    subprocess.run([bin_dir / "pg_ctl", "-D", data, "-w", "-l", root / "server.log", "-o",
                    f"-p {port} -c listen_addresses='' -c unix_socket_directories={root} -c fsync=off", "start"],
                   check=True, capture_output=True)
    info = {"host": str(root), "port": port, "dbname": "postgres", "user": "postgres"}
    admin = psycopg2.connect(**info)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(SCHEMA)
        cur.execute(MIGRATION.read_text())
    admin.close()
    yield info
    subprocess.run([bin_dir / "pg_ctl", "-D", data, "-m", "immediate", "stop"], capture_output=True)
    shutil.rmtree(root, ignore_errors=True)


def connect(info, role=None, autocommit=False):
    conn = psycopg2.connect(**info)
    conn.autocommit = autocommit
    if role:
        with conn.cursor() as cur:
            cur.execute(f"set role {role}")
        if not autocommit:
            conn.commit()
    return conn


@pytest.fixture
def db(cluster):
    """Admin autocommit connection; events/saved_events are emptied before each test."""
    conn = connect(cluster, autocommit=True)
    with conn.cursor() as cur:
        # A failed test may leave a transaction open; do not let it block the next one.
        cur.execute("select pg_terminate_backend(pid) from pg_stat_activity"
                    " where pid <> pg_backend_pid() and datname = current_database()")
        cur.execute("set lock_timeout = '10s'")
        cur.execute("alter table public.events drop constraint if exists poison_check")
        cur.execute("truncate public.events cascade")
    yield conn
    conn.close()


class World:
    """Four events: parent P with children C1, C2, and an unrelated S."""

    def __init__(self, conn):
        self.conn = conn
        self.ids = {}
        for name in ("P", "C1", "C2", "S"):
            self.ids[name] = str(uuid.uuid4())
        self._insert("P", None)
        self._insert("C1", "P")
        self._insert("C2", "P")
        self._insert("S", None)

    def _insert(self, name, parent):
        with self.conn.cursor() as cur:
            cur.execute(
                "insert into public.events (id, source_name, raw_title, raw_description, location_address,"
                " location_prefectures, annotation_status, parent_event_id) values (%s,'bigromantic',%s,%s,"
                "'Taipei','{taipei}'::text[],'annotated',%s)",
                (self.ids[name], f"title-{name}", f"description of {name} 台北", self.ids.get(parent)),
            )

    def before(self, name):
        with self.conn.cursor() as cur:
            cur.execute(BEFORE_SQL, (self.ids[name],))
            return cur.fetchone()[0]

    def manifest(self, names, external=(), **overrides):
        m = {
            "schema_version": 2,
            "manifest_digest": DIGEST,
            "target_count": len(names),
            "targets": [{"id": self.ids[n], "category": "A4_japan_band", "before": self.before(n)} for n in names],
            "external_children": [{"id": self.ids[n], "parent_event_id": self.ids["P"]} for n in external],
        }
        m.update(overrides)
        return m

    def row(self, name):
        with self.conn.cursor() as cur:
            cur.execute("select is_active, deactivated_at, deactivated_reason, deactivated_by_pass,"
                        " updated_at, parent_event_id from public.events where id = %s", (self.ids[name],))
            return cur.fetchone()

    def active(self, *names):
        return [self.row(n)[0] for n in names]


@pytest.fixture
def world(db):
    return World(db)


def call(info, mode, manifest, role="service_role"):
    conn = connect(info, role)
    try:
        with conn.cursor() as cur:
            cur.execute("select public.apply_scope_cleanup(%s, %s::jsonb)", (mode, json.dumps(manifest)))
            result = cur.fetchone()[0]
        conn.commit()
        return result
    finally:
        conn.close()


def expect_error(info, mode, manifest, role="service_role"):
    conn = connect(info, role)
    try:
        with conn.cursor() as cur, pytest.raises(psycopg2.Error) as exc:
            cur.execute("select public.apply_scope_cleanup(%s, %s::jsonb)", (mode, json.dumps(manifest)))
        conn.rollback()
        return exc.value
    finally:
        conn.close()


def problems_of(err):
    return json.loads(err.diag.message_detail)


# ---------------------------------------------------------------- definition


def test_function_is_invoker_pinned_and_service_role_only(db):
    with db.cursor() as cur:
        cur.execute("""select p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig,
            has_function_privilege('anon', p.oid, 'EXECUTE'),
            has_function_privilege('authenticated', p.oid, 'EXECUTE'),
            has_function_privilege('public', p.oid, 'EXECUTE'),
            has_function_privilege('service_role', p.oid, 'EXECUTE')
            from pg_proc p where p.oid = 'public.apply_scope_cleanup(text,jsonb)'::regprocedure""")
        secdef, owner, config, anon, auth, public, service = cur.fetchone()
    assert (secdef, owner) == (False, "postgres")
    assert set(config) == {"search_path=pg_catalog", "lock_timeout=5s"}
    assert (anon, auth, public, service) == (False, False, False, True)


def test_migration_can_be_reapplied(db):
    with db.cursor() as cur:
        cur.execute(MIGRATION.read_text())


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_api_roles_cannot_call_it(cluster, world, role):
    err = expect_error(cluster, "validate", world.manifest(["S"]), role=role)
    assert err.pgcode == "42501"


def test_postgres_owner_may_call_it(cluster, world):
    assert call(cluster, "validate", world.manifest(["S"]), role=None)["ok"] is True


# ------------------------------------------------------------------ validate


def test_validate_reports_ok_and_writes_nothing(cluster, world):
    before = world.row("S")
    result = call(cluster, "validate", world.manifest(["S"]))
    assert result["status"] == "valid" and result["ok"] is True
    assert world.row("S") == before


def test_validate_returns_problems_instead_of_raising(cluster, world, db):
    manifest = world.manifest(["S"])
    with db.cursor() as cur:
        cur.execute("update public.events set raw_title = 'edited' where id = %s", (world.ids["S"],))
    result = call(cluster, "validate", manifest)
    assert result["status"] == "invalid" and result["ok"] is False
    assert result["problems"][0]["id"] == world.ids["S"]
    assert "raw_title" in result["problems"][0]["fields"]


# --------------------------------------------------------------------- apply


def test_apply_deactivates_the_whole_family_in_one_statement(cluster, world):
    names = ["P", "C1", "C2"]
    result = call(cluster, "apply", world.manifest(names))
    assert result["status"] == "applied"
    assert result["applied_count"] == 3
    assert result["active_before"] - result["active_after"] == 3
    stamps = set()
    for n in names:
        active, at, reason, by_pass, _updated, parent = world.row(n)
        assert active is False
        assert reason == f"out_of_scope: A4_japan_band - scope cleanup {DIGEST12}"
        assert by_pass == "admin_manual"
        stamps.add(at)
    assert len(stamps) == 1, "one clock reading for the whole batch"
    assert world.active("S") == [True]
    assert str(world.row("C1")[5]) == world.ids["P"], "parent_event_id is left untouched"


def test_second_apply_is_a_noop(cluster, world):
    manifest = world.manifest(["P", "C1", "C2"])
    call(cluster, "apply", manifest)
    snapshot = [world.row(n) for n in ("P", "C1", "C2")]
    again = call(cluster, "apply", manifest)
    assert again["status"] == "noop" and again["applied_count"] == 0
    assert [world.row(n) for n in ("P", "C1", "C2")] == snapshot


def test_apply_with_inactive_external_children_listed(cluster, world, db):
    with db.cursor() as cur:
        cur.execute("update public.events set is_active = false where id = any(%s::uuid[])",
                    ([world.ids["C1"], world.ids["C2"]],))
    manifest = world.manifest(["P"], external=["C1", "C2"])
    assert call(cluster, "apply", manifest)["status"] == "applied"


# ------------------------------------------------------------ preconditions


@pytest.mark.parametrize("column,value,field", [
    ("raw_title", "edited", "raw_title"),
    ("location_prefectures", "{osaka}", "location_prefectures"),
    ("annotation_status", "pending", "annotation_status"),
    ("deactivated_reason", "something else", "deactivated_reason"),
    ("raw_description", "different body", "raw_description_sha256"),
])
def test_field_drift_aborts_with_zero_writes(cluster, world, db, column, value, field):
    manifest = world.manifest(["S", "P"])
    cast = "::text[]" if column == "location_prefectures" else ""
    with db.cursor() as cur:
        cur.execute(f"update public.events set {column} = %s{cast} where id = %s", (value, world.ids["S"]))
    before = [world.row(n) for n in ("P", "S")]
    err = expect_error(cluster, "apply", manifest)
    assert err.pgcode == "40001"
    drift = [p for p in problems_of(err) if p.get("problem") == "drift"]
    assert drift[0]["id"] == world.ids["S"] and field in drift[0]["fields"]
    assert [world.row(n) for n in ("P", "S")] == before, "no partial write"


def test_updated_at_alone_is_enough_to_abort(cluster, world, db):
    manifest = world.manifest(["S"])
    with db.cursor() as cur:  # a no-op UPDATE still fires the updated_at trigger
        cur.execute("update public.events set raw_title = raw_title where id = %s", (world.ids["S"],))
    err = expect_error(cluster, "apply", manifest)
    assert err.pgcode == "40001"
    assert problems_of(err)[0]["fields"] == ["updated_at"]


def test_timestamp_comparison_ignores_the_session_time_zone(cluster, world, db):
    with db.cursor() as cur:
        cur.execute("set timezone = 'Asia/Tokyo'")
        manifest = world.manifest(["S"])
    assert "+09:00" in manifest["targets"][0]["before"]["updated_at"]
    assert call(cluster, "apply", manifest)["status"] == "applied"


def test_missing_target_aborts(cluster, world, db):
    manifest = world.manifest(["S"])
    with db.cursor() as cur:
        cur.execute("delete from public.events where id = %s", (world.ids["S"],))
    err = expect_error(cluster, "apply", manifest)
    assert err.pgcode == "40001" and problems_of(err)[0]["problem"] == "missing"


def test_child_without_its_parent_in_the_set_aborts(cluster, world):
    err = expect_error(cluster, "apply", world.manifest(["C1"]))
    assert err.pgcode == "40001"
    assert {p["problem"] for p in problems_of(err)} == {"parent_outside_set"}
    assert world.active("C1") == [True]


def test_parent_alone_aborts_while_children_are_active(cluster, world):
    err = expect_error(cluster, "apply", world.manifest(["P"]))
    assert err.pgcode == "40001"
    kinds = {p["problem"] for p in problems_of(err)}
    assert kinds == {"external_children_mismatch", "active_external_child"}
    assert world.active("P", "C1", "C2") == [True, True, True]


def test_active_external_child_aborts_even_when_listed(cluster, world):
    err = expect_error(cluster, "apply", world.manifest(["P"], external=["C1", "C2"]))
    assert {p["problem"] for p in problems_of(err)} == {"active_external_child"}


def test_constraint_violation_rolls_back_the_whole_batch(cluster, world, db):
    with db.cursor() as cur:
        cur.execute("update public.events set source_name = 'poison' where id = %s", (world.ids["C2"],))
        cur.execute("alter table public.events add constraint poison_check "
                    "check (is_active or source_name <> 'poison')")
    manifest = world.manifest(["P", "C1", "C2"])
    err = expect_error(cluster, "apply", manifest)
    assert err.pgcode == "23514"
    assert world.active("P", "C1", "C2") == [True, True, True]


@pytest.mark.parametrize("change", [
    {"unexpected": 1},
    {"manifest_digest": "short"},
    {"manifest_digest": "A" * 64},
    {"schema_version": 1},
    {"target_count": 2},
])
def test_malformed_manifest_is_rejected(cluster, world, change):
    err = expect_error(cluster, "apply", world.manifest(["S"], **change))
    assert err.pgcode == "22023"


def test_malformed_targets_and_mode_are_rejected(cluster, world):
    m = world.manifest(["S"])
    m["targets"][0]["before"].pop("updated_at")
    assert expect_error(cluster, "apply", m).pgcode == "22023"
    m = world.manifest(["S"])
    m["targets"][0]["extra"] = 1
    assert expect_error(cluster, "apply", m).pgcode == "22023"
    m = world.manifest(["S"])
    m["targets"][0]["category"] = "bad category!"
    assert expect_error(cluster, "apply", m).pgcode == "22023"
    assert expect_error(cluster, "dry-run", world.manifest(["S"])).pgcode == "22023"
    dup = world.manifest(["S", "S"])
    assert expect_error(cluster, "apply", dup).pgcode == "22023"
    assert world.active("S") == [True]


def test_more_than_fifty_targets_is_rejected(cluster, world):
    m = world.manifest(["S"])
    m["targets"] = m["targets"] * 51
    m["target_count"] = 51
    assert expect_error(cluster, "apply", m).pgcode == "22023"


# --------------------------------------------------------------- concurrency


def _thread_call(info, mode, manifest, out):
    try:
        out["result"] = call(info, mode, manifest)
    except psycopg2.Error as exc:
        out["error"] = exc


def test_apply_holds_a_table_lock_that_blocks_inserts_and_fk_checks(cluster, world):
    applier = connect(cluster, "service_role")
    with applier.cursor() as cur:
        cur.execute("select public.apply_scope_cleanup('apply', %s::jsonb)", (json.dumps(world.manifest(["S"])),))
    # Transaction still open: a phantom child cannot appear and nobody else writes.
    writer = connect(cluster, "service_role")
    with writer.cursor() as cur:
        cur.execute("set lock_timeout = '500ms'")
        with pytest.raises(errors.LockNotAvailable):
            cur.execute("insert into public.events (parent_event_id, raw_title) values (%s, 'phantom')",
                        (world.ids["P"],))
    writer.rollback()
    # A foreign-key check only takes ROW SHARE on the table, which SHARE ROW EXCLUSIVE does
    # not conflict with: rows that reference an untouched event are not delayed...
    with writer.cursor() as cur:
        cur.execute("set lock_timeout = '500ms'")
        cur.execute("insert into public.saved_events (event_id) values (%s)", (world.ids["P"],))
    writer.rollback()
    # ...but the FK check on a target row (locked FOR UPDATE by apply) waits for the commit.
    with writer.cursor() as cur:
        cur.execute("set lock_timeout = '500ms'")
        with pytest.raises(errors.LockNotAvailable):
            cur.execute("insert into public.saved_events (event_id) values (%s)", (world.ids["S"],))
    writer.rollback()
    with writer.cursor() as cur:
        cur.execute("set lock_timeout = '500ms'")
        with pytest.raises(errors.LockNotAvailable):
            cur.execute("update public.events set raw_title = 'x' where id = %s", (world.ids["C1"],))
    writer.rollback()
    with writer.cursor() as cur:  # reads are not blocked
        cur.execute("select count(*) from public.events")
        assert cur.fetchone()[0] == 4
    writer.rollback()
    applier.rollback()
    writer.close()
    applier.close()
    assert world.active("S") == [True], "rolled back with the transaction"


def test_phantom_child_committed_after_the_snapshot_is_seen_once_the_lock_is_won(cluster, world, db):
    manifest = world.manifest(["P", "C1", "C2"])
    inserter = connect(cluster, "service_role")
    child = str(uuid.uuid4())
    with inserter.cursor() as cur:
        cur.execute("insert into public.events (id, parent_event_id, raw_title) values (%s, %s, 'late child')",
                    (child, world.ids["P"]))
    out: dict = {}
    t = threading.Thread(target=_thread_call, args=(cluster, "apply", manifest, out))
    t.start()
    time.sleep(1.0)  # the applier is now waiting for the lock
    assert t.is_alive()
    inserter.commit()
    t.join(10)
    inserter.close()
    assert out["error"].pgcode == "40001"
    kinds = {p["problem"] for p in problems_of(out["error"])}
    assert kinds == {"external_children_mismatch", "active_external_child"}
    assert world.active("P", "C1", "C2") == [True, True, True]


def test_concurrent_edit_that_commits_while_apply_waits_is_detected(cluster, world):
    manifest = world.manifest(["S"])
    editor = connect(cluster, "service_role")
    with editor.cursor() as cur:
        cur.execute("update public.events set raw_title = 'edited mid-flight' where id = %s", (world.ids["S"],))
    out: dict = {}
    t = threading.Thread(target=_thread_call, args=(cluster, "apply", manifest, out))
    t.start()
    time.sleep(1.0)
    editor.commit()
    t.join(10)
    editor.close()
    assert out["error"].pgcode == "40001"
    assert {"raw_title", "updated_at"} <= set(problems_of(out["error"])[0]["fields"])
    assert world.active("S") == [True]


def test_lock_timeout_fails_with_zero_writes(cluster, world):
    manifest = world.manifest(["S"])
    holder = connect(cluster, "service_role")
    with holder.cursor() as cur:
        cur.execute("update public.events set raw_title = raw_title where id = %s", (world.ids["C1"],))
    started = time.monotonic()
    err = expect_error(cluster, "apply", manifest)
    elapsed = time.monotonic() - started
    holder.rollback()
    holder.close()
    assert err.pgcode == "55P03"
    assert 4 < elapsed < 9, "function-level lock_timeout of 5s"
    assert world.active("S") == [True]


def test_validate_does_not_take_the_table_lock(cluster, world):
    holder = connect(cluster, "service_role")
    with holder.cursor() as cur:
        cur.execute("update public.events set raw_title = raw_title where id = %s", (world.ids["C1"],))
    started = time.monotonic()
    result = call(cluster, "validate", world.manifest(["S"]))
    holder.rollback()
    holder.close()
    assert result["ok"] is True
    assert time.monotonic() - started < 2

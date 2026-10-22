import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "inventory_events_writers", Path(__file__).resolve().parents[1] / "inventory_events_writers.py"
)
inv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inv)


def _scan(tmp_path, source):
    path = tmp_path / "mod.py"
    path.write_text(source, encoding="utf-8")
    return inv.scan_python(path)


def test_direct_and_variable_chains_are_writes(tmp_path):
    result = _scan(tmp_path, '''
def a(sb):
    sb.table("events").update({"x": 1}).eq("id", 1).execute()
def b(sb):
    q = sb.table("events")
    q.upsert({"x": 1}).execute()
def c(sb):
    sb.from_("events").delete().eq("id", 1).execute()
''')
    assert sorted(w["op"] for w in result["writes"]) == ["delete", "update", "upsert"]


def test_reads_other_tables_and_rpc_names(tmp_path):
    result = _scan(tmp_path, '''
def a(sb):
    sb.table("events").select("id").execute()
    sb.table("scraper_runs").insert({}).execute()
    sb.rpc("confirm_scope_report", {})
''')
    assert result["writes"] == [] and result["rpcs"] == ["confirm_scope_report"]


def test_raw_sql_writes_are_flagged(tmp_path):
    assert _scan(tmp_path, 'X = "UPDATE public.events SET is_active = false"')["sql"]
    assert _scan(tmp_path, 'X = "select * from events"')["sql"] == []


def test_reachability_follows_local_imports(tmp_path):
    modules = {n: tmp_path / f"{n}.py" for n in ("main", "db", "util")}
    modules["main"].write_text("import db\n"); modules["db"].write_text("from util import x\n")
    modules["util"].write_text("")
    graph = {n: inv.local_imports(p, modules) for n, p in modules.items()}
    assert inv.reachable("main", modules, graph) == {"main", "db", "util"}


def test_repository_inventory_finds_the_known_writers():
    data = inv.build()
    assert {"annotator", "merger", "database"} <= set(data["python_writers"])
    assert {"scraper.yml", "merger.yml", "error-recovery.yml", "refetch-thin-events.yml"} <= {
        wf for wf, info in data["workflows"].items() if info["writers"]
    }
    web = {row["file"]: row for row in data["web_writers"]}
    assert web["web/app/actions/owner-events.ts"]["maintenance_lock"] is True
    assert any("launchd" in item for item in data["not_covered"])

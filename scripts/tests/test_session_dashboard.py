import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import session_dashboard as sd  # noqa: E402
import session_map  # noqa: E402

ROOT_DIR = "/Users/u/Development/3-TTR/Tokyo Taiwan Radar"
SID_A = "aaaaaaaa-1111-2222-3333-444444444444"
SID_B = "bbbbbbbb-1111-2222-3333-444444444444"


def entry(**kw):
    base = {
        "pid": 111,
        "sessionId": SID_A,
        "cwd": ROOT_DIR,
        "startedAt": 1792744655947,
        "kind": "interactive",
        "entrypoint": "cli",
        "name": "ai-harness·next",
        "nameSource": "user",
        "status": "idle",
        "updatedAt": 1792821852378,
    }
    base.update(kw)
    return base


# --- worktree_of ---------------------------------------------------------------------------------


def test_worktree_slug_and_path_from_a_subdirectory():
    label, path = sd.worktree_of(f"{ROOT_DIR}/ttr-ai-harness-worktree/scraper")
    assert label == "ai-harness"
    assert path == f"{ROOT_DIR}/ttr-ai-harness-worktree"


def test_main_working_tree_is_labelled_root():
    label, path = sd.worktree_of(ROOT_DIR)
    assert label == "root（主工作目錄）"
    assert path == ROOT_DIR


def test_other_directories_use_their_basename():
    assert sd.worktree_of("/tmp/some-project") == ("some-project", "/tmp/some-project")
    assert sd.worktree_of("") == ("?", "")


# --- location ------------------------------------------------------------------------------------


def test_location_labels():
    assert sd.location(entry(entrypoint="claude-vscode"), "") == "VS Code 面板"
    assert sd.location(entry(entrypoint="cli"), "vscode") == "VS Code 終端機"
    assert sd.location(entry(entrypoint="cli"), "Apple_Terminal") == "Terminal.app"
    assert sd.location(entry(entrypoint="cli"), "iTerm.app") == "iTerm"
    assert sd.location(entry(entrypoint="cli"), "") == "終端機（未知）"
    assert sd.location(entry(entrypoint="cli"), "WezTerm") == "終端機（WezTerm）"
    assert sd.location(entry(kind="bg", entrypoint="cli"), "") == "背景（bg）"


def test_term_program_is_parsed_from_ps_output_and_failures_are_empty():
    ok = lambda pid: "PID TT STAT TIME COMMAND\n 1 s0 S claude HOME=/x TERM_PROGRAM=vscode PATH=/bin"  # noqa: E731
    assert sd.term_program_of(1, run=ok) == "vscode"
    none = lambda pid: "PID COMMAND\n 1 claude HOME=/x"  # noqa: E731
    assert sd.term_program_of(1, run=none) == ""

    def boom(pid):
        raise OSError("no ps")

    assert sd.term_program_of(1, run=boom) == ""


# --- registry ------------------------------------------------------------------------------------


def test_registry_skips_unreadable_files_and_marks_dead_pids(tmp_path):
    (tmp_path / "111.json").write_text(json.dumps(entry()), encoding="utf-8")
    (tmp_path / "222.json").write_text(json.dumps(entry(pid=222, sessionId=SID_B)), encoding="utf-8")
    (tmp_path / "333.json").write_text("not json", encoding="utf-8")
    (tmp_path / "x.key").write_text("secret", encoding="utf-8")
    reg = sd.load_registry(tmp_path, alive=lambda pid: pid == 111)
    assert set(reg) == {SID_A, SID_B}
    assert reg[SID_A]["alive"] is True
    assert reg[SID_B]["alive"] is False


# --- rows ----------------------------------------------------------------------------------------


def _session(sid, cwd, branch="main", parent="", title="", ai="", ts="2026-10-23T10:00:00Z"):
    return session_map.Session(
        sid=sid,
        path=Path(f"/t/{sid}.jsonl"),
        custom_title=title,
        ai_title=ai,
        cwd=cwd,
        branch=branch,
        entrypoint="cli",
        last_ts=ts,
        parent_sid=parent,
    )


def test_rows_prefer_transcript_cwd_over_start_directory_and_flag_unnamed():
    reg = {SID_A: {**entry(nameSource="derived", name="tokyo-taiwan-radar-8a"), "alive": True}}
    sess = [_session(SID_A, f"{ROOT_DIR}/ttr-ai-harness-worktree", branch="feat/ai-harness", ai="自動標題")]
    rows = sd.build_rows(reg, sess, term_program=lambda pid: "")
    assert len(rows) == 1
    row = rows[0]
    assert (row.worktree, row.branch) == ("ai-harness", "feat/ai-harness")
    assert row.unnamed is True
    assert row.summary == "自動標題"
    assert row.pid == 111


def test_live_sessions_without_a_transcript_still_appear():
    reg = {SID_A: {**entry(), "alive": True}}
    rows = sd.build_rows(reg, [], term_program=lambda pid: "vscode")
    assert [r.sid for r in rows] == [SID_A]
    assert rows[0].worktree == "root（主工作目錄）"
    assert rows[0].where == "VS Code 終端機"


def test_ended_sessions_only_appear_when_asked_and_without_a_pid():
    reg = {SID_A: {**entry(), "alive": True}}
    ended = _session(SID_B, f"{ROOT_DIR}/ttr-x-worktree", title="old")
    live_only = sd.build_rows(reg, [ended], term_program=lambda pid: "")
    assert [r.sid for r in live_only] == [SID_A]
    both = sd.build_rows(reg, [ended], term_program=lambda pid: "", include_ended=True)
    by_sid = {r.sid: r for r in both}
    assert by_sid[SID_B].status == "已結束"
    assert by_sid[SID_B].pid is None


def test_dead_registry_entries_count_as_ended():
    reg = {SID_A: {**entry(), "alive": False}}
    assert sd.build_rows(reg, [], term_program=lambda pid: "") == []
    rows = sd.build_rows(reg, [], term_program=lambda pid: "", include_ended=True)
    assert rows[0].status == "已結束"


def test_parent_link_is_resolved_when_the_parent_is_listed():
    reg = {
        SID_A: {**entry(), "alive": True},
        SID_B: {**entry(pid=222, sessionId=SID_B, name="child"), "alive": True},
    }
    sess = [_session(SID_B, ROOT_DIR, parent=SID_A[:8])]
    rows = {r.sid: r for r in sd.build_rows(reg, sess, term_program=lambda pid: "")}
    assert rows[SID_B].parent_sid == SID_A[:8]
    assert rows[SID_B].parent_listed is True


# --- html ----------------------------------------------------------------------------------------


def test_html_escapes_names_and_titles():
    reg = {SID_A: {**entry(name="<script>alert(1)</script>"), "alive": True}}
    sess = [_session(SID_A, ROOT_DIR, title="<img src=x onerror=alert(2)>")]
    html = sd.render_html(sd.build_rows(reg, sess, term_program=lambda pid: ""), generated_at="2026-10-23 22:00")
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x" not in html


def test_html_has_refresh_pid_worktree_link_and_parent_anchor():
    reg = {
        SID_A: {**entry(), "alive": True},
        SID_B: {**entry(pid=222, sessionId=SID_B, name="child"), "alive": True},
    }
    sess = [
        _session(SID_A, f"{ROOT_DIR}/ttr-ai-harness-worktree", branch="feat/ai-harness"),
        _session(SID_B, f"{ROOT_DIR}/ttr-ai-harness-worktree", parent=SID_A[:8]),
    ]
    html = sd.render_html(sd.build_rows(reg, sess, term_program=lambda pid: ""), generated_at="2026-10-23 22:00", refresh=15)
    assert "location.reload()" in html and "15000" in html
    assert 'http-equiv="refresh"' not in html
    assert ">111<" in html and ">222<" in html
    assert "vscode://file/Users/u/Development/3-TTR/Tokyo%20Taiwan%20Radar/ttr-ai-harness-worktree" in html
    assert f'id="s-{SID_A[:8]}"' in html
    assert f'href="#s-{SID_A[:8]}"' in html


def test_html_for_no_rows_says_so():
    html = sd.render_html([], generated_at="2026-10-23 22:00")
    assert "沒有" in html


# --- cli -----------------------------------------------------------------------------------------


def test_main_writes_the_output_file_and_leaves_no_temp_files(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "111.json").write_text(json.dumps(entry()), encoding="utf-8")
    projects = tmp_path / "projects"
    projects.mkdir()
    out = tmp_path / "out" / "sessions.html"
    code = sd.main(
        ["--sessions-dir", str(sessions_dir), "--projects-dir", str(projects), "--out", str(out), "--no-ps", "--no-gh"],
        alive=lambda pid: True,
    )
    assert code == 0
    assert "ai-harness·next" in out.read_text(encoding="utf-8")
    assert [p.name for p in out.parent.iterdir()] == ["sessions.html"]


# --- spec / issue / label / theme ---------------------------------------------------------------

CTX = sd.Context(
    specs={"ai-harness", "closer-auto-retire", "scraper-zero-output", "ai-portability-followups"},
    themes={"ai-harness": "AI工具鏈", "scraper-zero-output": "爬蟲管線"},
    overrides={"328": "追蹤清理"},
    issue_labels={378: ["spec:scraper-zero-output", "bug"], 328: ["spec:ai-harness"], 999: ["enhancement"]},
)


def _row(entry_kw=None, sess=None, ctx=CTX):
    reg = {SID_A: {**entry(**(entry_kw or {})), "alive": True}}
    return sd.build_rows(reg, [sess] if sess else [], term_program=lambda pid: "", ctx=ctx)[0]


def test_issue_numbers_are_found_in_names_and_summaries():
    assert sd.issues_in("#369.371 修理規劃") == [369, 371]
    assert sd.issues_in("fix #378 and #5 (#12345)") == [378, 12345]
    assert sd.issues_in("no issues here") == []
    assert sd.issues_in("#1 #2 #3 #4 #5 #6 #7") == []  # one-digit numbers are not treated as issues


def test_spec_comes_from_the_worktree_slug_first():
    sess = _session(SID_A, f"{ROOT_DIR}/ttr-ai-harness-worktree", branch="feat/something-else", title="#378 x")
    row = _row(sess=sess)
    assert (row.spec, row.spec_source) == ("ai-harness", "工作樹")
    assert row.theme == "AI工具鏈"


def test_spec_comes_from_the_branch_for_sessions_in_the_main_working_tree():
    sess = _session(SID_A, ROOT_DIR, branch="feat/closer-auto-retire")
    row = _row(sess=sess)
    assert (row.spec, row.spec_source) == ("closer-auto-retire", "branch")


def test_spec_comes_from_issue_labels_when_nothing_else_matches():
    sess = _session(SID_A, ROOT_DIR, branch="main", title="#378 台湾映画祭")
    row = _row({"name": "tokyo-taiwan-radar-ab"}, sess)
    assert (row.spec, row.spec_source) == ("scraper-zero-output", "issue #378")
    assert row.issues == [378]
    assert row.labels == ["spec:scraper-zero-output", "bug"]
    assert row.theme == "爬蟲管線"


def test_issue_override_theme_wins_over_the_spec_theme():
    sess = _session(SID_A, f"{ROOT_DIR}/ttr-ai-harness-worktree", title="#328 worktree 清理")
    assert _row(sess=sess).theme == "追蹤清理"


def test_no_information_leaves_the_columns_empty_without_crashing():
    row = _row({"name": "plain"}, _session(SID_A, ROOT_DIR, branch="main"), ctx=sd.Context())
    assert (row.spec, row.issues, row.labels, row.theme) == ("", [], [], "")


def test_issue_without_spec_label_gives_no_spec_but_keeps_its_labels():
    row = _row({"name": "#999 something"}, _session(SID_A, ROOT_DIR, branch="main"))
    assert row.spec == "" and row.labels == ["enhancement"]


def test_html_shows_spec_issue_label_and_theme_with_links_and_escaping():
    ctx = sd.Context(specs={"ai-harness"}, themes={"ai-harness": "AI工具鏈"}, issue_labels={378: ["spec:ai-harness", "<b>x</b>"]})
    sess = _session(SID_A, f"{ROOT_DIR}/ttr-ai-harness-worktree", title="#378 test")
    reg = {SID_A: {**entry(), "alive": True}}
    html = sd.render_html(sd.build_rows(reg, [sess], term_program=lambda pid: "", ctx=ctx), "2026-10-24 10:00")
    assert "/tree/main/docs/specs/active/ai-harness" in html or "/tree/main/docs/specs" in html
    assert "/issues/378" in html
    assert "label%3Aspec%3Aai-harness" in html or "label:spec:ai-harness" in html
    assert "AI工具鏈" in html
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_issue_label_fetch_parses_gh_output_caches_and_survives_failures(tmp_path):
    calls = []

    def fake_gh():
        calls.append(1)
        return json.dumps([{"number": 1, "labels": [{"name": "a"}]}, {"number": 22, "labels": []}])

    cache = tmp_path / "labels.json"
    first = sd.fetch_issue_labels(fake_gh, cache, now=1000.0)
    assert first == {1: ["a"], 22: []}
    again = sd.fetch_issue_labels(fake_gh, cache, now=1100.0)  # within the TTL: served from the cache
    assert again == first and len(calls) == 1
    later = sd.fetch_issue_labels(fake_gh, cache, now=1000.0 + sd.LABEL_TTL + 1)
    assert later == first and len(calls) == 2

    def broken():
        raise OSError("no gh")

    assert sd.fetch_issue_labels(broken, tmp_path / "none.json", now=1.0) == {}
    assert sd.fetch_issue_labels(lambda: "not json", tmp_path / "none2.json", now=1.0) == {}
    # a stale cache is still better than nothing when gh fails
    assert sd.fetch_issue_labels(broken, cache, now=1000.0 + 10 * sd.LABEL_TTL) == first


def test_load_context_reads_spec_dirs_themes_and_overrides(tmp_path):
    (tmp_path / "docs/specs/active/alpha").mkdir(parents=True)
    (tmp_path / "docs/specs/parked").mkdir(parents=True)
    (tmp_path / "docs/specs/parked/beta-followups.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs/specs/board-themes.json").write_text(
        json.dumps({"specs": {"alpha": "主題A"}, "overrides": {"5": {"theme": "T", "reason": "r"}}}), encoding="utf-8"
    )
    ctx = sd.load_context(tmp_path, issue_labels={})
    assert ctx.specs == {"alpha", "beta-followups"}
    assert ctx.themes == {"alpha": "主題A"}
    assert ctx.overrides == {"5": "T"}
    assert sd.load_context(tmp_path / "missing", issue_labels={}).specs == set()


def test_spec_label_is_accepted_even_when_the_spec_directory_is_not_in_this_checkout():
    ctx = sd.Context(specs={"ai-harness"}, themes={"scraper-zero-output": "爬蟲管線"}, issue_labels={378: ["spec:scraper-zero-output"]})
    row = _row({"name": "#378 x"}, _session(SID_A, ROOT_DIR, branch="main"), ctx=ctx)
    assert (row.spec, row.spec_source) == ("scraper-zero-output", "issue #378")
    assert row.theme == "爬蟲管線"


def test_all_distinct_spec_labels_are_listed_when_issues_disagree():
    ctx = sd.Context(
        specs={"a", "b"},
        themes={"a": "主題A", "b": "主題B"},
        issue_labels={369: ["spec:a", "spec:b"], 371: ["spec:b", "bug"]},
    )
    row = _row({"name": "#369.371 x"}, _session(SID_A, ROOT_DIR, branch="main"), ctx=ctx)
    assert row.spec == "a, b"
    assert row.theme == "主題A / 主題B"
    assert row.spec_source == "issue #369、#371"


def test_html_links_every_listed_spec():
    ctx = sd.Context(specs={"a", "b"}, issue_labels={369: ["spec:a", "spec:b"]})
    reg = {SID_A: {**entry(name="#369 x"), "alive": True}}
    html = sd.render_html(sd.build_rows(reg, [_session(SID_A, ROOT_DIR)], term_program=lambda pid: "", ctx=ctx), "t")
    assert "docs/specs/active/a" in html and "docs/specs/active/b" in html


# --- default order and click-to-sort -------------------------------------------------------------

SIDS = [f"{c}{c}{c}{c}{c}{c}{c}{c}-1111-2222-3333-444444444444" for c in "cdefgh"]


def _live(i, status, updated):
    return SIDS[i], {**entry(pid=100 + i, sessionId=SIDS[i], name=f"s{i}", status=status, updatedAt=updated), "alive": True}


def test_default_order_puts_sessions_that_need_attention_or_work_first():
    reg = dict(
        [
            _live(0, "idle", 1792800000000),
            _live(1, "busy", 1792700000000),
            _live(2, "waiting", 1792600000000),
            _live(3, "idle", 1792900000000),
            _live(4, "busy", 1792750000000),
        ]
    )
    rows = sd.build_rows(reg, [], term_program=lambda pid: "")
    assert [r.name for r in rows] == ["s2", "s4", "s1", "s3", "s0"]  # waiting, busy (newest first), idle (newest first)


def test_ended_sessions_come_last_in_the_default_order():
    reg = dict([_live(0, "idle", 1792800000000)])
    ended = _session(SIDS[5], ROOT_DIR, title="old", ts="2026-10-25T00:00:00Z")
    rows = sd.build_rows(reg, [ended], term_program=lambda pid: "", include_ended=True)
    assert [r.status for r in rows] == ["閒置", "已結束"]


def test_cells_carry_a_sort_key_and_headers_a_type():
    reg = dict([_live(0, "busy", 1792800000000), _live(1, "idle", 1792700000000)])
    html = sd.render_html(sd.build_rows(reg, [], term_program=lambda pid: ""), "t")
    assert 'data-type="pid"' in html and 'data-type="time"' in html and 'data-type="status"' in html
    assert '<td data-sort="100"' in html or 'data-sort="100"' in html
    assert "<script>" in html and "compareValues" in html
    # every body row has as many sort keys as there are columns
    header_cells = html.split("<thead>")[1].split("</thead>")[0].count("<th")
    first_row = html.split("<tbody>")[1].split("</tr>")[0]
    assert first_row.count("<td") == header_cells
    assert first_row.count("data-sort=") == header_cells


def test_sort_script_comparator_in_node():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node not available")
    script = sd.SORT_JS
    program = script + """
const eq = (a, b) => { if (JSON.stringify(a) !== JSON.stringify(b)) { console.log("FAIL", JSON.stringify(a), JSON.stringify(b)); process.exit(1); } };
eq(compareValues("9", "10", "pid"), -1);            // numbers, not strings
eq(compareValues("10", "9", "pid"), 1);
eq(compareValues("", "5", "pid") > 0, true);        // empty values go last when ascending
eq(compareValues("a", "B", "text") < 0, true);      // case-insensitive text
eq(compareValues("2", "10", "status"), -1);         // status uses its numeric rank
eq(compareValues("2026-10-24T01:00", "2026-10-23T23:00", "time") > 0, true);
eq(compareValues("x", "x", "text"), 0);
console.log("ok");
"""
    out = subprocess.run([node, "-e", program], capture_output=True, text=True, timeout=20, check=False)
    assert out.stdout.strip() == "ok", out.stdout + out.stderr


def test_sort_script_click_wiring_with_a_fake_dom():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node not available")
    program = (
        """
const store = {};
global.sessionStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } };
const mkRow = (name, pid) => ({ name, cells: [{ dataset: { sort: name } }, { dataset: { sort: String(pid) } }] });
const rows = [mkRow("b", 20), mkRow("a", 3), mkRow("c", ""), mkRow("d", 100)];
const body = { rows, tBodies: null, appendChild(r) { const i = this.rows.indexOf(r); if (i >= 0) this.rows.splice(i, 1); this.rows.push(r); } };
const listeners = [];
const mkHead = (type) => { const attrs = { "aria-sort": "none" }; return { dataset: { type }, getAttribute: (k) => attrs[k], setAttribute: (k, v) => { attrs[k] = v; }, addEventListener: (ev, fn) => listeners.push(fn) }; };
const heads = [mkHead("text"), mkHead("pid")];
global.document = { querySelector: () => ({ tHead: { rows: [{ cells: heads }] }, tBodies: [body] }) };
"""
        + sd.SORT_JS
        + """
const order = () => body.rows.map((r) => r.name).join("");
listeners[1]();                       // pid ascending, empty value last
if (order() !== "abdc") { console.log("FAIL asc", order()); process.exit(1); }
listeners[1]();                       // pid descending, empty value still last
if (order() !== "dbac") { console.log("FAIL desc", order()); process.exit(1); }
listeners[0]();                       // text ascending
if (order() !== "abcd") { console.log("FAIL text", order()); process.exit(1); }
if (heads[0].getAttribute("aria-sort") !== "ascending" || heads[1].getAttribute("aria-sort") !== "none") { console.log("FAIL aria"); process.exit(1); }
if (!store["session-dashboard-sort"]) { console.log("FAIL store"); process.exit(1); }
console.log("ok");
"""
    )
    out = subprocess.run([node, "-e", program], capture_output=True, text=True, timeout=20, check=False)
    assert out.stdout.strip() == "ok", out.stdout + out.stderr


def test_a_session_running_a_shell_command_counts_as_in_progress():
    reg = dict(
        [
            _live(0, "idle", 1792900000000),
            _live(1, "shell", 1792100000000),
            _live(2, "busy", 1792200000000),
        ]
    )
    rows = sd.build_rows(reg, [], term_program=lambda pid: "")
    assert [(r.name, r.status) for r in rows] == [("s2", "處理中"), ("s1", "執行指令"), ("s0", "閒置")]
    assert sd.STATUS_RANK["執行指令"] == sd.STATUS_RANK["處理中"]
    assert "st-執行指令 .dot" in sd.CSS


# --- /rename suggestion column ---------------------------------------------------------------------


def _unnamed(sess=None, ctx=CTX, **kw):
    return _row({"nameSource": "derived", "name": "tokyo-taiwan-radar-ab", **kw}, sess, ctx=ctx)


def test_suggestion_uses_spec_and_issue_numbers():
    sess = _session(SID_A, ROOT_DIR, branch="main", title="#369.371 修理規劃")
    ctx = sd.Context(specs={"source-health"}, issue_labels={369: ["spec:source-health"]})
    assert _unnamed(sess, ctx=ctx).rename == "/rename source-health·369-371"


def test_suggestion_falls_back_to_worktree_then_branch_then_root():
    wt = _session(SID_A, f"{ROOT_DIR}/ttr-japan-scope-gate-worktree", branch="feat/x", ai="修 RPC")
    assert _unnamed(wt, ctx=sd.Context()).rename == "/rename japan-scope-gate·修 RPC"
    br = _session(SID_A, ROOT_DIR, branch="fix/event-detail-404", ai="")
    assert _unnamed(br, ctx=sd.Context()).rename == "/rename event-detail-404·chat"
    rt = _session(SID_A, ROOT_DIR, branch="main", ai="分類標籤命名與精準度")
    assert _unnamed(rt, ctx=sd.Context()).rename == "/rename root·分類標籤命名與精準度"


def test_suggestion_is_at_most_24_code_points_and_single_line():
    sess = _session(SID_A, ROOT_DIR, branch="main", ai="很長很長的標題\n含有換行 和 / 斜線 " * 5)
    text = _unnamed(sess, ctx=sd.Context()).rename
    name = text.removeprefix("/rename ")
    assert len(name) <= 24 and "\n" not in name and "/" not in name


def test_named_sessions_keep_their_current_name_as_the_suggestion():
    row = _row({"nameSource": "user", "name": "my-name"}, _session(SID_A, ROOT_DIR, branch="main"))
    assert row.rename == "/rename my-name"


def test_ended_sessions_have_no_suggestion():
    ended = _session(SIDS[5], ROOT_DIR, title="old")
    rows = sd.build_rows({}, [ended], term_program=lambda pid: "", include_ended=True)
    assert rows[0].rename == ""


def test_html_has_an_editable_input_and_a_copy_button_with_escaping():
    reg = {SID_A: {**entry(nameSource="derived", name='x"><b>'), "alive": True}}
    sess = _session(SID_A, ROOT_DIR, branch="main", ai='a"b<i>')
    html = sd.render_html(sd.build_rows(reg, [sess], term_program=lambda pid: ""), "t")
    assert 'data-copy' in html and "<input" in html and "複製" in html
    assert "<b>" not in html.split("<tbody>")[1] and "<i>" not in html.split("<tbody>")[1]
    assert "copyText" in html


def test_copy_script_uses_the_clipboard_api_and_falls_back():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node not available")
    program = (
        """
let written = null;
const setNav = (v) => Object.defineProperty(globalThis, "navigator", { value: v, configurable: true, writable: true });
setNav({ clipboard: { writeText: (t) => { written = t; return Promise.resolve(); } } });
"""
        + sd.COPY_JS
        + """
copyText("/rename a").then((ok) => {
  if (!ok || written !== "/rename a") { console.log("FAIL api", ok, written); process.exit(1); }
  setNav({ clipboard: { writeText: () => Promise.reject(new Error("denied")) } });
  let selected = false;
  const fallback = { select() { selected = true; }, setSelectionRange() {} };
  global.document = { execCommand: (c) => c === "copy" };
  return copyText("/rename b", fallback).then((ok2) => {
    if (!ok2 || !selected) { console.log("FAIL fallback", ok2, selected); process.exit(1); }
    console.log("ok");
  });
});
"""
    )
    out = subprocess.run([node, "-e", program], capture_output=True, text=True, timeout=20, check=False)
    assert out.stdout.strip() == "ok", out.stdout + out.stderr


def test_auto_reload_skips_the_reload_while_an_input_has_focus():
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest

        pytest.skip("node not available")
    assert sd.reload_script(0) == ""
    program = (
        """
let tick = null, reloads = 0, interval = null;
global.setInterval = (fn, ms) => { tick = fn; interval = ms; };
global.document = { activeElement: { tagName: "BODY" } };
global.location = { reload: () => { reloads += 1; } };
"""
        + sd.reload_script(15)
        + """
tick();
document.activeElement = { tagName: "INPUT" };
tick();
document.activeElement = { tagName: "BODY" };
tick();
console.log(interval === 15000 && reloads === 2 ? "ok" : "FAIL " + interval + " " + reloads);
"""
    )
    out = subprocess.run([node, "-e", program], capture_output=True, text=True, timeout=20, check=False)
    assert out.stdout.strip() == "ok", out.stdout + out.stderr


def test_suggestion_drops_a_purpose_that_only_repeats_the_slug():
    sess = _session(SID_A, f"{ROOT_DIR}/ttr-japan-scope-gate-worktree", ai="japan-scope-gate RPC 103 與 CLI v2")
    assert _unnamed(sess, ctx=sd.Context()).rename == "/rename japan-scope-gate·RPC 103"


def test_suggestion_has_no_purpose_when_the_slug_leaves_no_room():
    sess = _session(SID_A, f"{ROOT_DIR}/ttr-ndl-relevance-publication-worktree", ai="NDL 相關性過濾")
    text = _unnamed(sess, ctx=sd.Context()).rename.removeprefix("/rename ")
    assert text == "ndl-relevance-publicatio"  # 24 code points, no dangling "·N"
    assert "·" not in text

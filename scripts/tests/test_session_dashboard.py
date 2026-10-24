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
    assert '<meta http-equiv="refresh" content="15">' in html
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
        ["--sessions-dir", str(sessions_dir), "--projects-dir", str(projects), "--out", str(out), "--no-ps"],
        alive=lambda pid: True,
    )
    assert code == 0
    assert "ai-harness·next" in out.read_text(encoding="utf-8")
    assert [p.name for p in out.parent.iterdir()] == ["sessions.html"]

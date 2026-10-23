import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import session_map  # noqa: E402


def _write(root: Path, sid: str, rows: list[dict]) -> Path:
    d = root / "-proj"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{sid}.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return p


def _user(text: str, ts: str, cwd: str = "/x/Tokyo Taiwan Radar", branch: str = "main") -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": text},
        "timestamp": ts,
        "cwd": cwd,
        "gitBranch": branch,
        "entrypoint": "cli",
    }


def test_custom_title_wins_and_last_cwd_is_used(tmp_path):
    p = _write(
        tmp_path,
        "aaaaaaaa-0000-0000-0000-000000000000",
        [
            {"type": "ai-title", "aiTitle": "自動標題"},
            _user("hi", "2026-10-23T01:00:00Z"),
            {"type": "custom-title", "customTitle": "ai-harness·handoff"},
            _user("again", "2026-10-23T02:00:00Z", cwd="/x/Tokyo Taiwan Radar/wt", branch="feat/y"),
        ],
    )
    s = session_map.parse_session(p)
    assert s.title == "ai-harness·handoff"
    assert (s.cwd, s.branch, s.last_ts) == ("/x/Tokyo Taiwan Radar/wt", "feat/y", "2026-10-23T02:00:00Z")


def test_ai_title_used_without_custom_title(tmp_path):
    p = _write(tmp_path, "bbbbbbbb-0", [{"type": "ai-title", "aiTitle": "自動標題"}])
    assert session_map.parse_session(p).title == "自動標題"


def test_parent_line_links_child_under_parent(tmp_path):
    _write(
        tmp_path,
        "11111111-aaaa",
        [{"type": "custom-title", "customTitle": "parent"}, _user("go", "2026-10-23T01:00:00Z")],
    )
    _write(
        tmp_path,
        "22222222-bbbb",
        [
            {"type": "custom-title", "customTitle": "child"},
            _user("父 session：parent (11111111)。做 X", "2026-10-23T02:00:00Z"),
        ],
    )
    roots = session_map.link(session_map.collect(tmp_path, days=3650, repo=""))
    assert [r.title for r in roots] == ["parent"]
    assert [c.title for c in roots[0].children] == ["child"]
    out = session_map.render(roots)
    assert "└─ child (22222222)" in out


def test_parent_only_read_from_first_user_message(tmp_path):
    p = _write(
        tmp_path,
        "33333333-c",
        [_user("hello", "2026-10-23T01:00:00Z"), _user("父 session：p (11111111)", "2026-10-23T02:00:00Z")],
    )
    assert session_map.parse_session(p).parent_sid == ""


def test_missing_parent_is_reported_as_root(tmp_path):
    _write(tmp_path, "44444444-d", [_user("父 session：gone (deadbeef)。x", "2026-10-23T01:00:00Z")])
    roots = session_map.link(session_map.collect(tmp_path, days=3650, repo=""))
    assert len(roots) == 1
    assert "不在清單內" in session_map.render(roots)


def test_repo_filter_and_bad_lines(tmp_path):
    p = _write(tmp_path, "55555555-e", [_user("hi", "2026-10-23T01:00:00Z", cwd="/other/place")])
    p.write_text(p.read_text() + "not json\n", encoding="utf-8")
    assert session_map.collect(tmp_path, days=3650, repo="Tokyo Taiwan Radar") == []
    assert len(session_map.collect(tmp_path, days=3650, repo="other")) == 1

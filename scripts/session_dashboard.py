#!/usr/bin/env python3
"""Write a local HTML table of all running Claude Code sessions (read-only; #426).

Sources, all local:
- ~/.claude/sessions/<pid>.json  Claude Code's own live registry: pid, session ID, name and where the
  name came from, status, entry point. Reading it does not start the background service, unlike
  `claude agents --json`.
- ~/.claude/projects/*/<id>.jsonl  transcripts (via session_map): the directory and branch the
  session is actually working in, the title/summary, and the ``父 session：…`` line.
- `ps eww -p <pid>` for CLI sessions only, to read TERM_PROGRAM (VS Code terminal or not).

Usage: python3 scripts/session_dashboard.py [--open] [--watch SECONDS] [--include-ended]
Output defaults to ~/.ai-notes/ttr/sessions.html (outside the repository: it contains local paths).
Never reads or prints message content other than the parent line session_map already parses.
Not available from local data: cloud sessions, and the difference between a VS Code side chat and
the main panel (same entry point and arguments).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_map  # noqa: E402

WORKTREE_RE = re.compile(r"^ttr-(?P<slug>.+)-worktree$")
ROOT_NAME = "Tokyo Taiwan Radar"
ROOT_LABEL = "root（主工作目錄）"
STATUS_LABEL = {"busy": "處理中", "idle": "閒置", "waiting": "等待輸入"}


def worktree_of(cwd: str) -> tuple[str, str]:
    """(label, absolute path of the worktree or working tree) for a working directory."""
    if not cwd:
        return "?", ""
    parts = Path(cwd).parts
    for i, part in enumerate(parts):
        m = WORKTREE_RE.match(part)
        if m:
            return m["slug"], str(Path(*parts[: i + 1]))
    for i, part in enumerate(parts):
        if part == ROOT_NAME:
            return ROOT_LABEL, str(Path(*parts[: i + 1]))
    return Path(cwd).name or "?", cwd


def location(entry: dict, term_program: str) -> str:
    kind = entry.get("kind", "interactive")
    if kind != "interactive":
        return f"背景（{kind}）"
    if entry.get("entrypoint") == "claude-vscode":
        return "VS Code 面板"
    known = {"vscode": "VS Code 終端機", "Apple_Terminal": "Terminal.app", "iTerm.app": "iTerm"}
    if term_program in known:
        return known[term_program]
    return f"終端機（{term_program}）" if term_program else "終端機（未知）"


def _ps_env(pid: int) -> str:
    out = subprocess.run(["ps", "eww", "-p", str(pid)], capture_output=True, text=True, timeout=3, check=False)
    return out.stdout


def term_program_of(pid: int, run: Callable[[int], str] = _ps_env) -> str:
    try:
        text = run(pid)
    except Exception:
        return ""
    m = re.search(r"(?:^|\s)TERM_PROGRAM=(\S+)", text)
    return m.group(1) if m else ""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def load_registry(directory: Path, alive: Callable[[int], bool] = _pid_alive) -> dict[str, dict]:
    registry: dict[str, dict] = {}
    if not directory.is_dir():
        return registry
    for path in directory.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or not data.get("sessionId"):
            continue
        pid = data.get("pid")
        data["alive"] = bool(isinstance(pid, int) and alive(pid))
        registry[str(data["sessionId"])] = data
    return registry


@dataclass
class Row:
    sid: str
    name: str
    unnamed: bool
    summary: str
    pid: int | None
    where: str
    worktree: str
    worktree_path: str
    branch: str
    status: str
    last_ts: str
    started: str
    parent_sid: str = ""
    parent_title: str = ""
    parent_listed: bool = False

    @property
    def short(self) -> str:
        return self.sid[:8]


def _ms_to_iso(ms: object) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def build_rows(
    registry: dict[str, dict],
    sessions: list[session_map.Session],
    term_program: Callable[[int], str],
    include_ended: bool = False,
) -> list[Row]:
    by_sid = {s.sid: s for s in sessions}
    rows: list[Row] = []

    def make(sid: str, entry: dict | None, sess: session_map.Session | None, live: bool) -> Row:
        cwd = (sess.cwd if sess and sess.cwd else "") or (entry or {}).get("cwd", "")
        label, wt_path = worktree_of(cwd)
        if entry:
            tp = term_program(entry["pid"]) if live and entry.get("kind") == "interactive" and entry.get("entrypoint") == "cli" else ""
            where = location(entry, tp)
        else:
            where = location({"kind": "interactive", "entrypoint": sess.entrypoint if sess else ""}, "")
        name = (entry or {}).get("name") or (sess.title if sess else "") or sid[:8]
        status = STATUS_LABEL.get((entry or {}).get("status", ""), (entry or {}).get("status", "")) if live else "已結束"
        last = (sess.last_ts if sess and sess.last_ts else "") or _ms_to_iso((entry or {}).get("updatedAt"))
        return Row(
            sid=sid,
            name=name,
            unnamed=bool(entry) and entry.get("nameSource") == "derived",
            summary=(sess.custom_title or sess.ai_title) if sess else "",
            pid=entry["pid"] if live and entry else None,
            where=where,
            worktree=label,
            worktree_path=wt_path,
            branch=(sess.branch if sess else ""),
            status=status,
            last_ts=last,
            started=_ms_to_iso((entry or {}).get("startedAt")),
            parent_sid=sess.parent_sid if sess else "",
            parent_title=sess.parent_title if sess else "",
        )

    seen: set[str] = set()
    for sid, entry in registry.items():
        live = bool(entry.get("alive"))
        if not live and not include_ended:
            continue
        rows.append(make(sid, entry, by_sid.get(sid), live))
        seen.add(sid)
    if include_ended:
        for sess in sessions:
            if sess.sid not in seen:
                rows.append(make(sess.sid, None, sess, False))
    shorts = {r.short for r in rows}
    for r in rows:
        r.parent_listed = bool(r.parent_sid) and r.parent_sid in shorts
    rows.sort(key=lambda r: r.last_ts, reverse=True)
    rows.sort(key=lambda r: (r.worktree != ROOT_LABEL, r.worktree))
    return rows


def _local(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M")
    except ValueError:
        return "?"


CSS = """
:root{color-scheme:light dark;--bg:#fff;--fg:#1d1d1f;--mut:#6b6b70;--line:#d8d8de;--head:#f3f3f6;--busy:#d97706;--idle:#16a34a;--wait:#dc2626;--end:#9ca3af;--link:#2563eb;--warn:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececf0;--mut:#9a9aa3;--line:#33333a;--head:#212125;--link:#7aa7ff;--warn:#fbbf24}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
h1{font-size:18px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 12px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:980px}
th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:var(--head);position:sticky;top:0}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;background:var(--end)}
.st-處理中 .dot{background:var(--busy)}.st-閒置 .dot{background:var(--idle)}.st-等待輸入 .dot{background:var(--wait)}
.mut{color:var(--mut)}.badge{font-size:11px;border:1px solid var(--warn);color:var(--warn);border-radius:8px;padding:0 6px;margin-left:6px}
a{color:var(--link)}tr:target{outline:2px solid var(--link)}.num{font-variant-numeric:tabular-nums}
"""


def render_html(rows: list[Row], generated_at: str, refresh: int = 0) -> str:
    e = html.escape
    meta = f'<meta http-equiv="refresh" content="{int(refresh)}">' if refresh else ""
    if not rows:
        body = '<p class="mut">沒有符合條件的 session。</p>'
    else:
        out = [
            '<div class="wrap"><table><thead><tr><th>狀態</th><th>名稱</th><th>標題 / 摘要</th><th>PID</th>'
            "<th>位置</th><th>工作樹</th><th>Branch</th><th>父 session</th><th>最後活動</th><th>開始</th></tr></thead><tbody>"
        ]
        for r in rows:
            wt = e(r.worktree)
            if r.worktree_path:
                href = "vscode://file" + urllib.parse.quote(r.worktree_path)
                wt = f'<a href="{e(href, quote=True)}" title="{e(r.worktree_path)}">{wt}</a>'
            if r.parent_sid and r.parent_listed:
                parent = f'<a href="#s-{e(r.parent_sid)}">↑ {e(r.parent_title or r.parent_sid)}</a>'
            elif r.parent_sid:
                parent = f'<span class="mut">{e(r.parent_title)} ({e(r.parent_sid)}) 不在清單</span>'
            else:
                parent = ""
            badge = '<span class="badge">未命名</span>' if r.unnamed else ""
            pid = "" if r.pid is None else str(r.pid)
            out.append(
                f'<tr id="s-{e(r.short)}" class="st-{e(r.status)}">'
                f'<td><span class="dot"></span>{e(r.status)}</td>'
                f"<td>{e(r.name)}{badge}<br><span class=\"mut\">{e(r.short)}</span></td>"
                f'<td class="mut">{e(r.summary)}</td><td class="num">{e(pid)}</td>'
                f"<td>{e(r.where)}</td><td>{wt}</td><td>{e(r.branch)}</td><td>{parent}</td>"
                f'<td class="num">{e(_local(r.last_ts))}</td><td class="num">{e(_local(r.started))}</td></tr>'
            )
        out.append("</tbody></table></div>")
        body = "".join(out)
    return (
        "<!doctype html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"{meta}<title>Session 一覽</title><style>{CSS}</style></head><body>"
        f'<h1>Session 一覽</h1><p class="sub">產生於 {e(generated_at)} · {len(rows)} 個 · '
        "雲端 session 與 VS Code side chat 的區別在本機資料中查不到</p>"
        f"{body}</body></html>"
    )


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main(argv: list[str] | None = None, alive: Callable[[int], bool] = _pid_alive) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sessions-dir", type=Path, default=Path.home() / ".claude" / "sessions")
    ap.add_argument("--projects-dir", type=Path, default=session_map.DEFAULT_ROOT)
    ap.add_argument("--out", type=Path, default=Path.home() / ".ai-notes" / "ttr" / "sessions.html")
    ap.add_argument("--days", type=float, default=3, help="只對照最近 N 天有活動的 transcript（預設 3）")
    ap.add_argument("--repo", default=ROOT_NAME, help="只列所在目錄含此字串的 session；空字串表示全部")
    ap.add_argument("--include-ended", action="store_true", help="也列出已結束的 session")
    ap.add_argument("--no-ps", action="store_true", help="不用 ps 查終端機種類")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS", help="每 N 秒重新產生一次")
    ap.add_argument("--open", action="store_true", help="產生後用預設瀏覽器開啟")
    args = ap.parse_args(argv)
    term = (lambda pid: "") if args.no_ps else term_program_of
    opened = False
    while True:
        registry = load_registry(args.sessions_dir, alive=alive)
        sessions = session_map.collect(args.projects_dir, args.days, "") if args.projects_dir.is_dir() else []
        known = {s.sid for s in sessions}
        for sid, entry in registry.items():
            if entry.get("alive") and sid not in known:
                for path in args.projects_dir.glob(f"*/{sid}.jsonl"):
                    sessions.append(session_map.parse_session(path))
                    break
        rows = build_rows(registry, sessions, term, include_ended=args.include_ended)
        if args.repo:
            rows = [r for r in rows if args.repo in r.worktree_path or args.repo in r.worktree]
        text = render_html(rows, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), refresh=args.watch)
        write_atomic(args.out, text)
        print(f"{args.out}  ({len(rows)} 個 session)")
        if args.open and not opened:
            subprocess.run(["open", str(args.out)], check=False)
            opened = True
        if not args.watch:
            return 0
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""List recent Claude Code sessions as a parent → child tree (read-only).

Reads ~/.claude/projects/*/<session-id>.jsonl and prints, per session: the visible
title (custom title from /rename or -n, else the auto title), the first 8 characters
of the session ID, the last working directory and branch, the entry point and the
last activity. A session whose first user message starts with
``父 session：<title> (<8 hex chars>)`` is drawn under that parent (see
.github/instructions/handoff.instructions.md §3).

Usage: python3 scripts/session_map.py [--days N] [--repo SUBSTRING] [--root DIR]
Writes nothing; never prints message content other than the parent line.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PARENT_RE = re.compile(r"^\s*父 session[：:]\s*(?P<title>.*?)\s*\((?P<sid>[0-9a-f]{8})\)")
DEFAULT_ROOT = Path.home() / ".claude" / "projects"


@dataclass
class Session:
    sid: str
    path: Path
    custom_title: str = ""
    ai_title: str = ""
    cwd: str = ""
    branch: str = ""
    entrypoint: str = ""
    last_ts: str = ""
    parent_sid: str = ""
    parent_title: str = ""
    children: list["Session"] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.custom_title or self.ai_title or "(無標題)"

    @property
    def short(self) -> str:
        return self.sid[:8]


def _first_text(message: object) -> str:
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return str(block.get("text", ""))
    return ""


def parse_session(path: Path) -> Session:
    s = Session(sid=path.stem, path=path)
    seen_first_user = False
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            t = d.get("type")
            if t == "custom-title":
                s.custom_title = d.get("customTitle") or s.custom_title
            elif t == "ai-title":
                s.ai_title = d.get("aiTitle") or s.ai_title
            if d.get("cwd"):
                s.cwd = d["cwd"]
            if d.get("gitBranch"):
                s.branch = d["gitBranch"]
            if d.get("entrypoint"):
                s.entrypoint = d["entrypoint"]
            if d.get("timestamp"):
                s.last_ts = d["timestamp"]
            if t == "user" and not seen_first_user and not d.get("isMeta"):
                text = _first_text(d.get("message"))
                if text.strip():
                    seen_first_user = True
                    m = PARENT_RE.match(text)
                    if m:
                        s.parent_sid, s.parent_title = m["sid"], m["title"]
    return s


def collect(root: Path, days: float, repo: str) -> list[Session]:
    cutoff = time.time() - days * 86400
    sessions = []
    for path in root.glob("*/*.jsonl"):
        if path.stat().st_mtime < cutoff:
            continue
        s = parse_session(path)
        if repo and repo not in (s.cwd or path.parent.name):
            continue
        sessions.append(s)
    return sessions


def link(sessions: list[Session]) -> list[Session]:
    """Attach children to parents; return the roots, newest first."""
    by_short = {s.short: s for s in sessions}
    roots = []
    for s in sessions:
        parent = by_short.get(s.parent_sid) if s.parent_sid else None
        if parent and parent is not s:
            parent.children.append(s)
        else:
            roots.append(s)
    key = lambda x: x.last_ts  # noqa: E731
    for s in sessions:
        s.children.sort(key=key)
    return sorted(roots, key=key, reverse=True)


def _where(s: Session) -> str:
    home = str(Path.home())
    cwd = s.cwd.replace(home, "~") if s.cwd else "?"
    return f"{cwd}  [{s.branch or '?'}]"


def _age(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "?"
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if secs >= size:
            return f"{int(secs // size)}{unit} 前"
    return "剛剛"


def render(roots: list[Session]) -> str:
    lines: list[str] = []

    def walk(s: Session, prefix: str, last: bool, top: bool) -> None:
        branch = "" if top else ("└─ " if last else "├─ ")
        orphan = ""
        if s.parent_sid and top:
            orphan = f"  （父 session {s.parent_title} ({s.parent_sid}) 不在清單內）"
        lines.append(
            f"{prefix}{branch}{s.title} ({s.short}) · {s.entrypoint or '?'} · {_age(s.last_ts)}{orphan}"
        )
        pad = prefix + ("" if top else ("   " if last else "│  "))
        lines.append(f"{pad}   {_where(s)}")
        for i, c in enumerate(s.children):
            walk(c, pad, i == len(s.children) - 1, False)

    for r in roots:
        walk(r, "", True, True)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--days", type=float, default=3, help="只列最近 N 天有活動的 session（預設 3）")
    ap.add_argument("--repo", default="Tokyo Taiwan Radar", help="只列所在目錄含此字串的 session")
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="session 紀錄根目錄")
    args = ap.parse_args(argv)
    if not args.root.is_dir():
        print(f"找不到 {args.root}", file=sys.stderr)
        return 1
    roots = link(collect(args.root, args.days, args.repo))
    print(render(roots) if roots else "沒有符合條件的 session")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

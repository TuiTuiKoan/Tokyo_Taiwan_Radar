#!/usr/bin/env python3
"""Validate a research-team run (state.json) and render its report page.

The research agents only write structured data. This script is the single
place that numbers footnotes, builds the bibliography, computes tournament
Elo and draws the issue map, so citation integrity does not depend on a
model keeping numbers straight.

Usage:
    python3 scripts/research/render_report.py validate <state.json>
    python3 scripts/research/render_report.py rank <state.json>
    python3 scripts/research/render_report.py render <state.json> -o <report.html>

Rules and schema: .github/skills/research-team/SKILL.md
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

VERIFICATION = {
    "verified": "已驗證",
    "partial": "部分支持",
    "unsupported": "查無支持",
    "contradicted": "與來源矛盾",
    "unchecked": "未查核",
}
HYPOTHESIS_STATUS = {
    "active": "存活",
    "refuted": "已否證",
    "merged": "已合併",
    "retired": "已淘汰",
}
SOURCE_TYPES = {
    "paper": "期刊論文",
    "preprint": "預印本",
    "report": "報告",
    "data": "資料集／統計",
    "book": "專書",
    "web": "網頁",
}
ELO_START = 1200.0
ELO_K = 32.0
CITE_RE = re.compile(r"\[\^([A-Za-z0-9_-]+)\]")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


# ---------------------------------------------------------------- validation


def _ids(items: object, kind: str, errors: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not isinstance(items, list):
        errors.append(f"`{kind}` 必須是陣列")
        return out
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            errors.append(f"`{kind}` 內有項目缺少 id")
            continue
        if item["id"] in out:
            errors.append(f"`{kind}` id 重複：{item['id']}")
        out[item["id"]] = item
    return out


def source_url(source: dict) -> str:
    url = str(source.get("url") or "").strip()
    if url:
        return url
    doi = str(source.get("doi") or "").strip()
    return f"https://doi.org/{doi}" if doi else ""


def body_citations(state: dict) -> list[str]:
    """Source ids cited in report text, in order of first appearance."""
    report = state.get("report") or {}
    texts = [str(report.get("summary") or "")]
    texts += [str(s.get("body") or "") for s in report.get("sections") or [] if isinstance(s, dict)]
    seen: list[str] = []
    for text in texts:
        for sid in CITE_RE.findall(text):
            if sid not in seen:
                seen.append(sid)
    return seen


def validate(state: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for key in ("slug", "title", "question"):
        if not str(state.get(key) or "").strip():
            errors.append(f"缺少必要欄位 `{key}`")

    issues = _ids(state.get("issues", []), "issues", errors)
    hyps = _ids(state.get("hypotheses", []), "hypotheses", errors)
    claims = _ids(state.get("claims", []), "claims", errors)
    sources = _ids(state.get("sources", []), "sources", errors)

    roots = [i for i in issues.values() if not i.get("parent")]
    if issues and len(roots) != 1:
        errors.append(f"議題樹必須恰有一個根議題（parent 為空），目前 {len(roots)} 個")
    for issue in issues.values():
        if not str(issue.get("title") or "").strip():
            errors.append(f"議題 {issue['id']} 缺少 title")
        seen = {issue["id"]}
        parent = issue.get("parent")
        while parent:
            if parent not in issues:
                errors.append(f"議題 {issue['id']} 的 parent `{parent}` 不存在")
                break
            if parent in seen:
                errors.append(f"議題 {issue['id']} 的 parent 鏈成環")
                break
            seen.add(parent)
            parent = issues[parent].get("parent")

    for src in sources.values():
        if not str(src.get("title") or "").strip():
            errors.append(f"來源 {src['id']} 缺少 title")
        url = source_url(src)
        if not url:
            errors.append(f"來源 {src['id']} 沒有 url 或 doi，無法產生超連結")
        elif not re.match(r"https?://", url):
            errors.append(f"來源 {src['id']} 的 url 不是 http(s)：{url}")
        if src.get("type") and src["type"] not in SOURCE_TYPES:
            errors.append(f"來源 {src['id']} 的 type `{src['type']}` 不在允許值內")

    for claim in claims.values():
        status = claim.get("verification", "unchecked")
        if status not in VERIFICATION:
            errors.append(f"主張 {claim['id']} 的 verification `{status}` 不在允許值內")
        refs = claim.get("sources") or []
        for sid in refs:
            if sid not in sources:
                errors.append(f"主張 {claim['id']} 引用不存在的來源 {sid}")
        known = [sources[s] for s in refs if s in sources]
        if status in ("verified", "partial", "contradicted") and not known:
            errors.append(f"主張 {claim['id']} 標為「{VERIFICATION.get(status, status)}」但沒有來源")
        if status == "verified":
            if not str(claim.get("quote") or "").strip():
                errors.append(f"主張 {claim['id']} 標為已驗證但沒有原文引句 quote")
            if known and not any(s.get("fetched") for s in known):
                errors.append(f"主張 {claim['id']} 標為已驗證，但沒有任何來源實際開啟過（fetched）")
        if status == "unchecked":
            warnings.append(f"主張 {claim['id']} 尚未查核")

    for hyp in hyps.values():
        if not str(hyp.get("statement") or "").strip():
            errors.append(f"假說 {hyp['id']} 缺少 statement")
        if hyp.get("issue") not in issues:
            errors.append(f"假說 {hyp['id']} 的 issue `{hyp.get('issue')}` 不存在")
        if hyp.get("status", "active") not in HYPOTHESIS_STATUS:
            errors.append(f"假說 {hyp['id']} 的 status `{hyp.get('status')}` 不在允許值內")
        for cid in hyp.get("claims") or []:
            if cid not in claims:
                errors.append(f"假說 {hyp['id']} 引用不存在的主張 {cid}")
        for pid in hyp.get("parents") or []:
            if pid not in hyps:
                errors.append(f"假說 {hyp['id']} 的 parents 含不存在的假說 {pid}")
        if hyp.get("status", "active") == "active" and not hyp.get("claims"):
            warnings.append(f"存活假說 {hyp['id']} 沒有任何可查核主張")

    matches = state.get("matches") or []
    if not isinstance(matches, list):
        errors.append("`matches` 必須是陣列")
        matches = []
    for n, match in enumerate(matches, 1):
        a, b, winner = match.get("a"), match.get("b"), match.get("winner")
        if a not in hyps or b not in hyps:
            errors.append(f"第 {n} 場對戰引用不存在的假說（{a} vs {b}）")
        if winner not in (a, b, "draw"):
            errors.append(f"第 {n} 場對戰的 winner 必須是 a、b 其中之一或 draw")

    report = state.get("report") or {}
    for n, section in enumerate(report.get("sections") or [], 1):
        if section.get("issue") and section["issue"] not in issues:
            errors.append(f"報告第 {n} 節對應的議題 {section['issue']} 不存在")
    cited = body_citations(state)
    for sid in cited:
        if sid not in sources:
            errors.append(f"報告內文引用不存在的來源 [^{sid}]")
        elif not sources[sid].get("fetched"):
            errors.append(f"報告內文引用的來源 {sid} 沒有實際開啟過（fetched 不是 true）")

    used = set(cited)
    for claim in claims.values():
        used.update(claim.get("sources") or [])
    for sid in sources:
        if sid not in used:
            warnings.append(f"來源 {sid} 沒有被任何主張或內文引用，不會列入書目")
    return errors, warnings


# ----------------------------------------------------------------------- elo


def elo_table(state: dict) -> dict[str, dict]:
    table = {
        h["id"]: {"elo": ELO_START, "win": 0, "loss": 0, "draw": 0}
        for h in state.get("hypotheses") or []
        if isinstance(h, dict) and h.get("id")
    }
    for match in state.get("matches") or []:
        a, b, winner = match.get("a"), match.get("b"), match.get("winner")
        if a not in table or b not in table or a == b:
            continue
        score_a = 0.5 if winner == "draw" else (1.0 if winner == a else 0.0)
        expect_a = 1.0 / (1.0 + 10 ** ((table[b]["elo"] - table[a]["elo"]) / 400.0))
        table[a]["elo"] += ELO_K * (score_a - expect_a)
        table[b]["elo"] += ELO_K * ((1.0 - score_a) - (1.0 - expect_a))
        if winner == "draw":
            table[a]["draw"] += 1
            table[b]["draw"] += 1
        else:
            loser = b if winner == a else a
            table[winner]["win"] += 1
            table[loser]["loss"] += 1
    return table


def ranking(state: dict) -> list[dict]:
    table = elo_table(state)
    order = {"active": 0, "merged": 1, "retired": 2, "refuted": 3}
    hyps = [h for h in state.get("hypotheses") or [] if h.get("id") in table]
    hyps.sort(key=lambda h: (order.get(h.get("status", "active"), 9), -table[h["id"]]["elo"], h["id"]))
    return [{**h, **table[h["id"]]} for h in hyps]


# ------------------------------------------------------------------ html bits


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def cite_text(source: dict) -> str:
    authors = source.get("authors") or []
    if isinstance(authors, str):
        authors = [authors]
    who = "、".join(str(a) for a in authors[:6]) + ("等" if len(authors) > 6 else "")
    year = source.get("year")
    head = f"{who}（{year}）" if who and year else (who or (f"（{year}）" if year else ""))
    parts = [p for p in (head, str(source.get("title") or "").strip(), str(source.get("venue") or "").strip()) if p]
    return "。".join(parts) + "。"


class Footnotes:
    """Numbers sources by first citation and remembers the first back-link."""

    def __init__(self, sources: dict[str, dict]):
        self.sources = sources
        self.order: list[str] = []
        self.uses: dict[str, int] = {}

    def ref(self, sid: str) -> str:
        if sid not in self.sources:
            return f"[^{esc(sid)}]"
        if sid not in self.order:
            self.order.append(sid)
        n = self.order.index(sid) + 1
        self.uses[sid] = self.uses.get(sid, 0) + 1
        anchor = f' id="fnref-{n}"' if self.uses[sid] == 1 else ""
        return f'<sup class="fn"><a href="#fn-{n}"{anchor} aria-label="腳註 {n}">{n}</a></sup>'

    def inline(self, text: str) -> str:
        out = esc(text)
        out = BOLD_RE.sub(r"<strong>\1</strong>", out)
        return CITE_RE.sub(lambda m: self.ref(m.group(1)), out)

    def block(self, text: str) -> str:
        chunks = []
        for para in re.split(r"\n\s*\n", str(text or "").strip()):
            lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
            if not lines:
                continue
            if all(ln.startswith("- ") for ln in lines):
                items = "".join(f"<li>{self.inline(ln[2:])}</li>" for ln in lines)
                chunks.append(f"<ul>{items}</ul>")
            else:
                chunks.append(f"<p>{self.inline(' '.join(lines))}</p>")
        return "\n".join(chunks)


# ----------------------------------------------------------------- issue map

NODE_W, NODE_H, COL_GAP, ROW_GAP = 216, 64, 56, 14


def _units(ch: str) -> int:
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def wrap(text: str, width: int = 30, lines: int = 2) -> list[str]:
    out, cur, used = [], "", 0
    for ch in " ".join(str(text or "").split()):
        u = _units(ch)
        if used + u > width:
            out.append(cur)
            cur, used = "", 0
            if len(out) == lines:
                break
        cur += ch
        used += u
    else:
        if cur:
            out.append(cur)
        return out
    out[-1] = out[-1][:-1].rstrip() + "…"
    return out


def issue_map(state: dict, table: dict[str, dict]) -> str:
    issues = {i["id"]: i for i in state.get("issues") or []}
    hyps = [h for h in state.get("hypotheses") or []]
    children: dict[str, list[tuple[str, str]]] = {}
    root = None
    for issue in issues.values():
        if issue.get("parent"):
            children.setdefault(issue["parent"], []).append(("issue", issue["id"]))
        else:
            root = issue["id"]
    for hyp in hyps:
        children.setdefault(hyp.get("issue"), []).append(("hyp", hyp["id"]))
    if root is None:
        return ""

    pos: dict[tuple[str, str], tuple[int, float]] = {}
    cursor = 0

    def place(node: tuple[str, str], depth: int) -> float:
        nonlocal cursor
        kids = children.get(node[1], []) if node[0] == "issue" else []
        if not kids:
            y = cursor * (NODE_H + ROW_GAP)
            cursor += 1
        else:
            ys = [place(kid, depth + 1) for kid in kids]
            y = (ys[0] + ys[-1]) / 2
        pos[node] = (depth, y)
        return y

    place(("issue", root), 0)
    max_depth = max(d for d, _ in pos.values())
    width = (max_depth + 1) * NODE_W + max_depth * COL_GAP + 48
    height = cursor * (NODE_H + ROW_GAP) - ROW_GAP + 8
    hyp_by_id = {h["id"]: h for h in hyps}

    def xy(node: tuple[str, str]) -> tuple[float, float]:
        depth, y = pos[node]
        return 4 + depth * (NODE_W + COL_GAP), 4 + y

    edges, nodes = [], []
    for node in pos:
        if node[0] != "issue":
            continue
        x, y = xy(node)
        for kid in children.get(node[1], []):
            kx, ky = xy(kid)
            x1, y1, x2, y2 = x + NODE_W, y + NODE_H / 2, kx, ky + NODE_H / 2
            mid = (x1 + x2) / 2
            edges.append(f'<path class="edge" d="M{x1:.0f},{y1:.0f} C{mid:.0f},{y1:.0f} {mid:.0f},{y2:.0f} {x2:.0f},{y2:.0f}"/>')
    for hyp in hyps:
        for pid in hyp.get("parents") or []:
            if ("hyp", pid) in pos and ("hyp", hyp["id"]) in pos:
                px, py = xy(("hyp", pid))
                cx, cy = xy(("hyp", hyp["id"]))
                x1, y1 = px + NODE_W, py + NODE_H / 2
                x2, y2 = cx + NODE_W, cy + NODE_H / 2
                bend = max(x1, x2) + 30
                edges.append(
                    f'<path class="edge lineage" d="M{x1:.0f},{y1:.0f} C{bend:.0f},{y1:.0f} {bend:.0f},{y2:.0f} {x2:.0f},{y2:.0f}"/>'
                )
    for node in pos:
        x, y = xy(node)
        if node[0] == "issue":
            item = issues[node[1]]
            cls, label, title, href = "n-issue", item["id"], item.get("title", ""), f"#issue-{item['id']}"
            if not item.get("parent"):
                cls += " n-root"
        else:
            item = hyp_by_id[node[1]]
            status = item.get("status", "active")
            cls = f"n-hyp s-{status}"
            label = f"{item['id']} · Elo {round(table[item['id']]['elo'])} · {HYPOTHESIS_STATUS.get(status, status)}"
            title, href = item.get("statement", ""), f"#hyp-{item['id']}"
        lines = wrap(title)
        text = "".join(
            f'<text class="n-title" x="{x + 12:.0f}" y="{y + 38 + n * 16:.0f}">{esc(line)}</text>' for n, line in enumerate(lines)
        )
        nodes.append(
            f'<a href="{esc(href)}"><g class="{cls}"><title>{esc(title)}</title>'
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{NODE_W}" height="{NODE_H}" rx="6"/>'
            f'<text class="n-label" x="{x + 12:.0f}" y="{y + 18:.0f}">{esc(label)}</text>{text}</g></a>'
        )
    return (
        f'<div class="map-scroll"><svg class="map" viewBox="0 0 {width:.0f} {height:.0f}" width="{width:.0f}" '
        f'height="{height:.0f}" role="img" aria-label="議題、子議題與假說的關係圖">'
        + "".join(edges)
        + "".join(nodes)
        + "</svg></div>"
    )


# -------------------------------------------------------------------- render

STYLE = """
/* layout: one reading column; the issue map and tables may scroll sideways on their own */
:root {
  --bg: #f5f7fa; --surface: #ffffff; --fg: #18212f; --muted: #566273; --line: #d5dbe4;
  --accent: #1b56b3; --accent-soft: #e4ecf9;
  --ok: #1d7a4d; --ok-soft: #e0f2e8; --warn: #96650a; --warn-soft: #fbefd3;
  --bad: #b3312b; --bad-soft: #fbe3e1; --idle: #566273; --idle-soft: #e9edf2;
  --font-body: "Inter", "Noto Sans TC", "PingFang TC", "Hiragino Sans", "Microsoft JhengHei", sans-serif;
  --font-head: "Space Grotesk", "Noto Sans TC", "PingFang TC", "Hiragino Sans", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #10151d; --surface: #18202b; --fg: #e6ebf2; --muted: #9aa7b8; --line: #2c3746;
  --accent: #7fb0ff; --accent-soft: #1c2c47;
  --ok: #6fd3a0; --ok-soft: #153526; --warn: #eebf5c; --warn-soft: #3a2e10;
  --bad: #ff8f88; --bad-soft: #43201e; --idle: #9aa7b8; --idle-soft: #232d3a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #10151d; --surface: #18202b; --fg: #e6ebf2; --muted: #9aa7b8; --line: #2c3746;
  --accent: #7fb0ff; --accent-soft: #1c2c47;
  --ok: #6fd3a0; --ok-soft: #153526; --warn: #eebf5c; --warn-soft: #3a2e10;
  --bad: #ff8f88; --bad-soft: #43201e; --idle: #9aa7b8; --idle-soft: #232d3a; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font-family: var(--font-body); font-size: 16px; line-height: 1.75;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 40px 72px; }
.page { max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 44px; }
.page > * { min-width: 0; }
h1, h2, h3 { font-family: var(--font-head); text-wrap: balance; line-height: 1.3; margin: 0; }
h1 { font-size: 2rem; letter-spacing: -0.01em; }
h2 { font-size: 1.3rem; padding-bottom: 8px; border-bottom: 1px solid var(--line); }
h3 { font-size: 1.05rem; }
p, ul { margin: 0; }
a { color: var(--accent); text-underline-offset: 3px; }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
section { display: flex; flex-direction: column; gap: 16px; }
.prose { display: flex; flex-direction: column; gap: 12px; max-width: 70ch; }
.prose ul { padding-left: 1.3em; display: flex; flex-direction: column; gap: 6px; }
.eyebrow { font-family: var(--font-mono); font-size: .75rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
header { display: flex; flex-direction: column; gap: 14px; }
.question { font-size: 1.1rem; color: var(--muted); max-width: 70ch; }
.facts { display: flex; flex-wrap: wrap; gap: 8px 24px; font-size: .88rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.facts b { color: var(--fg); font-family: var(--font-mono); font-weight: 500; }
.id { font-family: var(--font-mono); font-size: .8rem; color: var(--muted); white-space: nowrap; }
.pill { display: inline-block; font-size: .75rem; line-height: 1.5; padding: 1px 8px; border-radius: 999px; white-space: nowrap; background: var(--idle-soft); color: var(--idle); }
.pill.verified, .pill.active { background: var(--ok-soft); color: var(--ok); }
.pill.partial, .pill.merged { background: var(--warn-soft); color: var(--warn); }
.pill.contradicted, .pill.refuted, .pill.unsupported { background: var(--bad-soft); color: var(--bad); }
.scroll, .map-scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
.map-scroll { padding: 16px; }
.map .edge { fill: none; stroke: var(--line); stroke-width: 1.5; }
.map .edge.lineage { stroke: var(--accent); stroke-dasharray: 4 4; }
.map rect { fill: var(--surface); stroke: var(--line); stroke-width: 1.2; }
.map .n-issue rect { fill: var(--accent-soft); stroke: var(--accent); }
.map .n-root rect { stroke-width: 2.2; }
.map .s-active rect { stroke: var(--ok); }
.map .s-refuted rect { stroke: var(--bad); stroke-dasharray: 5 3; }
.map .s-merged rect, .map .s-retired rect { stroke: var(--idle); stroke-dasharray: 2 3; }
.map text { fill: var(--fg); font-family: var(--font-body); font-size: 12.5px; }
.map .n-label { fill: var(--muted); font-family: var(--font-mono); font-size: 10.5px; }
.map a { text-decoration: none; }
.map a:hover rect, .map a:focus rect { stroke-width: 2.4; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: .82rem; color: var(--muted); }
table { border-collapse: collapse; width: 100%; font-size: .9rem; }
th, td { text-align: left; vertical-align: top; padding: 10px 12px; border-bottom: 1px solid var(--line); }
th { font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); font-weight: 600; white-space: nowrap; }
tr:last-child td { border-bottom: 0; }
td.num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
td.wide { min-width: 260px; }
blockquote { margin: 6px 0 0; padding-left: 12px; border-left: 2px solid var(--line); color: var(--muted); font-size: .86rem; }
.hyp { display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
.hyp-head { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; }
.hyp p.note { color: var(--muted); font-size: .9rem; }
sup.fn { font-size: .72em; line-height: 0; margin-left: 1px; }
sup.fn a { text-decoration: none; font-family: var(--font-mono); padding: 0 2px; }
ol.notes, ul.biblio { margin: 0; padding-left: 1.6em; display: flex; flex-direction: column; gap: 10px; font-size: .9rem; overflow-wrap: anywhere; }
ul.biblio { list-style: none; padding-left: 0; }
ul.biblio li { padding-left: 1.6em; text-indent: -1.6em; }
:target { scroll-margin-top: 16px; background: var(--accent-soft); }
.empty { color: var(--muted); font-size: .9rem; }
footer { font-size: .8rem; color: var(--muted); border-top: 1px solid var(--line); padding-top: 16px; }
@media (max-width: 520px) { h1 { font-size: 1.55rem; } body { font-size: 15px; } }
"""

FONTS = (
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500'
    "&family=Inter:wght@400;600&family=Noto+Sans+TC:wght@400;600&family=Space+Grotesk:wght@500;600&display=swap\">"
)


def pill(kind: str, labels: dict[str, str]) -> str:
    return f'<span class="pill {esc(kind)}">{esc(labels.get(kind, kind))}</span>'


def source_link(source: dict, text: str = "") -> str:
    url = source_url(source)
    label = text or (f"doi:{source['doi']}" if source.get("doi") else url)
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def render(state: dict) -> str:
    sources = {s["id"]: s for s in state.get("sources") or []}
    claims = {c["id"]: c for c in state.get("claims") or []}
    issues = {i["id"]: i for i in state.get("issues") or []}
    table = elo_table(state)
    ranked = ranking(state)
    notes = Footnotes(sources)
    report = state.get("report") or {}
    out: list[str] = []

    checked = [c for c in claims.values() if c.get("verification", "unchecked") != "unchecked"]
    verified = [c for c in claims.values() if c.get("verification") == "verified"]
    primary = [s for s in sources.values() if s.get("primary")]
    facts = [
        ("迭代輪數", state.get("round", 0)),
        ("假說", len(ranked)),
        ("對戰", len(state.get("matches") or [])),
        ("主張已驗證", f"{len(verified)}/{len(claims)}"),
        ("來源", len(sources)),
        ("其中一手來源", len(primary)),
    ]
    out.append(
        "<header>"
        '<div class="eyebrow">研究助理團報告</div>'
        f"<h1>{esc(state.get('title'))}</h1>"
        f'<p class="question">{esc(state.get("question"))}</p>'
        '<div class="facts">' + "".join(f"<span>{esc(k)} <b>{esc(v)}</b></span>" for k, v in facts) + "</div>"
        "</header>"
    )

    summary = notes.block(report.get("summary", ""))
    if summary:
        out.append(f'<section id="summary"><h2>摘要</h2><div class="prose">{summary}</div></section>')

    out.append(
        '<section id="map"><h2>議題與假說關係圖</h2>'
        + issue_map(state, table)
        + '<div class="legend"><span>藍底：議題與子議題</span><span>綠框：存活假說</span>'
        "<span>紅虛線框：已否證</span><span>灰點線框：已合併或淘汰</span><span>藍虛線：由哪個假說演化而來</span></div></section>"
    )

    rows = []
    for n, hyp in enumerate(ranked, 1):
        mine = [claims[c] for c in hyp.get("claims") or [] if c in claims]
        ok = sum(1 for c in mine if c.get("verification") == "verified")
        rows.append(
            f'<tr><td class="num">{n}</td><td class="num"><a href="#hyp-{esc(hyp["id"])}">{esc(hyp["id"])}</a></td>'
            f'<td class="wide">{esc(hyp.get("statement"))}</td><td class="num">{round(hyp["elo"])}</td>'
            f'<td class="num">{hyp["win"]}–{hyp["loss"]}{"–" + str(hyp["draw"]) if hyp["draw"] else ""}</td>'
            f'<td class="num">{ok}/{len(mine)}</td><td>{pill(hyp.get("status", "active"), HYPOTHESIS_STATUS)}</td></tr>'
        )
    if rows:
        out.append(
            '<section id="ranking"><h2>假說排名</h2><div class="scroll"><table><thead><tr><th>#</th><th>編號</th><th>假說</th>'
            "<th>Elo</th><th>勝–負</th><th>已驗證主張</th><th>狀態</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div></section>"
        )

    def claim_rows(hyp: dict) -> str:
        cells = []
        for cid in hyp.get("claims") or []:
            claim = claims.get(cid)
            if not claim:
                continue
            links = "、".join(
                f'<a href="#src-{esc(s)}">{esc(s)}</a>' for s in claim.get("sources") or [] if s in sources
            )
            quote = f"<blockquote>「{esc(claim['quote'])}」</blockquote>" if claim.get("quote") else ""
            note = f'<blockquote>{esc(claim["note"])}</blockquote>' if claim.get("note") else ""
            cells.append(
                f'<tr id="claim-{esc(cid)}"><td class="num">{esc(cid)}</td><td class="wide">{esc(claim.get("text"))}{quote}{note}</td>'
                f"<td>{pill(claim.get('verification', 'unchecked'), VERIFICATION)}</td><td>{links or '—'}</td></tr>"
            )
        if not cells:
            return '<p class="empty">這個假說還沒有可查核的主張。</p>'
        return (
            '<div class="scroll"><table><thead><tr><th>主張</th><th>內容與原文引句</th><th>查核結果</th><th>來源</th></tr></thead>'
            "<tbody>" + "".join(cells) + "</tbody></table></div>"
        )

    def hyp_card(hyp: dict) -> str:
        lineage = ""
        if hyp.get("parents"):
            links = "、".join(f'<a href="#hyp-{esc(p)}">{esc(p)}</a>' for p in hyp["parents"])
            lineage = f'<span class="id">演化自 {links}</span>'
        extra = "".join(
            f'<p class="note">{esc(label)}：{esc(hyp[key])}</p>'
            for key, label in (("rationale", "依據"), ("verdict", "評審結論"))
            if hyp.get(key)
        )
        return (
            f'<div class="hyp" id="hyp-{esc(hyp["id"])}"><div class="hyp-head"><span class="id">{esc(hyp["id"])}</span>'
            f'{pill(hyp.get("status", "active"), HYPOTHESIS_STATUS)}<span class="id">Elo {round(hyp["elo"])}</span>{lineage}</div>'
            f"<h3>{esc(hyp.get('statement'))}</h3>{extra}{claim_rows(hyp)}</div>"
        )

    sections = {s.get("issue"): s for s in report.get("sections") or [] if s.get("issue")}
    order: list[str] = []

    def walk(parent: object) -> None:
        for issue in issues.values():
            if (issue.get("parent") or None) == parent:
                order.append(issue["id"])
                walk(issue["id"])

    walk(None)
    for iid in order:
        issue, section = issues[iid], sections.get(iid, {})
        cards = "".join(hyp_card(h) for h in ranked if h.get("issue") == iid)
        body = notes.block(section.get("body", "")) or (f"<p>{esc(issue['summary'])}</p>" if issue.get("summary") else "")
        if not body and not cards:
            continue
        out.append(
            f'<section id="issue-{esc(iid)}"><div class="eyebrow">{esc(iid)}</div>'
            f"<h2>{esc(section.get('heading') or issue.get('title'))}</h2>"
            + (f'<div class="prose">{body}</div>' if body else "")
            + cards
            + "</section>"
        )

    meta = state.get("meta_review") or {}
    blocks = []
    for key, label in (("patterns", "勝敗樣態"), ("limitations", "限制"), ("next_steps", "下一步")):
        items = meta.get(key) or []
        if items:
            blocks.append(f"<h3>{label}</h3><ul>" + "".join(f"<li>{notes.inline(i)}</li>" for i in items) + "</ul>")
    if blocks:
        out.append('<section id="meta"><h2>總評（Meta-review）</h2><div class="prose">' + "".join(blocks) + "</div></section>")

    if notes.order:
        items = []
        for n, sid in enumerate(notes.order, 1):
            src = sources[sid]
            items.append(
                f'<li id="fn-{n}">{esc(cite_text(src))} {source_link(src, "開啟原文")} · '
                f'<a href="#src-{esc(sid)}">書目</a> · <a href="#fnref-{n}" aria-label="回到內文">↩</a></li>'
            )
        out.append('<section id="notes"><h2>腳註</h2><ol class="notes">' + "".join(items) + "</ol></section>")

    used = set(notes.order)
    for claim in claims.values():
        used.update(s for s in claim.get("sources") or [] if s in sources)
    biblio = sorted((sources[s] for s in used), key=lambda s: (cite_text(s).casefold(), s["id"]))
    if biblio:
        items = []
        for src in biblio:
            tags = [f'<span class="id">{esc(src["id"])}</span>']
            if src.get("type"):
                tags.append(f'<span class="pill">{esc(SOURCE_TYPES.get(src["type"], src["type"]))}</span>')
            tags.append('<span class="pill verified">一手來源</span>' if src.get("primary") else '<span class="pill">二手來源</span>')
            if not src.get("fetched"):
                tags.append('<span class="pill partial">未能開啟全文</span>')
            accessed = f"（查閱日 {esc(src['accessed'])}）" if src.get("accessed") else ""
            items.append(f'<li id="src-{esc(src["id"])}">{esc(cite_text(src))} {source_link(src)}{accessed} {" ".join(tags)}</li>')
        out.append('<section id="bibliography"><h2>參考書目</h2><ul class="biblio">' + "".join(items) + "</ul></section>")

    out.append(
        f"<footer>由研究助理團產生；slug <span class=\"id\">{esc(state.get('slug'))}</span>，"
        f"更新於 {esc(state.get('updated') or state.get('created') or '')}。"
        "「已驗證」表示查核 agent 開啟過來源並摘錄了原文引句，不代表該研究本身的結論正確。</footer>"
    )
    title = " ".join(str(state.get("title") or "研究報告").split())
    return (
        f"<title>{esc(title)}</title>\n"
        '<meta name="claude:viewport-fit-sides" content="cover">\n'
        f"{FONTS}\n<style>{STYLE}</style>\n"
        '<div class="page">\n' + "\n".join(out) + "\n</div>\n"
    )


# ----------------------------------------------------------------------- cli


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("state.json 的最外層必須是物件")
    return data


def report_problems(errors: list[str], warnings: list[str]) -> None:
    for message in warnings:
        print(f"warning: {message}", file=sys.stderr)
    for message in errors:
        print(f"error: {message}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "rank", "render"):
        cmd = sub.add_parser(name)
        cmd.add_argument("state", type=Path)
        if name == "render":
            cmd.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args(argv)
    state = load(args.state)
    errors, warnings = validate(state)

    if args.command == "rank":
        report_problems(errors, [])
        for n, hyp in enumerate(ranking(state), 1):
            print(
                f"{n}\t{hyp['id']}\t{round(hyp['elo'])}\t{hyp['win']}-{hyp['loss']}-{hyp['draw']}\t"
                f"{hyp.get('status', 'active')}\t{hyp.get('statement', '')}"
            )
        return 1 if errors else 0

    report_problems(errors, warnings)
    if errors:
        print(f"{len(errors)} 個錯誤；未產生報告。", file=sys.stderr)
        return 1
    if args.command == "render":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render(state), encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(f"ok（{len(warnings)} 個警告）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

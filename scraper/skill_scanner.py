"""SKILL.md scanner — classifies rule candidates from agent SKILL.md files.

Outputs: stdout markdown report, LINE push (≤800 chars), docs/skill_scan/YYYY-MM.md.
Env: SKIP_LINE=1, SKIP_REPORT_WRITE=1, GITHUB_REPOSITORY (URL).
"""
from __future__ import annotations

import difflib
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("skill_scanner")

ROOT = Path(__file__).resolve().parent.parent
SKILLS_GLOB = ROOT / ".github" / "skills" / "agents"
SCRAPER_DIR = ROOT / "scraper"
REPORT_DIR = ROOT / "docs" / "skill_scan"

HOOK_RE = re.compile(r"def\s+(_check_\w+_(?:sync|guard))\s*\(")
_KNOWN_HOOK_FILES = {"secret_reminder.py", "monthly_health_check.py"}
_KNOWN_HOOK_FUNCS = {"_check_category_sync"}

KEYWORDS = {"i18n", "annotator", "FC", "merger", "migration", "scraper", "category",
            "event_form", "RLS", "GPT"}
HOOK_TRIGGERS = ("sync", "必須", "禁止", "四處", "五處", "同步點", "啟動時")
HUMAN_TRIGGERS = ("商業", "優先", "美感", "體驗")

MAX_PER_CATEGORY = 15
LINE_LIMIT = 800
DUP_RATIO = 0.50

HEADER_RE = re.compile(r"^(##+)\s+(.+?)\s*$", re.MULTILINE)
JST = timezone(timedelta(hours=9))


def discover_hooks() -> set[str]:
    found: set[str] = set(_KNOWN_HOOK_FUNCS)
    for py in SCRAPER_DIR.rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        found.update(m.group(1) for m in HOOK_RE.finditer(text))
    return found


def extract_sections(md: str) -> list[tuple[str, str]]:
    matches = list(HEADER_RE.finditer(md))
    out: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        out.append((m.group(2).strip(), md[m.end():end].strip()))
    return out


def matched_keywords(text: str) -> set[str]:
    low = text.lower()
    return {k for k in KEYWORDS if k.lower() in low}


def classify(text: str, hooks: set[str], source_file: str) -> str:
    low = text.lower()
    if any(h in text for h in hooks):
        return "already_hooked"
    if source_file in _KNOWN_HOOK_FILES:
        return "already_hooked"
    if any(t in text or t in low for t in HOOK_TRIGGERS):
        return "hookable_candidate"
    if any(t in text for t in HUMAN_TRIGGERS):
        return "human_only"
    return "other"


def collect_candidates() -> list[dict]:
    hooks = discover_hooks()
    out: list[dict] = []
    # R2: glob "*/SKILL.md" 結構性排除 history.md（編年記錄，與規則手冊結構不同，
    # 混掃會把過去 bug fix 誤判為 hookable_candidate）。若改 glob 為 "*/*.md" 須同步補回手動排除。
    for skill_md in sorted(SKILLS_GLOB.glob("*/SKILL.md")):
        if skill_md.name != "SKILL.md":
            continue
        agent = skill_md.parent.name
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("read fail %s: %s", skill_md, e)
            continue
        mtime = skill_md.stat().st_mtime
        for header, body in extract_sections(text):
            if not body:
                continue
            full = f"{header}\n{body}"
            out.append({"agent": agent, "header": header, "body": body,
                        "keywords": matched_keywords(full),
                        "label": classify(full, hooks, skill_md.name),
                        "mtime": mtime})
    return out


def detect_duplicates(cands: list[dict]) -> None:
    n = len(cands)
    for i in range(n):
        a = cands[i]
        if a["label"] == "already_hooked":
            continue
        for j in range(i + 1, n):
            b = cands[j]
            if a["agent"] == b["agent"] or not (a["keywords"] & b["keywords"]):
                continue
            ratio = difflib.SequenceMatcher(None, a["body"][:400], b["body"][:400]).ratio()
            if ratio >= DUP_RATIO:
                a["label"] = b["label"] = "duplicate_candidate"
                a.setdefault("dup_with", set()).add(b["agent"])
                b.setdefault("dup_with", set()).add(a["agent"])


EMOJI = {"hookable_candidate": "⚠", "duplicate_candidate": "🔁",
         "already_hooked": "✓", "human_only": "💭"}


def render_report(cands: list[dict], agents: int, sections: int) -> str:
    by_label: dict[str, list[dict]] = {}
    for c in cands:
        by_label.setdefault(c["label"], []).append(c)
    today = datetime.now(JST).date().isoformat()
    lines = ["# 🔍 SKILL.md Scan Report", "", f"- Date (JST): {today}",
             f"- Agents scanned: {agents}", f"- Sections parsed: {sections}", ""]
    for label in ("hookable_candidate", "duplicate_candidate", "already_hooked", "human_only"):
        bucket = by_label.get(label, [])
        items = sorted(bucket, key=lambda c: -c["mtime"])[:MAX_PER_CATEGORY]
        lines.append(f"## {EMOJI[label]} {label} ({len(bucket)})")
        if not items:
            lines.extend(["", "_(none)_", ""])
            continue
        for c in items:
            kw = ", ".join(sorted(c["keywords"])) or "—"
            extra = f" · shared with: {', '.join(sorted(c['dup_with']))}" \
                if label == "duplicate_candidate" and c.get("dup_with") else ""
            lines.append(f"- **{c['agent']}** › {c['header']}  ")
            lines.append(f"  keywords: {kw}{extra}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_line_body(cands: list[dict], agents: int, sections: int) -> str:
    counts: dict[str, int] = {}
    for c in cands:
        counts[c["label"]] = counts.get(c["label"], 0) + 1
    today = datetime.now(JST).date().isoformat()
    repo = os.environ.get("GITHUB_REPOSITORY", "TuiTuiKoan/Tokyo_Taiwan_Radar")
    url = f"https://github.com/{repo}/blob/main/docs/skill_scan/{today[:7]}.md"
    body = (
        f"🔍 SKILL Scanner 月報 {today}\n"
        f"agents 掃描: {agents} 個 × {sections} sections\n"
        f"✓ already_hooked: {counts.get('already_hooked', 0)}\n"
        f"⚠ hookable_candidate: {counts.get('hookable_candidate', 0)}（建議優先處理）\n"
        f"🔁 duplicate_candidate: {counts.get('duplicate_candidate', 0)} 組\n"
        f"💭 human_only: {counts.get('human_only', 0)}\n"
        f"完整報告: {url}"
    )
    assert len(body) <= LINE_LIMIT, f"LINE body {len(body)} chars exceeds {LINE_LIMIT}"
    return body


def main() -> int:
    cands = collect_candidates()
    agents = len({c["agent"] for c in cands})
    sections = len(cands)
    detect_duplicates(cands)
    report = render_report(cands, agents, sections)
    line_body = build_line_body(cands, agents, sections)
    sys.stdout.write(report)
    sys.stdout.flush()
    if not os.environ.get("SKIP_REPORT_WRITE"):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        ym = datetime.now(JST).strftime("%Y-%m")
        (REPORT_DIR / f"{ym}.md").write_text(report, encoding="utf-8")
        logger.info("report written: %s/%s.md", REPORT_DIR, ym)
    if not os.environ.get("SKIP_LINE"):
        try:
            from line_notify import send_line_message
            send_line_message(line_body)
        except Exception as e:
            logger.warning("LINE push failed: %s", e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

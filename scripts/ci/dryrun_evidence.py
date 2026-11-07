#!/usr/bin/env python3
"""Before/after dry-run evidence for scraper source PRs (agent-autonomy Phase D1②).

Used by .github/workflows/pr-dryrun-evidence.yml. The workflow runs
`python main.py --dry-run --source <s>` on the PR's base and head commits
without any secrets, then calls this script to turn the raw output into one
PR comment. Everything in the dry-run output comes from external websites
and from the PR's own code, so it is treated as untrusted text: titles are
shortened, stripped of markdown and mention syntax, and the whole comment is
capped in size.

Usage:
    dryrun_evidence.py summarize --out OUT --err ERR --rc N --json-output F
    dryrun_evidence.py render --results-dir DIR --pr N --base SHA --head SHA
                              [--skipped TEXT] --output F
        DIR holds <source>.<base|head>.json files written by `summarize`.
    dryrun_evidence.py diagnose-section --source S --summary F --output F
        One per-source block for source-diagnose.yml's issue comment.

main.py catches every scraper exception, logs "<Class>: scraper failed: <exc>"
and still exits 0, so the exit code alone cannot tell a broken scraper from
a quiet one; `summarize` extracts that log line as `exception`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MARKER = "<!-- pr-dryrun-evidence -->"
MAX_COMMENT = 60_000
MAX_TITLES = 5
MAX_TITLE_LEN = 80
MAX_DATE_ROWS = 20  # events kept per run for the base/head start_date comparison
MAX_DATE_CHANGES = 5
ERR_TAIL_LINES = 30
ERR_LINE_LEN = 200
SOURCE_RE = re.compile(r"^[a-z0-9_]+$")
EXCEPTION_RE = re.compile(r"scraper failed: (.*)")


def parse_events(stdout: str) -> list[dict] | None:
    """The JSON array main.py --dry-run prints, or None when it cannot be found.

    main.py prints the array with indent=2, so it starts with "[" at the start
    of a line; log lines that contain "[" earlier are skipped by trying each
    line-start "[" in turn.
    """
    end = stdout.rfind("]")
    if end < 0:
        return None
    starts = [m.start() for m in re.finditer(r"(?m)^\[", stdout)]
    for start in starts:
        try:
            data = json.loads(stdout[start:end + 1])
        except ValueError:
            continue
        if isinstance(data, list):
            return data
    return None


def clean(text: object, limit: int = MAX_TITLE_LEN) -> str:
    """One line of untrusted text that cannot break out of a list item or ping anyone."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    s = re.sub(r"[`*_\[\]<>|#~\\]", "", s)
    s = s.replace("@", "@​")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def clean_code(text: object, limit: int = ERR_LINE_LEN) -> str:
    """One line of untrusted text for inside a fenced code block.

    Markdown is not rendered there, so underscores and brackets stay readable
    (log lines, source keys); only what could close the fence, open HTML or
    ping someone is neutralised.
    """
    s = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or "")).strip()
    s = re.sub(r"[`<>]", "", s).replace("@", "@\u200b")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def summarize(stdout: str, stderr: str, rc: int) -> dict:
    events = parse_events(stdout)
    titles: list[str] = []
    for e in (events or [])[:MAX_TITLES]:
        if isinstance(e, dict):
            titles.append(clean(e.get("name_ja") or e.get("raw_title") or ""))
    dates: list[dict] = []
    for e in (events or [])[:MAX_DATE_ROWS]:
        if not isinstance(e, dict):
            continue
        row = {
            "id": clean(e.get("source_id") or e.get("source_url") or "", 120),
            "title": clean(e.get("name_ja") or e.get("raw_title") or ""),
            "start": clean(str(e.get("start_date") or "")[:10], 10),
        }
        if row["id"] or row["title"]:
            dates.append(row)
    tail = [clean_code(line, ERR_LINE_LEN) for line in stderr.splitlines()[-ERR_TAIL_LINES:]]
    found = EXCEPTION_RE.findall(stderr)
    return {
        "rc": rc,
        "exception": clean(found[-1], 300) if found else None,
        "count": len(events) if events is not None else None,
        "titles": [t for t in titles if t],
        "dates": dates,
        "stderr_tail": [t for t in tail if t],
    }


def _count(s: dict | None) -> str:
    if not s:
        return "未執行"
    if s.get("rc") == 124:
        return "逾時"
    if s.get("exception"):
        return f"例外（exit {s.get('rc')}）"
    if s.get("count") is None:
        return f"無法解析（exit {s.get('rc')}）"
    return f"{s['count']} 筆（exit {s.get('rc')}）"


def _date_map(s: dict | None) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for r in (s or {}).get("dates") or []:
        if isinstance(r, dict) and r.get("id"):
            rows[clean(r["id"], 120)] = r
    return rows


def date_changes(base: dict | None, head: dict | None) -> tuple[list[tuple[str, str, str]], int]:
    """Events present in both runs (matched by source_id) whose start date differs.

    Returns (changes, number of events compared). The summaries come from jobs that ran
    untrusted code, so every value is cleaned again here.
    """
    b, h = _date_map(base), _date_map(head)
    shared = [k for k in h if k in b]
    changes: list[tuple[str, str, str]] = []
    for k in shared:
        before, after = clean(b[k].get("start"), 10), clean(h[k].get("start"), 10)
        if before != after:
            changes.append((clean(h[k].get("title")) or k, before or "（無）", after or "（無）"))
    return changes, len(shared)


def _date_change_lines(base: dict | None, head: dict | None) -> list[str]:
    changes, compared = date_changes(base, head)
    if not compared:
        return []
    head_note = f"前 {MAX_DATE_ROWS} 筆內比對 {compared} 筆"
    if not changes:
        return [f"- 開始日變化：無（{head_note}）"]
    out = [f"- 開始日變化（修復前 → 修復後，{head_note}）："]
    out += [f"  - {t}：{b} → {a}" for t, b, a in changes[:MAX_DATE_CHANGES]]
    if len(changes) > MAX_DATE_CHANGES:
        out.append(f"  - …另有 {len(changes) - MAX_DATE_CHANGES} 筆")
    return out


def verdict(base: dict | None, head: dict | None) -> str:
    if head and head.get("exception"):
        return "⚠️ 修復後 scraper 拋出例外"
    if not head or head.get("count") is None or head.get("rc") not in (0, None):
        return "⚠️ 修復後 dry-run 失敗"
    b = (base or {}).get("count") if not (base or {}).get("exception") else None
    h = head["count"]
    if h == 0:
        return "⚠️ 修復後仍是 0 筆"
    if b is None:
        return "✅ 修復後有產出（修復前無法執行或拋出例外）"
    if b == 0:
        return "✅ 0 → 有產出"
    if h > b * 10:
        return "⚠️ 筆數暴增超過 10 倍，請檢查過濾條件"
    if h < b:
        return "⚠️ 筆數減少"
    # A fix for "production 0" whose base already scrapes fine here proves nothing
    # about production (prtimes, #538): say so instead of a green check.
    return "ℹ️ 修復前 dry-run 已有產出：無法以 dry-run 證明修好 production，合併後看下一次 Daily Scraper（#450）"


def render(results: dict[str, dict[str, dict]], pr: int, base_sha: str, head_sha: str,
           skipped: str = "") -> str:
    lines = [
        MARKER,
        f"## dry-run 證據（PR #{pr}）",
        f"base `{base_sha[:7]}` → head `{head_sha[:7]}`。在 GitHub Actions 上執行 "
        "`python main.py --dry-run --source <s>`，不帶任何 secrets、不寫資料庫。"
        "標題來自外部網站，只當症狀參考。",
        "",
        "| 來源 | 修復前 | 修復後 | 判讀 |",
        "| --- | --- | --- | --- |",
    ]
    for source in sorted(results):
        sides = results[source]
        lines.append(f"| `{source}` | {_count(sides.get('base'))} | {_count(sides.get('head'))} | "
                     f"{verdict(sides.get('base'), sides.get('head'))} |")
    if not results:
        lines.append("| — | — | — | 沒有改到已註冊的來源 |")
    if skipped:
        lines += ["", f"未檢查：{clean(skipped, 300)}"]
    for source in sorted(results):
        head = results[source].get("head") or {}
        lines += ["", f"### `{source}`（修復後）", ""]
        lines += _detail_lines(head)
        lines += _date_change_lines(results[source].get("base"), head)
    lines += ["", "需要憑證的來源在這裡會失敗，屬 NOT TESTED，不代表修錯。"]
    body = "\n".join(lines) + "\n"
    if len(body) > MAX_COMMENT:
        body = body[: MAX_COMMENT - 40] + "\n\n（內容過長，已截斷）\n"
    return body


def _detail_lines(s: dict) -> list[str]:
    """Exception, titles and stderr tail of one run; re-cleaned because the summary may come
    from a job that ran untrusted code."""
    out = [f"- 例外：{clean(s['exception'], 300)}" if s.get("exception") else "- 例外：無"]
    titles = [clean(t) for t in s.get("titles", [])][:MAX_TITLES]
    rows = [r for r in (s.get("dates") or []) if isinstance(r, dict) and clean(r.get("title"))][:MAX_TITLES]
    if rows:
        items = []
        for r in rows:
            start = clean(r.get("start"), 10)
            items.append(f"  - {clean(r['title'])}" + (f"（開始 {start}）" if start else ""))
    else:
        items = [f"  - {t}" for t in titles if t]
    out += ["- 前幾筆標題："] + (items or ["  - （沒有）"])
    tail = [clean_code(t, ERR_LINE_LEN) for t in s.get("stderr_tail", [])][-ERR_TAIL_LINES:]
    if tail:
        out += ["", "<details><summary>stderr 末段</summary>", "", "```"] + tail + ["```", "</details>"]
    return out


def diagnose_section(source: str, s: dict) -> str:
    """One source block for source-diagnose.yml (marker and header are added by the workflow)."""
    lines = ["", f"### {source}", f"- exit code: {s.get('rc')}",
             f"- 筆數: {s['count'] if s.get('count') is not None else 'unparsed'}"]
    lines += _detail_lines(s)
    return "\n".join(lines) + "\n"


def _load_results(directory: Path) -> dict[str, dict[str, dict]]:
    results: dict[str, dict[str, dict]] = {}
    for f in sorted(directory.glob("*.json")):
        source, _, side = f.stem.rpartition(".")
        if not SOURCE_RE.match(source) or side not in ("base", "head"):
            continue
        results.setdefault(source, {})[side] = json.loads(f.read_text(encoding="utf-8"))
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summarize")
    s.add_argument("--out", type=Path, required=True)
    s.add_argument("--err", type=Path, required=True)
    s.add_argument("--rc", type=int, required=True)
    s.add_argument("--json-output", type=Path, required=True)
    r = sub.add_parser("render")
    r.add_argument("--results-dir", type=Path, required=True)
    r.add_argument("--pr", type=int, required=True)
    r.add_argument("--base", required=True)
    r.add_argument("--head", required=True)
    r.add_argument("--skipped", default="")
    r.add_argument("--output", type=Path, required=True)
    d = sub.add_parser("diagnose-section")
    d.add_argument("--source", required=True)
    d.add_argument("--summary", type=Path, required=True)
    d.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)

    if args.cmd == "summarize":
        out = args.out.read_text(encoding="utf-8", errors="replace") if args.out.exists() else ""
        err = args.err.read_text(encoding="utf-8", errors="replace") if args.err.exists() else ""
        args.json_output.write_text(json.dumps(summarize(out, err, args.rc), ensure_ascii=False),
                                    encoding="utf-8")
        return 0
    if args.cmd == "diagnose-section":
        if not SOURCE_RE.match(args.source):
            print("invalid source", file=sys.stderr)
            return 2
        s = json.loads(args.summary.read_text(encoding="utf-8"))
        with args.output.open("a", encoding="utf-8") as fh:
            fh.write(diagnose_section(args.source, s))
        return 0
    body = render(_load_results(args.results_dir), args.pr, args.base, args.head, args.skipped)
    args.output.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

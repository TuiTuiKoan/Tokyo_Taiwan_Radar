"""Find "0 產出" scraper issues whose symptom is gone.

Read-only against production: selects from ``scraper_runs`` only. The GitHub
side (listing issues, commenting, closing) is done by
``.github/workflows/zero-output-recovery.yml`` with ``gh``; this script only
decides. Spec: docs/specs/active/agent-autonomy/proposal.md §8 (D1③).

The decision reuses ``eval_scraper_quality.classify_output`` and
``source_expectations.json``, the same logic and data the weekly report uses
to put a source in "28 天以上 0，原因未知". An issue is closed only when the
report would no longer list the source as needing action:

    active          the source produced events in the last 7 days
    off_season      registered as seasonal and outside its months
    quiet_expected  registered as sporadic and still within max_quiet_days

``failing`` (the latest run failed), ``quiet``, ``quiet_too_long``,
``known_broken``, ``zero_unexplained`` and ``no_runs`` leave the issue open.

Input:  --issues  gh api issues JSON (number, title, state, labels, pull_request)
        --prs     gh api pulls JSON for open PRs (number, title, body); optional
Output: --output  JSON list of {"issue", "source", "status", "summary", "prs", "comment"}
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eval_scraper_quality import EXPECTATIONS_PATH, RUN_LOOKBACK_DAYS, STATUS_LABEL, classify_output

logger = logging.getLogger(__name__)

UTC = timezone.utc
MARKER = "<!-- zero-output-recovery -->"
CLOSE_REASONS = {
    "active": "最近 7 天在 production 有產出，症狀已消失",
    "off_season": "已在 `scraper/source_expectations.json` 登記為季節性來源，目前是季節外",
    "quiet_expected": "已在 `scraper/source_expectations.json` 登記為零星來源，安靜仍在預期內",
}

# Titles are written by the heartbeat: "<source_name>：<症狀>" (full-width colon).
_TITLE_RE = re.compile(r"^([a-z0-9_]+)：")
_ZERO_OUTPUT_MARKERS = ("0 產出",)


def parse_source(title: str) -> str | None:
    """Source key of a zero-output issue title, or None if the title is not one."""
    if not isinstance(title, str):
        return None
    m = _TITLE_RE.match(title)
    if not m or not any(marker in title for marker in _ZERO_OUTPUT_MARKERS):
        return None
    return m.group(1)


def candidate_issues(issues: list[dict]) -> dict[int, str]:
    """Map issue number -> source for open zero-output scraper issues.

    Pull requests (the issues API returns them too) and issues without the
    ``scraper`` label are skipped. Labels can only be set by collaborators and
    the heartbeat, so an outsider's issue titled like one is never touched.
    """
    out: dict[int, str] = {}
    for issue in issues:
        if issue.get("pull_request"):  # PRs carry an object; plain issues None or absent
            continue
        if issue.get("state", "open") != "open":
            continue
        labels = {lbl.get("name") for lbl in issue.get("labels", []) if isinstance(lbl, dict)}
        if "scraper" not in labels:
            continue
        source = parse_source(issue.get("title", ""))
        number = issue.get("number")
        if source and isinstance(number, int):
            out[number] = source
    return out


def referencing_prs(prs: list[dict], issue: int) -> list[int]:
    """Open PRs whose body or title mentions #<issue> (they lose their target when it closes)."""
    pat = re.compile(rf"#{issue}(?!\d)")
    hits = []
    for pr in prs:
        text = f"{pr.get('title') or ''}\n{pr.get('body') or ''}"
        if isinstance(pr.get("number"), int) and pat.search(text):
            hits.append(pr["number"])
    return sorted(hits)


def comment_body(action: dict) -> str:
    """Closing comment; only numbers, the source key and repo-controlled text."""
    s = action["summary"]
    lines = [
        MARKER,
        f"`{action['source']}`：{CLOSE_REASONS[action['status']]}。",
        "判定與每週報表相同（`eval_scraper_quality.classify_output` ＋ `source_expectations.json`），"
        f"報表狀態：{STATUS_LABEL[action['status']]}。由 zero-output-recovery 自動關閉。",
        "",
        "| 7 天執行 | 7 天產出 | 28 天產出 | 最後有產出 |",
        "| --- | --- | --- | --- |",
        f"| {int(s['runs_7d'])} | {int(s['events_7d'])} | {int(s['events_28d'])} | {s['last_nonzero'] or '—'} |",
    ]
    if s.get("note") and action["status"] != "active":
        lines += ["", f"expectations 註記：{s['note']}"]
    if action["prs"]:
        refs = "、".join(f"#{n}" for n in action["prs"])
        lines += ["", f"仍指向這張 issue 的 open PR：{refs}。請在週審時決定合併或關閉。"]
    lines += ["", "若其實還有問題，重新打開這張 issue 並留言說明即可；本 job 不會再關同一張 issue 第二次。"]
    return "\n".join(lines) + "\n"


def decide(issues: dict[int, str], runs_by_source: dict[str, list[dict]],
           expectations: dict[str, dict], now: datetime, prs: list[dict] | None = None) -> list[dict]:
    """Issues to close, ordered by issue number."""
    actions = []
    for number in sorted(issues):
        source = issues[number]
        summary = classify_output(runs_by_source.get(source, []), expectations.get(source), now)
        if summary["status"] not in CLOSE_REASONS:
            continue
        action = {"issue": number, "source": source, "status": summary["status"],
                  "summary": summary, "prs": referencing_prs(prs or [], number)}
        action["comment"] = comment_body(action)
        actions.append(action)
    return actions


def fetch_runs(sb, sources: list[str], now: datetime) -> dict[str, list[dict]]:  # pragma: no cover - network
    since = (now - timedelta(days=RUN_LOOKBACK_DAYS)).isoformat()
    runs_by_source: dict[str, list[dict]] = {s: [] for s in sources}
    if not sources:
        return runs_by_source
    page, start = 1000, 0
    while True:
        batch = (sb.table("scraper_runs")
                 .select("source,ran_at,events_processed,success")
                 .gte("ran_at", since).in_("source", sources).order("ran_at")
                 .range(start, start + page - 1).execute().data) or []
        for r in batch:
            runs_by_source.setdefault(r.get("source"), []).append(r)
        if len(batch) < page:
            return runs_by_source
        start += page


def main() -> int:  # pragma: no cover - needs credentials
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--issues", type=Path, required=True)
    ap.add_argument("--prs", type=Path, default=None)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    issues = candidate_issues(json.loads(args.issues.read_text(encoding="utf-8")))
    prs = json.loads(args.prs.read_text(encoding="utf-8")) if args.prs else []
    expectations = json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))["sources"]
    now = datetime.now(tz=UTC)
    from database import _get_client  # noqa: PLC0415 — needs credentials, keep tests import-free

    runs = fetch_runs(_get_client(), sorted(set(issues.values())), now)
    actions = decide(issues, runs, expectations, now, prs)
    args.output.write_text(json.dumps(actions, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    logger.info("zero-output issues: %d, to close: %d", len(issues), len(actions))
    return 0


if __name__ == "__main__":
    sys.exit(main())

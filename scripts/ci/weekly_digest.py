#!/usr/bin/env python3
"""Weekly review digest for the user's one review morning (agent-autonomy #559, proposal §8 D4).

Collects everything that waits for the user and renders one issue, in the
order the user should work through it:

  1. 稽核區      what was merged or auto-closed this week (glance only)
  2. 一鍵合併區  tier 1 PRs: gitleaks, conflicts, dry-run evidence verdict
  3. 判斷區      tier 2 PRs, PRs without a tier, needs-human issues, ready-to-close parents
  4. 回收區      PRs open over 14 days, duplicate "Closes #n", PRs whose issue is closed

Read-only: it never merges, closes or labels anything. Evidence comes only
from comments written by github-actions[bot] (anyone can comment on this
public repo). Titles are cleaned like other untrusted text.

Usage:
    weekly_digest.py --repo OWNER/REPO --output body.md --title-file title.txt
    weekly_digest.py --data data.json --output body.md --title-file title.txt   # offline
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dryrun_evidence import clean_code  # noqa: E402

UTC = timezone.utc
JST = timezone(timedelta(hours=9))
BOT = "github-actions[bot]"
EVIDENCE = "<!-- pr-dryrun-evidence -->"
RECOVERY = "<!-- zero-output-recovery -->"
STALE_DAYS = 14
MAX_LIST = 15
CLOSES_RE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)", re.IGNORECASE)
VERDICT_RE = re.compile(r"^\| `[a-z0-9_]+` \|.*\| ([^|]+) \|$", re.MULTILINE)


# ─── Pure logic ───────────────────────────────────────────────────────────────

def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _days(value: str | None, now: datetime) -> int:
    ts = _ts(value)
    return (now - ts).days if ts else 0


def _labels(item: dict) -> set[str]:
    return {lbl.get("name") for lbl in item.get("labels") or [] if isinstance(lbl, dict)}


def _title(text: object) -> str:
    return re.sub(r"[|*\[\]~]", "", clean_code(text, 70))


def tier(pr: dict) -> str | None:
    for name in sorted(_labels(pr)):
        if name.startswith("tier:"):
            return name.split(":", 1)[1]
    return None


def closes(pr: dict) -> list[int]:
    return sorted({int(n) for n in CLOSES_RE.findall(pr.get("body") or "")})


def verdicts(comments: list[dict]) -> list[str]:
    """Verdict cells of the latest bot dry-run evidence comment."""
    bot = [c for c in comments if (c.get("user") or {}).get("login") == BOT
           and (c.get("body") or "").startswith(EVIDENCE)]
    if not bot:
        return []
    return [clean_code(v.strip(), 80) for v in VERDICT_RE.findall(bot[-1]["body"])]


def iso_week(now: datetime) -> str:
    y, w, _ = now.astimezone(JST).isocalendar()
    return f"{y}-W{w:02d}"


def _pr_line(pr: dict, now: datetime) -> str:
    bits = [f"#{pr['number']} {_title(pr.get('title'))}", f"{_days(pr.get('created_at'), now)} 天"]
    if pr.get("mergeable_state") == "dirty":
        bits.append("⚠️ 與 main 衝突")
    gl = pr.get("gitleaks")
    if gl and gl != "success":
        bits.append(f"⚠️ gitleaks {gl}")
    if pr.get("verdicts"):
        bits.append("dry-run：" + "；".join(pr["verdicts"]))
    if pr.get("draft"):
        bits.append("draft")
    return "- " + "｜".join(bits)


def _cap(lines: list[str], what: str) -> list[str]:
    if len(lines) <= MAX_LIST:
        return lines
    return lines[:MAX_LIST] + [f"- …其餘 {len(lines) - MAX_LIST} {what}"]


def build(data: dict, now: datetime) -> tuple[str, str]:
    """Return (title, markdown body)."""
    prs = data.get("open_prs", [])
    issue_state = data.get("issue_state", {})  # "n" -> "open"/"closed" for Closes targets
    week = iso_week(now)
    title = f"週審 digest：{week}（{now.astimezone(JST):%m/%d}）"

    tier1 = [p for p in prs if tier(p) == "1"]
    tier2 = [p for p in prs if tier(p) == "2"]
    untiered = [p for p in prs if tier(p) is None]
    stale = [p for p in prs if _days(p.get("created_at"), now) > STALE_DAYS]
    by_target: dict[int, list[int]] = {}
    for p in prs:
        for n in closes(p):
            by_target.setdefault(n, []).append(p["number"])
    dupes = {n: sorted(v) for n, v in by_target.items() if len(v) > 1}
    orphans = [p for p in prs if closes(p) and all(issue_state.get(str(n)) == "closed" for n in closes(p))]
    conflicts = [p for p in prs if p.get("mergeable_state") == "dirty"]
    needs_human = sorted(data.get("needs_human", []), key=lambda i: i.get("created_at") or "")
    ready = data.get("ready_to_close", [])
    merged = data.get("merged", [])
    recovered = data.get("auto_closed", [])

    out = [
        f"# {title}",
        "",
        f"待審 PR {len(prs)} 張（tier 1：{len(tier1)}、tier 2：{len(tier2)}、未分層：{len(untiered)}）；"
        f"needs-human issue {len(needs_human)} 張；可關閉的母 issue {len(ready)} 張。",
        "由上往下處理：1 掃一眼 → 2 一鍵合併 → 3 需要判斷 → 4 回收。本 issue 只整理，不會合併、關閉或貼 label。",
        "",
        "## 1. 稽核區（本週已處理，掃一眼）",
        "",
    ]
    if merged:
        out.append(f"本週合併 {len(merged)} 張 PR：")
        out += _cap([f"- #{p['number']} {_title(p.get('title'))}（tier {tier(p) or '?'}"
                     f"{'，自動合併' if tier(p) == '0' else ''}）" for p in merged], "張")
    else:
        out.append("本週沒有合併的 PR。")
    out.append("")
    if recovered:
        out.append(f"zero-output-recovery 本週依資料自動關閉 {len(recovered)} 張 issue（有問題就重開）：")
        out += _cap([f"- #{i['number']} {_title(i.get('title'))}" for i in recovered], "張")
    else:
        out.append("本週沒有自動關閉的 0 產出 issue。")

    out += ["", "## 2. 一鍵合併區（tier 1：只改單一爬蟲來源）", ""]
    out += _cap([_pr_line(p, now) for p in sorted(tier1, key=lambda p: p["number"])], "張") or ["（沒有）"]
    out += ["", "沒有 ⚠️ 的就可以直接按合併；dry-run 判讀看不懂就跳過，留到下週。"]

    out += ["", "## 3. 判斷區（需要你看內容或做決定）", "", "**tier 2 PR**（看 PR 說明的「要看什麼」）："]
    out += _cap([_pr_line(p, now) for p in sorted(tier2, key=lambda p: p["number"])], "張") or ["（沒有）"]
    if untiered:
        out += ["", "**還沒有 tier label 的 PR**（gitleaks 未跑完或失敗）："]
        out += _cap([_pr_line(p, now) for p in untiered], "張")
    if ready:
        out += ["", "**可以關閉的母 issue**（子 issue 與內文列的來源都已有結論）："]
        out += [f"- #{i['number']} {_title(i.get('title'))}" for i in ready]
    out += ["", f"**needs-human issue**（由舊到新，{len(needs_human)} 張）："]
    out += _cap([f"- #{i['number']} {_title(i.get('title'))}｜{_days(i.get('created_at'), now)} 天"
                 for i in needs_human], "張") or ["（沒有）"]

    out += ["", "## 4. 回收區（建議關閉或重開）", ""]
    recycle = []
    for p in stale:
        recycle.append(f"- #{p['number']} {_title(p.get('title'))}｜開了 {_days(p.get('created_at'), now)} 天，建議關閉或請 agent 重開")
    for n, nums in sorted(dupes.items()):
        keep, *rest = sorted(nums, reverse=True)
        recycle.append(f"- #{n} 有 {len(nums)} 張 PR 同時要關閉它（{'、'.join(f'#{x}' for x in nums)}）：建議保留 #{keep}，關閉 {'、'.join(f'#{x}' for x in rest)}")
    for p in orphans:
        recycle.append(f"- #{p['number']} {_title(p.get('title'))}｜要關閉的 issue 已經關了，建議關閉這張 PR")
    for p in conflicts:
        if p not in stale:
            recycle.append(f"- #{p['number']} {_title(p.get('title'))}｜與 main 衝突，請 agent rebase 後重開")
    out += recycle or ["（沒有）"]
    out += ["", "---", f"_{now.astimezone(JST):%Y-%m-%d %H:%M} JST 由 weekly-digest workflow 產生；下一份產生時，這張會自動關閉。_"]
    return title, "\n".join(out) + "\n"


# ─── GitHub collection (Actions or a session with gh) ─────────────────────────

def _gh(path: str) -> object:  # pragma: no cover - network
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def _pages(path: str, stop=None) -> list[dict]:  # pragma: no cover - network
    """Manual paging: the Claude Code sandbox proxy rejects --paginate's repositories/{id} links."""
    sep = "&" if "?" in path else "?"
    items: list[dict] = []
    for page in range(1, 30):
        batch = _gh(f"{path}{sep}per_page=100&page={page}")
        items += batch
        if len(batch) < 100 or (stop and batch and stop(batch[-1])):
            break
    return items


def collect(repo: str, now: datetime) -> dict:  # pragma: no cover - network
    r = f"repos/{repo}"
    since = (now - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    open_prs = []
    for p in _pages(f"{r}/pulls?state=open"):
        full = _gh(f"{r}/pulls/{p['number']}")
        runs = _gh(f"{r}/commits/{p['head']['sha']}/check-runs").get("check_runs", [])
        gl = next((c.get("conclusion") or c.get("status") for c in runs if c.get("name") == "gitleaks"), None)
        comments = _pages(f"{r}/issues/{p['number']}/comments")
        open_prs.append({
            "number": p["number"], "title": p["title"], "labels": p["labels"], "body": p.get("body"),
            "created_at": p["created_at"], "draft": p.get("draft"),
            "mergeable_state": full.get("mergeable_state"), "gitleaks": gl, "verdicts": verdicts(comments),
        })
    targets = {n for p in open_prs for n in closes(p)}
    issue_state = {str(n): _gh(f"{r}/issues/{n}").get("state") for n in sorted(targets)}
    closed_prs = _pages(f"{r}/pulls?state=closed&sort=updated&direction=desc",
                        stop=lambda last: (last.get("updated_at") or "") < since)
    merged = [{"number": p["number"], "title": p["title"], "labels": p["labels"]}
              for p in closed_prs if (p.get("merged_at") or "") >= since]
    closed_issues = [i for i in _pages(f"{r}/issues?state=closed&since={since}&labels=scraper")
                     if not i.get("pull_request") and (i.get("closed_at") or "") >= since]
    auto_closed = []
    for i in closed_issues:
        cs = _pages(f"{r}/issues/{i['number']}/comments")
        if any((c.get("user") or {}).get("login") == BOT and (c.get("body") or "").startswith(RECOVERY) for c in cs):
            auto_closed.append({"number": i["number"], "title": i["title"]})
    needs_human = [{"number": i["number"], "title": i["title"], "created_at": i["created_at"]}
                   for i in _pages(f"{r}/issues?state=open&labels=needs-human") if not i.get("pull_request")]
    ready = [{"number": i["number"], "title": i["title"]}
             for i in _pages(f"{r}/issues?state=open&labels=ready-to-close") if not i.get("pull_request")]
    return {"open_prs": open_prs, "issue_state": issue_state, "merged": merged,
            "auto_closed": auto_closed, "needs_human": needs_human, "ready_to_close": ready}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--repo")
    src.add_argument("--data", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--title-file", type=Path, required=True)
    ap.add_argument("--save-data", type=Path)
    args = ap.parse_args(argv)
    now = datetime.now(tz=UTC)
    data = json.loads(args.data.read_text(encoding="utf-8")) if args.data else collect(args.repo, now)
    if args.save_data:
        args.save_data.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    title, body = build(data, now)
    args.output.write_text(body, encoding="utf-8")
    args.title_file.write_text(title + "\n", encoding="utf-8")
    print(title)
    return 0


if __name__ == "__main__":
    sys.exit(main())

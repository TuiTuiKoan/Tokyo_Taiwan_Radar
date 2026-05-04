"""Layer B Phase 1b — automated candidate → researched pipeline.

Evaluates each ``candidate`` source in ``research_sources`` using GPT-4o
+ Playwright and automatically promotes/demotes based on a Taiwan relevance
score.

Pipeline per source:
  score >= 0.70 + easy   → status=researched  (feeds generate.py)
  score >= 0.70 + medium → status=recommended + GitHub Issue created
  score <  0.30          → status=not-viable
  0.30 – 0.70            → status unchanged   (human review needed)

Run with::

    cd scraper
    python -m auto_scraper.auto_research --source-id 42 [--dry-run] [--mock-llm assessment.json]
    python -m auto_scraper.auto_research --batch [--max-sources 10] [--create-issue]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GPT4O_INPUT_COST_PER_1M = 2.50
GPT4O_OUTPUT_COST_PER_1M = 10.00

SCORE_PROMOTE_THRESHOLD = 0.70
SCORE_DEMOTE_THRESHOLD = 0.30
SAMPLE_HTML_TRUNCATE = 40_000
MAX_LLM_ATTEMPTS = 2
COOLDOWN_DAYS = 7
DEFAULT_BUDGET_USD = 0.50
GPT_MODEL = "gpt-4o"

GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar"

_HERE = Path(__file__).parent
_SCHEMA_PATH = _HERE / "assessment_schema.json"
ASSESSMENT_SCHEMA_TEXT = _SCHEMA_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = """You are a web scraper research analyst. Given a sample HTML page from an event listing website, evaluate it and output ONLY a JSON object matching the assessment_schema.json (provided). Do NOT write Python code. Do NOT include markdown fences. Output JSON only.

Your primary task is to score how likely this source REGULARLY publishes Taiwan-related events in Japan.

Scoring guidance for taiwan_relevance_score:
- 0.9–1.0: Dedicated Taiwan cultural/events organization (e.g. Taiwan Cultural Center, Taiwan Festival)
- 0.7–0.9: Regularly features Taiwan events among other Asia content (e.g. film festivals with Taiwan section)
- 0.5–0.7: Occasionally has Taiwan events but primary focus is unrelated
- 0.3–0.5: Taiwan content appears rarely or only by coincidence
- 0.0–0.3: No Taiwan-specific content visible; site is not relevant

taiwan_evidence: List actual text strings you found on the page that justify your score.

CRITICAL for CSS selectors — ONLY use classes/IDs/attributes that appear VERBATIM in the sample HTML:
- Do NOT invent selectors like .event-card, .event-list-item, .c-event__title
- Use tag+class combinations exactly as they appear (e.g. li.article-list, article.entry-card)
- If you cannot find a stable repeating class/id verbatim in the HTML, leave the corresponding *_selector_hint as an empty string ""
- Do NOT substitute generic tag selectors (article, li, div[class*="..."]) when class names are unclear — an empty hint is better than a hallucinated one. The next pipeline stage can fall back gracefully on empty hints but cannot recover from wrong ones.
"""

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result / error model
# ---------------------------------------------------------------------------


class AssessError(Exception):
    """Pipeline failure carrying the status code to persist."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass
class AssessmentResult:
    assessment: dict
    taiwan_relevance_score: float
    feasibility: str
    source_profile_patch: dict
    cost_usd: float
    retries: int


# ---------------------------------------------------------------------------
# Supabase + Playwright helpers
# ---------------------------------------------------------------------------


def _get_supabase():
    from supabase import create_client  # local import for cheap test patching

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise AssessError(
            "llm-error",
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required",
        )
    return create_client(url, key)


def _fetch_sample_html(url: str) -> str:
    """Fetch the first listing page and return its outerHTML (full, untruncated)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto(url, timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:
                pass
            html = page.content()
            return html or ""
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Eligibility + cooldown
# ---------------------------------------------------------------------------


def _check_eligibility(row: dict) -> None:
    if (row.get("status") or "") != "candidate":
        raise AssessError(
            "ineligible",
            f"row.status={row.get('status')!r} (need 'candidate')",
        )
    if row.get("url_verified") is not True:
        raise AssessError("ineligible", "url_verified is not True")


def _within_cooldown(row: dict, now: datetime | None = None) -> bool:
    ts = row.get("auto_research_attempted_at")
    if not ts:
        return False
    try:
        prev = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return False
    if prev.tzinfo is None:
        prev = prev.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - prev) < timedelta(days=COOLDOWN_DAYS)


# ---------------------------------------------------------------------------
# LLM prompt + call
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = [
    "taiwan_relevance_score",
    "feasibility",
    "card_selector_hint",
    "title_selector_hint",
    "date_selector_hint",
    "notes",
    "update_frequency",
]


def _build_assessment_prompt(
    row: dict, sample_html: str, retry_error: str | None = None
) -> str:
    parts = [
        f"Source name: {row.get('name', '')}",
        f"Source URL: {row.get('url', '')}",
        f"Agent category: {row.get('agent_category', '')}",
        f"Researcher notes: {row.get('reason', '')}",
        "",
        "## Required JSON schema (your output MUST validate against this)",
        ASSESSMENT_SCHEMA_TEXT,
        "",
        f"## Sample HTML (first {SAMPLE_HTML_TRUNCATE} chars)",
        "",
        sample_html[:SAMPLE_HTML_TRUNCATE],
    ]
    if retry_error:
        parts.append("")
        parts.append(
            f"Previous attempt failed: {retry_error}. Fix and retry."
        )
    return "\n".join(parts)


def _llm_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1_000_000 * GPT4O_INPUT_COST_PER_1M
        + completion_tokens / 1_000_000 * GPT4O_OUTPUT_COST_PER_1M
    )


def _call_llm_assessment(
    row: dict,
    sample_html: str,
    *,
    budget_usd: float,
    mock_path: Path | None,
) -> AssessmentResult:
    if mock_path is not None:
        data = json.loads(mock_path.read_text(encoding="utf-8"))
        missing = [f for f in _REQUIRED_FIELDS if f not in data]
        if missing:
            raise AssessError("llm-error", f"mock JSON missing required fields: {missing}")
        score = float(data["taiwan_relevance_score"])
        patch = _extract_profile_patch(data)
        return AssessmentResult(
            assessment=data,
            taiwan_relevance_score=score,
            feasibility=data["feasibility"],
            source_profile_patch=patch,
            cost_usd=0.0,
            retries=0,
        )

    from openai import OpenAI

    client = OpenAI()
    cumulative_cost = 0.0
    cumulative_in = 0
    cumulative_out = 0
    last_error: str | None = None

    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
        user_msg = _build_assessment_prompt(row, sample_html, retry_error=last_error)
        try:
            resp = client.chat.completions.create(
                model=GPT_MODEL,
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
        except Exception as exc:
            raise AssessError("llm-error", f"OpenAI call failed: {exc}") from exc

        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        cumulative_in += prompt_tokens
        cumulative_out += completion_tokens
        cumulative_cost = _llm_cost(cumulative_in, cumulative_out)
        if cumulative_cost > budget_usd:
            raise AssessError(
                "budget-exceeded",
                f"cost ${cumulative_cost:.4f} > budget ${budget_usd:.2f}",
            )

        content = resp.choices[0].message.content if resp.choices else ""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            last_error = f"response was not valid JSON: {exc}"
            continue

        missing = [f for f in _REQUIRED_FIELDS if f not in data]
        if missing:
            last_error = f"missing required fields: {missing}"
            continue

        score = float(data["taiwan_relevance_score"])
        patch = _extract_profile_patch(data)

        # Selector grounding check — skip for mock path (already returned above)
        hint_violations = _validate_hints_against_html(patch, sample_html)
        if hint_violations:
            last_error = "selector grounding failed: " + "; ".join(hint_violations)
            continue

        return AssessmentResult(
            assessment=data,
            taiwan_relevance_score=score,
            feasibility=data["feasibility"],
            source_profile_patch=patch,
            cost_usd=cumulative_cost,
            retries=attempt - 1,
        )

    raise AssessError(
        "llm-error",
        f"assessment validation failed after {MAX_LLM_ATTEMPTS} attempts: {last_error}",
    )


def _validate_hints_against_html(patch: dict, html: str) -> list[str]:
    """Lightweight check: non-empty *_selector_hint values must match ≥1 element
    in sample HTML. Empty hints are valid (LLM chose not to guess). Returns list
    of human-readable violations."""
    from bs4 import BeautifulSoup

    violations: list[str] = []
    if not html:
        return []  # cannot validate without HTML — let it pass
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []  # parser error — skip validation

    card_hint = patch.get("card_selector_hint", "")
    if not card_hint:
        # No card hint — nothing else to validate (child hints meaningless without parent)
        return []

    # Validate card selector
    try:
        cards = soup.select(card_hint)
    except Exception as exc:
        return [f"card_selector_hint {card_hint!r} is not valid CSS: {exc}"]
    if not cards:
        violations.append(f"card_selector_hint {card_hint!r} matches 0 elements in sample HTML")
        return violations  # child checks meaningless if card fails

    first_card = cards[0]

    # Validate child selectors within first card
    for field in ("title_selector_hint", "date_selector_hint", "detail_link_selector_hint"):
        sel = patch.get(field, "")
        if not sel:
            continue  # empty is valid
        try:
            matched = first_card.select(sel)
        except Exception as exc:
            violations.append(f"{field}={sel!r} is not valid CSS: {exc}")
            continue
        if not matched:
            violations.append(f"{field}={sel!r} matches 0 elements within first card")

    return violations


def _extract_profile_patch(data: dict) -> dict:
    return {
        "feasibility": data.get("feasibility"),
        "card_selector_hint": data.get("card_selector_hint", ""),
        "title_selector_hint": data.get("title_selector_hint", ""),
        "date_selector_hint": data.get("date_selector_hint", ""),
        "pagination_hint": data.get("pagination_hint", ""),
        "date_format_hint": data.get("date_format_hint", ""),
        "detail_link_selector_hint": data.get("detail_link_selector_hint", ""),
        "notes": data.get("notes", ""),
        "update_frequency": data.get("update_frequency", "unknown"),
        "taiwan_evidence": data.get("taiwan_evidence", []),
    }


# ---------------------------------------------------------------------------
# GitHub Issue creation
# ---------------------------------------------------------------------------


def _create_github_issue(
    name: str, url: str, source_id: int, assessment: dict
) -> str:
    import requests  # local import — not needed in offline tests

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise AssessError(
            "github-error",
            "GITHUB_TOKEN env var required for --create-issue. "
            "Set a classic token with 'repo' scope or a fine-grained token with "
            "Issues: write and Metadata: read.",
        )

    score = assessment.get("taiwan_relevance_score", "?")
    feasibility = assessment.get("feasibility", "?")
    evidence = assessment.get("taiwan_evidence") or []
    notes = assessment.get("notes", "")
    card_sel = assessment.get("card_selector_hint", "")
    title_sel = assessment.get("title_selector_hint", "")
    date_sel = assessment.get("date_selector_hint", "")

    body = (
        f"## 來源資訊\n\n"
        f"- **名稱**: {name}\n"
        f"- **URL**: {url}\n"
        f"- **research_sources.id**: {source_id}\n\n"
        f"## Auto-Research Assessment\n\n"
        f"- **Taiwan relevance score**: {score}\n"
        f"- **Feasibility**: {feasibility}\n"
        f"- **Taiwan evidence**: {', '.join(evidence) if evidence else '（なし）'}\n\n"
        f"## Notes\n\n{notes}\n\n"
        f"## CSS Selector Hints\n\n"
        f"- card: `{card_sel}`\n"
        f"- title: `{title_sel}`\n"
        f"- date: `{date_sel}`\n\n"
        f"## 実装ステップ\n\n"
        f"1. `@Scraper Expert` 依照 hints 分析頁面結構\n"
        f"2. 建立 `scraper/sources/<name>.py` 繼承 `BaseScraper`\n"
        f"3. 加入 `scraper/main.py` 的 `SCRAPERS` 清單\n"
        f"4. `python main.py --dry-run --source <name>` 驗證\n"
        f"5. 確認 `start_date` 有正確填入\n"
    )

    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "title": f"[Scraper] {name}",
        "body": body,
        "labels": ["scraper", "enhancement"],
    }

    resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
    if resp.status_code == 201:
        issue_url = resp.json()["html_url"]
        logger.info("Created GitHub Issue: %s", issue_url)
        return issue_url
    else:
        raise AssessError(
            "github-error",
            f"GitHub API error {resp.status_code}: {resp.text[:300]}",
        )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _update_db_error(sb: Any, source_id: int, message: str) -> None:
    sb.table("research_sources").update(
        {
            "auto_research_status": "error",
            "auto_research_attempted_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", source_id).execute()


# ---------------------------------------------------------------------------
# Assessment application
# ---------------------------------------------------------------------------


def _apply_assessment(
    sb: Any,
    row: dict,
    result: AssessmentResult,
    *,
    dry_run: bool,
    create_issue: bool,
) -> dict:
    score = result.taiwan_relevance_score

    if score >= SCORE_PROMOTE_THRESHOLD:
        new_status = "researched"
    elif score < SCORE_DEMOTE_THRESHOLD:
        new_status = "not-viable"
    else:
        new_status = row["status"]  # unchanged "candidate"

    if score < SCORE_DEMOTE_THRESHOLD:
        auto_research_status = "not-viable"
    else:
        auto_research_status = "assessed"

    # Merge patch into existing source_profile (existing keys preserved)
    existing_profile = row.get("source_profile") or {}
    merged_profile = {**existing_profile, **result.source_profile_patch}

    github_issue_url = None

    # Create GitHub Issue for medium-feasibility promoted sources (human review needed)
    if (
        new_status == "researched"
        and result.feasibility == "medium"
        and create_issue
        and not dry_run
    ):
        try:
            github_issue_url = _create_github_issue(
                row["name"], row["url"], row["id"], result.assessment
            )
            new_status = "recommended"
        except AssessError as exc:
            logger.warning("GitHub Issue creation failed: %s", exc.message)

    patch: dict[str, Any] = {
        "status": new_status,
        "auto_research_status": auto_research_status,
        "auto_research_score": round(score, 2),
        "auto_research_attempted_at": datetime.now(timezone.utc).isoformat(),
        "source_profile": merged_profile,
    }
    if github_issue_url:
        patch["github_issue_url"] = github_issue_url

    if not dry_run:
        sb.table("research_sources").update(patch).eq("id", row["id"]).execute()

    return patch


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


@dataclass
class ResearchOptions:
    source_id: int
    mock_llm: Path | None = None
    dry_run: bool = False
    create_issue: bool = False
    budget_usd: float = DEFAULT_BUDGET_USD
    ignore_cooldown: bool = False
    output_dir: Path | None = None


@dataclass
class BatchOptions:
    max_sources: int = 10
    mock_llm: Path | None = None
    dry_run: bool = False
    create_issue: bool = False
    budget_usd: float = DEFAULT_BUDGET_USD


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run(opts: ResearchOptions, *, sb: Any | None = None) -> int:
    sb = sb or _get_supabase()

    # Step 1: fetch row
    res = (
        sb.table("research_sources")
        .select("*")
        .eq("id", opts.source_id)
        .single()
        .execute()
    )
    row = getattr(res, "data", None)
    if not row:
        logger.error("research_sources id=%s not found", opts.source_id)
        return 1

    # Cooldown check (no DB write, exit 0)
    if not opts.ignore_cooldown and _within_cooldown(row):
        logger.info(
            "source_id=%s within cooldown — skipping (no DB write)", opts.source_id
        )
        print(
            f"skipping source_id={opts.source_id}: retry cooldown active (<{COOLDOWN_DAYS}d)"
        )
        return 0

    try:
        _check_eligibility(row)

        # Step 2: sample HTML
        sample_html = _fetch_sample_html(row["url"])

        # Step 3: LLM assessment
        result = _call_llm_assessment(
            row,
            sample_html,
            budget_usd=opts.budget_usd,
            mock_path=opts.mock_llm,
        )

        # Step 4: apply to DB
        patch = _apply_assessment(
            sb,
            row,
            result,
            dry_run=opts.dry_run,
            create_issue=opts.create_issue,
        )

        action_map = {
            "researched": "promoted",
            "recommended": "promoted (issue created)",
            "not-viable": "demoted",
        }
        action = action_map.get(patch.get("status", ""), "unchanged")

        print("=" * 60)
        print(f"source_id={opts.source_id}  name={row.get('name', '?')}")
        print(f"  score  : {result.taiwan_relevance_score:.2f}")
        print(f"  action : {action}")
        print(f"  status : {patch.get('status')}")
        print(f"  cost   : ${result.cost_usd:.4f}")
        print("=" * 60)
        return 0

    except AssessError as exc:
        logger.error("[%s] %s", exc.status, exc.message)
        if not opts.dry_run:
            try:
                _update_db_error(sb, opts.source_id, exc.message)
            except Exception as db_exc:
                logger.warning("failed to update DB error status: %s", db_exc)
        return 1


def run_batch(opts: BatchOptions, *, sb: Any | None = None) -> tuple[int, int, int]:
    """Process up to opts.max_sources candidate sources. Returns (promoted, demoted, human_review)."""
    sb = sb or _get_supabase()

    rows = (
        sb.table("research_sources")
        .select("*")
        .eq("status", "candidate")
        .eq("url_verified", True)
        .or_("auto_research_status.is.null,auto_research_status.eq.pending,auto_research_status.eq.error")
        .order("id")
        .limit(opts.max_sources)
        .execute()
        .data or []
    )

    logger.info("run_batch: %d rows to process", len(rows))

    promoted = 0
    demoted = 0
    human_review = 0

    for row in rows:
        source_opts = ResearchOptions(
            source_id=row["id"],
            mock_llm=opts.mock_llm,
            dry_run=opts.dry_run,
            create_issue=opts.create_issue,
            budget_usd=opts.budget_usd,
            ignore_cooldown=False,
        )
        rc = run(source_opts, sb=sb)

        if rc != 0:
            continue

        if not opts.dry_run:
            # Re-fetch updated status to classify the outcome
            try:
                updated = (
                    sb.table("research_sources")
                    .select("status")
                    .eq("id", row["id"])
                    .single()
                    .execute()
                    .data
                ) or {}
                new_status = updated.get("status", row["status"])
            except Exception:
                new_status = row["status"]

            if new_status in ("researched", "recommended"):
                promoted += 1
            elif new_status == "not-viable":
                demoted += 1
            else:
                human_review += 1
        else:
            human_review += 1  # dry_run: no DB change, treat as human_review

    print(
        f"run_batch complete: {promoted} promoted, {demoted} demoted, "
        f"{human_review} human_review"
    )
    return promoted, demoted, human_review


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="auto_scraper.auto_research",
        description=(
            "Layer B Phase 1b — evaluate candidate sources via GPT-4o and "
            "promote/demote based on Taiwan relevance score."
        ),
    )
    p.add_argument("--source-id", type=int, default=None, help="research_sources.id")
    p.add_argument("--batch", action="store_true", help="Process up to --max-sources candidates.")
    p.add_argument(
        "--max-sources", type=int, default=10, help="Max sources per batch run (default: 10)."
    )
    p.add_argument(
        "--mock-llm",
        type=Path,
        default=None,
        help="Read assessment JSON from file instead of calling OpenAI (offline tests).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except writing back to research_sources DB.",
    )
    p.add_argument(
        "--create-issue",
        action="store_true",
        help="Create GitHub Issue for medium-feasibility promoted sources.",
    )
    p.add_argument(
        "--budget-usd",
        type=float,
        default=DEFAULT_BUDGET_USD,
        help=f"LLM cost ceiling in USD (default {DEFAULT_BUDGET_USD}).",
    )
    p.add_argument(
        "--ignore-cooldown",
        action="store_true",
        help="Skip the 7-day retry cooldown check.",
    )
    return p


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args()

    if args.batch:
        batch_opts = BatchOptions(
            max_sources=args.max_sources,
            mock_llm=args.mock_llm,
            dry_run=args.dry_run,
            create_issue=args.create_issue,
            budget_usd=args.budget_usd,
        )
        promoted, demoted, human = run_batch(batch_opts)
        sys.exit(0 if (promoted + demoted + human) >= 0 else 1)
    elif args.source_id:
        opts = ResearchOptions(
            source_id=args.source_id,
            mock_llm=args.mock_llm,
            dry_run=args.dry_run,
            create_issue=args.create_issue,
            budget_usd=args.budget_usd,
            ignore_cooldown=args.ignore_cooldown,
        )
        sys.exit(run(opts))
    else:
        _build_parser().print_help()
        sys.exit(1)

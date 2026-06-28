"""Layer B Phase 2 — auto-scraper codegen + sandbox dry-run CLI.

Pipeline (per ``research_sources`` row):
  1. Fetch row + eligibility check (researched / url_verified / feasibility=easy)
  2. Pull a sample HTML page via Playwright (truncated for token cost)
  3. Build prompt → call GPT-4o (JSON mode, schema-enforced retries)
  4. Validate spec via ``spec_to_code.render`` + ``ast_check``
  5. Persist generated code to ``runs/<source_id>/generated.py``
  6. Sandbox subprocess dry-run with stripped env (no SUPABASE_*, OPENAI_*, GITHUB_*)
  7. Update ``research_sources.auto_scraper_*`` status columns

Phase 2 boundaries (intentionally NOT done here):
  * Does NOT open a PR or push branches.
  * Does NOT register the scraper into ``main.py``'s ``SCRAPERS`` list.
  * Does NOT write to ``events`` / ``scraper_runs`` tables.
  * The temporary ``sources/_auto_<name>.py`` file used during the sandbox
    subprocess is always cleaned up via ``try/finally`` AND ``atexit``.

Run with::

    cd scraper
    python -m auto_scraper.generate --source-id 42 [--dry-run] [--mock-llm spec.json]
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

# Load .env from the scraper/ directory so SUPABASE_* and OPENAI_* vars are
# available when running locally (python -m auto_scraper.generate ...).
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on shell env (CI already has vars set)

# GPT-4o pricing as of 2026-05 (verify against current OpenAI pricing).
GPT4O_INPUT_COST_PER_1M = 2.50
GPT4O_OUTPUT_COST_PER_1M = 10.00

DEFAULT_BUDGET_USD = 1.50
SAMPLE_HTML_TRUNCATE = 50_000
RETRY_COOLDOWN_DAYS = 7
MAX_LLM_ATTEMPTS = 3
SANDBOX_TIMEOUT_SEC = 300

_HERE = Path(__file__).parent
_SCRAPER_DIR = _HERE.parent
_DEFAULT_RUNS_DIR = _HERE / "runs"

_SCHEMA_PATH = _HERE / "spec_schema.json"
SPEC_SCHEMA_TEXT = _SCHEMA_PATH.read_text(encoding="utf-8")

SYSTEM_PROMPT = """You are a web scraper spec generator. Given a sample HTML page from an event listing site, output ONLY a JSON object matching the spec_schema.json (provided). Do NOT write Python code. Do NOT include markdown fences. Output JSON only.

Constraints:
- source_name must be snake_case, derived from domain (e.g. "iwafu_com" -> "iwafu", "acros.or.jp" -> "acros")
- class_name must be PascalCase derived from source_name
- Use CSS selectors that target the most likely event-card element. Pick a selector that matches MULTIPLE sibling elements on the page (an event listing).
- field_selectors.title and field_selectors.date are REQUIRED.
- date_regex must extract a date from the text matched by field_selectors.date. Common patterns: r"(\\d{4})[/-](\\d{1,2})[/-](\\d{1,2})" or r"(\\d{4})年(\\d{1,2})月(\\d{1,2})日".
- source_id_url_pattern must extract a numeric or alphanumeric ID from event detail URLs.
- max_pages: pick conservatively (3-5 for unknown sites).
- detail_link_selector: CSS selector for the per-card anchor that links to the event detail page (e.g. "a.title", "a[href*='/event/']"). Set this whenever cards link to detail pages — leave empty ONLY if the listing has no detail links at all. If you leave it empty, the generated scraper will fall back to the first <a href> inside each card, which works for most cases but is less precise.

CRITICAL — card_selector_hint:
- If the researcher has provided a 'card_selector_hint' in the hints JSON, use it DIRECTLY as card_selector. It was manually verified against the live page and takes priority over your own inference.

CRITICAL — Selector grounding rule:
- ONLY use CSS classes, IDs, or attributes that appear VERBATIM in the sample HTML provided below.
- A 'Observed classes (≥3 occurrences)' list is provided — prefer selectors built from these classes over inventing new ones.
- DO NOT invent class names that look reasonable but are not actually in the HTML (e.g. ".event-card", ".c-event-list__item" are common LLM fabrications).
- Before outputting each selector, scan the sample HTML and confirm the class/id/tag is present.
- If you cannot find any clear class to anchor on, prefer tag selectors (e.g. "article", "li.article-list", "div.post") over making up class names.
- Empty card_selector or selectors that match nothing will cause sandbox failure and waste an expensive retry.

CRITICAL — card_selector must be a CONTAINER element:
- card_selector must select a CONTAINER element (div, li, article, section, tr) that WRAPS the title, date, and link as DESCENDANTS.
- NEVER use the title or heading element itself (h1, h2, h3, h4, h5, h6, a, span) as card_selector — field_selectors cannot find elements inside a leaf node.
- Test mentally: can you find field_selectors.title inside card_selector? If card_selector IS the title element, the answer is always no.
"""

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result / error model
# ---------------------------------------------------------------------------


class GenerateError(Exception):
    """Pipeline failure carrying the status code to persist."""

    def __init__(
        self,
        status: str,
        message: str,
        payload: dict | None = None,
        raw: str | None = None,
        cost_usd: float = 0.0,
        retries: int = 0,
    ):
        super().__init__(message)
        self.status = status
        self.message = message
        self.payload = payload
        self.raw = raw
        self.cost_usd = cost_usd
        self.retries = retries


@dataclass
class LLMResult:
    spec: dict
    cost_usd: float
    prompt_tokens: int
    completion_tokens: int
    retries: int
    raw_messages: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Supabase + Playwright helpers (kept thin so tests can patch them)
# ---------------------------------------------------------------------------


def _get_supabase():
    from supabase import create_client  # local import for cheap test patching

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise GenerateError(
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
# Eligibility
# ---------------------------------------------------------------------------


def _check_eligibility(row: dict) -> None:
    if (row.get("status") or "") not in ("researched", "recommended"):
        raise GenerateError(
            "spec-invalid",
            f"row.status={row.get('status')!r} (need 'researched' or 'recommended')",
        )
    if row.get("url_verified") is not True:
        raise GenerateError("spec-invalid", "url_verified is not True")
    profile = row.get("source_profile")
    if not isinstance(profile, dict):
        raise GenerateError("spec-invalid", "source_profile is missing")
    if profile.get("feasibility") not in ("easy", "medium"):
        raise GenerateError(
            "spec-invalid",
            f"feasibility={profile.get('feasibility')!r} (need 'easy' or 'medium')",
        )


def _validate_selectors_against_html(spec: dict, html: str) -> list[str]:
    """Lightweight pre-sandbox check: confirm LLM-generated CSS selectors match
    real elements in the sample HTML. Catches hallucinated class names without
    spending 30s in Playwright. Returns list of human-readable violations."""
    from bs4 import BeautifulSoup

    violations: list[str] = []
    if not html:
        return ["sample HTML is empty — cannot validate selectors"]
    soup = BeautifulSoup(html, "html.parser")

    card_sel = spec.get("card_selector", "")
    if not card_sel:
        return ["card_selector is empty"]
    try:
        cards = soup.select(card_sel)
    except Exception as exc:
        return [f"card_selector {card_sel!r} is not a valid CSS selector: {exc}"]
    if not cards:
        return [f"card_selector {card_sel!r} matches 0 elements in sample HTML"]

    first_card = cards[0]
    field_sels = spec.get("field_selectors", {}) or {}
    for field, sel in field_sels.items():
        if not sel:
            continue
        try:
            matched = first_card.select(sel)
        except Exception as exc:
            violations.append(
                f"field_selectors.{field}={sel!r} is not a valid CSS selector: {exc}"
            )
            continue
        if not matched:
            violations.append(
                f"field_selectors.{field}={sel!r} matches 0 elements within first card"
            )

    detail_sel = spec.get("detail_link_selector", "")
    if detail_sel:
        try:
            matched = first_card.select(detail_sel)
        except Exception as exc:
            violations.append(
                f"detail_link_selector={detail_sel!r} is not a valid CSS selector: {exc}"
            )
        else:
            if not matched:
                violations.append(
                    f"detail_link_selector={detail_sel!r} matches 0 elements within first card"
                )
    return violations


def _within_cooldown(row: dict, now: datetime | None = None) -> bool:
    ts = row.get("auto_scraper_attempted_at")
    if not ts:
        return False
    try:
        prev = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return False
    if prev.tzinfo is None:
        prev = prev.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (now - prev) < timedelta(days=RETRY_COOLDOWN_DAYS)


# ---------------------------------------------------------------------------
# LLM call with retries
# ---------------------------------------------------------------------------


def _extract_observed_classes(html: str, min_count: int = 3) -> list[str]:
    """Return CSS class names that appear >= min_count times in the HTML.

    Gives GPT a verified whitelist to pick selectors from instead of guessing.
    """
    import re
    from collections import Counter

    all_classes: list[str] = []
    for m in re.finditer(r'class=["\']([^"\']+)["\']', html):
        all_classes.extend(m.group(1).split())
    counts = Counter(all_classes)
    return [cls for cls, n in counts.most_common() if n >= min_count]


def _strip_non_structural_html(html: str) -> str:
    """Remove script/style/svg content to make token budget more useful.

    BeautifulSoup is not available at module level — use simple regex strip.
    This is best-effort; actual HTML parsing happens in _validate_selectors.
    """
    import re

    for tag in ("script", "style", "svg", "noscript"):
        html = re.sub(
            rf"<{tag}[^>]*>.*?</{tag}>", f"<!-- {tag} removed -->", html,
            flags=re.DOTALL | re.IGNORECASE,
        )
    return html


def _build_user_message(row: dict, sample_html: str, retry_error: str | None = None) -> str:
    profile = row.get("source_profile") or {}

    # Option B: strip non-structural tags so the 50k budget contains more structure
    stripped_html = _strip_non_structural_html(sample_html)

    # Option A: extract class names that actually appear in the HTML
    observed_classes = _extract_observed_classes(stripped_html)
    classes_hint = (
        ", ".join(f".{c}" for c in observed_classes[:60])
        if observed_classes
        else "(none found)"
    )

    # Option C: surface card_selector_hint prominently
    card_hint = profile.get("card_selector_hint", "")
    card_hint_line = (
        f"\n⚠️  card_selector_hint (use this directly): {card_hint}"
        if card_hint
        else ""
    )

    parts = [
        f"Source name: {row.get('name', '')}",
        f"Source URL: {row.get('url', '')}",
        f"Hints from researcher: {json.dumps(profile, ensure_ascii=False)}{card_hint_line}",
        "",
        f"Observed classes (≥3 occurrences in sample HTML): {classes_hint}",
        "",
        "## Required JSON schema (your output MUST validate against this)",
        SPEC_SCHEMA_TEXT,
        "",
        "## Critical required fields \u2014 do NOT omit ANY of these",
        "source_name, class_name, base_url, search_url, card_selector,",
        "field_selectors (must include title and date), date_regex,",
        "source_id_prefix, source_id_url_pattern",
        "",
        f"## Sample HTML (first {SAMPLE_HTML_TRUNCATE} chars, script/style stripped)",
        "",
        stripped_html[:SAMPLE_HTML_TRUNCATE],
    ]
    if retry_error:
        parts.append("")
        parts.append(
            f"Previous attempt failed validation: {retry_error}. "
            "Fix and retry \u2014 preserve ALL required fields."
        )
    return "\n".join(parts)


def _llm_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1_000_000 * GPT4O_INPUT_COST_PER_1M
        + completion_tokens / 1_000_000 * GPT4O_OUTPUT_COST_PER_1M
    )


def _call_llm_with_retries(
    row: dict,
    sample_html: str,
    *,
    budget_usd: float,
    mock_llm_path: Path | None,
) -> LLMResult:
    from auto_scraper import spec_to_code

    if mock_llm_path is not None:
        spec = json.loads(mock_llm_path.read_text(encoding="utf-8"))
        # Validate eagerly; no cost incurred.
        try:
            spec_to_code.render(spec)
        except ValueError as exc:
            raise GenerateError("spec-invalid", f"mock spec invalid: {exc}") from exc
        return LLMResult(spec=spec, cost_usd=0.0, prompt_tokens=0, completion_tokens=0, retries=0)

    from openai import OpenAI

    client = OpenAI()
    cumulative_cost = 0.0
    cumulative_in = 0
    cumulative_out = 0
    last_error: str | None = None
    last_parsed: dict | None = None
    last_raw: str | None = None

    for attempt in range(1, MAX_LLM_ATTEMPTS + 1):
        user_msg = _build_user_message(row, sample_html, retry_error=last_error)
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
            )
        except Exception as exc:
            raise GenerateError(
                "llm-error",
                f"OpenAI call failed: {exc}",
                cost_usd=cumulative_cost,
                retries=attempt - 1,
            ) from exc

        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        cumulative_in += prompt_tokens
        cumulative_out += completion_tokens
        cumulative_cost = _llm_cost(cumulative_in, cumulative_out)
        if cumulative_cost > budget_usd:
            raise GenerateError(
                "budget-exceeded",
                f"cost ${cumulative_cost:.4f} > budget ${budget_usd:.2f}",
                cost_usd=cumulative_cost,
                retries=attempt - 1,
            )

        content = resp.choices[0].message.content if resp.choices else ""
        last_raw = content
        try:
            spec = json.loads(content)
        except json.JSONDecodeError as exc:
            last_error = f"response was not valid JSON: {exc}"
            last_parsed = None
            continue

        last_parsed = spec
        try:
            spec_to_code.render(spec)
        except ValueError as exc:
            last_error = str(exc)
            continue

        # Selector grounding check — fast-fail on hallucinated CSS classes
        # before spending 30s+ in Playwright sandbox. Skipped for --mock-llm.
        selector_violations = _validate_selectors_against_html(spec, sample_html)
        if selector_violations:
            last_error = "selector grounding failed: " + "; ".join(selector_violations)
            continue

        return LLMResult(
            spec=spec,
            cost_usd=cumulative_cost,
            prompt_tokens=cumulative_in,
            completion_tokens=cumulative_out,
            retries=attempt - 1,
        )

    raise GenerateError(
        "spec-invalid",
        f"spec validation failed after {MAX_LLM_ATTEMPTS} attempts: {last_error}",
        payload=last_parsed,
        raw=last_raw,
        cost_usd=cumulative_cost,
        retries=MAX_LLM_ATTEMPTS,
    )


# ---------------------------------------------------------------------------
# Sandbox subprocess
# ---------------------------------------------------------------------------


_TEMP_FILES_TO_CLEANUP: set[Path] = set()


def _register_cleanup(path: Path) -> None:
    _TEMP_FILES_TO_CLEANUP.add(path)


def _atexit_cleanup() -> None:
    for path in list(_TEMP_FILES_TO_CLEANUP):
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass
        _TEMP_FILES_TO_CLEANUP.discard(path)


atexit.register(_atexit_cleanup)


def _run_sandbox(spec: dict, generated_code: str) -> tuple[bool, str, list[dict]]:
    """Run generated scraper in a stripped subprocess. Returns (ok, combined_output, sample_events)."""
    source_name = spec["source_name"]
    class_name = spec["class_name"]
    sources_dir = _SCRAPER_DIR / "sources"
    temp_path = sources_dir / f"_auto_{source_name}.py"

    _register_cleanup(temp_path)
    try:
        temp_path.write_text(generated_code, encoding="utf-8")

        snippet = (
            "import json, dataclasses\n"
            f"from sources._auto_{source_name} import {class_name}Scraper\n"
            f"events = {class_name}Scraper().scrape()\n"
            "print(f'len={len(events)}')\n"
            "out = []\n"
            "for ev in events[:3]:\n"
            "    d = dataclasses.asdict(ev) if dataclasses.is_dataclass(ev) else dict(ev.__dict__)\n"
            "    out.append({k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in d.items()})\n"
            "print('SAMPLE_EVENTS=' + json.dumps(out, ensure_ascii=False, default=str))\n"
        )

        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "PYTHONUNBUFFERED": "1",
        }
        # Preserve playwright browser cache locations if user set them.
        for key in ("PLAYWRIGHT_BROWSERS_PATH", "TMPDIR", "LANG", "LC_ALL"):
            if key in os.environ:
                env[key] = os.environ[key]

        result = subprocess.run(
            [sys.executable, "-c", snippet],
            cwd=str(_SCRAPER_DIR),
            env=env,
            timeout=SANDBOX_TIMEOUT_SEC,
            capture_output=True,
            text=True,
        )
        combined = (result.stdout or "") + "\n--- STDERR ---\n" + (result.stderr or "")

        if result.returncode != 0:
            return False, combined, []

        m = re.search(r"^len=(\d+)$", result.stdout or "", re.MULTILINE)
        if not m or int(m.group(1)) < 1:
            return False, combined, []

        events: list[dict] = []
        sm = re.search(r"^SAMPLE_EVENTS=(.+)$", result.stdout or "", re.MULTILINE)
        if sm:
            try:
                events = json.loads(sm.group(1))
            except json.JSONDecodeError:
                events = []

        if not events:
            return False, combined + "\n[no SAMPLE_EVENTS found]", []

        first = events[0]
        has_name = any(first.get(k) for k in ("name_ja", "name_zh", "name_en"))
        if not (
            has_name
            and first.get("source_url")
            and first.get("source_id")
            and first.get("start_date")
        ):
            return False, combined + "\n[first event missing required fields]", events

        return True, combined, events
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        _TEMP_FILES_TO_CLEANUP.discard(temp_path)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _persist_artifacts(
    out_dir: Path,
    *,
    spec: dict,
    generated_code: str,
    user_prompt: str,
    sandbox_output: str,
    sample_html: str,
    meta: dict,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "generated.py").write_text(generated_code, encoding="utf-8")
    (out_dir / "prompt.txt").write_text(user_prompt, encoding="utf-8")
    (out_dir / "dry_run.txt").write_text(sandbox_output, encoding="utf-8")
    (out_dir / "sample.html").write_text(sample_html, encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _persist_failure_artifacts(
    out_dir: Path,
    *,
    prompt_text: str,
    sample_html: str | None,
    last_spec_attempt: dict | None,
    last_raw: str | None,
    error_message: str,
    status: str,
    retries: int,
    cost_usd: float,
    spec: dict | None = None,
    generated_code: str | None = None,
    dry_run_text: str | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")
    if sample_html is not None:
        (out_dir / "sample.html").write_text(sample_html, encoding="utf-8")
    if last_spec_attempt is not None:
        (out_dir / "last_attempt_spec.json").write_text(
            json.dumps(last_spec_attempt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    elif last_raw is not None:
        (out_dir / "last_attempt_raw.txt").write_text(last_raw, encoding="utf-8")
    if spec is not None:
        (out_dir / "spec.json").write_text(
            json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if generated_code is not None:
        (out_dir / "generated.py").write_text(generated_code, encoding="utf-8")
    if dry_run_text is not None:
        (out_dir / "dry_run.txt").write_text(dry_run_text, encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "status": status,
                "error": error_message,
                "retries": retries,
                "cost_usd": round(cost_usd, 6),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _update_db_status(
    sb: Any,
    source_id: int,
    *,
    status: str,
    failed_reason: str | None,
    artifacts: dict | None = None,
) -> None:
    payload = {
        "auto_scraper_status": status,
        "auto_scraper_attempted_at": datetime.now(timezone.utc).isoformat(),
        "auto_scraper_failed_reason": (failed_reason or None) if failed_reason else None,
    }
    if not failed_reason:
        payload["auto_scraper_failed_reason"] = None
    if artifacts is not None:
        payload["auto_scraper_artifacts"] = artifacts
    sb.table("research_sources").update(payload).eq("id", source_id).execute()


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


@dataclass
class GenerateOptions:
    source_id: int
    mock_llm: Path | None = None
    skip_sandbox: bool = False
    dry_run: bool = False
    output_dir: Path | None = None
    budget_usd: float = DEFAULT_BUDGET_USD
    ignore_cooldown: bool = False


def run(opts: GenerateOptions, *, sb: Any | None = None) -> int:
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
        logger.info("source_id=%s within cooldown \u2014 skipping (no DB write)", opts.source_id)
        print(f"skipping source_id={opts.source_id}: retry cooldown active (<7d)")
        return 0

    out_dir = opts.output_dir or (_DEFAULT_RUNS_DIR / str(opts.source_id))

    try:
        _check_eligibility(row)
    except GenerateError as exc:
        logger.error("eligibility failed: %s", exc.message)
        if not opts.dry_run:
            _update_db_status(sb, opts.source_id, status=exc.status, failed_reason=exc.message)
        return 1

    try:
        # Step 2: sample HTML
        sample_html = _fetch_sample_html(row["url"])

        # Steps 3–5: LLM + validate
        llm = _call_llm_with_retries(
            row,
            sample_html,
            budget_usd=opts.budget_usd,
            mock_llm_path=opts.mock_llm,
        )

        # Step 6: render + AST check
        from auto_scraper import spec_to_code

        generated_code = spec_to_code.render(llm.spec)
        violations = spec_to_code.ast_check(generated_code)
        if violations:
            raise GenerateError(
                "spec-invalid",
                "ast violations: " + "; ".join(violations),
            )

        # Step 7: sandbox
        sandbox_output = ""
        events_found = 0
        sample_events: list = []
        if not opts.skip_sandbox:
            ok, sandbox_output, sample_events = _run_sandbox(llm.spec, generated_code)
            events_found = len(sample_events)
            if not ok:
                raise GenerateError(
                    "sandbox-failed",
                    f"sandbox dry-run failed for {llm.spec.get('source_name')}",
                )

        # Step 8: persist
        meta = {
            "model": "gpt-4o",
            "cost_usd": round(llm.cost_usd, 6),
            "prompt_tokens": llm.prompt_tokens,
            "completion_tokens": llm.completion_tokens,
            "retries": llm.retries,
            "events_found": events_found,
            "sha256": hashlib.sha256(generated_code.encode("utf-8")).hexdigest(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "skip_sandbox": opts.skip_sandbox,
        }
        user_prompt = _build_user_message(row, sample_html)
        if not opts.dry_run:
            _persist_artifacts(
                out_dir,
                spec=llm.spec,
                generated_code=generated_code,
                user_prompt=user_prompt,
                sandbox_output=sandbox_output,
                sample_html=sample_html,
                meta=meta,
            )
            _artifacts = {
                "events_found": events_found,
                "cost_usd": round(llm.cost_usd, 6),
                "source_id_url_pattern": llm.spec.get("source_id_url_pattern", ""),
                "sample_titles": [
                    ev.get("name_ja") or ev.get("name_zh") or ev.get("name_en") or ev.get("raw_title") or ""
                    for ev in sample_events[:3]
                    if ev.get("name_ja") or ev.get("name_zh") or ev.get("name_en") or ev.get("raw_title")
                ],
            }
            _update_db_status(
                sb,
                opts.source_id,
                status="success",
                failed_reason=None,
                artifacts=_artifacts,
            )

        print("=" * 60)
        print(f"source_id={opts.source_id} status=success")
        print(f"  source_name : {llm.spec.get('source_name')}")
        print(f"  cost_usd    : ${llm.cost_usd:.4f}")
        print(f"  retries     : {llm.retries}")
        print(f"  events_found: {events_found}")
        print(f"  artifacts   : {out_dir}")
        print("=" * 60)
        return 0

    except GenerateError as exc:
        logger.error("[%s] %s", exc.status, exc.message)
        if not opts.dry_run:
            try:
                _local = locals()
                _sample = _local.get("sample_html")
                _prompt_text = _build_user_message(row, _sample or "")
                _llm_obj = _local.get("llm")
                _cost = getattr(exc, "cost_usd", 0.0) or getattr(_llm_obj, "cost_usd", 0.0)
                _retries = getattr(exc, "retries", 0) or getattr(_llm_obj, "retries", 0)
                _persist_failure_artifacts(
                    out_dir,
                    prompt_text=_prompt_text,
                    sample_html=_sample,
                    last_spec_attempt=getattr(exc, "payload", None),
                    last_raw=getattr(exc, "raw", None),
                    error_message=exc.message,
                    status=exc.status,
                    retries=_retries,
                    cost_usd=_cost,
                    spec=getattr(_llm_obj, "spec", None),
                    generated_code=_local.get("generated_code"),
                    dry_run_text=_local.get("sandbox_output"),
                )
            except Exception as art_exc:
                logger.warning("failed to persist failure artifacts: %s", art_exc)
            _update_db_status(
                sb,
                opts.source_id,
                status=exc.status,
                failed_reason=exc.message[:500],
            )
        return 1


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------


@dataclass
class BatchOptions:
    max_sources: int = 3
    mock_llm: Path | None = None
    skip_sandbox: bool = False
    dry_run: bool = False
    output_dir: Path | None = None
    budget_usd: float = DEFAULT_BUDGET_USD
    ignore_cooldown: bool = False


def run_batch(opts: BatchOptions, *, sb: Any | None = None) -> tuple[int, int]:
    """Process up to opts.max_sources researched sources. Returns (success_count, failed_count)."""
    sb = sb or _get_supabase()

    # Query: researched + easy/medium + not yet attempted (or sandbox-failed / llm-error retry)
    rows = (
        sb.table("research_sources")
        .select("*")
        .eq("status", "researched")
        .eq("url_verified", True)
        .in_("scraping_feasibility", ["easy", "medium"])
        .or_("auto_scraper_status.is.null,auto_scraper_status.eq.sandbox-failed,auto_scraper_status.eq.llm-error")
        .order("id")
        .limit(opts.max_sources)
        .execute()
        .data or []
    )
    # Filter out cooldown
    now = datetime.now(timezone.utc)
    eligible = [r for r in rows if not _within_cooldown(r, now) or opts.ignore_cooldown]

    logger.info(
        "run_batch: %d/%d rows eligible (after cooldown filter)",
        len(eligible),
        len(rows),
    )

    success = 0
    failed = 0
    for row in eligible:
        source_opts = GenerateOptions(
            source_id=row["id"],
            mock_llm=opts.mock_llm,
            skip_sandbox=opts.skip_sandbox,
            dry_run=opts.dry_run,
            output_dir=opts.output_dir,
            budget_usd=opts.budget_usd,
            ignore_cooldown=True,  # already filtered above
        )
        result = run(source_opts, sb=sb)
        if result == 0:
            success += 1
        else:
            failed += 1

    print(
        f"run_batch complete: {success} success, {failed} failed, "
        f"{len(rows) - len(eligible)} skipped (cooldown)"
    )
    return success, failed


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="auto_scraper.generate",
        description=(
            "Layer B Phase 2 — generate a scraper spec via GPT-4o, render it, "
            "and validate via a sandbox subprocess dry-run. Does NOT open a PR "
            "or register the scraper into main.py."
        ),
    )
    p.add_argument("--source-id", type=int, default=None, help="research_sources.id")
    p.add_argument(
        "--batch",
        action="store_true",
        help="Process up to --max-sources researched sources.",
    )
    p.add_argument(
        "--max-sources",
        type=int,
        default=3,
        help="Max sources per batch run (default: 3).",
    )
    p.add_argument(
        "--mock-llm",
        type=Path,
        default=None,
        help="Read spec.json from file instead of calling OpenAI (offline tests).",
    )
    p.add_argument(
        "--skip-sandbox",
        action="store_true",
        help="Skip the dry-run subprocess (for unit tests).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do everything except writing back to research_sources DB / saving generated .py.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Override default scraper/auto_scraper/runs/<source_id>/.",
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
        help="Skip the 7-day retry cooldown check (for e2e re-runs).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.batch:
        batch_opts = BatchOptions(
            max_sources=args.max_sources,
            mock_llm=args.mock_llm,
            skip_sandbox=args.skip_sandbox,
            dry_run=args.dry_run,
            output_dir=args.output_dir,
            budget_usd=args.budget_usd,
            ignore_cooldown=args.ignore_cooldown,
        )
        success, failed = run_batch(batch_opts)
        # Exit 1 only when every eligible source failed (all-fail = likely systemic issue).
        # Partial failures (some success) exit 0 — normal when some sources have known-bad URLs.
        sys.exit(1 if failed > 0 and success == 0 else 0)

    if args.source_id is None:
        parser.print_help()
        sys.exit(1)

    opts = GenerateOptions(
        source_id=args.source_id,
        mock_llm=args.mock_llm,
        skip_sandbox=args.skip_sandbox,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        budget_usd=args.budget_usd,
        ignore_cooldown=args.ignore_cooldown,
    )
    return run(opts)


if __name__ == "__main__":
    raise SystemExit(main())

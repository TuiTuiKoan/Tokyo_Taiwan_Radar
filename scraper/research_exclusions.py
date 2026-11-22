"""Domains that source discovery must never propose as new sources.

Used by auto_scraper/auto_research.py (researcher.py was removed in 2026-10, #318).

research_sources already blocks domains it has seen, but only by exact host,
and only when the DB fetch succeeds. Platforms we have tried and retired
publish under per-organizer subdomains (e.g. <group>.connpass.com), so they
need a curated, reviewed list that also covers subdomains.

To exclude a platform: add one entry below (registrable domain, no "www.")
with the reason and date, then mark its research_sources rows not-viable.
"""

from __future__ import annotations

from urllib.parse import urlparse

# domain -> why it is excluded (keep the date so stale entries can be reviewed)
RESEARCH_EXCLUDED_DOMAINS: dict[str, str] = {
    "connpass.com": "2026-10 retired: removed from production earlier as a low-value source",
    "doorkeeper.jp": "2026-10 retired: scraped events were almost all unrelated to Taiwan",
}


# research_sources rows with these agent_category values are account lists read
# by a dedicated scraper (spec social-sources D1), not websites to assess or to
# generate a scraper for. auto_research.py and auto_scraper/generate.py must
# leave them alone: assessment would open a login-walled page and demote the row
# to not-viable, and generation would spend LLM budget on a scraper that cannot work.
MANAGED_AGENT_CATEGORIES: tuple[str, ...] = ("facebook_page", "x_account")

# PostgREST ``or`` filter that keeps every row not in MANAGED_AGENT_CATEGORIES.
# The ``is.null`` arm is required: ``not.in`` alone drops rows whose
# agent_category is NULL, which is most of the table.
UNMANAGED_ROWS_FILTER = (
    "agent_category.is.null,agent_category.not.in.(" + ",".join(MANAGED_AGENT_CATEGORIES) + ")"
)


def managed_reason(row: dict) -> str | None:
    """Why a research_sources row is outside auto-research / auto-generate, or None."""
    category = row.get("agent_category") if isinstance(row, dict) else None
    if category in MANAGED_AGENT_CATEGORIES:
        return f"agent_category={category} is an account list handled by its own scraper"
    return None


def excluded_reason(url: str) -> str | None:
    """Return the exclusion reason if url is on (or under) an excluded domain."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return None
    host = host.removeprefix("www.")
    for domain, reason in RESEARCH_EXCLUDED_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return reason
    return None


def prompt_block() -> str:
    """Instruction appended to researcher prompts."""
    domains = ", ".join(sorted(RESEARCH_EXCLUDED_DOMAINS))
    return (
        "EXCLUDED platforms — do NOT search on, cite, or suggest any URL from "
        f"these domains or their subdomains: {domains}\n\n"
    )

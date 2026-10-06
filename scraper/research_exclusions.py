"""Domains that researcher.py must never propose as new sources.

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

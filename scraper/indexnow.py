"""
IndexNow integration for Tokyo Taiwan Radar.

Submits newly-upserted event URLs to the IndexNow API so Bing (and
ChatGPT Search, which is powered by Bing) indexes them within minutes
instead of days.

Spec: https://www.indexnow.org/documentation
Supported engines: Bing, Yandex, Seznam, Naver, Yep, DuckDuckGo

Usage:
    from indexnow import submit_urls
    submit_urls(["https://example.com/zh/events/abc", ...])

The function is a no-op (logs a warning) if INDEXNOW_KEY or
NEXT_PUBLIC_SITE_URL are not set, so it never breaks the main pipeline.
"""

import logging
import os
import urllib.request
import urllib.error
import json

logger = logging.getLogger(__name__)

# IndexNow endpoint — Bing is the canonical host that relays to all partners
_INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"

# Chunk size: IndexNow accepts max 10,000 URLs per request; we batch smaller
_BATCH_SIZE = 200


def submit_urls(urls: list[str]) -> None:
    """
    Submit a list of absolute URLs to IndexNow (Bing relay).

    Silently skips if:
    - INDEXNOW_KEY env var is not set
    - NEXT_PUBLIC_SITE_URL env var is not set
    - urls list is empty

    Never raises — any network error is logged as a warning.
    """
    key = os.environ.get("INDEXNOW_KEY", "").strip()
    site = os.environ.get("NEXT_PUBLIC_SITE_URL", "").strip().rstrip("/")

    if not key:
        logger.debug("IndexNow: INDEXNOW_KEY not set — skipping submission")
        return
    if not site:
        logger.debug("IndexNow: NEXT_PUBLIC_SITE_URL not set — skipping submission")
        return
    if not urls:
        return

    key_location = f"{site}/{key}.txt"
    host = site.replace("https://", "").replace("http://", "").split("/")[0]

    for i in range(0, len(urls), _BATCH_SIZE):
        batch = urls[i : i + _BATCH_SIZE]
        payload = {
            "host": host,
            "key": key,
            "keyLocation": key_location,
            "urlList": batch,
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                _INDEXNOW_ENDPOINT,
                data=data,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "User-Agent": "TokyoTaiwanRadar/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            if status in (200, 202):
                logger.info("IndexNow: submitted %d URL(s) → HTTP %d", len(batch), status)
            else:
                logger.warning("IndexNow: unexpected HTTP %d for batch of %d", status, len(batch))
        except urllib.error.HTTPError as exc:
            # 422 = key file not yet accessible (e.g. Vercel not deployed), non-fatal
            logger.warning("IndexNow: HTTP error %d — %s", exc.code, exc.reason)
        except Exception as exc:
            logger.warning("IndexNow: submission failed: %s", exc)


def event_urls(event_ids: list[str], locales: list[str] | None = None) -> list[str]:
    """
    Build canonical event URLs for each locale from a list of event IDs.

    Args:
        event_ids: list of UUID strings
        locales: defaults to ["zh", "ja", "en"]

    Returns flat list: ["/zh/events/id1", "/zh/events/id2", "/ja/events/id1", ...]
    """
    if locales is None:
        locales = ["zh", "ja", "en"]
    site = os.environ.get("NEXT_PUBLIC_SITE_URL", "").strip().rstrip("/")
    return [
        f"{site}/{locale}/events/{eid}"
        for locale in locales
        for eid in event_ids
    ]

#!/usr/bin/env python3
"""Dry-run the social-source pipeline and print a JSON report.

Spec: docs/specs/active/social-sources/proposal.md (M1/M2)

Never writes to the database. Reads targets from a JSON file of
``research_sources``-shaped rows, or (with --from-db) read-only from the
database. A live run needs X_BEARER_TOKEN (x) or APIFY_TOKEN (facebook) and
costs money per post read; adding those secrets is a human gate.

Exit codes: 0 ok, 1 a configured backend failed, 2 backend not configured.

    python social_dryrun.py --platform x --targets-file targets.json
    python social_dryrun.py --platform facebook --from-db --no-links
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from social.enrich import LinkEnricher
from social.facebook_backend import FacebookBackend
from social.filters import to_jst_date
from social.models import PLATFORM_X, PLATFORMS
from social.pipeline import run_pipeline
from social.targets import load_targets, targets_from_rows
from social.x_backend import XBackend


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    raise TypeError(f"not JSON serialisable: {type(obj).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--targets-file", type=Path, help="JSON list of research_sources-shaped rows")
    source.add_argument("--from-db", action="store_true", help="read implemented targets from the database (read-only)")
    parser.add_argument("--lookback-hours", type=int, default=26)
    parser.add_argument("--max-posts", type=int, default=None, help="per-run cap on posts read (x only)")
    parser.add_argument("--no-links", action="store_true", help="do not fetch linked pages")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)

    if args.from_db:
        targets = load_targets(args.platform)
    else:
        rows = json.loads(args.targets_file.read_text(encoding="utf-8"))
        targets = targets_from_rows(rows if isinstance(rows, list) else [], args.platform)

    if args.platform == PLATFORM_X:
        backend = XBackend(**({"max_posts_per_run": args.max_posts} if args.max_posts is not None else {}))
    else:
        backend = FacebookBackend()
    enricher = None if args.no_links else LinkEnricher()
    report = run_pipeline(
        targets,
        backend,
        today=to_jst_date(datetime.now(timezone.utc)),
        enricher=enricher,
        lookback_hours=args.lookback_hours,
    )
    summary = {
        "platform": report.platform,
        "targets": len(targets),
        "posts_read": report.posts_read,
        "pages_fetched": report.pages_fetched,
        "events": len(report.events),
        "insufficient": len(report.insufficient),
        "flagged": len(report.flagged),
        "dropped": report.dropped,
        "link_stats": report.link_stats,
        "skipped": report.skipped,
        "errors": report.errors,
    }
    if args.platform == PLATFORM_X:
        summary["estimated_cost_usd"] = backend.estimated_cost_usd()
    print(json.dumps(
        {"summary": summary, "events": report.events, "insufficient": report.insufficient,
         "flagged": report.flagged, "newest_post_ids": report.newest_post_ids},
        ensure_ascii=False, indent=2, default=_json_default,
    ))
    if report.errors:
        return 1          # a configured backend failed
    return 2 if report.skipped else 0   # 2: backend not configured, nothing ran


if __name__ == "__main__":
    sys.exit(main())

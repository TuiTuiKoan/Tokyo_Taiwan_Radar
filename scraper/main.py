"""
Main scraper orchestrator.

Runs all source scrapers, saves raw data to Supabase,
then runs the AI annotator to extract structured fields.

Usage:
    python main.py                              # normal run (scrape + save + annotate)
    python main.py --dry-run                    # scrape all, print JSON, no DB/AI calls
    python main.py --dry-run --source peatix    # scrape one source, print JSON
    python main.py --dry-run --source taiwan_cultural_center

Environment variables required (set in .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    OPENAI_API_KEY
"""

import argparse
import dataclasses
import json
import logging
import os
import re
import sys
import time
from datetime import datetime

from dotenv import load_dotenv

# Load .env file from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import sentry_sdk

_SENTRY_DSN = os.environ.get("SENTRY_DSN")
if _SENTRY_DSN:
    sentry_sdk.init(dsn=_SENTRY_DSN, traces_sample_rate=0.1)

from sources.taiwan_cultural_center import TaiwanCulturalCenterScraper
from sources.peatix import PeatixScraper
from sources.taioan_dokyokai import TaioanDokyokaiScraper
from sources.iwafu import IwafuScraper
from sources.taiwan_festival_tokyo import TaiwanFestivalTokyoScraper
from sources.koryu import KoryuScraper
from sources.taiwan_kyokai import TaiwanKyokaiScraper
from sources.doorkeeper import DoorkeeperScraper
from sources.connpass import ConnpassScraper
from sources.arukikata import ArukikataScraper
from sources.ide_jetro import IdeJetroScraper
from sources.taiwan_matsuri import TaiwanMatsuriScraper
from sources.eplus import EplusScraper
from sources.tokyonow import TokyoNowScraper
from sources.tokyocity_i import TokyoCityIScraper
from sources.ifi import IfiScraper
from sources.tuat_global import TuatGlobalScraper
from sources.jinf import JinfScraper
from sources.jats import JatsScraper
from sources.waseda_taiwan import WasedaTaiwanScraper
from sources.taiwanshi import TaiwanshiScraper
from sources.tobunken import TobunkenScraper
from sources.ks_cinema import KsCinemaScraper
from sources.cinemart_shinjuku import CinemartShinjukuScraper
from sources.kokuchpro import KokuchproScraper
from sources.taiwanbunkasai import TaiwanbunkasaiScraper
from sources.eiga_com import EigaComScraper
from sources.oaff import OaffScraper
from sources.jposa_ja import JposaJaScraper
from sources.taipei_fukuoka import TaipeiFukuokaScraper
from sources.yebizo import YebizoScraper
from sources.cineswitch_ginza import CineswitchGinzaScraper
from sources.human_trust_cinema import HumanTrustCinemaScraper
from sources.faam_fukuoka import FaamFukuokaScraper
from sources.note_creators import NoteCreatorsScraper
from sources.zinbun_kyoto import ZinbunKyotoScraper
from sources.uplink_cinema import UplinkCinemaScraper
from sources.eurospace import EurospaceScraper
from sources.tokyoartbeat import TokyoArtBeatScraper
from sources.hankyu_umeda import HankyuUmedaScraper
from sources.daimaru_matsuzakaya import DaimaruMatsuzakayaScraper
from sources.google_news_rss import GoogleNewsRssScraper
from sources.nhk_rss import NhkRssScraper
from sources.gguide_tv import GguideTvScraper
from sources.base import dedup_events
from database import upsert_events, _get_client
from annotator import annotate_pending_events
from merger import run_merger

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# All active scrapers — add new sources here
# ---------------------------------------------------------------------------
SCRAPERS = [
    TaiwanCulturalCenterScraper(),
    PeatixScraper(),
    TaioanDokyokaiScraper(),
    IwafuScraper(),
    TaiwanFestivalTokyoScraper(),
    KoryuScraper(),
    TaiwanKyokaiScraper(),
    DoorkeeperScraper(),
    ConnpassScraper(),
    ArukikataScraper(),
    IdeJetroScraper(),
    TaiwanMatsuriScraper(),
    EplusScraper(),
    TokyoNowScraper(),
    TokyoCityIScraper(),
    IfiScraper(),
    TuatGlobalScraper(),
    JinfScraper(),
    JatsScraper(),
    WasedaTaiwanScraper(),
    TaiwanshiScraper(),
    TobunkenScraper(),
    KsCinemaScraper(),
    CinemartShinjukuScraper(),
    KokuchproScraper(),
    EigaComScraper(),
    OaffScraper(),
    JposaJaScraper(),
    TaiwanbunkasaiScraper(),
    TaipeiFukuokaScraper(),
    YebizoScraper(),
    CineswitchGinzaScraper(),
    HumanTrustCinemaScraper(),
    FaamFukuokaScraper(),
    NoteCreatorsScraper(),
    ZinbunKyotoScraper(),
    UplinkCinemaScraper(),
    EurospaceScraper(),
    TokyoArtBeatScraper(),
    HankyuUmedaScraper(),
    DaimaruMatsuzakayaScraper(),
    GoogleNewsRssScraper(),
    NhkRssScraper(),
    GguideTvScraper(),
]


def _scraper_key(scraper) -> str:
    """Convert a scraper class name to its snake_case source key.

    e.g. TaiwanCulturalCenterScraper -> taiwan_cultural_center
         PeatixScraper                -> peatix
    """
    name = type(scraper).__name__
    name = re.sub(r"Scraper$", "", name)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def run(dry_run: bool = False, source: str | None = None, rescrape_ids: list[str] | None = None) -> None:
    active_scrapers = SCRAPERS

    if source:
        active_scrapers = [s for s in SCRAPERS if _scraper_key(s) == source]
        if not active_scrapers:
            available = ", ".join(_scraper_key(s) for s in SCRAPERS)
            logger.error("Unknown source %r. Available: %s", source, available)
            sys.exit(1)

    all_events = []
    rescrape_force_keys: set[tuple[str, str]] = set()
    if rescrape_ids:
        # Build (source_name, source_id) tuples from CLI-supplied source_ids.
        # Each ID is the full source_id value (e.g. "peatix_8134728").
        # We resolve source_name by querying the DB for each given source_id.
        if not dry_run:
            try:
                client = _get_client()
                resp = client.table("events").select("source_name,source_id").in_("source_id", rescrape_ids).execute()
                for row in (resp.data or []):
                    rescrape_force_keys.add((row["source_name"], row["source_id"]))
                if rescrape_force_keys:
                    logger.info("CLI --rescrape-ids: forcing re-scrape for %d event(s): %s",
                                len(rescrape_force_keys), rescrape_ids)
                else:
                    logger.warning("CLI --rescrape-ids: none of %s found in DB.", rescrape_ids)
            except Exception as exc:
                logger.warning("Could not pre-resolve --rescrape-ids: %s", exc)

    for scraper in active_scrapers:
        source_label = type(scraper).__name__
        source_key = _scraper_key(scraper)
        logger.info("=== Starting scraper: %s ===", source_label)
        try:
            scraper_start = time.time()
            events = scraper.scrape()
            events = dedup_events(events)
            logger.info("%s: scraped %d events", source_label, len(events))
            all_events.extend(events)

            if not dry_run:
                upsert_events(events, force_keys=rescrape_force_keys)
                try:
                    _get_client().table("scraper_runs").insert({
                        "source": source_key,
                        "events_processed": len(events),
                        "deepl_chars": getattr(scraper, "_deepl_chars_used", 0),
                        "success": True,
                        "duration_seconds": int(time.time() - scraper_start),
                    }).execute()
                    logger.info("%s: logged %d events to scraper_runs", source_label, len(events))
                except Exception as log_exc:
                    logger.warning("%s: could not write scraper_runs: %s", source_label, log_exc)
        except Exception as exc:
            logger.error("%s: scraper failed: %s", source_label, exc)
            if not dry_run:
                try:
                    _get_client().table("scraper_runs").insert({
                        "source": source_key,
                        "events_processed": 0,
                        "deepl_chars": 0,
                        "success": False,
                        "duration_seconds": int(time.time() - scraper_start),
                    }).execute()
                except Exception:
                    pass

    logger.info("Total events scraped: %d", len(all_events))

    if dry_run:
        logger.info("DRY RUN — skipping DB write and AI annotation")
        print(json.dumps(
            [dataclasses.asdict(e) for e in all_events],
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        ))
        return

    # Upsert is done per-source in the loop above.
    # Run cross-source duplicate merger first, then AI annotator.
    logger.info("Running cross-source duplicate merger...")
    run_merger()

    # Run AI annotator on pending events
    logger.info("Running AI annotator on pending events...")
    annotate_pending_events()

    logger.info("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tokyo Taiwan Radar scraper")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and print JSON output without writing to DB or calling OpenAI",
    )
    parser.add_argument(
        "--source",
        metavar="NAME",
        help="Only run the named scraper (e.g. peatix, taiwan_cultural_center)",
    )
    parser.add_argument(
        "--rescrape-ids",
        metavar="SOURCE_ID",
        nargs="+",
        help=(
            "Force re-scrape for one or more specific events by source_id "
            "(e.g. peatix_8134728). The event will be fully overwritten and "
            "annotation_status reset to pending."
        ),
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, source=args.source, rescrape_ids=args.rescrape_ids)

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
from datetime import datetime, timezone as _tz

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
from sources.zinbun_kyoto import ZinbunKyotoScraper
from sources.uplink_cinema import UplinkCinemaScraper
from sources.livepocket import LivepocketScraper
from sources.prtimes import PrtimesScraper
from sources.fukuoka_now import FukuokaNowScraper
from sources.maruhiro import MaruhiroScraper
from sources.eurospace import EurospaceScraper
from sources.tokyoartbeat import TokyoArtBeatScraper
from sources.hankyu_umeda import HankyuUmedaScraper
from sources.daimaru_matsuzakaya import DaimaruMatsuzakayaScraper
from sources.cinemarine import CineMarineScraper
from sources.eslite_spectrum import EsliteSpectrumScraper
from sources.moonromantic import MoonRomanticScraper
from sources.morc_asagaya import MorcAsagayaScraper
from sources.shin_bungeiza import ShinBungeizaScraper
from sources.ssff import SsffScraper
from sources.taiwan_faasai import TaiwanFaasaiScraper
from sources.tokyo_filmex import TokyoFilmexScraper
from sources.google_news_rss import GoogleNewsRssScraper
from sources.nhk_rss import NhkRssScraper
from sources.gguide_tv import GguideTvScraper
from sources.mot import MotScraper
from sources.transit_store import TransitStoreScraper
from sources.go_taiwan import GoTaiwanScraper
from sources.taiwan_festa import TaiwanFestaScraper
from sources.tiff import TiffJpScraper, TiffScraper
from sources.note_creators import NoteCreatorsScraper
from sources.artistcafe import ArtistcafeScraper
from sources.rightscube import RightscubeScraper
from sources.bookandbeer import BookandbeerScraper
from sources.hakusuisha import HakusuishaScraper
from sources.walkerplus import WalkerplusScraper
from sources.bigromanticrecords import BigRomanticRecordsScraper
from sources.waseda_icl import WasedaIclScraper
from sources.tsutaya_portal import TsutayaPortalScraper
from sources.sakurazaka import SakurazakaScraper
from sources.nagano_aioiza import NaganoAioizaScraper
from sources.cinemaclair import CinemaClairScraper
from sources.kyoto_cinema import KyotoCinemaScraper
from sources.kino_shinsaibashi import KinoCinemaShinsaibashiScraper
from sources.kawasaki_ac import KawasakiAcScraper
from sources.midland_cinema import MidlandCinemaScraper
from sources.onariza import OnarizaScraper
from sources.stranger import StrangerScraper
from sources.starcat_cinema import StarcatCinemaScraper
from sources.cine_gallery import CineGalleryScraper
from sources.wuext_waseda import WuextWasedaScraper
from sources.startup_terrace import StartupTerraceScraper
from sources.taiwan_prism import TaiwanPrismScraper
from sources.ftip import FtipScraper
from sources.acros_fukuoka import AcrosFukuokaScraper
from sources.amayaza import AmayazaScraper
from sources.asahiculture import AsahiCultureScraper
from sources.ciema import CiemaScraper
from sources.cinemadict import CinemadictScraper
from sources.cineplaza import CineplazaScraper
from sources.cinewind import CinewindScraper
from sources.ginsee import GinseeRobleScraper, GinseeHikarizaScraper
from sources.internet_museum import InternetMuseumScraper
from sources.johakyu import JohakyuScraper
from sources.kbc_cinema import KbcCinemaScraper
from sources.kgplus_kyotographie import KgplusKyotographieScraper
from sources.matsumoto_cinema_select import MatsumotoCinemaSelectScraper
from sources.nittai_toumonkai import NittaiToumonkaiScraper
from sources.otto import OttoScraper
from sources.placebymethod import PlacebymethodScraper
from sources.rti_jp import RtiJpScraper
from sources.snet_taiwan import SnetTaiwanScraper
from sources.theater_enya import TheaterEnyaScraper
from sources.theater_kino import TheaterKinoScraper
from sources.tsudoi_osaka import TsudoiOsakaScraper
from sources.ttcg_kansai import TtcgUmedaScraper, CinelibreKobeScraper
from sources.uedaeigeki import UedaEigekiScraper
from sources.united_cinemas import UnitedCinemasScraper
from sources.us_cinema_chiba import UsCinemaChibaGekijoScraper
from sources.whitestone_gallery import WhitestoneGalleryScraper
from sources.ycam_cinema import YcamCinemaScraper
from sources.base import dedup_events
from database import upsert_events, _get_client
from annotator import annotate_pending_events
from annotator import enrich_movie_titles, enrich_person_names
from merger import run_merger
from indexnow import submit_urls as _indexnow_submit, event_urls as _indexnow_event_urls

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
    FtipScraper(),
    IwafuScraper(),
    TaiwanFestivalTokyoScraper(),
    KoryuScraper(),
    TaiwanKyokaiScraper(),
    DoorkeeperScraper(),
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
    ZinbunKyotoScraper(),
    UplinkCinemaScraper(),
    LivepocketScraper(),
    FukuokaNowScraper(),
    PrtimesScraper(),
    MaruhiroScraper(),
    EurospaceScraper(),
    TokyoArtBeatScraper(),
    HankyuUmedaScraper(),
    DaimaruMatsuzakayaScraper(),
    CineMarineScraper(),
    EsliteSpectrumScraper(),
    MoonRomanticScraper(),
    MorcAsagayaScraper(),
    ShinBungeizaScraper(),
    SsffScraper(),
    TaiwanFaasaiScraper(),
    TokyoFilmexScraper(),
    GoogleNewsRssScraper(),
    NhkRssScraper(),
    GguideTvScraper(),
    MotScraper(),
    TransitStoreScraper(),
    GoTaiwanScraper(),
    TaiwanFestaScraper(),
    TiffJpScraper(),
    TiffScraper(),
    NoteCreatorsScraper(),
    ArtistcafeScraper(),
    RightscubeScraper(),
    BookandbeerScraper(),
    HakusuishaScraper(),
    WalkerplusScraper(),
    BigRomanticRecordsScraper(),
    WasedaIclScraper(),
    TsutayaPortalScraper(),
    SakurazakaScraper(),
    NaganoAioizaScraper(),
    CinemaClairScraper(),
    KyotoCinemaScraper(),
    KinoCinemaShinsaibashiScraper(),
    KawasakiAcScraper(),
    MidlandCinemaScraper(),
    OnarizaScraper(),
    StrangerScraper(),
    StarcatCinemaScraper(),
    CineGalleryScraper(),
    WuextWasedaScraper(),
    StartupTerraceScraper(),
    TaiwanPrismScraper(),
    # ---- Registered via T-0.1 audit (2026-05-25): orphaned but production-ready ----
    AcrosFukuokaScraper(),
    AmayazaScraper(),
    AsahiCultureScraper(),
    CiemaScraper(),
    CinemadictScraper(),
    CineplazaScraper(),
    CinewindScraper(),
    GinseeRobleScraper(),
    GinseeHikarizaScraper(),
    InternetMuseumScraper(),
    JohakyuScraper(),
    KbcCinemaScraper(),
    KgplusKyotographieScraper(),
    MatsumotoCinemaSelectScraper(),
    NittaiToumonkaiScraper(),
    OttoScraper(),
    PlacebymethodScraper(),
    RtiJpScraper(),
    SnetTaiwanScraper(),
    TheaterEnyaScraper(),
    TheaterKinoScraper(),
    TsudoiOsakaScraper(),
    TtcgUmedaScraper(),
    CinelibreKobeScraper(),
    UedaEigekiScraper(),
    UnitedCinemasScraper(),
    UsCinemaChibaGekijoScraper(),
    WhitestoneGalleryScraper(),
    YcamCinemaScraper(),
]

# ---------------------------------------------------------------------------
# Weekly-only sources — skip on non-Monday UTC days (unless _RUN_ALL or --source)
# ---------------------------------------------------------------------------
_RUN_ALL: bool = os.getenv("SCRAPER_RUN_ALL", "0") == "1"

WEEKLY_SOURCES: frozenset[str] = frozenset({
    "oaff", "tokyo_filmex", "tiff", "tiff_jp",
    "ifi", "waseda_icl", "tuat_global",
    "tokyo_now", "fukuoka_now", "hankyu_umeda",
    "nagano_aioiza", "maruhiro", "whitestone_gallery",
})


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


def _ensure_scrapers_registered() -> None:
    """Auto-insert a minimal research_sources row for every scraper in SCRAPERS that is not
    yet registered (i.e. no row with matching scraper_source_name exists).

    This runs on every non-dry-run execution so the admin /sources page stays in sync
    automatically — no manual DB step required when a new scraper is added to SCRAPERS.

    Inserted rows use:
      status='implemented', url='', url_verified=False
    The name defaults to the snake_case source key; edit in admin UI afterwards if needed.
    """
    scraper_keys = {_scraper_key(s) for s in SCRAPERS}
    try:
        client = _get_client()
        resp = client.table("research_sources").select("scraper_source_name").not_.is_(
            "scraper_source_name", "null"
        ).execute()
        registered = {row["scraper_source_name"] for row in (resp.data or [])}
        missing = scraper_keys - registered
        if not missing:
            logger.debug("research_sources sync OK — all %d scrapers registered", len(scraper_keys))
            return
        rows = [
            {
                "name": key,
                "url": "",
                "status": "implemented",
                "scraper_source_name": key,
                "url_verified": False,
            }
            for key in sorted(missing)
        ]
        client.table("research_sources").insert(rows).execute()
        logger.info(
            "✅ Auto-registered %d new scraper(s) in research_sources: %s",
            len(rows),
            [r["scraper_source_name"] for r in rows],
        )
    except Exception as exc:
        logger.warning("research_sources auto-register skipped: %s", exc)


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
    all_new_event_ids: list[str] = []  # UUIDs of newly-inserted events (for IndexNow)

    # Auto-register any scrapers in SCRAPERS that are missing from research_sources.
    # Runs on every non-dry-run so the admin /sources page stays in sync automatically.
    if not dry_run:
        _ensure_scrapers_registered()

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

    _is_monday_utc = datetime.now(_tz.utc).weekday() == 0

    for scraper in active_scrapers:
        source_label = type(scraper).__name__
        source_key = _scraper_key(scraper)
        if source is None and not _RUN_ALL and source_key in WEEKLY_SOURCES and not _is_monday_utc:
            logger.info("Skipping %s (weekly-only, today is not Monday UTC)", source_key)
            continue
        logger.info("=== Starting scraper: %s ===", source_label)
        try:
            scraper_start = time.time()
            events = scraper.scrape()
            events = dedup_events(events)
            logger.info("%s: scraped %d events", source_label, len(events))
            all_events.extend(events)

            if not dry_run:
                new_ids = upsert_events(events, force_keys=rescrape_force_keys)
                all_new_event_ids.extend(new_ids)
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

    # Enrich movie titles and person names (same as CI pipeline steps)
    logger.info("Enriching movie titles from eiga.com...")
    enrich_movie_titles()
    logger.info("Enriching person names via eiga.com + Wikipedia...")
    enrich_person_names()

    # Ended events are no longer auto-archived here.
    # Public visibility is controlled by frontend time filters (timeMode/end_date).

    # Submit newly-inserted event URLs to IndexNow (Bing relay → ChatGPT Search)
    if all_new_event_ids:
        logger.info("IndexNow: submitting %d new event URL(s)...", len(all_new_event_ids))
        try:
            urls = _indexnow_event_urls(all_new_event_ids)
            _indexnow_submit(urls)
        except Exception as exc:
            logger.warning("IndexNow submission error (non-fatal): %s", exc)

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

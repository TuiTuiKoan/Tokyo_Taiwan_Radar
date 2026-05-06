"""
estat_population.py — 都道府県別総人口（e-Stat 人口推計）

statsDataId: 0003448237 (人口推計 都道府県×年齢×男女別)
Update cycle: annual (October 1st reference date)
Unit: 千人 (thousands)
License: CC BY 4.0 (政府統計ポータル e-Stat)

Usage:
    python estat_population.py --year 2024 [--dry-run]
    python estat_population.py --all [--dry-run]     # 2020-2024
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from external_stats.base import ExternalStatsBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_STATS_DATA_ID = "0003448237"
_ESTAT_API_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
_META_API_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json/getMetaInfo"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Prefecture area code → name mapping (e-Stat codes: 01000 = 北海道 ... 47000 = 沖縄県)
_AREA_CODE_TO_NAME: dict[str, str] = {
    "01000": "北海道", "02000": "青森県", "03000": "岩手県", "04000": "宮城県",
    "05000": "秋田県", "06000": "山形県", "07000": "福島県", "08000": "茨城県",
    "09000": "栃木県", "10000": "群馬県", "11000": "埼玉県", "12000": "千葉県",
    "13000": "東京都", "14000": "神奈川県", "15000": "新潟県", "16000": "富山県",
    "17000": "石川県", "18000": "福井県", "19000": "山梨県", "20000": "長野県",
    "21000": "岐阜県", "22000": "静岡県", "23000": "愛知県", "24000": "三重県",
    "25000": "滋賀県", "26000": "京都府", "27000": "大阪府", "28000": "兵庫県",
    "29000": "奈良県", "30000": "和歌山県", "31000": "鳥取県", "32000": "島根県",
    "33000": "岡山県", "34000": "広島県", "35000": "山口県", "36000": "徳島県",
    "37000": "香川県", "38000": "愛媛県", "39000": "高知県", "40000": "福岡県",
    "41000": "佐賀県", "42000": "長崎県", "43000": "熊本県", "44000": "大分県",
    "45000": "宮崎県", "46000": "鹿児島県", "47000": "沖縄県",
}

# Area code → 2-digit prefecture code
_AREA_TO_PREF_CODE: dict[str, str] = {
    k: k[:2] for k in _AREA_CODE_TO_NAME
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _discover_time_codes(app_id: str) -> dict[int, str]:
    """
    Fetch metadata to build {year: time_code} mapping dynamically.
    Example: {2020: '1601', 2021: '1301', 2022: '1701', 2023: '1801', 2024: '1901'}
    """
    import re
    r = requests.get(
        _META_API_BASE,
        params={"appId": app_id, "statsDataId": _STATS_DATA_ID},
        headers=_HEADERS,
        timeout=15,
    )
    r.raise_for_status()
    d = r.json()
    cls_inf = (
        d.get("GET_META_INFO", {})
        .get("METADATA_INF", {})
        .get("CLASS_INF", {})
        .get("CLASS_OBJ", [])
    )
    if not isinstance(cls_inf, list):
        cls_inf = [cls_inf]

    mapping: dict[int, str] = {}
    for c in cls_inf:
        if c.get("@id") == "time":
            classes = c.get("CLASS", [])
            if not isinstance(classes, list):
                classes = [classes]
            for cls in classes:
                name = cls.get("@name", "")
                code = cls.get("@code", "")
                m = re.match(r"(\d{4})年", name)
                if m:
                    mapping[int(m.group(1))] = code
    logger.debug("Time code mapping: %s", mapping)
    return mapping


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------
class EstatPopulationPuller(ExternalStatsBase):
    """
    都道府県別総人口（e-Stat 人口推計）を年1回取得。

    Returns: list of records for external_stats_population table.
    Unit: 千人 (thousands) — stored as-is in population_1000 column.
    """

    source_name = "estat-population"
    license_code = "CC-BY-4.0"

    def _table_name(self) -> str:
        return "external_stats_population"

    def fetch(self, app_id: str, year: int, **kwargs) -> dict:  # type: ignore[override]
        """
        Call e-Stat API for prefecture total population for the given year.

        Args:
            app_id: e-Stat application ID
            year:   Reference year (e.g. 2024 → October 1, 2024)

        Returns:
            Raw API response dict.
        """
        time_codes = _discover_time_codes(app_id)
        time_code = time_codes.get(year)
        if not time_code:
            available = sorted(time_codes.keys())
            raise ValueError(
                f"Year {year} not available. Known years: {available}"
            )

        r = requests.get(
            _ESTAT_API_BASE,
            params={
                "appId": app_id,
                "statsDataId": _STATS_DATA_ID,
                "cdCat01": "000",    # 男女計
                "cdCat02": "01000",  # 年齢総数
                "cdCat03": "001",    # 総人口
                "cdTimeFrom": time_code,
                "cdTimeTo": time_code,
                "limit": 60,
            },
            headers=_HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        d = r.json()
        status = d.get("GET_STATS_DATA", {}).get("RESULT", {})
        if status.get("STATUS") != 0:
            raise RuntimeError(
                f"e-Stat API error {status.get('STATUS')}: {status.get('ERROR_MSG','')}"
            )
        logger.info("Fetched population data for year %d (time_code=%s)", year, time_code)
        return d

    def parse(self, raw: dict, year: int, **kwargs) -> list[dict]:  # type: ignore[override]
        """
        Parse e-Stat response and return prefecture population records.

        Returns:
            list of dicts with keys:
                year            int    e.g. 2024
                prefecture      str    e.g. "東京都"
                pref_code       str    e.g. "13"
                population_1000 int    in thousands (e.g. 14043)
                source          str    "estat-population"
                license         str    "CC-BY-4.0"
        """
        values = (
            raw.get("GET_STATS_DATA", {})
            .get("STATISTICAL_DATA", {})
            .get("DATA_INF", {})
            .get("VALUE", [])
        )
        if not isinstance(values, list):
            values = [values]

        records: list[dict] = []
        for v in values:
            area = v.get("@area", "")
            if area == "00000":
                continue  # Skip 全国 total
            if area not in _AREA_CODE_TO_NAME:
                continue

            pref_name = _AREA_CODE_TO_NAME[area]
            pref_code = _AREA_TO_PREF_CODE[area]

            raw_val = v.get("$", "")
            try:
                pop_1000 = int(raw_val)
            except (ValueError, TypeError):
                pop_1000 = 0

            records.append(
                {
                    "year": year,
                    "prefecture": pref_name,
                    "pref_code": pref_code,
                    "population_1000": pop_1000,
                    "source": self.source_name,
                    "license_code": self.license_code,
                }
            )

        logger.info("Parsed %d prefecture records for year %d", len(records), year)
        return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main() -> None:
    import argparse
    from dotenv import load_dotenv
    from supabase import create_client

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    load_dotenv(Path(__file__).parent.parent / ".env")

    parser = argparse.ArgumentParser(
        description="Pull e-Stat 人口推計 (prefecture total population)"
    )
    parser.add_argument("--year", type=int, help="Reference year (e.g. 2024)")
    parser.add_argument("--all", action="store_true", help="Pull all available years")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    app_id = os.environ["ESTAT_APP_ID"]
    url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(url, key)

    puller = EstatPopulationPuller(sb, dry_run=args.dry_run)

    time_codes = _discover_time_codes(app_id)
    available_years = sorted(time_codes.keys())

    years_to_fetch: list[int]
    if args.all:
        years_to_fetch = available_years
    elif args.year:
        years_to_fetch = [args.year]
    else:
        parser.print_help()
        sys.exit(1)

    for year in years_to_fetch:
        try:
            raw = puller.fetch(app_id=app_id, year=year)
            records = puller.parse(raw, year=year)
            if args.dry_run:
                print(f"\n=== Year {year} ===")
                for rec in records[:3]:
                    print(rec)
                print(f"  ... ({len(records)} total)")
            else:
                puller.upsert(puller._table_name(), records)
        except Exception as exc:
            logger.error("Failed for year %d: %s", year, exc)


if __name__ == "__main__":
    _main()

"""
moj_residents.py — 在留外国人統計（MOJ ISA → e-Stat XLSX）

調査: 年2回（6月末・12月末）
対象: 都道府県別 台湾籍在留者数
出典: 出入国在留管理庁 → e-Stat テーブルデータ
ライセンス: 政府統計の総合窓口利用規約（jp-gov-pdl-1.0）

Usage:
    python moj_residents.py --year 2024 --period 12 [--dry-run]
    python moj_residents.py --year 2024 --period 6  [--dry-run]
    python moj_residents.py --all [--dry-run]         # all known periods
"""
from __future__ import annotations

import io
import logging
import re
import sys
import unicodedata
from pathlib import Path
from typing import Optional

import openpyxl
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from external_stats.base import ExternalStatsBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MOJ_PAGE = (
    "https://www.moj.go.jp/isa/policies/statistics/toukei_ichiran_touroku.html"
)
_ESTAT_BASE = "https://www.e-stat.go.jp"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
}

# Fullwidth digit map for converting year text (２０２４ → 2024)
_FW_DIGIT = {
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
}


def _fw_to_ascii(s: str) -> str:
    """Convert fullwidth digits to ASCII digits."""
    return "".join(_FW_DIGIT.get(c, c) for c in s)


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------
class MojResidentsPuller(ExternalStatsBase):
    """
    在留外国人統計（台湾籍・都道府県別）を e-Stat XLSX から取得。

    Data chain:
      1. MOJ ISA page   → find e-Stat lid by year/period
      2. e-Stat list    → find statInfId for テーブルデータ t1 (都道府県×国籍)
      3. e-Stat download → XLSX → openpyxl parse
    """

    source_name = "moj-isa"
    license_code = "jp-gov-pdl-1.0"

    def _table_name(self) -> str:
        return "external_stats_resident_taiwanese"

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def _discover_lid(self, year: int, period: int) -> Optional[str]:
        """
        Find e-Stat list LID from MOJ ISA page for given year and period.

        Args:
            year:   Gregorian year (e.g. 2024)
            period: 6 (June) or 12 (December)

        Returns:
            lid string like '000001462230', or None if not found.
        """
        r = requests.get(_MOJ_PAGE, headers=_HEADERS, timeout=20)
        r.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.content, "html.parser")

        # Convert year to fullwidth (2024 → ２０２４)
        fw_year = "".join(
            chr(ord(c) + 0xFEE0) if c.isdigit() else c for c in str(year)
        )

        # Build expected text patterns for the link
        if period == 12:
            patterns = [
                f"{fw_year}年１２月末",
                f"{fw_year}年12月末",
            ]
        elif period == 6:
            patterns = [
                f"{fw_year}年\u3000６月末",   # ideographic space
                f"{fw_year}年　６月末",         # full-width space
                f"{fw_year}年 ６月末",          # regular space
                f"{fw_year}年６月末",
                f"{fw_year}年6月末",
            ]
        else:
            raise ValueError(f"period must be 6 or 12, got {period}")

        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            # Normalise whitespace for comparison
            norm = re.sub(r"\s+", "", text)
            for p in patterns:
                if re.sub(r"\s+", "", p) in norm:
                    href = a["href"]
                    m = re.search(r"lid=(\d+)", href)
                    if m:
                        logger.debug("Found lid %s for %d-%02d", m.group(1), year, period)
                        return m.group(1)

        logger.warning("lid not found on MOJ ISA page for %d period %d", year, period)
        return None

    def _discover_statinf_id(self, lid: str) -> Optional[str]:
        """
        From an e-Stat list page (lid), find the statInfId for the
        prefecture×nationality table data file (表番号 YY-MM-t1).

        We identify it by: title contains 'テーブルデータ' AND '都道府県'.
        """
        url = f"{_ESTAT_BASE}/stat-search/files?lid={lid}&layout=datalist"
        r = requests.get(url, headers=_HEADERS, timeout=20)
        r.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.content, "html.parser")

        # Find <li> or <tr> items that contain an EXCEL download link AND
        # whose text includes テーブルデータ + 都道府県.
        # We use li/tr only (not div) to avoid parent containers that would
        # match first but contain multiple unrelated download links.
        for item in soup.select("li, tr, article"):
            text = item.get_text(" ", strip=True)
            if "テーブルデータ" in text and "都道府県" in text:
                links = [
                    a["href"]
                    for a in item.find_all("a", href=True)
                    if "statInfId=" in a["href"] and "fileKind=0" in a["href"]
                ]
                if links:
                    m = re.search(r"statInfId=(\d+)", links[0])
                    if m:
                        logger.debug("Found statInfId %s for lid %s", m.group(1), lid)
                        return m.group(1)

        logger.warning("statInfId not found on e-Stat list page (lid=%s)", lid)
        return None

    # ------------------------------------------------------------------
    # ExternalStatsBase interface
    # ------------------------------------------------------------------

    def fetch(self, year: int, period: int, **kwargs) -> bytes:  # type: ignore[override]
        """
        Download the prefecture×nationality XLSX for year/period.

        Args:
            year:   Survey year (e.g. 2024)
            period: 6 or 12

        Returns:
            Raw XLSX bytes.
        """
        lid = self._discover_lid(year, period)
        if not lid:
            raise RuntimeError(
                f"Could not find e-Stat lid for {year} period {period}"
            )

        stat_inf_id = self._discover_statinf_id(lid)
        if not stat_inf_id:
            raise RuntimeError(
                f"Could not find statInfId for lid={lid} ({year} period {period})"
            )

        url = (
            f"{_ESTAT_BASE}/stat-search/file-download"
            f"?statInfId={stat_inf_id}&fileKind=0"
        )
        logger.info("Downloading XLSX from %s", url)
        r = requests.get(url, headers=_HEADERS, timeout=60)
        r.raise_for_status()
        logger.info("Downloaded %d bytes", len(r.content))
        return r.content

    def parse(self, raw: bytes, year: int, period: int, **kwargs) -> list[dict]:  # type: ignore[override]
        """
        Parse the pivot-table XLSX and return records for Taiwan by prefecture.

        XLSX structure (as of 2024-12 version):
          Row 1-5: Filter labels (在留資格 = すべて, etc.)
          Row 6:   Column section label ("合計 / 在留外国人数", "列ラベル", ...)
          Row 7:   Header row — nationality codes  e.g. "01_022：台湾"
          Row 8+:  Prefecture rows  e.g. "01：北海道"  with counts per nationality

        Returns:
            list of dicts with keys:
                year_month   str   e.g. "2024-12"
                prefecture   str   e.g. "東京都"
                pref_code    str   e.g. "13"
                count        int
                source       str   "moj-isa"
                license      str   "jp-gov-pdl-1.0"
        """
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb.active

        year_month = f"{year}-{period:02d}"

        # ---- Scan rows to find header and data ----
        header_row_idx = None
        taiwan_col_idx = None
        header_row_values: list = []

        # We'll collect all rows first (worksheet may be large)
        all_rows: list[tuple] = []
        for row in ws.iter_rows(values_only=True):
            all_rows.append(row)

        # Find header row: first row where any cell contains '台湾'
        for i, row in enumerate(all_rows):
            for j, cell in enumerate(row):
                if cell and "台湾" in str(cell):
                    header_row_idx = i
                    taiwan_col_idx = j
                    header_row_values = list(row)
                    break
            if header_row_idx is not None:
                break

        if header_row_idx is None or taiwan_col_idx is None:
            raise ValueError(
                "Could not locate Taiwan column in XLSX "
                f"(year={year}, period={period})"
            )

        logger.info(
            "Header row at index %d, Taiwan column at index %d (%s)",
            header_row_idx,
            taiwan_col_idx,
            header_row_values[taiwan_col_idx],
        )

        # ---- Extract prefecture rows ----
        records: list[dict] = []
        # Rows with prefecture data start after the header
        # Prefecture code format: "NN：XXX"  (01：北海道 ... 47：沖縄県)
        pref_pattern = re.compile(r"^(\d{2})：(.+)$")

        for row in all_rows[header_row_idx + 1:]:
            if not row or not row[0]:
                continue
            cell0 = str(row[0]).strip()
            m = pref_pattern.match(cell0)
            if not m:
                continue  # Skip 総計, 未定・不詳, empty rows

            pref_code = m.group(1)
            pref_name = m.group(2).strip()

            # Skip 未定・不詳 (code 48 or '48')
            if pref_code == "48":
                continue

            raw_count = row[taiwan_col_idx] if taiwan_col_idx < len(row) else None
            if raw_count is None or raw_count == "":
                count = 0
            else:
                try:
                    count = int(raw_count)
                except (ValueError, TypeError):
                    count = 0

            records.append(
                {
                    "year_month": year_month,
                    "prefecture": pref_name,
                    "pref_code": pref_code,
                    "count": count,
                    "source": self.source_name,
                    "license_code": self.license_code,
                }
            )

        logger.info("Parsed %d prefecture records for %s", len(records), year_month)
        return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main() -> None:
    import argparse
    import os

    from dotenv import load_dotenv
    from supabase import create_client

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    load_dotenv(Path(__file__).parent.parent / ".env")

    parser = argparse.ArgumentParser(
        description="Pull MOJ ISA 在留外国人統計 (Taiwan residents by prefecture)"
    )
    parser.add_argument("--year", type=int, help="Survey year (e.g. 2024)")
    parser.add_argument(
        "--period",
        type=int,
        choices=[6, 12],
        help="Survey period: 6 (June) or 12 (December)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Pull all known periods from 2012 to latest",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(url, key)

    puller = MojResidentsPuller(sb, dry_run=args.dry_run)

    if args.all:
        import datetime
        current_year = datetime.date.today().year
        errors: list[str] = []
        for year in range(2012, current_year + 1):
            for period in (6, 12):
                try:
                    raw = puller.fetch(year=year, period=period)
                    records = puller.parse(raw, year=year, period=period)
                    puller.upsert(puller._table_name(), records)
                except Exception as exc:
                    logger.warning("Skipping %d-%02d: %s", year, period, exc)
                    errors.append(f"{year}-{period:02d}: {exc}")
        if errors:
            print(f"\nSkipped {len(errors)} periods (not yet published or error):")
            for e in errors:
                print(f"  {e}")
    elif args.year and args.period:
        raw = puller.fetch(year=args.year, period=args.period)
        records = puller.parse(raw, year=args.year, period=args.period)
        if args.dry_run:
            for rec in records:
                print(rec)
        else:
            puller.upsert(puller._table_name(), records)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    _main()

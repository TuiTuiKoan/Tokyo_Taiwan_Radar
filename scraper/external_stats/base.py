"""
base.py — ExternalStatsBase ABC for government open data pull pipelines.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class ExternalStatsBase(ABC):
    """
    Abstract base for external statistics pullers.

    Subclasses implement fetch() and parse(), then call upsert() with the
    normalised record dict.
    """

    source_name: str  # must be overridden
    license_code: str  # 'jp-gov-pdl-1.0' | 'CC-BY-4.0'

    def __init__(self, sb_client, dry_run: bool = False):
        self.sb = sb_client
        self.dry_run = dry_run

    @abstractmethod
    def fetch(self, **kwargs) -> Any:
        """Download raw data. Return whatever parse() needs."""

    @abstractmethod
    def parse(self, raw: Any, **kwargs) -> list[dict]:
        """Return list of normalised record dicts ready for upsert."""

    def upsert(self, table: str, records: list[dict]) -> int:
        """
        Upsert records into Supabase table. Returns count of upserted rows.
        Skips if dry_run=True.
        """
        if not records:
            return 0
        if self.dry_run:
            logger.info("[DRY-RUN] Would upsert %d rows to %s", len(records), table)
            for r in records:
                logger.info("  %s", r)
            return 0
        result = self.sb.table(table).upsert(records).execute()
        count = len(result.data) if result.data else len(records)
        logger.info("Upserted %d rows to %s", count, table)
        return count

    def run(self, **kwargs) -> int:
        """Full pipeline: fetch → parse → upsert. Returns row count."""
        raw = self.fetch(**kwargs)
        records = self.parse(raw, **kwargs)
        table = self._table_name()
        return self.upsert(table, records)

    def _table_name(self) -> str:
        raise NotImplementedError("Subclass must implement _table_name()")

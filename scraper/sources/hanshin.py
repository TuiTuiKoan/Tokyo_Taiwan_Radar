"""
Scraper for 阪神百貨店 (Hanshin department stores) — weekly event schedules.

Hanshin is the sister department store of Hankyu within the H2O Retailing group,
and shares the **same H2O CMS** as ``hankyu.py`` (confirmed 2026-07-10: identical
``article > div.o-event > p.o-event__title`` + ``p.o-event__desc`` +
``div.o-event__detail`` structure, same ``[◎●]`` date markers). Rather than
duplicate the parser, this module **reuses** ``_HankyuBase`` and only overrides
``_store`` to point at a Hanshin store registry.

Only the domain and store metadata differ:
  - Hanshin domain: ``www.hanshin-dept.jp`` (Hankyu is ``www.hankyu-dept.co.jp``);
    ``_Store.base_url`` already supports a per-store base URL.

Enabled stores (2026-07):
  - hanshin_umeda  阪神梅田本店  /hshonten/event/  (Osaka) — hosts 「阪神の台湾展」

Adding another verified Hanshin branch (e.g. 西宮 / 御影 / 尼崎) is a one-line
entry in ``_HANSHIN_STORES`` once its ``/event/`` page is confirmed.
"""

from .hankyu import _HankyuBase, _Store

_HANSHIN_BASE_URL = "https://www.hanshin-dept.jp"

_HANSHIN_STORES: dict[str, _Store] = {
    "hanshin_umeda": _Store(
        source_name="hanshin_umeda",
        display_name="阪神梅田本店",
        event_url=f"{_HANSHIN_BASE_URL}/hshonten/event/",
        base_url=_HANSHIN_BASE_URL,
        location_address="大阪府大阪市北区梅田1-13-13 阪神梅田本店",
        location_prefectures=("大阪府",),
    ),
}


class _HanshinBase(_HankyuBase):
    """Shared H2O-CMS scrape/parse (inherited from ``_HankyuBase``) for Hanshin.

    Only ``_store`` is overridden to resolve against the Hanshin registry;
    all parsing (date parser, two-tier Taiwan filter, ``_fetch_taiwan_detail_evidence``,
    ``_build_source_id``, scrape/parse) is reused from ``_HankyuBase``.
    """

    @property
    def _store(self) -> _Store:
        return _HANSHIN_STORES[self._STORE_KEY]


class HanshinUmedaScraper(_HanshinBase):
    """阪神梅田本店 (Osaka) — weekly event schedule."""

    SOURCE_NAME = "hanshin_umeda"
    _STORE_KEY = "hanshin_umeda"

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
  - hanshin_umeda        阪神梅田本店      /hshonten/event/     (Osaka) — hosts 「阪神の台湾展」
  - hanshin_nishinomiya  阪神・にしのみや  /nishinomiya/event/  (Hyogo)
  - hanshin_mikage       阪神・御影        /mikage/event/       (Hyogo)
  - hanshin_amagasaki    あまがさき阪神    /amagasaki/event/    (Hyogo)

The three Hyogo branches share the identical H2O CMS (confirmed 2026-07-10) and
are low-volume (0 Taiwan events at time of adding); the two-tier filter still
catches occasional Taiwan/Asia fairs. Adding another verified Hanshin branch is
a one-line entry in ``_HANSHIN_STORES`` (plus a concrete class) once its
``/event/`` page is confirmed.
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
    "hanshin_nishinomiya": _Store(
        source_name="hanshin_nishinomiya",
        display_name="阪神・にしのみや",
        event_url=f"{_HANSHIN_BASE_URL}/nishinomiya/event/",
        base_url=_HANSHIN_BASE_URL,
        location_address="兵庫県西宮市田中町1-26 阪神・にしのみや",
        location_prefectures=("兵庫県",),
    ),
    "hanshin_mikage": _Store(
        source_name="hanshin_mikage",
        display_name="阪神・御影",
        event_url=f"{_HANSHIN_BASE_URL}/mikage/event/",
        base_url=_HANSHIN_BASE_URL,
        location_address="兵庫県神戸市東灘区御影中町3丁目2番1号 阪神・御影",
        location_prefectures=("兵庫県",),
    ),
    "hanshin_amagasaki": _Store(
        source_name="hanshin_amagasaki",
        display_name="あまがさき阪神",
        event_url=f"{_HANSHIN_BASE_URL}/amagasaki/event/",
        base_url=_HANSHIN_BASE_URL,
        location_address="兵庫県尼崎市潮江1丁目3番1号 あまがさき阪神",
        location_prefectures=("兵庫県",),
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


class HanshinNishinomiyaScraper(_HanshinBase):
    """阪神・にしのみや (Nishinomiya, Hyogo) — weekly event schedule."""

    SOURCE_NAME = "hanshin_nishinomiya"
    _STORE_KEY = "hanshin_nishinomiya"


class HanshinMikageScraper(_HanshinBase):
    """阪神・御影 (Mikage, Kobe, Hyogo) — weekly event schedule."""

    SOURCE_NAME = "hanshin_mikage"
    _STORE_KEY = "hanshin_mikage"


class HanshinAmagasakiScraper(_HanshinBase):
    """あまがさき阪神 (Amagasaki, Hyogo) — weekly event schedule."""

    SOURCE_NAME = "hanshin_amagasaki"
    _STORE_KEY = "hanshin_amagasaki"

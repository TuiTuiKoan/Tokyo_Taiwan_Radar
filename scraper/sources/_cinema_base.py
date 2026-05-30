"""共通電影院 scraper 基底模組。

提供 CinemaScraper 基底類別與工具函式，供各固定電影院 scraper 繼承使用。
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from sources.base import BaseScraper

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_TAIWAN_KEYWORDS = [
    "台湾", "Taiwan", "臺灣", "台灣",
    "台湾映画", "台湾電影", "台北", "台中",
    "金馬", "金马",
]

_STATUS_WORDS = re.compile(
    r'[　 ]*(?:上映中|公開中|公開終了|好評上映中|近日公開|先行上映|絶賛上映中|上映予定)\s*$'
)


def _normalize_film_title(name_ja: str) -> str:
    """片名正規化（用於 source_id hash 輸入）。

    - 去除前後空白、全形空白（U+3000）
    - 全形英數 → 半形（NFKC）
    - 統一 dash：－—― → -（ー U+30FC 長音符不替換，為カタカナ語音成分）
    - 剝除尾部狀態詞（上映中 等），不剝除版本資訊（4K修復版 等）
    """
    text = name_ja.strip().replace("\u3000", " ")
    text = unicodedata.normalize("NFKC", text)
    for ch in "－—―":
        text = text.replace(ch, "-")
    text = _STATUS_WORDS.sub("", text).strip()
    return text


def make_film_source_id(cinema_slug: str, name_ja: str) -> str:
    """以「戲院 slug + 正規化片名」生成穩定 source_id。

    hash = MD5(f"{cinema_slug}:{normalized_title}")[:12]
    returns f"{cinema_slug}_{hash}"
    """
    normalized = _normalize_film_title(name_ja)
    h = hashlib.md5(f"{cinema_slug}:{normalized}".encode()).hexdigest()[:12]
    return f"{cinema_slug}_{h}"


class CinemaScraper(BaseScraper):
    """固定電影院 scraper 基底類別。

    子類別需定義 source_name 並實作 scrape()。
    """

    def make_session(self, verify_ssl: bool = True, retry: bool = True) -> requests.Session:
        """建立統一 UA + retry 的 HTTP session。"""
        session = requests.Session()
        session.headers["User-Agent"] = _UA
        if retry:
            adapter = HTTPAdapter(
                max_retries=Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504],
                )
            )
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        session.verify = verify_ssl
        return session

    def is_taiwan_relevant(self, text: str) -> bool:
        """台湾關連テキスト判定。"""
        return any(kw in text for kw in _TAIWAN_KEYWORDS)

    def make_film_source_id(self, cinema_slug: str, name_ja: str) -> str:
        """instance method ラッパー（モジュール関数への委譲）。"""
        return make_film_source_id(cinema_slug, name_ja)

    def set_fixed_venue(
        self,
        event_dict: dict[str, Any],
        location_name: str,
        location_address: str,
        location_prefectures: list[str],
    ) -> None:
        """固定場地欄位 + organizer_type の設定 helper。"""
        event_dict["location_name"] = location_name
        event_dict["location_address"] = location_address
        event_dict["location_prefectures"] = location_prefectures
        event_dict.setdefault("organizer_type", ["commercial_brand"])

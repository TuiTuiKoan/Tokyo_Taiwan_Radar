"""Shared Taiwan keyword regex for keyword-search sources (spec coverage-audit Phase A).

Used by prtimes (title filter) and google_news_rss (title + description filter).

Besides the plain names, titles such as 「日中台：交錯するまなざし」「日台交流」
「台日友好」 name Taiwan only inside a compound (#701). The compounds are bare
substrings of very common Japanese words, so each one carries context guards:

- 日中台 must not continue as 日中台風 (日中 + 台風) or 日中台頭.
- 日台 must not be the tail of 今日／本日／毎日／昨日／明日／前日／翌日／当日／
  連日／終日／平日／休日／祝日／曜日／土日, and must
  not continue as 台数／台風／台所／台帳／台車／台本／台詞.
- 台日 must not be the tail of 舞台／屋台／灯台／高台／演台／土台／寝台／鏡台／
  番台／縁台／荷台, and must not continue as 日本 (舞台日本公演 etc.).

「中台」alone is not a Taiwan signal (中台禅寺), and city names are not added
here; widen only with evidence from the weekly coverage audit.
"""
from __future__ import annotations

import re

_PLAIN = r"台湾|台灣|臺灣|(?i:taiwan)"
_NICHUTAI = r"日中台(?![風頭])"
_NITTAI = r"(?<![今本毎昨明前翌当連終平休祝曜土])日台(?![数風所帳車本詞])"
_TAINICHI = r"(?<![舞屋灯高演土寝鏡番縁荷])台日(?!本)"

TAIWAN_TITLE_RE = re.compile("|".join((_PLAIN, _NICHUTAI, _NITTAI, _TAINICHI)))
PLAIN_TAIWAN_RE = re.compile(_PLAIN)


def has_taiwan_keyword(text: str) -> bool:
    return bool(TAIWAN_TITLE_RE.search(text or ""))


def compound_only(text: str) -> bool:
    """True when text names Taiwan only through a compound (日中台／日台／台日)."""
    text = text or ""
    return has_taiwan_keyword(text) and not PLAIN_TAIWAN_RE.search(text)

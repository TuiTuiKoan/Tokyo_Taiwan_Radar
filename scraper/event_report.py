"""Event-report (活動報導) detection — spec no-event-reports (2026-11-22).

Tokyo Taiwan Radar no longer lists event reports: pages whose main content
recaps an event that has already ended (トークイベント レポート, 開催報告,
活動記録, 〜が閉幕 …). Readers cannot attend them, so they are not events.

This module is the single deterministic judgement shared by scrapers, the
annotator gate and the one-off retirement script. It only looks at the title:
descriptions of upcoming events often mention a past edition ("前回のレポート
はこちら"), so body text is left to the annotator's GPT verdict.

Not event reports (kept as events):
  - upcoming 報告会 / 成果報告会 / 活動報告会 — attendable presentations;
  - pure publication records (event_form == ['publication']), e.g. 調査報告書;
  - TV / radio broadcasts (event_form only 'broadcast').
"""

from __future__ import annotations

import re
from typing import Iterable

from publication_rules import normalize_event_forms

EVENT_REPORT_REASON = "auto-deactivated: event report (post-event recap)"

# Composite recap terms only. Bare 報告 / 記録 are too broad (研究報告,
# 記録を更新, 記録映画), so they never match on their own.
_RECAP_RE = re.compile(
    r"レポート(?!ー)"            # イベントレポート, 現地レポート (not レポーター)
    r"|レポ(?![ーぉ])(?=[\s！!】」』≫)）\]|｜]|$)"  # 鑑賞レポ, 参加レポ at a word end
    r"|開催報告|実施報告|活動報告|参加報告|視察報告"
    r"|活動記録|開催記録|鑑賞記録|イベント記録"
    r"|が閉幕|閉幕しました|閉幕！|盛況のうちに閉幕"
    r"|行ってきた|観てきた|見てきた|参加してきた"
    r"|^【結果発表】"              # results post; a bare 結果発表 can be a contest's schedule
    r"|活動紀錄|活動報導|活動回顧|精彩回顧|活動側記"
    r"|\brecap\b|\bevent report\b",
    re.IGNORECASE,
)

# A recap term immediately followed by 会 is an upcoming presentation event
# (活動報告会, 視察報告会), not a report article. 報告書 is a document.
_UPCOMING_PRESENTATION_RE = re.compile(r"(報告|レポート)(会|書|集)")

# Whole-title veto: a title that announces or recruits for something is an
# upcoming event even when it also contains a recap word
# (「台湾に行ってきた！視察報告会」, 「フォトコンテスト 参加者募集」).
_UPCOMING_TITLE_RE = re.compile(
    r"報告会|発表会|説明会|のお知らせ|募集|開催決定|開催予定|申込|申し込み|受付中"
)


def _forms(event_form: Iterable[str] | str | None) -> list[str]:
    if event_form is None:
        return []
    return normalize_event_forms(event_form)


def is_event_report(title: str | None, event_form: Iterable[str] | str | None = None) -> bool:
    """True when the title clearly marks a post-event report / recap."""
    if not title:
        return False
    forms = _forms(event_form)
    if forms == ["publication"]:
        return False
    if forms and all(f == "broadcast" for f in forms):
        return False
    text = " ".join(title.split())
    if _UPCOMING_TITLE_RE.search(text):
        return False
    for match in _RECAP_RE.finditer(text):
        tail = text[match.start():match.end() + 1]
        if _UPCOMING_PRESENTATION_RE.search(tail):
            continue
        return True
    return False


# Name prefixes the annotator used to inject for category 'report'.
REPORT_NAME_PREFIXES = ("【レポート】", "【活動報導】", "[Report] ")


def strip_report_prefix(name: str | None) -> str | None:
    """Remove a leading report prefix the old annotator injected."""
    if not name:
        return name
    for prefix in REPORT_NAME_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):].lstrip()
    return name

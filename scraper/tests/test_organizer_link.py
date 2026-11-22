"""Unit tests for sources/_organizer_link.py (spec organizer-source-subevents)."""

import re
from datetime import datetime
from pathlib import Path

from sources._organizer_link import (
    count_schedule_slots,
    extract_schedule_dates,
    pick_organizer_link,
    slice_article,
)

FIXTURE = (Path(__file__).parent / "fixtures" / "tiff_jp_news_70779_body.txt").read_text(encoding="utf-8")
HEADER_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2} \[", re.MULTILINE)
FOOTERS = ("前の記事", "次の記事", "ニュース一覧へもどる", "新着ニュース")


# ── pick_organizer_link ─────────────────────────────────────────────────────

def test_pick_skips_own_domain_sns_and_ticketing():
    links = [
        ("https://2026.tiff-jp.net/news/ja/?p=1", "前の記事"),
        ("https://x.com/tiff_site", "X"),
        ("https://peatix.com/event/1", "チケット"),
        ("https://athenee.net/culturalcenter/program/ta/taiwanese_language_cinema.html", "コチラ"),
        ("https://example.org/other.html", "その他"),
    ]
    html, pdf = pick_organizer_link(links, own_domains=["tiff-jp.net"])
    assert html == "https://athenee.net/culturalcenter/program/ta/taiwanese_language_cinema.html"
    assert pdf is None


def test_pick_reports_pdf_separately_and_never_as_html():
    links = [("https://athenee.net/culturalcenter/program/ta/flyer.pdf", "コチラから（PDF）")]
    html, pdf = pick_organizer_link(links, own_domains=["tiff-jp.net"])
    assert html is None
    assert pdf == "https://athenee.net/culturalcenter/program/ta/flyer.pdf"


def test_pick_pdf_and_html_both_found():
    links = [
        ("https://athenee.net/x/flyer.PDF?dl=1", "PDF"),
        ("https://athenee.net/x/page.html", "HP"),
    ]
    html, pdf = pick_organizer_link(links, own_domains=["tiff-jp.net"])
    assert html == "https://athenee.net/x/page.html"
    assert pdf == "https://athenee.net/x/flyer.PDF?dl=1"


def test_pick_ignores_relative_mailto_images_and_subdomains_of_own():
    links = [
        ("/news/ja/", "ニュース"),
        ("mailto:a@b.jp", "mail"),
        ("https://img.example.com/a.jpg", "画像"),
        ("https://api-2026.tiff-jp.net/x", "api"),
    ]
    assert pick_organizer_link(links, own_domains=["tiff-jp.net"]) == (None, None)


# ── slice_article ───────────────────────────────────────────────────────────

def test_slice_drops_navigation_and_sidebar():
    body = slice_article(FIXTURE, HEADER_RE, FOOTERS)
    assert body.startswith("2026.11.15 [更新／お知らせ]")
    assert "イベントレポート" not in body  # nav tab and sidebar entries both gone
    assert "前の記事" not in body
    assert "18:30　交流会" in body


def test_slice_without_markers_returns_text():
    assert slice_article("本文のみ", HEADER_RE, FOOTERS) == "本文のみ"


# ── extract_schedule_dates ──────────────────────────────────────────────────

def test_dates_from_tiff_article_not_publish_date():
    start, end = extract_schedule_dates([FIXTURE], datetime(2026, 11, 15))
    assert start == datetime(2026, 12, 2)
    assert end == datetime(2026, 12, 9)


def test_dates_roll_into_next_year():
    start, end = extract_schedule_dates(["1月10日（土）上映"], datetime(2026, 12, 20))
    assert start == end == datetime(2027, 1, 10)


def test_dates_slash_form_requires_weekday_marker():
    assert extract_schedule_dates(["比率は1/2です"], datetime(2026, 11, 15)) == (None, None)
    start, _ = extract_schedule_dates(["12/2(水)開催"], datetime(2026, 11, 15))
    assert start == datetime(2026, 12, 2)


def test_dates_ignore_past_mentions():
    # 前年の映画祭への言及（発行日より大幅に前）→ 翌年扱いで horizon 外なら無視
    start, end = extract_schedule_dates(["10月30日に上映されました。12月2日開催"], datetime(2026, 11, 15))
    assert (start, end) == (datetime(2026, 12, 2), datetime(2026, 12, 2))


def test_dates_none_when_absent():
    assert extract_schedule_dates([None, "日付なし"], datetime(2026, 11, 15)) == (None, None)


# ── count_schedule_slots ────────────────────────────────────────────────────

def test_slots_in_tiff_schedule():
    slots, titles = count_schedule_slots(FIXTURE)
    assert slots == 11  # 10 screenings + 1 symposium (交流会 is not counted)
    assert titles == 11  # first title per slot; 12/4 opens with 『チマキ売り』, 12/8 with 『チマキ売り2019』


def test_single_film_multiple_times_has_one_title():
    text = "4月25日（土）\n10:00『花様年華』\n14:40『花様年華』\n18:00『花様年華』\n"
    assert count_schedule_slots(text) == (3, 1)


def test_slots_empty():
    assert count_schedule_slots(None) == (0, 0)
    assert count_schedule_slots("上映は10:00から") == (0, 0)

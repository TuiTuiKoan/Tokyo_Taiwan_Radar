"""tiff_jp news → event fields (spec organizer-source-subevents)."""

from datetime import datetime
from pathlib import Path

import pytest

from sources.tiff import build_news_fields

FIXTURE = (Path(__file__).parent / "fixtures" / "tiff_jp_news_70779_body.txt").read_text(encoding="utf-8")
PUBLISHED = datetime(2026, 11, 15)
ATHENEE = "https://athenee.net/culturalcenter/program/ta/taiwanese_language_cinema.html"
ORGANIZER_TEXT = "東京国際映画祭2026提携企画 台湾語映画誕生70周年特集 in Japan\n期間：2026年12月2日（水）～4日（金）、8日（火）～9日（水）"


def _never_fetch(url):
    raise AssertionError(f"unexpected fetch: {url}")


def test_dates_come_from_schedule_not_publish_date():
    f = build_news_fields(FIXTURE, [], PUBLISHED, _never_fetch)
    assert f["start_date"] == datetime(2026, 12, 2)
    assert f["end_date"] == datetime(2026, 12, 9)
    assert f["raw_description"].startswith("開催日時: 2026年12月02日〜2026年12月09日")


def test_navigation_and_sidebar_removed():
    raw = build_news_fields(FIXTURE, [], PUBLISHED, _never_fetch)["raw_description"]
    assert "イベントレポート" not in raw
    assert "上映作品\nスケジュール" not in raw
    assert "18:30　交流会" in raw
    assert build_news_fields(FIXTURE, [], PUBLISHED, _never_fetch)["official_url"] is None


def test_organizer_page_first_and_official_url_set():
    fetched = []

    def fetch(url):
        fetched.append(url)
        return ORGANIZER_TEXT

    links = [
        ("https://ad.example.com/banner", "AD"),           # AD block: text not in article
        ("https://other.example.org/sidebar.html", "第39回東京国際映画祭、受賞者の喜びの声　審査委員長の総評も"),  # sidebar
        ("https://2026.tiff-jp.net/news/ja/", "ニュース"),
        (ATHENEE, "コチラから"),
    ]
    f = build_news_fields(FIXTURE, links, PUBLISHED, fetch)
    assert fetched == [ATHENEE]
    assert f["official_url"] == ATHENEE
    raw = f["raw_description"]
    assert raw.index("【主催者ページ】") < raw.index("【東京国際映画祭ニュース】")


def test_pdf_only_is_noted_not_fetched_and_becomes_official_url():
    # Expected outcome for 407a033b: the article's organiser link is a flyer PDF.
    pdf = "https://athenee.net/culturalcenter/program/ta/flyer.pdf"
    f = build_news_fields(FIXTURE, [(pdf, "コチラから")], PUBLISHED, _never_fetch)
    assert f["official_url"] == pdf
    assert f"チラシ: {pdf}" in f["raw_description"]


def test_sidebar_link_is_never_chosen():
    links = [("https://other.example.org/x.html", "新着ニュース")]
    f = build_news_fields(FIXTURE, links, PUBLISHED, _never_fetch)
    assert f["official_url"] is None


def test_organizer_without_taiwan_or_failed_fetch_is_ignored():
    for result in ("フランス映画特集のお知らせ", None):
        f = build_news_fields(FIXTURE, [(ATHENEE, "コチラから")], PUBLISHED, lambda url, r=result: r)
        assert f["official_url"] is None
        assert "【主催者ページ】" not in f["raw_description"]


def test_no_dates_returns_none():
    f = build_news_fields("2026.11.15 [インタビュー]\n台湾の監督に聞く", [], PUBLISHED, _never_fetch)
    assert f["start_date"] is None and f["end_date"] is None
    assert not f["raw_description"].startswith("開催日時")


@pytest.mark.parametrize("kind", ["イベントレポート", "インタビュー"])
def test_recap_and_interview_keep_publish_date(kind):
    body = f"2026.11.03 [{kind}]\n11月1日の上映後、監督が登壇。12月5日から劇場公開。"
    f = build_news_fields(body, [], datetime(2026, 11, 3), _never_fetch)
    assert f["start_date"] is None and f["end_date"] is None


def test_empty_body():
    f = build_news_fields(None, [], PUBLISHED, _never_fetch)
    assert f["raw_description"] is None

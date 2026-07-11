from pathlib import Path

from publication_rules import is_ndl_periodical_article, is_pure_publication_record
from sources.eslite_spectrum import EsliteSpectrumScraper
from sources.hanmoto import (
    _normalize_official_url,
    _normalize_organizer_url,
    _scrape_hanmoto_detail,
)
from sources.kawade_rss import KawadeRssScraper
from sources.ndl_opensearch import NdlOpensearchScraper


FIXTURES = Path(__file__).parent / "fixtures" / "publication"


class FakeResponse:
    def __init__(self, body: bytes):
        self.content = body
        self.text = body.decode("utf-8")
        self.status_code = 200

    def raise_for_status(self):
        return None


def test_ndl_fixture_emits_ordinary_pure_book(monkeypatch):
    body = (FIXTURES / "ndl_feed.xml").read_bytes()
    monkeypatch.setattr("sources.ndl_opensearch.requests.get", lambda *args, **kwargs: FakeResponse(body))

    events = NdlOpensearchScraper().scrape()

    assert len(events) == 1
    event = events[0]
    assert event.event_form == ["publication"]
    assert event.organizer == "架空出版社"
    assert event.organizer_type == []
    assert event.location_address is None
    assert event.business_hours is None
    assert not is_ndl_periodical_article({
        "source_name": event.source_name,
        "event_form": event.event_form,
        "source_url": event.source_url,
    })


def test_ndl_fixture_detects_periodical_publication(monkeypatch):
    body = (FIXTURES / "ndl_periodical_feed.xml").read_bytes()
    monkeypatch.setattr("sources.ndl_opensearch.requests.get", lambda *args, **kwargs: FakeResponse(body))

    events = NdlOpensearchScraper().scrape()

    assert len(events) == 1
    event = events[0]
    assert event.event_form == ["publication"]
    assert is_ndl_periodical_article({
        "source_name": event.source_name,
        "event_form": event.event_form,
        "source_url": event.source_url,
    })


def test_kawade_fixture_splits_pure_book_and_physical_talk(monkeypatch):
    body = (FIXTURES / "kawade_feed.rdf").read_bytes()
    monkeypatch.setattr("sources.kawade_rss.requests.get", lambda *args, **kwargs: FakeResponse(body))

    events = KawadeRssScraper().scrape()

    assert len(events) == 2
    pure = next(event for event in events if event.source_url.endswith("/book/pure"))
    talk = next(event for event in events if event.source_url.endswith("/event/talk"))
    assert pure.event_form == ["publication"]
    assert pure.location_name is None
    assert pure.business_hours is None
    assert talk.event_form == ["lecture"]
    assert "publication" not in talk.event_form
    assert talk.start_date.isoformat() == "2026-07-20T00:00:00+00:00"
    assert talk.location_name == "河出ホール"
    assert talk.location_address == "東京都新宿区1-2-3"
    assert talk.business_hours == "13:00〜15:00"
    assert talk.organizer_url == "https://www.kawade.co.jp/"


def test_eslite_fixture_uses_uuid_identity_and_physical_priority(monkeypatch):
    listing_html = (FIXTURES / "eslite_news.html").read_bytes()
    detail_html = (FIXTURES / "eslite_article_talk.html").read_bytes()

    def fake_get(session, url, timeout=15):
        if url.endswith("/news"):
            return FakeResponse(listing_html)
        if "f0039984-3181-450d-8b59-e024a8eea070" in url:
            return FakeResponse(detail_html)
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setenv("ESLITE_ALLOW_UUID_IDENTITY", "1")
    monkeypatch.setattr("sources.eslite_spectrum.requests.Session.get", fake_get)

    events = EsliteSpectrumScraper().scrape()

    assert len(events) == 1
    event = events[0]
    assert event.source_id == "eslite_spectrum_f0039984-3181-450d-8b59-e024a8eea070"
    assert event.source_url.endswith("/news/f0039984-3181-450d-8b59-e024a8eea070")
    assert event.event_form == ["lecture"]
    assert "publication" not in event.event_form
    assert event.start_date.isoformat() == "2026-07-20T00:00:00+00:00"
    assert event.end_date.isoformat() == "2026-07-20T00:00:00+00:00"
    assert event.location_name == "誠品生活日本橋 EVENT SPACE"
    assert event.location_address == "東京都中央区日本橋室町3-2-1 COREDO室町テラス2F"
    assert event.business_hours == "13:00〜15:00"
    assert event.price_info == "1,500円"
    assert event.is_paid is True
    assert "ページ公開日: 2026年07月05日" in (event.raw_description or "")
    assert "開催日時: 2026年07月20日" in (event.raw_description or "")


def test_hanmoto_detail_keeps_real_price_and_anchor_href(monkeypatch):
    body = (FIXTURES / "hanmoto_detail.html").read_bytes()
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse(body))

    detail = _scrape_hanmoto_detail("https://www.hanmoto.com/bd/isbn/9784123456789")

    assert detail["price_info"] == "定価 1,980円（本体1,800円+税）"
    assert detail["price_amount"] == 1800.0
    assert detail["official_url"] == "https://book.example.jp/items/taiwan-book"
    assert detail["organizer_url"] == "https://publisher.example.jp/"
    assert "書籍詳細ページ: https://book.example.jp/items/taiwan-book" in detail["raw_description"]
    assert "出版社サイト: https://publisher.example.jp/" in detail["raw_description"]


def test_hanmoto_url_policy_accepts_only_allowed_targets():
    assert _normalize_official_url("https://book.example.jp/items/taiwan-book") == "https://book.example.jp/items/taiwan-book"
    assert _normalize_official_url("https://www.hanmoto.com/bd/search/top?keyword=台湾") is None

    detail_text = "架空出版社 公式サイト"
    organizer = _normalize_organizer_url("https://publisher.example.jp/", "架空出版社", detail_text)
    denied = _normalize_organizer_url("https://www.amazon.co.jp/example", "架空出版社", detail_text)
    assert organizer == "https://publisher.example.jp/"
    assert denied is None


def test_source_and_category_do_not_force_publication():
    assert not is_pure_publication_record({
        "source_name": "hanmoto",
        "category": ["books_media"],
        "event_form": ["lecture"],
    })

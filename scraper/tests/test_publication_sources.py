import re
from pathlib import Path

from publication_rules import is_ndl_periodical_article, is_pure_publication_record
from sources.eslite_spectrum import (
    _HISTORY_FLOOR,
    _SKIP_TITLE_RE,
    EsliteSpectrumScraper,
    _extract_event_datetime_range,
)
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


def test_ndl_fixture_captures_container_title_from_dc_description(monkeypatch):
    body = (FIXTURES / "ndl_container_title_feed.xml").read_bytes()
    monkeypatch.setattr("sources.ndl_opensearch.requests.get", lambda *args, **kwargs: FakeResponse(body))

    events = {event.source_id: event for event in NdlOpensearchScraper().scrape()}

    assert set(events) == {"ndl_111111111", "ndl_222222222"}

    with_container = events["ndl_111111111"]
    assert with_container.raw_description == (
        "掲載誌: 秋田大学高等教育グローバルセンター紀要 2026-03-20 p.11-16\n\n"
        "著者: 研究者A\n\n"
        "出版社: 秋田大学高等教育グローバルセンター\n\n"
        "台湾研究に関する記事。"
    )
    # The 掲載誌 label is stripped and re-emitted exactly once, never both forms.
    assert with_container.raw_description.count("掲載誌") == 1
    assert "掲載誌：" not in with_container.raw_description
    # Only the 掲載誌 dc:description is used; the sibling one is ignored.
    assert "出版タイプ" not in with_container.raw_description
    # dcndl:seriesTitle is a book-series title, never the container title.
    assert "退職記念号" not in with_container.raw_description
    assert with_container.location_name is None
    assert with_container.location_address is None

    without_container = events["ndl_222222222"]
    assert without_container.raw_description == (
        "著者: 著者名\n\n出版社: 架空出版社\n\n台湾文化を紹介する書籍。"
    )
    assert "掲載誌" not in without_container.raw_description
    assert "退職記念号" not in without_container.raw_description
    assert without_container.location_name is None
    assert without_container.location_address is None


def test_ndl_detail_page_parser_reads_the_label_from_a_sibling_element():
    from _oneoff_backfill_ndl_container_title import container_title_from_detail_html

    # The live page puts label and value in sibling <dt>/<dd> elements, so a
    # same-line regex finds nothing.
    html = (
        "<dl><dt><span>掲載誌名</span></dt>"
        "<dd><span>拓殖大学語学研究 154</span></dd></dl>"
        "<dl><dt>掲載ページ</dt><dd>p.177-210</dd></dl>"
    )
    assert "掲載誌名</span></dt><dd><span>拓殖大学語学研究" in html
    assert container_title_from_detail_html(html) == "拓殖大学語学研究 154"
    assert container_title_from_detail_html("<div>掲載ページ p.1-2</div>") is None


def _plan_ndl_row(monkeypatch, *, location_name, api=None, detail=None, raw_description=None):
    import _oneoff_backfill_ndl_container_title as backfill

    monkeypatch.setattr(backfill, "lookup_via_api", lambda row: api)
    monkeypatch.setattr(backfill, "lookup_via_detail_page", lambda row: detail)
    return backfill.plan_row({
        "id": "00000000-0000-0000-0000-000000000000",
        "source_url": "https://ndlsearch.ndl.go.jp/books/R000000025-I008880007382266",
        "location_name": location_name,
        "raw_title": "台湾に関する研究",
        "raw_description": raw_description,
    })


def test_ndl_backfill_preserves_journal_name_when_ndl_returns_only_the_volume(monkeypatch):
    # D1: this detail page's 掲載誌名 field genuinely holds only the volume, so
    # re-deriving the citation from NDL destroys the journal name.
    from _oneoff_backfill_ndl_container_title import container_title_from_detail_html

    detail = container_title_from_detail_html(
        "<dl><dt><span>掲載誌名</span></dt>"
        '<dd data-cy="meta-t07731-value"><span>16</span></dd></dl>'
    )
    assert detail == "16"

    plan = _plan_ndl_row(monkeypatch, location_name="東京福祉大学・大学院紀要 16", detail=detail)

    assert "東京福祉大学・大学院紀要 16" in plan["planned_raw_description"]
    assert plan["planned_raw_description"] != "掲載誌: 16"
    assert plan["status"] == "planned"


def test_ndl_backfill_keeps_the_volume_the_api_omits(monkeypatch):
    # D2: the API string carries date and pages but drops the volume; the volume
    # only survives in location_name, which the cleanup is about to clear.
    plan = _plan_ndl_row(
        monkeypatch,
        location_name="北海学園大学学園論集 199",
        api="北海学園大学学園論集 2026-03-27 p.13-29",
    )

    assert plan["planned_raw_description"] == (
        "掲載誌: 北海学園大学学園論集 199 2026-03-27 p.13-29"
    )
    assert "199" in plan["planned_raw_description"]
    assert plan["status"] == "planned"


def test_ndl_backfill_flags_an_unrelated_container_title_for_review(monkeypatch):
    from _oneoff_backfill_ndl_container_title import applicable_plans

    plan = _plan_ndl_row(
        monkeypatch,
        location_name="北海学園大学学園論集 199",
        api="立命館大学国際地域研究 2026-03-25 p.1-2",
    )

    assert plan["status"] == "needs_review"
    assert "北海学園大学学園論集 199" in plan["planned_raw_description"]
    assert "立命館大学国際地域研究" not in plan["planned_raw_description"]
    assert applicable_plans([plan]) == []


def test_ndl_backfill_leaves_a_row_that_already_carries_the_container_title(monkeypatch):
    plan = _plan_ndl_row(
        monkeypatch,
        location_name="北海学園大学学園論集 199",
        api="北海学園大学学園論集 2026-03-27 p.13-29",
        raw_description="掲載誌: 北海学園大学学園論集 199\n\n本文",
    )

    assert plan["status"] == "already_present"
    assert plan["planned_raw_description"] is None


def test_ndl_backfill_writes_nothing_when_location_name_carries_no_journal_identity(monkeypatch):
    from _oneoff_backfill_ndl_container_title import applicable_plans

    # No identity-bearing core in location_name means there is no journal title
    # to preserve, so the row must stay unavailable and never reach a write.
    unavailable = [
        "16",
        "",
        None,
        "   ",
        "2026-03-20 p.1-2",
    ]
    plans = [
        _plan_ndl_row(monkeypatch, location_name=location_name)
        for location_name in unavailable
    ]
    for location_name, plan in zip(unavailable, plans):
        assert plan["status"] == "unavailable", location_name
        assert plan["planned_raw_description"] is None, location_name
        assert plan["container_title"] is None, location_name

    control = _plan_ndl_row(monkeypatch, location_name="拓殖大学語学研究 154")

    assert control["status"] == "planned"
    assert control["planned_raw_description"] == "掲載誌: 拓殖大学語学研究 154"
    assert applicable_plans([*plans, control]) == [control]


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


def _eslite_fake_get(detail_html: bytes):
    listing_html = (FIXTURES / "eslite_news.html").read_bytes()

    def fake_get(session, url, timeout=15):
        if url.endswith("/news"):
            return FakeResponse(listing_html)
        if "f0039984-3181-450d-8b59-e024a8eea070" in url:
            return FakeResponse(detail_html)
        raise AssertionError(f"Unexpected URL: {url}")

    return fake_get


def _eslite_detail_with_event_date(event_date: str) -> bytes:
    body = (FIXTURES / "eslite_article_talk.html").read_text(encoding="utf-8")
    return body.replace("2026年7月20日", event_date).encode("utf-8")


def test_eslite_emits_events_with_gate_default_and_no_env(monkeypatch):
    monkeypatch.delenv("ESLITE_ALLOW_UUID_IDENTITY", raising=False)
    monkeypatch.setattr(
        "sources.eslite_spectrum.requests.Session.get",
        _eslite_fake_get((FIXTURES / "eslite_article_talk.html").read_bytes()),
    )

    events = EsliteSpectrumScraper().scrape()

    assert len(events) == 1
    assert re.fullmatch(
        r"eslite_spectrum_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        events[0].source_id,
    )


def test_eslite_gate_still_closable_by_env(monkeypatch):
    monkeypatch.setenv("ESLITE_ALLOW_UUID_IDENTITY", "0")
    monkeypatch.setattr(
        "sources.eslite_spectrum.requests.Session.get",
        _eslite_fake_get((FIXTURES / "eslite_article_talk.html").read_bytes()),
    )

    assert EsliteSpectrumScraper().scrape() == []


def test_eslite_history_floor_drops_archive_and_keeps_floor_day(monkeypatch):
    monkeypatch.delenv("ESLITE_ALLOW_UUID_IDENTITY", raising=False)

    monkeypatch.setattr(
        "sources.eslite_spectrum.requests.Session.get",
        _eslite_fake_get(_eslite_detail_with_event_date("2025年12月31日")),
    )
    assert EsliteSpectrumScraper().scrape() == []

    monkeypatch.setattr(
        "sources.eslite_spectrum.requests.Session.get",
        _eslite_fake_get(_eslite_detail_with_event_date("2026年1月1日")),
    )
    kept = EsliteSpectrumScraper().scrape()
    assert len(kept) == 1
    assert kept[0].start_date.date() == _HISTORY_FLOOR


def test_eslite_event_range_accepts_a_weekday_token_and_a_wave_separator():
    start, end, _hours = _extract_event_datetime_range("2026.1.30 Fri. ～ 2.23 Mon.")

    assert start.date().isoformat() == "2026-01-30"
    assert end.date().isoformat() == "2026-02-23"


def test_eslite_event_range_accepts_a_prolonged_sound_mark_separator():
    start, end, _hours = _extract_event_datetime_range("2026.7.18 Sat.ー8.31 Mon.")

    assert start.date().isoformat() == "2026-07-18"
    assert end.date().isoformat() == "2026-08-31"


def test_eslite_labelled_one_day_event_keeps_identical_start_and_end():
    text = (
        "会場：誠品生活日本橋 EVENT SPACE\n"
        "開催日時：2026年7月20日 13:00〜15:00\n"
        "参加費：1,500円"
    )

    start, end, hours = _extract_event_datetime_range(text)

    assert start == end
    assert start.date().isoformat() == "2026-07-20"
    assert hours == "13:00〜15:00"


def test_eslite_publication_line_never_outranks_the_labelled_event_range():
    # The page-publication date sits first and previously won by document order,
    # which truncated multi-month exhibitions to their publication day.
    text = (
        "ページ公開日: 2026年07月05日\n"
        "2026-07-05\n"
        "会期：2026.7.18 Sat.ー8.31 Mon."
    )

    start, end, _hours = _extract_event_datetime_range(text)

    assert start.date().isoformat() == "2026-07-18"
    assert end.date().isoformat() == "2026-08-31"


def test_eslite_nested_ranges_without_an_umbrella_never_invent_an_end():
    text = (
        "台湾ブックフェア\n"
        "1F 展示：2026.7.18 Sat.ー7.31 Thu.\n"
        "2F 物販：2026.8.1 Sat.ー8.20 Wed."
    )

    start, end, _hours = _extract_event_datetime_range(text)

    assert start.date().isoformat() == "2026-07-18"
    assert end is None


def test_eslite_skip_patterns_drop_promotions_but_keep_real_events():
    promotions = [
        "2023年 誠品生活日本橋「新春福袋」",
        "春の週替わりノベルティキャンペーン",
        "食で学ぶ台湾「好吃・好喝キャンペーン」開催！",
        "誠品禮物節「会えるのが、いちばんのギフト」",
        "母の日ギフト2023「HAPPY MOTHER'S DAY」",
        "父の日ギフト2022「父親節」",
        "誠品生活日本橋ご出店者関係者内覧会",
        "中文書特急便　サービス開始のご案内",
        "【誠品選書】2026年7月おすすめ書籍",
    ]
    for title in promotions:
        assert _SKIP_TITLE_RE.search(title), title

    real_events = [
        "【クッキング】「居酒屋だけメシ」この日限りの特別オープン！",
        "6周年記念24時間営業「Culture Wonderland」書籍フェア",
        "『台湾夜市大全』刊行記念 三文字昌也さんトークイベント",
        "物外YSTUDIO 書くことの体験ワークショップ",
        "「中間淳太の満福台湾ガイド」発売記念トークイベント",
    ]
    for title in real_events:
        assert not _SKIP_TITLE_RE.search(title), title


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

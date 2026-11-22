"""Unit tests for the AA研 (tufs_aa) scraper.

The HTML below is SYNTHETIC: it reproduces the labels and URL patterns seen on
https://www.aa.tufs.ac.jp/events/ and /events/detail/e441/ (2026-11-22), not
the verbatim markup. The parser is label/URL based on purpose, so these tests
check that contract; the CI dry-run checks the live site.
"""

from datetime import datetime, timedelta, timezone

from sources import tufs_aa
from sources.tufs_aa import (
    AA_ADDRESS,
    TufsAaScraper,
    is_taiwan_related,
    parse_detail,
    parse_listing,
    resolve_venue,
)

JST = timezone(timedelta(hours=9))

LISTING = """
<html><body><main>
<ul>
 <li><a href="https://www.aa.tufs.ac.jp/events/detail/e564/">
   <h3>Iran Through a Peripheral Lens</h3>
   <span>公開</span><span>研究会・シンポジウム・WS</span>
   <dl><dt>日時</dt><dd>: 2099年12月07日（月） 14:00-18:30</dd></dl></a></li>
 <li><a href="/events/detail/e578/">
   <h3>「文法の動的体系性を探る (2)」2026年度第4回研究会</h3>
   <span>非公開</span><span>共共課題研究会</span>
   <dl><dt>日時</dt><dd>: 2099年12月05日（土） 13:00-17:00</dd></dl></a></li>
 <li><a href="/en/events/detail/e564/">English</a></li>
</ul>
</main></body></html>
"""

DETAIL_E441 = """
<html><head>
<meta property="og:title" content="小川尚義・浅井恵倫・土田滋台湾資料贈呈記念式典 | AA研">
<meta property="og:image" content="https://www.aa.tufs.ac.jp/wp-content/uploads/x.jpg">
</head><body><header>ナビ</header><main>
<ul><li>公開</li><li>TUFiSCo</li></ul>
<h1>小川尚義・浅井恵倫・土田滋台湾資料贈呈記念式典</h1>
<dl>
 <dt>日時</dt><dd>: 2026年06月19日（金） 13:00-17:30</dd>
 <dt>場所</dt><dd>: 303 : AA研 大会議室</dd>
 <dt>開催形態</dt><dd>: 対面</dd>
 <dt>使用言語</dt><dd>: 英語</dd>
</dl>
<h2>プログラム</h2>
<ul><li>14:30 - 15:10 · Early Japanese Linguistic Contributions to Taiwan · 李壬癸</li></ul>
<dl><dt>主催・共催</dt><dd>: AA研, TUFiSCo</dd></dl>
</main><footer>フッター</footer></body></html>
"""

DETAIL_AMIS_ONLY = """
<html><body><main>
<h1>文法研究会</h1>
<dl><dt>日時</dt><dd>: 2099年12月07日（月） 14:00-18:30 / 2099年12月08日（火） 14:00-19:00</dd>
<dt>場所</dt><dd>: オンライン会議室/301 : AA研 セミナー室</dd></dl>
<ul><li>書き言葉の発達によるアミ語の変容 · 今西一太</li></ul>
</main></body></html>
"""


def test_parse_listing_cards_public_flag_and_skips_english():
    cards = {c["event_no"]: c for c in parse_listing(LISTING)}
    assert set(cards) == {"564", "578"}
    assert cards["564"]["is_public"] is True
    assert cards["578"]["is_public"] is False  # 非公開 must not read as 公開
    assert cards["564"]["url"] == "https://www.aa.tufs.ac.jp/events/detail/e564/"
    assert cards["564"]["dates"][0].date().isoformat() == "2099-12-07"


def test_parse_detail_e441():
    d = parse_detail(DETAIL_E441)
    assert d["title"] == "小川尚義・浅井恵倫・土田滋台湾資料贈呈記念式典"
    assert d["start"] == datetime(2026, 6, 19, 13, 0, tzinfo=JST)
    assert d["end"] == datetime(2026, 6, 19, 17, 30, tzinfo=JST)
    assert d["end"] >= d["start"]
    assert d["venue"].startswith("303 : AA研 大会議室")
    assert d["language"] == "英語"
    assert "AA研" in d["organizer"]
    assert "ナビ" not in d["body"] and "フッター" not in d["body"]


def test_multi_day_and_hybrid_venue():
    d = parse_detail(DETAIL_AMIS_ONLY)
    assert d["start"].date().isoformat() == "2099-12-07"
    assert d["end"].date().isoformat() == "2099-12-08"
    name, addr = resolve_venue(d["venue"], None)
    assert name == "301 : AA研 セミナー室"
    assert addr == AA_ADDRESS


def test_online_only_venue():
    assert resolve_venue("オンライン", "オンライン") == ("オンライン", None)


def test_relevance_keywords():
    assert is_taiwan_related("台湾原住民語資料")
    assert is_taiwan_related("Comparing Seediq Data")
    assert is_taiwan_related("アミ語の変容")
    assert not is_taiwan_related("アミノ酸とイランの社会")
    assert not is_taiwan_related("Iran Through a Peripheral Lens")
    assert not is_taiwan_related("仙台湾の漁村調査")


def test_scrape_end_to_end(monkeypatch):
    pages = {
        tufs_aa.LISTING_URL: LISTING,
        "https://www.aa.tufs.ac.jp/events/detail/e564/": DETAIL_AMIS_ONLY,
    }
    monkeypatch.setattr(tufs_aa, "REQUEST_SLEEP", 0)
    scraper = TufsAaScraper()
    monkeypatch.setattr(scraper, "_get", lambda url: pages.get(url, "<html></html>"))
    events = scraper.scrape()
    assert [e.source_id for e in events] == ["tufs_aa_e564"]  # e578 is 非公開
    ev = events[0]
    assert ev.raw_description.startswith("開催日時: 2099年12月07日")
    assert ev.location_address == AA_ADDRESS
    assert ev.category == ["academic"]

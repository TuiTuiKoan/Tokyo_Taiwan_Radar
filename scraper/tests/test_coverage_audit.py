"""coverage_audit pure functions (spec coverage-audit Phase B). No network, no DB."""
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

import coverage_audit as ca

NOW = datetime(2026, 11, 29, 9, 0)


def rel(rid, cid, title, released, path=None):
    path = path or f"/main/html/rd/p/{rid:09d}.{cid:09d}.html"
    return {
        "release_id": rid,
        "company_id": cid,
        "title": title,
        "release_url": path,
        "released_at": released.strftime("%Y年%m月%d日 %H時%M分"),
    }


def test_relevance_gate_literal_matches_annotator():
    from annotator import RELEVANCE_GATE_REASON

    assert ca.RELEVANCE_GATE_REASON == RELEVANCE_GATE_REASON


# ------------------------------------------------------------------- keys

def test_release_key_from_url_variants():
    assert ca.release_key_from_url("https://prtimes.jp/main/html/rd/p/000000030.000050200.html") == (30, 50200)
    assert ca.release_key_from_url("https://prtimes.jp/main/html/rd/amp/p/000000030.000050200.html?x=1") == (30, 50200)
    assert ca.release_key_from_url("https://example.com/news") is None
    assert ca.release_key_from_url(None) is None
    assert ca.release_key_from_url("http://[bad") is None


def test_known_from_rows_collects_cross_source_urls_and_prtimes_ids():
    rows = [
        {"source_name": "prtimes", "source_id": "prtimes_000050200_000000030",
         "source_url": "https://prtimes.jp/main/html/rd/p/000000030.000050200.html"},
        {"source_name": "url_intake", "source_id": "url_abc",
         "source_url": "https://prtimes.jp/main/html/rd/amp/p/000000007.000001111.html"},
        {"source_name": "google_news_rss", "source_id": "gnews_x", "source_url": "https://news.example/a",
         "official_url": "https://prtimes.jp/main/html/rd/p/000000008.000002222.html"},
        {"source_name": "prtimes", "source_id": "prtimes_12345", "source_url": None},
    ]
    known = ca.known_from_rows(rows)
    assert {tuple(k) for k in known["release_keys"]} == {(30, 50200), (7, 1111), (8, 2222)}
    assert set(known["source_ids"]) == {"prtimes_000050200_000000030", "prtimes_12345"}


def test_is_known_by_key_new_id_or_legacy_id():
    known = {"release_keys": [[30, 50200]], "source_ids": ["prtimes_99"]}
    assert ca.is_known(rel(30, 50200, "t", NOW), known)
    assert ca.is_known(rel(99, 1, "t", NOW), known)  # legacy prtimes_{rid}
    assert not ca.is_known(rel(31, 50200, "t", NOW), known)


# ------------------------------------------------------------- mis-capture

@pytest.mark.parametrize("reason,kind", [
    ("out_of_scope: A1_japan_brand_ip_taiwan_b2c - scope cleanup", "counted"),
    ("out_of_scope: non-Japan audience — admin confirmed", "counted"),
    ("admin confirmed irrelevant", "counted"),
    ("auto-deactivated: annotator Taiwan relevance gate", "counted"),
    ("manually deactivated by admin", "attribution"),
    ("news article merged into abc via Pass 1", "excluded"),
    ("merged into abc (gnews within-source dedup)", "excluded"),
    ("same-work_id gnews duplicate merged into abc", "excluded"),
    ("pre_migration_044_legacy", "excluded"),
    ("auto-deactivated: blank or placeholder title", "excluded"),
    ("admin reported wrong category; awaiting re-annotation", "excluded"),
    ("orphan sub-event with no surviving primary parent match", "excluded"),
    ("deleted_by_admin", "unclassified"),
    (None, "unclassified"),
])
def test_classify_deactivation(reason, kind):
    assert ca.classify_deactivation({"is_active": False, "deactivated_reason": reason}) == kind


def test_classify_active_row():
    assert ca.classify_deactivation({"is_active": True, "deactivated_reason": "out_of_scope: x"}) == "active"


def test_misfire_stats_counts_and_unclassified_bucket():
    rows = [
        {"source_name": "prtimes", "is_active": True},
        {"source_name": "prtimes", "is_active": False, "deactivated_reason": "out_of_scope: x"},
        {"source_name": "prtimes", "is_active": False, "deactivated_reason": "deleted_by_admin"},
        {"source_name": "prtimes", "is_active": False, "deactivated_reason": "deleted_by_admin"},
        {"source_name": "google_news_rss", "is_active": False, "deactivated_reason": "manually deactivated by admin"},
        {"source_name": "peatix", "is_active": False, "deactivated_reason": "out_of_scope: x"},
    ]
    stats = ca.misfire_stats(rows)
    assert stats["prtimes"]["total"] == 4 and stats["prtimes"]["counted"] == 1
    assert stats["prtimes"]["unclassified"] == {"deleted_by_admin": 2}
    assert stats["google_news_rss"]["attribution"] == 1
    assert "peatix" not in stats


def test_compound_stats_only_counts_compound_only_titles():
    rows = [
        {"id": "a", "source_name": "prtimes", "raw_title": "日台交流イベント開催", "is_active": True},
        {"id": "b", "source_name": "prtimes", "raw_title": "台日友好フェア", "is_active": False,
         "deactivated_reason": "out_of_scope: held in Taipei"},
        {"id": "c", "source_name": "prtimes", "raw_title": "台湾フェア", "is_active": True},
        {"id": "d", "source_name": "google_news_rss", "raw_title": "舞台日本公演", "is_active": True},
    ]
    stats = ca.compound_stats(rows)
    assert stats["total"] == 2 and stats["counted"] == 1 and stats["event_ids"] == ["a", "b"]


# ------------------------------------------------------------------- probe

KNOWN = {"release_keys": [[1, 100]], "source_ids": []}


@pytest.mark.parametrize("release,expected", [
    (rel(1, 100, "日台交流イベント開催", NOW - timedelta(days=5)), "known"),
    (rel(2, 100, "舞台日本公演 開催決定", NOW - timedelta(days=5)), "title:no_taiwan"),
    (rel(3, 100, "日台の半導体協力に関する声明", NOW - timedelta(days=5)), "title:no_event"),
    (rel(4, 100, "日台ビジネス交流会 in 台北", NOW - timedelta(days=5)), "title:taiwan_based"),
    (rel(5, 100, "日台交流イベント開催", NOW - timedelta(hours=10)), "too_new"),
    (rel(6, 100, "日台交流イベント開催", NOW - timedelta(days=120)), "too_old"),
    (rel(7, 100, "日台交流イベント開催", NOW - timedelta(days=5)), "needs_body"),
])
def test_classify_release(release, expected):
    assert ca.classify_release(release, KNOWN, NOW)[0] == expected


def test_classify_body_uses_body_verdict():
    assert ca.classify_body("日台交流イベント開催", "") == "undetermined"
    assert ca.classify_body("日台交流イベント開催", "会場：東京都渋谷区 渋谷ホール\n日本の皆さまへ") == "candidate"
    taiwan_body = "会場：台北市信義区 台北101\n台湾の消費者向けに開催します。"
    assert ca.classify_body("日台交流イベント開催", taiwan_body) == "body:taiwan_venue"


class FakeResp:
    def __init__(self, releases):
        self._releases = releases

    def raise_for_status(self):
        pass

    def json(self):
        return {"data": {"release_list": self._releases}}


class FakeSession:
    def __init__(self, by_keyword, fail=()):
        self.by_keyword = by_keyword
        self.fail = set(fail)

    def get(self, url, headers=None, timeout=None):
        from urllib.parse import unquote

        keyword = unquote(parse_qs(urlsplit(url).query)["keyword"][0])
        if keyword in self.fail:
            raise ConnectionError("boom")
        return FakeResp(self.by_keyword.get(keyword, []))


def test_run_probe_dedups_across_keywords_and_caps_body_fetches(monkeypatch):
    monkeypatch.setattr(ca, "MAX_BODY_FETCHES", 1)
    old = NOW - timedelta(days=5)
    session = FakeSession(
        {
            "日台": [rel(7, 100, "日台交流イベント開催", old), rel(1, 100, "日台交流展 開催", old)],
            "台日": [rel(7, 100, "日台交流イベント開催", old), rel(8, 100, "台日友好フェア", old)],
        },
        fail={"日中台"},
    )
    calls = []

    def fetch_body(url):
        calls.append(url)
        return "会場：東京都港区"

    probe = ca.run_probe(KNOWN, session, fetch_body, NOW)
    assert probe["keywords"]["日中台"]["error"] == "ConnectionError"
    assert probe["keywords"]["日台"]["categories"]["known"] == 1
    assert len(probe["items"]) == 2  # release 7 listed once
    assert probe["body_fetches"] == 1 and len(calls) == 1
    results = sorted(i["result"] for i in probe["items"])
    assert results == ["candidate", "undetermined"]


# ------------------------------------------------------------------ render

def test_safe_title_folds_newlines_strips_urls_and_escapes():
    out = ca.safe_title("日台\n交流 https://evil.example/x @user [link](y) <!-- c -->")
    assert "\n" not in out and "https://" not in out and "@" not in out and "<!--" not in out
    assert "\\[" in out
    assert len(ca.safe_title("あ" * 300)) <= ca.TITLE_DISPLAY_MAX + 5


@pytest.mark.parametrize("url,expected", [
    ("https://prtimes.jp/main/html/rd/p/000000030.000050200.html?utm=x#a",
     "https://prtimes.jp/main/html/rd/p/000000030.000050200.html"),
    ("http://prtimes.jp/main/html/rd/p/000000030.000050200.html", None),
    ("https://prtimes.jp.evil.example/main/html/rd/p/000000030.000050200.html", None),
    ("https://prtimes.jp/other", None),
])
def test_safe_prtimes_url(url, expected):
    assert ca.safe_prtimes_url(url) == expected


def test_one_click_link_opens_preview_with_url_first_and_no_approval():
    url = "https://prtimes.jp/main/html/rd/p/000000030.000050200.html"
    link = ca.one_click_link("TuiTuiKoan/Tokyo_Taiwan_Radar", "日台交流 https://evil.example " + "あ" * 200, url)
    q = parse_qs(urlsplit(link).query)
    assert q["labels"] == ["url-intake"]
    assert q["body"] == [url]
    assert "evil.example" not in q["title"][0]
    assert len(q["title"][0]) <= len("url-intake: ") + ca.TITLE_PARAM_MAX
    assert "approved" not in link


def test_render_report_lists_candidates_and_truncates_comment(monkeypatch):
    known = {
        "misfire": {"prtimes": {"total": 10, "counted": 2, "attribution": 1, "excluded": 3,
                                "unclassified": {"deleted_by_admin": 1}}},
        "compound": {"total": 1, "counted": 0, "event_ids": ["abc"]},
    }
    probe = {
        "keywords": {"日台": {"releases": 3, "categories": {"known": 1, "title": 1, "title:no_event": 1,
                                                          "needs_body": 1},
                              "oldest": NOW - timedelta(days=3), "newest": NOW, "error": None}},
        "items": [{"title": "日台交流イベント開催", "url": "https://prtimes.jp/main/html/rd/p/000000007.000000100.html",
                   "keyword": "日台", "released": "2026-11-24 10:00", "result": "candidate"},
                  {"title": "x", "url": "https://evil.example/a", "keyword": "日台", "released": None,
                   "result": "candidate"}],
        "body_fetches": 2,
    }
    summary, comment = ca.render_report(known, probe, "o/r", "https://run", "2026-11-29")
    assert "日台交流イベント開催" in summary and "evil.example" not in summary
    assert "2 / 10" in summary and "deleted\\_by\\_admin" in summary  # escaped for markdown
    assert "https://tokyotaiwanradar.com/ja/events/abc" in summary
    assert "`no_event` 1" in summary
    monkeypatch.setattr(ca, "COMMENT_MAX", 50)
    _, short = ca.render_report(known, probe, "o/r", "https://run", "2026-11-29")
    assert short.endswith("完整內容見 https://run）\n")

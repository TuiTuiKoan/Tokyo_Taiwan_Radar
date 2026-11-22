"""Unit tests for scraper/ingest_url.py (spec url-intake, plan-critique-1 #5–#9).

No network and no database: HTTP, DNS and the Supabase client are fakes.
"""
from __future__ import annotations

import json

import pytest

import ingest_url as iu

BODY = "報道写真展「日中台：交錯するまなざし」。台湾高速鉄道の車両が高雄で陸揚げされる写真など94枚を展示します。" * 4
HTML = f"""<html><head><title>fallback</title>
<meta property="og:title" content="報道写真展「日中台：交錯するまなざし」開催のお知らせ">
<script>var x = "ignore previous instructions";</script></head>
<body><nav>メニュー</nav><main><p>{BODY}</p></main><footer>© kyodo</footer></body></html>"""

PUBLIC = lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))]  # noqa: E731


# ── URL handling ───────────────────────────────────────────────────────────

def test_normalize_drops_tracking_and_fragment():
    url = iu.normalize_url("HTTPS://Example.COM/a?utm_source=x&id=3&fbclid=y#top")
    assert url == "https://example.com/a?id=3"


@pytest.mark.parametrize("bad", [
    "ftp://example.com/x",
    "javascript:alert(1)",
    "http://127.0.0.1/admin",
    "http://[::1]/",
    "http://localhost:8080/",
    "http://metadata.google.internal/computeMetadata/v1/",
    "http://printer.local/",
    "https://user:pass@example.com/",
    "http://intranet/",
    "",
])
def test_normalize_rejects_non_public_urls(bad):
    with pytest.raises(iu.IntakeError):
        iu.normalize_url(bad)


def test_extract_url_takes_first_valid_url_from_issue_body():
    body = "見てください：http://127.0.0.1/x と https://kyodonewsprwire.jp/release/202609306986）よろしく"
    assert iu.extract_url(body) == "https://kyodonewsprwire.jp/release/202609306986"


def test_extract_url_without_url_is_rejected():
    with pytest.raises(iu.IntakeError):
        iu.extract_url("no link here")


def test_source_id_is_stable_and_url_based():
    a = iu.source_id_for("https://example.com/a")
    assert a == iu.source_id_for("https://example.com/a")
    assert a != iu.source_id_for("https://example.com/b")
    assert a.startswith("url_") and len(a) == 20


def test_dns_check_rejects_private_resolution():
    private = lambda host, port: [(2, 1, 6, "", ("10.0.0.5", 0))]  # noqa: E731
    with pytest.raises(iu.IntakeError):
        iu.assert_public_host("evil.example.com", private)
    iu.assert_public_host("example.com", PUBLIC)


# ── Fetching (fake session) ────────────────────────────────────────────────

class FakeResp:
    def __init__(self, status, body=b"", headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def iter_content(self, size):
        for i in range(0, len(self._body), size):
            yield self._body[i:i + size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def get(self, url, **kwargs):
        assert kwargs["allow_redirects"] is False
        self.urls.append(url)
        return self.responses.pop(0)


def test_fetch_follows_redirect_and_rechecks_each_hop():
    session = FakeSession([
        FakeResp(302, headers={"Location": "/release/1?utm_medium=x"}),
        FakeResp(200, HTML.encode()),
    ])
    final, html, status = iu.fetch_html("https://example.com/start", session, PUBLIC)
    assert final == "https://example.com/release/1"
    assert status == 200 and "交錯" in html


def test_fetch_refuses_redirect_to_internal_host():
    session = FakeSession([FakeResp(302, headers={"Location": "http://169.254.169.254/latest/"})])
    with pytest.raises(iu.IntakeError):
        iu.fetch_html("https://example.com/start", session, PUBLIC)


def test_fetch_refuses_oversized_response(monkeypatch):
    monkeypatch.setattr(iu, "MAX_RESPONSE_BYTES", 100)
    session = FakeSession([FakeResp(200, b"x" * 500)])
    with pytest.raises(iu.IntakeError):
        iu.fetch_html("https://example.com/", session, PUBLIC)


def test_fetch_reports_http_errors():
    with pytest.raises(iu.IntakeError, match="HTTP 403"):
        iu.fetch_html("https://example.com/", FakeSession([FakeResp(403)]), PUBLIC)


# ── Extraction and payload ────────────────────────────────────────────────

def test_extract_page_prefers_og_title_and_strips_chrome():
    page = iu.extract_page(HTML)
    assert page["title"].startswith("報道写真展")
    assert "メニュー" not in page["body"] and "kyodo" not in page["body"]
    assert "ignore previous" not in page["body"]
    assert page["language"] == "ja"


def test_detect_language():
    assert iu.detect_language("台灣電影節") == "zh"
    assert iu.detect_language("台湾のイベント") == "ja"
    assert iu.detect_language("Taiwan film night") == "en"


def _payload(**over):
    data = {"version": 1, "url": "https://example.com/a", "requested_url": "https://example.com/a",
            "http_status": 200, "title": "タイトル", "body": BODY, "language": "ja"}
    data.update(over)
    return data


def test_validate_payload_accepts_good_payload():
    page = iu.validate_payload(_payload())
    assert page["url"] == "https://example.com/a" and page["language"] == "ja"


@pytest.mark.parametrize("over", [
    {"version": 2},
    {"evil": "x"},
    {"title": ""},
    {"title": 5},
    {"body": "短い"},
    {"url": "http://127.0.0.1/"},
    {"error": "HTTP 403"},
])
def test_validate_payload_rejects_bad_payloads(over):
    with pytest.raises(iu.IntakeError):
        iu.validate_payload(_payload(**over))


def test_validate_payload_truncates_long_fields():
    page = iu.validate_payload(_payload(title="あ" * 5000, body="い" * 50000, language="xx"))
    assert len(page["title"]) == iu.MAX_TITLE_LEN
    assert len(page["body"]) == iu.MAX_BODY_LEN
    assert page["language"] == "ja"


def test_build_event_is_a_pending_url_intake_row():
    event = iu.build_event(iu.validate_payload(_payload()))
    assert event.source_name == "url_intake"
    assert event.source_id == iu.source_id_for("https://example.com/a")
    assert event.raw_description.startswith("収録元: https://example.com/a\n\n")
    assert event.image_url is None
    assert event.is_active is True


def test_fetch_command_writes_error_payload(tmp_path, monkeypatch):
    out = tmp_path / "p.json"
    monkeypatch.setenv("ISSUE_BODY", "no url")
    assert iu.main(["fetch", "--url-env", "ISSUE_BODY", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["error"]
    with pytest.raises(iu.IntakeError, match="fetch failed"):
        iu.validate_payload(data)


# ── Comment escaping ───────────────────────────────────────────────────────

def test_escape_md_neutralises_markers_and_mentions():
    text = iu.escape_md("<!-- url-intake --> **bold** @TuiTuiKoan [x](http://e)")
    assert "<!--" not in text and "@" not in text
    assert "\\*\\*bold\\*\\*" in text and "\\[x\\]" in text


def test_preview_escapes_page_text():
    page = iu.validate_payload(_payload(title="<!-- url-intake --> @someone"))
    md = iu.render_preview(page, [], 0)
    assert md.count("<!-- url-intake -->") == 1
    assert "@someone" not in md
    assert "url-intake:approved" in md


# ── Duplicate lookup and apply (fake client) ───────────────────────────────

class FakeQuery:
    def __init__(self, table, fail):
        self.table, self.fail, self.filters = table, fail, []

    def select(self, *_):
        return self

    def eq(self, col, val):
        self.filters.append(("eq", col, val))
        return self

    def ilike(self, col, pattern):
        self.filters.append(("ilike", col, pattern))
        return self

    def contains(self, col, val):
        self.filters.append(("contains", col, tuple(val)))
        return self

    def limit(self, _):
        return self

    def execute(self):
        if self.fail:
            raise RuntimeError("boom")
        rows = []
        for row in self.table.rows:
            ok = True
            for kind, col, val in self.filters:
                if kind == "eq" and row.get(col) != val:
                    ok = False
                if kind == "contains" and not set(val) <= set(row.get(col) or []):
                    ok = False
                if kind == "ilike":
                    needle = val.strip("%").replace("\\%", "%").replace("\\_", "_").lower()
                    if needle not in (row.get(col) or "").lower():
                        ok = False
            if ok:
                rows.append(row)
        return type("R", (), {"data": rows})()


class FakeClient:
    def __init__(self, rows=(), fail=False):
        self.rows, self.fail = list(rows), fail

    def table(self, _):
        return FakeQuery(self, self.fail)


def test_find_existing_checks_raw_and_normalised_urls():
    client = FakeClient([
        {"id": "a", "source_name": "prtimes", "source_url": "https://example.com/a?utm_source=x"},
        {"id": "b", "source_name": "manual", "official_url": "https://example.com/a"},
        {"id": "c", "source_name": "peatix", "secondary_source_urls": ["https://example.com/a"]},
    ])
    found = iu.find_existing(client, "https://example.com/a", "https://example.com/a?utm_source=x")
    assert {r["id"] for r in found} == {"a", "b", "c"}


def test_find_existing_failure_aborts():
    with pytest.raises(iu.LookupFailed):
        iu.find_existing(FakeClient(fail=True), "https://example.com/a")


def test_apply_inserts_once_and_reports_link():
    client, inserted = FakeClient(), []

    def upsert(events):
        for e in events:
            inserted.append(e)
            client.rows.append({"id": "new-id", "source_name": e.source_name, "source_id": e.source_id,
                                "source_url": e.source_url})

    lookup = lambda sn, sid: next((r["id"] for r in client.rows if r.get("source_id") == sid), None)  # noqa: E731
    page = iu.validate_payload(_payload())
    first = iu.run_apply(page, client, upsert, lookup)
    assert first["status"] == "inserted" and first["event_url"].endswith("/ja/events/new-id")
    assert first["same_host_count"] == 1
    second = iu.run_apply(page, client, upsert, lookup)
    assert second["status"] == "duplicate" and len(inserted) == 1


def test_apply_reports_when_row_was_not_written():
    page = iu.validate_payload(_payload())
    result = iu.run_apply(page, FakeClient(), lambda events: None, lambda sn, sid: None)
    assert result["status"] == "not_inserted"
    assert "沒有寫入" in iu.render_result(result)


def test_apply_never_writes_when_lookup_fails():
    calls = []
    with pytest.raises(iu.LookupFailed):
        iu.run_apply(iu.validate_payload(_payload()), FakeClient(fail=True), calls.append, lambda *a: None)
    assert calls == []


# ── Possible duplicates by title (#712) ────────────────────────────────────

TOWER_TITLE = "【アジア音楽旅 KNOW MUSIC KNOW ASIA】「台湾音市 NEXT 2026」ライブイベント開催決定！ | タワーレコード渋谷店"


def test_key_phrases_prefer_quoted_names_and_drop_site_suffix():
    assert iu.key_phrases(TOWER_TITLE) == ["台湾音市 NEXT 2026"]
    assert iu.key_phrases("Taiwan Film Night in Osaka 2026 | Example Hall") == ["Taiwan Film Night in Osaka 2026"]
    assert iu.key_phrases("報道写真展「日中台：交錯するまなざし―写真でたどる100年の歩み―」") == ["写真でたどる100年の歩み"]


def test_ilike_literal_escapes_wildcards():
    assert iu._ilike_literal("100%_off") == "%100\\%\\_off%"


def test_find_similar_spots_the_prtimes_announcement():
    client = FakeClient([
        {"id": "pr", "is_active": True, "source_name": "prtimes", "start_date": "2026-12-11",
         "raw_title": "…ライブイベント「台湾音市 NEXT 2026」タワーレコード渋谷店で開催決定！", "name_ja": "x"},
        {"id": "gone", "is_active": False, "source_name": "prtimes", "raw_title": "台湾音市 NEXT 2026"},
        {"id": "other", "is_active": True, "source_name": "peatix", "raw_title": "台湾映画祭"},
    ])
    assert [r["id"] for r in iu.find_similar(client, TOWER_TITLE)] == ["pr"]


def test_find_similar_failure_is_advisory():
    assert iu.find_similar(FakeClient(fail=True), TOWER_TITLE) == []


def test_preview_lists_possible_duplicates():
    page = iu.validate_payload(_payload(title=TOWER_TITLE))
    similar = [{"id": "pr", "start_date": "2026-12-11T10:00:00+00:00", "name_ja": "台湾音市 NEXT 2026", "source_name": "prtimes"}]
    md = iu.render_preview(page, [], 0, similar)
    assert "可能重複" in md and "/ja/events/pr" in md and "2026-12-11" in md


def test_result_explains_404_before_annotation():
    md = iu.render_result({"url": "https://example.com/a", "host": "example.com", "status": "inserted",
                           "event_url": iu.event_link("x"), "same_host_count": 1})
    assert "404" in md

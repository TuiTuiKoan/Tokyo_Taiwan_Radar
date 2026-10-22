"""A failed list/API fetch must raise, not return [].

main.py only records success=False when scrape() raises, so a scraper that swallows a
blocked or broken list endpoint and returns [] shows up as "success, 0 events"
(#375 #376 #377 #378).
"""
import pytest
import requests
from playwright.sync_api import TimeoutError as PWTimeout

from sources import bookandbeer, jposa_ja, mot, taipei_fukuoka, tokyoartbeat, tokyonow


class FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None, url="https://example.test/", headers=None):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self._json = json_data
        self.url = url
        self.headers = headers or {"content-type": "text/html"}
        self.apparent_encoding = "utf-8"
        self.encoding = "utf-8"

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Error for url: {self.url}", response=self)


def patch_get(monkeypatch, handler):
    """Route requests.get and requests.Session.get through handler(url, params)."""
    monkeypatch.setattr(requests, "get", lambda url, **kw: handler(url, kw.get("params")))
    monkeypatch.setattr(requests.Session, "get", lambda self, url, **kw: handler(url, kw.get("params")))
    monkeypatch.setattr("time.sleep", lambda *_: None)


# ---------------------------------------------------------------- mot

def test_mot_raises_when_json_is_forbidden(monkeypatch):
    patch_get(monkeypatch, lambda url, params: FakeResponse(403, "<html>404 Not Found</html>", url=url))
    with pytest.raises(requests.HTTPError):
        mot.MotScraper().scrape()


@pytest.mark.parametrize("payload", [{}, [], "oops"])
def test_mot_raises_on_unexpected_json(monkeypatch, payload):
    patch_get(monkeypatch, lambda url, params: FakeResponse(200, json_data=payload, url=url))
    with pytest.raises(RuntimeError):
        mot.MotScraper().scrape()


def test_mot_returns_empty_when_nothing_matches(monkeypatch):
    listing = [{"id": 1, "type": "collections", "title": "Collection", "permalink": "/c/", "start": 20260101, "end": 20261231}]
    patch_get(monkeypatch, lambda url, params: FakeResponse(200, json_data=listing, url=url))
    assert mot.MotScraper().scrape() == []


# ---------------------------------------------------------------- taipei_fukuoka

ROC_ERROR_PAGE = "<html><head><title>The website is under repair</title></head><body>repair</body></html>"


def test_taipei_fukuoka_raises_on_block_page(monkeypatch):
    # roc-taiwan.org redirects GitHub Actions IPs to /Embassy_Error/ (200 HTML)
    patch_get(monkeypatch, lambda url, params: FakeResponse(200, ROC_ERROR_PAGE, url=url))
    with pytest.raises(RuntimeError, match="no .news-item"):
        taipei_fukuoka.TaipeiFukuokaScraper().scrape()


def test_taipei_fukuoka_raises_when_list_fetch_fails(monkeypatch):
    patch_get(monkeypatch, lambda url, params: FakeResponse(403, "denied", url=url))
    with pytest.raises(RuntimeError, match="failed to fetch main page"):
        taipei_fukuoka.TaipeiFukuokaScraper().scrape()


def test_taipei_fukuoka_empty_when_no_local_posts(monkeypatch):
    html = '<div class="news-item"><div class="text-holder"><a href="https://example.test/ext">x</a></div></div>'
    patch_get(monkeypatch, lambda url, params: FakeResponse(200, html, url=url))
    assert taipei_fukuoka.TaipeiFukuokaScraper().scrape() == []


# ---------------------------------------------------------------- jposa_ja

def test_jposa_ja_raises_when_feed_is_forbidden(monkeypatch):
    patch_get(monkeypatch, lambda url, params: FakeResponse(403, "denied", url=url))
    with pytest.raises(RuntimeError, match="RSS fetch failed"):
        jposa_ja.JposaJaScraper().scrape()


def test_jposa_ja_raises_when_feed_returns_html_block_page(monkeypatch):
    # 200 OK but no <item>: the 0.08 s "0 events found" run seen in production
    patch_get(monkeypatch, lambda url, params: FakeResponse(200, ROC_ERROR_PAGE, url=url))
    with pytest.raises(RuntimeError, match="no RSS items"):
        jposa_ja.JposaJaScraper().scrape()


def test_jposa_ja_tolerates_404_past_the_last_page(monkeypatch):
    item = (
        "<item><title><![CDATA[台湾映画上映会]]></title>"
        "<link>https://www.roc-taiwan.org/jposa_ja/post/1.html</link>"
        "<pubDate>Mon, 01 Jan 2001 00:00:00 +0900</pubDate></item>"
    )
    feed = "<rss><channel>" + item * 10 + "</channel></rss>"

    def handler(url, params):
        if "paged=1" in url:
            return FakeResponse(200, feed, url=url)
        return FakeResponse(404, "not found", url=url)

    patch_get(monkeypatch, handler)
    # items are older than LOOKBACK_DAYS, so they are cut off; page 2 is never needed
    assert jposa_ja.JposaJaScraper().scrape() == []


# ---------------------------------------------------------------- tokyo_art_beat

def cda_handler(total_upcoming, items=()):
    def handler(url, params):
        params = params or {}
        if "query" in params:
            return FakeResponse(200, json_data={"total": len(items), "items": list(items), "includes": {}}, url=url)
        return FakeResponse(200, json_data={"total": total_upcoming, "items": []}, url=url)
    return handler


def test_tokyo_art_beat_raises_on_unauthorized(monkeypatch):
    patch_get(monkeypatch, lambda url, params: FakeResponse(401, json_data={"sys": {"id": "AccessTokenInvalid"}}, url=url))
    with pytest.raises(RuntimeError, match="status=401"):
        tokyoartbeat.TokyoArtBeatScraper().scrape()


def test_tokyo_art_beat_error_message_does_not_leak_token(monkeypatch):
    monkeypatch.setattr(tokyoartbeat, "CONTENTFUL_TOKEN", "SECRET-TOKEN-VALUE")

    def boom(url, params):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}?access_token={params['access_token']}")

    patch_get(monkeypatch, boom)
    with pytest.raises(RuntimeError) as excinfo:
        tokyoartbeat.TokyoArtBeatScraper().scrape()
    assert "SECRET-TOKEN-VALUE" not in str(excinfo.value)
    assert excinfo.value.__cause__ is None and excinfo.value.__suppress_context__


def test_tokyo_art_beat_raises_when_space_is_frozen(monkeypatch):
    # the old cdn.contentful.com space answers 200 with only 18 stale events
    patch_get(monkeypatch, cda_handler(total_upcoming=18))
    with pytest.raises(RuntimeError, match="moved or is frozen"):
        tokyoartbeat.TokyoArtBeatScraper().scrape()


def test_tokyo_art_beat_empty_result_on_live_space_is_not_an_error(monkeypatch):
    patch_get(monkeypatch, cda_handler(total_upcoming=1740))
    assert tokyoartbeat.TokyoArtBeatScraper().scrape() == []


def test_tokyo_art_beat_uses_the_live_cda_proxy():
    assert tokyoartbeat.CONTENTFUL_BASE.startswith("https://cdn.prod.tabdev.net/api/cda/published/")


def test_tokyo_art_beat_parse_error_is_logged_not_crashing(caplog):
    # used to raise AttributeError: no attribute 'logger'
    scraper = tokyoartbeat.TokyoArtBeatScraper()
    with caplog.at_level("WARNING"):
        assert scraper._parse_event({"sys": {"id": "x"}, "fields": None}, {}) is None
    assert "Failed to parse event x" in caplog.text


# ---------------------------------------------------------------- tokyo_now

def test_tokyo_now_raises_when_events_api_is_404(monkeypatch):
    patch_get(monkeypatch, lambda url, params: FakeResponse(404, json_data={"code": "rest_no_route"}, url=url))
    with pytest.raises(requests.HTTPError):
        tokyonow.TokyoNowScraper().scrape()


def test_tokyo_now_raises_on_unexpected_payload(monkeypatch):
    patch_get(monkeypatch, lambda url, params: FakeResponse(200, json_data={"hello": "world"}, url=url))
    with pytest.raises(RuntimeError, match="unexpected API payload"):
        tokyonow.TokyoNowScraper().scrape()


# ---------------------------------------------------------------- bookandbeer

class FakeLocator:
    def __init__(self, n):
        self._n = n

    def count(self):
        return self._n


class FakePage:
    def __init__(self, cards=0, goto_error=None):
        self.cards = cards
        self.goto_error = goto_error

    def goto(self, url, timeout=0):
        if self.goto_error:
            raise self.goto_error

    def wait_for_load_state(self, *args, **kwargs):
        pass

    def locator(self, selector):
        return FakeLocator(self.cards)


class FakePlaywright:
    def __init__(self, page):
        self.chromium = self
        self._page = page

    def launch(self, headless=True):
        page = self._page

        class Browser:
            def new_context(self_inner):
                class Ctx:
                    def new_page(self_ctx):
                        return page

                    def close(self_ctx):
                        pass

                return Ctx()

            def close(self_inner):
                pass

        return Browser()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_bookandbeer_raises_when_page_1_has_no_cards(monkeypatch):
    monkeypatch.setattr(bookandbeer, "sync_playwright", lambda: FakePlaywright(FakePage(cards=0)))
    with pytest.raises(RuntimeError, match="no article.article-archive-detail cards"):
        bookandbeer.BookandbeerScraper().scrape()


def test_bookandbeer_raises_when_page_1_times_out(monkeypatch):
    page = FakePage(goto_error=PWTimeout("timeout"))
    monkeypatch.setattr(bookandbeer, "sync_playwright", lambda: FakePlaywright(page))
    with pytest.raises(RuntimeError, match="listing page 1 timed out"):
        bookandbeer.BookandbeerScraper().scrape()

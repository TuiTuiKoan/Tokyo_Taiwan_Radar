from sources import johakyu as johakyu_module
from sources import starcat_cinema as starcat_module
from sources.johakyu import JohakyuScraper, _THEATERS
from sources.starcat_cinema import (
    StarcatCinemaScraper,
    THEATER_LOCATIONS,
    TICKET_SCHEDULE_URLS,
)


class _ScheduleResponse:
    def __init__(self, html):
        self.content = html.encode("utf-8")

    def raise_for_status(self):
        return None


def test_johakyu_uses_current_official_addresses_without_homepages():
    by_name = {theater["name"]: theater for theater in _THEATERS}

    assert by_name["八丁座"]["location_address"] == (
        "広島県広島市中区胡町6-26 福屋八丁堀本店8F"
    )
    assert by_name["サロンシネマ"]["location_address"] == (
        "広島県広島市中区八丁堀16-10 広島東映プラザビル8階"
    )
    assert all("location_url" not in theater for theater in _THEATERS)
    assert all("homepage" not in theater for theater in _THEATERS)


def test_century_uses_parco_address_and_ticket_url_only_for_schedule():
    century = THEATER_LOCATIONS["センチュリーシネマ"]

    assert century["address"] == (
        "愛知県名古屋市中区栄3-29-1 名古屋パルコ東館8F"
    )
    assert "location_url" not in century
    assert "homepage" not in century
    assert TICKET_SCHEDULE_URLS["センチュリーシネマ"] == (
        "https://www.starcat-ticket.com/cc/theater/century/schedule"
    )


def test_johakyu_event_leaves_homepage_to_registry(monkeypatch):
    html = """
    <section class="schedule-sec">
      <div class="schedule-date-block">
        <div class="schedule-week">8月1日(金)～8月7日(木)のスケジュール</div>
        <div class="schedule-movie-list__item">
          <h3 class="schedule-movie__title">
            <a href="https://films.example/taiwan">台湾映画</a>
          </h3>
          <img src="/images/movie_10001.jpg">
        </div>
      </div>
    </section>
    """
    scraper = JohakyuScraper()
    monkeypatch.setattr(
        scraper._session,
        "get",
        lambda *_args, **_kwargs: _ScheduleResponse(html),
    )
    monkeypatch.setattr(
        johakyu_module,
        "lookup_movie_titles",
        lambda _title: (None, None, None),
    )
    monkeypatch.setattr(johakyu_module.time, "sleep", lambda _seconds: None)

    event = scraper.scrape()[0]

    assert event.location_address == "広島県広島市中区胡町6-26 福屋八丁堀本店8F"
    assert event.source_url == "https://johakyu.co.jp/schedule.html"
    assert event.location_url is None


def test_century_event_keeps_ticket_url_out_of_event_url_fields(monkeypatch):
    scraper = StarcatCinemaScraper()
    ticket_url = TICKET_SCHEDULE_URLS["センチュリーシネマ"]
    schedule_calls = []
    monkeypatch.setattr(
        scraper,
        "_get",
        lambda url: schedule_calls.append(url) or None,
    )

    assert scraper._build_ticket_schedule("センチュリーシネマ") == {}
    assert schedule_calls == [ticket_url]

    detail_url = "https://eiga.starcat.co.jp/schedule/detail/?thumbnail=10001"
    monkeypatch.setattr(
        scraper,
        "_collect_listing",
        lambda: [
            {
                "thumbnail_id": "10001",
                "detail_url": detail_url,
                "theater": "センチュリーシネマ",
                "link_text": "センチュリーシネマ 台湾映画",
            }
        ],
    )
    monkeypatch.setattr(
        scraper,
        "_scrape_detail",
        lambda _url: {
            "title": "台湾映画",
            "description": "台湾映画の紹介",
            "full_text": "台湾映画の紹介",
            "date_text": "2026年8月1日(土)より公開",
            "theater": "センチュリーシネマ",
        },
    )
    monkeypatch.setattr(scraper, "_lookup_end_date", lambda *_args: None)
    monkeypatch.setattr(
        scraper,
        "_lookup_business_hours",
        lambda *_args: "8/1(土): 10:00〜12:00",
    )
    monkeypatch.setattr(starcat_module.time, "sleep", lambda _seconds: None)

    event = scraper.scrape()[0]

    assert event.location_address == (
        "愛知県名古屋市中区栄3-29-1 名古屋パルコ東館8F"
    )
    assert event.business_hours == "8/1(土): 10:00〜12:00"
    assert event.source_url == detail_url
    assert event.location_url is None
    assert ticket_url not in {event.source_url, event.official_url, event.location_url}

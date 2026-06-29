from datetime import datetime

from bs4 import BeautifulSoup

from sources.amayaza import (
    _extract_business_hours,
    _extract_detail_title,
    _extract_film_title,
    _parse_dates_from_title,
    _select_post_title,
)


def test_empty_listing_title_uses_detail_title_for_film_dates_and_hours():
    post_title = _select_post_title("", "『日泰食堂』 2026/7/4（土）〜7/10（金） | あまや座")
    start_date, end_date = _parse_dates_from_title(post_title)

    assert _extract_film_title(post_title) == "日泰食堂"
    assert start_date == datetime(2026, 7, 4)
    assert end_date == datetime(2026, 7, 10)
    assert _extract_business_hours("7/4（土）〜10（金）10:05〜11:38") == "10:05〜11:38"


def test_detail_title_prefers_og_title_over_navigation_articles():
        soup = BeautifulSoup(
                """
                <html>
                    <head><meta property="og:title" content="『日泰食堂』2026/7/4（土）〜7/10（金）" /></head>
                    <body><article><h1>『廃用身』2026/6/20（土）〜7/3（金）</h1></article></body>
                </html>
                """,
                "html.parser",
        )

        assert _extract_detail_title(soup) == "『日泰食堂』2026/7/4（土）〜7/10（金）"


def test_extract_business_hours_from_screening_period_line():
    assert _extract_business_hours("7/4（土）〜10（金）10:05〜11:38") == "10:05〜11:38"


def test_extract_business_hours_normalizes_wave_dash():
    assert _extract_business_hours("上映時間 10:05～11:38") == "10:05〜11:38"


def test_extract_business_hours_returns_none_without_time_range():
    assert _extract_business_hours("上映期間のみ 7/4（土）〜10（金）") is None

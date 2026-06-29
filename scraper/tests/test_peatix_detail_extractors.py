from sources.peatix import (
    _extract_peatix_business_hours,
    _extract_peatix_location_from_text,
    _extract_price_from_text,
)


def test_extract_business_hours_from_japanese_date_block():
    page_text = """
日時

2026/6/30(火)

14:00 - 15:30 GMT+09:00

場所
"""

    assert _extract_peatix_business_hours(page_text) == "14:00 - 15:30 GMT+09:00"


def test_extract_business_hours_from_body_label():
    page_text = "時　間｜14:00~15:30\n参加費｜2,500円(税込)"

    assert _extract_peatix_business_hours(page_text) == "14:00~15:30"


def test_extract_business_hours_from_english_date_block():
    page_text = """
DATE AND TIME

Mon, May 12, 2025

1:00 PM - 2:00 PM GMT+09:00
"""

    assert _extract_peatix_business_hours(page_text) == "1:00 PM - 2:00 PM GMT+09:00"


def test_extract_business_hours_from_date_text_fallback():
    assert _extract_peatix_business_hours("", "14:00 - 15:30") == "14:00 - 15:30"


def test_extract_business_hours_returns_none_when_absent():
    assert _extract_peatix_business_hours("台湾茶イベント\n時間未定") is None


def test_extract_location_from_japanese_block():
    page_text = """
場所

誠品生活日本橋

中央区日本橋室町３丁目２−１ COREDO室町テラス 2F

Japan
"""

    location_name, location_address = _extract_peatix_location_from_text(page_text)

    assert location_name == "誠品生活日本橋"
    assert "日本橋室町３丁目２−１" in location_address
    assert location_address != location_name


def test_extract_location_from_english_block():
    page_text = """
LOCATION

Tokyo Taiwan Center

東京都港区虎ノ門1丁目1-1

Japan
"""

    assert _extract_peatix_location_from_text(page_text) == (
        "Tokyo Taiwan Center",
        "東京都港区虎ノ門1丁目1-1",
    )


def test_extract_location_rejects_japanese_ward_only_address():
    page_text = """
場所

誠品生活日本橋

東京都中央区

Japan
"""

    assert _extract_peatix_location_from_text(page_text) == ("誠品生活日本橋", None)


def test_extract_location_english_online_event():
    page_text = """
LOCATION

Online event

Event description
"""

    assert _extract_peatix_location_from_text(page_text) == ("オンライン", "オンライン")


def test_extract_location_japanese_online_event():
    page_text = """
場所

オンライン

イベント詳細
"""

    assert _extract_peatix_location_from_text(page_text) == ("オンライン", "オンライン")


def test_extract_location_returns_none_without_structured_block():
    assert _extract_peatix_location_from_text("東京都中央区\n台湾茶イベント") == (None, None)

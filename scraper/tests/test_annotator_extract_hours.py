from annotator import _extract_hours_from_raw


def test_extract_hours_keeps_multi_day_date_specific_ranges():
    raw = """開催日時: 2026年07月13日 ～ 2026年07月14日

鄭成功まつりは、開催日は前夜祭が7月13日17:00～20:00、神事が7月14日10:00～11:30です。"""

    assert _extract_hours_from_raw(raw) == "7/13（月） 17:00〜20:00\n7/14（火） 10:00〜11:30"


def test_extract_hours_single_date_time_range_uses_generic_range():
    assert _extract_hours_from_raw("2026年8月1日（土）10:00～20:00") == "10:00〜20:00"


def test_extract_hours_simple_range_still_works():
    assert _extract_hours_from_raw("提供時間は12:00～17:30です。") == "12:00〜17:30"


def test_extract_hours_kanji_time_fallback_still_works():
    assert _extract_hours_from_raw("開演：13時30分") == "13:30〜"
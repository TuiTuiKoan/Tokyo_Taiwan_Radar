from annotator import _apply_small_venue_organizer_fallback, _inject_keyword_categories


def test_taiwan_city_birthplace_injects_history():
    text = "小俣冠丞 Kanjo Omata\n台湾台中市 出身"

    assert "history" in _inject_keyword_categories(["exhibition"], text)


def test_taiwan_born_writer_injects_history():
    text = "台湾生まれの作家による新作展"

    assert "history" in _inject_keyword_categories(["exhibition"], text)


def test_non_taiwan_birthplace_with_taiwan_later_does_not_inject_history():
    text = "京都市出身。台湾及び中国上海で活動。"

    assert "history" not in _inject_keyword_categories(["exhibition"], text)


def test_taiwan_university_alumnus_does_not_inject_history():
    text = "台湾大学出身の研究者による講演"

    assert "history" not in _inject_keyword_categories(["lecture"], text)


def test_small_exhibition_venue_fallback_sets_organizer_and_type():
    event = {"source_name": "venue_owned_source", "category": []}
    update_data = {
        "event_form": ["exhibition"],
        "location_name": "急須と器 いそべ",
        "organizer_type": ["unknown"],
    }

    _apply_small_venue_organizer_fallback(event, update_data, "会場：急須と器 いそべ")

    assert update_data["organizer"] == "急須と器 いそべ"
    assert update_data["organizer_type"] == ["independent_venue"]


def test_large_venue_does_not_fallback_to_organizer():
    event = {"source_name": "venue_owned_source", "category": []}
    update_data = {
        "event_form": ["exhibition"],
        "location_name": "東京ビッグサイト",
        "organizer_type": ["unknown"],
    }

    _apply_small_venue_organizer_fallback(event, update_data, "会場：東京ビッグサイト")

    assert "organizer" not in update_data
    assert update_data["organizer_type"] == ["unknown"]


def test_aggregator_source_does_not_fallback_to_organizer():
    event = {"source_name": "tokyoartbeat", "category": []}
    update_data = {
        "event_form": ["exhibition"],
        "location_name": "急須と器 いそべ",
        "organizer_type": ["unknown"],
    }

    _apply_small_venue_organizer_fallback(event, update_data, "会場：急須と器 いそべ")

    assert "organizer" not in update_data
    assert update_data["organizer_type"] == ["unknown"]


def test_existing_organizer_is_not_overwritten():
    event = {"source_name": "venue_owned_source", "category": [], "organizer": "既存主催"}
    update_data = {
        "event_form": ["exhibition"],
        "location_name": "急須と器 いそべ",
        "organizer_type": ["civic_group"],
    }

    _apply_small_venue_organizer_fallback(event, update_data, "会場：急須と器 いそべ")

    assert "organizer" not in update_data
    assert update_data["organizer_type"] == ["civic_group"]


def test_field_corrections_protected_organizer_is_not_overwritten():
    event = {"source_name": "venue_owned_source", "category": []}
    update_data = {
        "event_form": ["exhibition"],
        "location_name": "急須と器 いそべ",
        "organizer_type": ["unknown"],
    }

    _apply_small_venue_organizer_fallback(
        event,
        update_data,
        "会場：急須と器 いそべ",
        {"organizer": "人手補正"},
    )

    assert "organizer" not in update_data
    assert update_data["organizer_type"] == ["unknown"]


def test_archive_streaming_ticket_is_not_a_report_or_history():
    # #711: 台湾音市 NEXT 2026 (prtimes) got report + history from this line.
    text = "ライブイベント開催決定！＜オンライン配信チケット＞【オンライン視聴券】後日アーカイブ配信：4,000円（税込）"
    cats = _inject_keyword_categories(["performing_arts"], text)
    assert "report" not in cats
    assert "history" not in cats


def test_real_archive_keywords_still_inject_history():
    assert "history" in _inject_keyword_categories(["exhibition"], "戦前の台湾写真アーカイブを公開する展示")


def test_report_category_is_never_injected():
    # spec no-event-reports: the report category was retired on 2026-11-22.
    assert "report" not in _inject_keyword_categories(["art"], "台湾映画祭 開催レポート")

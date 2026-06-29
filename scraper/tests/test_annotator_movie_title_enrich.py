from annotator import _movie_title_name_updates


def test_embedded_movie_title_update_preserves_talk_show_wrapper():
    event = {
        "source_name": "peatix",
        "raw_title": "7/4(土)【オンライン】『海辺の一日 4Kレストア』公開記念トークショー",
        "name_ja": "7/4(土)【オンライン】『海辺の一日 4Kレストア』公開記念トークショー",
        "name_zh": "【線上】《海邊的一天 4K修復版》公開紀念座談會",
        "name_en": 'Online "A Day by the Sea 4K Restoration" Release Commemorative Talk Show',
    }

    update = _movie_title_name_updates(
        event,
        name_zh="海灘的一天 4K修復版",
        name_en="That Day, on the Beach 4K Restoration",
        resolution_kind="embedded_bracket",
    )

    assert update == {
        "name_zh": "【線上】《海灘的一天 4K修復版》公開紀念座談會",
        "name_en": 'Online "That Day, on the Beach 4K Restoration" Release Commemorative Talk Show',
    }


def test_suffix_normalized_screening_update_replaces_whole_movie_title():
    event = {
        "source_name": "cinema",
        "raw_title": "海辺の一日 4Kレストア",
        "name_ja": "海辺の一日 4Kレストア",
        "name_zh": "海邊的一天 4K修復版",
        "name_en": "A Day by the Sea 4K Restoration",
    }

    assert _movie_title_name_updates(
        event,
        name_zh="海灘的一天 4K修復版",
        name_en="That Day, on the Beach 4K Restoration",
        resolution_kind="suffix_normalized",
    ) == {
        "name_zh": "海灘的一天 4K修復版",
        "name_en": "That Day, on the Beach 4K Restoration",
    }
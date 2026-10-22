from eval_annotator import sync_title_in_descriptions


def test_sync_title_replaces_bracketed_old_titles_in_both_descriptions():
    ann = {
        "description_zh": "電影《霧的故事》是2025年上映的台灣電影。",
        "description_en": "The film 'A Foggy Tale' is a Taiwanese movie.",
    }
    sync_title_in_descriptions(
        ann,
        old_name_zh="霧的故事",
        old_name_en="Misty Story",
        new_name_zh="大濛",
        new_name_en="A Foggy Tale",
    )
    assert ann["description_zh"] == "電影《大濛》是2025年上映的台灣電影。"
    # English title was not quoted with a recognised bracket pair → untouched.
    assert ann["description_en"] == "The film 'A Foggy Tale' is a Taiwanese movie."


def test_sync_title_noop_when_title_unresolved_or_unbracketed():
    ann = {"description_zh": "電影霧的故事上映", "description_en": ""}
    sync_title_in_descriptions(
        ann, old_name_zh="霧的故事", old_name_en=None, new_name_zh=None, new_name_en=None,
    )
    assert ann == {"description_zh": "電影霧的故事上映", "description_en": ""}


def test_sync_title_news_source_also_replaces_lookup_title():
    ann = {"description_zh": "新作《霧のごとく》公開", "description_en": ""}
    sync_title_in_descriptions(
        ann,
        old_name_zh="別名",
        old_name_en=None,
        new_name_zh="大濛",
        new_name_en=None,
        lookup_title="霧のごとく",
        is_news_source=True,
    )
    assert ann["description_zh"] == "新作《大濛》公開"

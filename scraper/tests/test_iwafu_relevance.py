"""Regression tests for the 2026-10-12 iwafu incident.

iwafu changed its card and detail layouts and broadened its keyword search.
16 Conan escape-game events were saved with the title 「詳細を見る」 and no
Taiwan connection. See .github/skills/sources/iwafu/history.md.
"""

from sources.iwafu import (
    _clean_og_title,
    _extract_title_from_card,
    _GLOBAL_TOUR_PATTERNS,
    _is_ui_title,
    _mentions_taiwan,
    _strip_iwafu_noise,
    _title_anomaly,
)

CONAN = "リアル脱出ゲーム×名探偵コナン最新作『疾風の追走（ハイウェイ）からの脱出』"


# --- card title -------------------------------------------------------------

def test_card_title_new_layout_title_first():
    lines = [
        CONAN,
        "大阪2026.07.09 ～ 2026.10.12",
        CONAN,
        "- 大人気テレビアニメ「名探偵コナン」とコラボレーションした…",
        "文化/芸術キャラクター/アニメ",
        "心斎橋駅",
    ]
    assert _extract_title_from_card(lines) == CONAN


def test_card_title_old_layout_date_first():
    lines = [
        "2026.06.26 ～ 2026.06.28",
        "台湾フェスティバル TOKYO",
        "",
        "- 上野恩賜公園で開催",
        "東京",
        "上野駅",
    ]
    assert _extract_title_from_card(lines) == "台湾フェスティバル TOKYO"


def test_card_title_skips_ui_label():
    assert _extract_title_from_card(["詳細を見る", "2026.10.10", "台湾文化祭"]) == "台湾文化祭"


# --- detail title -----------------------------------------------------------

def test_og_title_strips_site_branding():
    og = (
        f"iwafu ワフ - {CONAN}｜関西 大阪｜日本期間限定文化旅行ガイド｜"
        "深い体験と地域活動情報プラットフォーム"
    )
    assert _clean_og_title(og) == CONAN


def test_og_title_keeps_fullwidth_bar_inside_title():
    og = "iwafu ワフ - 台湾映画上映会｜監督トーク付き｜関東 東京｜日本期間限定文化旅行ガイド｜x"
    assert _clean_og_title(og) == "台湾映画上映会｜監督トーク付き"


def test_ui_titles_are_rejected():
    assert _is_ui_title("詳細を見る")
    assert _is_ui_title(" 詳細を見る ")
    assert not _is_ui_title("台湾文化祭2026秋")


# --- relevance --------------------------------------------------------------

def test_conan_og_description_triggers_global_tour_reject():
    og_desc = (
        "大人気テレビアニメ「名探偵コナン」とコラボレーションしたリアル脱出ゲームの最新作"
        "『疾風の追走(ハイウェイ)からの脱出』が、全国各地をはじめ、台湾など世界各地で開催！"
    )
    assert _GLOBAL_TOUR_PATTERNS.search(og_desc)


def test_ai_summary_without_taiwan_fails_phase2():
    # iwafu's AI summary dropped 台湾 — this is what reached the DB on 10/12.
    summary = "大人気テレビアニメ「名探偵コナン」とコラボレーションしたリアル脱出ゲーム最新作が日本や世界で各地で開催されます。"
    assert not _mentions_taiwan("詳細を見る", summary)


def test_unrelated_fuzzy_search_results_fail_phase2():
    assert not _mentions_taiwan("第33回 鉄道フェスティバル", "お台場イーストプロムナードで開催")
    assert not _mentions_taiwan("きらきら焼き芋パフェ", "岡田美術館の足湯カフェにて")


def test_taiwan_events_pass_phase2():
    assert _mentions_taiwan("台湾文化祭2026秋（10月10日～12日 丸の内KITTE）", "")
    assert _mentions_taiwan("Freckles Japan Tour", "From TAIWAN indie band")
    assert _mentions_taiwan("赤城で台灣さんぽ", "")


# --- run-level anomaly guard ------------------------------------------------

def test_title_anomaly_detects_layout_break():
    titles = ["詳細を見る"] * 16 + ["台湾文化祭"]
    assert _title_anomaly(titles) == "詳細を見る"


def test_title_anomaly_ignores_healthy_runs():
    assert _title_anomaly(["台湾映画祭"] * 3 + ["台湾フェス", "台湾茶会"]) is None
    assert _title_anomaly(["a", "b", "c", "d", "e", "f"]) is None
    assert _title_anomaly(["x"] * 4) is None  # below min_count


# --- noise stripping --------------------------------------------------------

def test_new_layout_noise_markers_are_stripped():
    text = "本文です。\n\nタグ\n\n# キャラクター/アニメ\n近くのスポット\n心斎橋筋商店街"
    assert _strip_iwafu_noise(text) == "本文です。"

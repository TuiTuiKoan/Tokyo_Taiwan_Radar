"""Shared Taiwan keyword regex (spec coverage-audit Phase A, #701)."""
import pytest

from taiwan_keywords import compound_only, has_taiwan_keyword

POSITIVE = [
    "報道写真展「日中台：交錯するまなざし―写真でたどる100年の歩み―」 開催のお知らせ",
    "日台交流イベント開催",
    "台日友好フェア",
    "2026日台交流フェア",
    "第3回日台文化交流展",
    "台湾フェスティバル2026を東京で開催",
    "台灣電影節",
    "臺灣文化展",
    "TAIWAN NIGHT in 渋谷",
    "taiwan pop live",
]

# Common Japanese words that contain the compounds as bare substrings
# (plan-critique-1 B1), plus 中台禅寺.
NEGATIVE = [
    "ミュージカル舞台日本公演 開催決定",
    "本日台数限定セール開催",
    "1日台数限定 体験イベント",
    "今日台風接近によりイベント開催中止",
    "屋台日本一決定戦 開催",
    "毎日台所から 料理教室イベント",
    "日中台風の影響でフェス中止",
    "中台禅寺 特別拝観 開催",
    "土日台風対策セミナー",
    "灯台日和 写真展",
    "寝台列車の旅 説明会",
    "3日台風一過 イベント再開",
    "1日台数限定",
]


@pytest.mark.parametrize("title", POSITIVE)
def test_taiwan_titles_match(title):
    assert has_taiwan_keyword(title)


@pytest.mark.parametrize("title", NEGATIVE)
def test_everyday_words_do_not_match(title):
    assert not has_taiwan_keyword(title)


def test_compound_only():
    assert compound_only("日台交流イベント開催")
    assert compound_only("報道写真展「日中台：交錯するまなざし」")
    assert not compound_only("台湾と日台交流イベント")
    assert not compound_only("台湾フェア")
    assert not compound_only("舞台日本公演")

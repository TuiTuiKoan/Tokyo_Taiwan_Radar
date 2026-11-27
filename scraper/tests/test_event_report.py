"""Event-report detection (spec no-event-reports, 2026-11-22).

Titles are real production rows from the 2026-11-22 read-only inventory.
"""

import pytest

from event_report import is_event_report, strip_report_prefix


@pytest.mark.parametrize(
    "title",
    [
        "台湾文化センター台湾映画上映会2026 -映画『うなぎ』（原題：河鰻）トークイベント レポート",
        "台湾映画上映会2026『荒野の夢』上映会【トークイベントレポート】 - Cinem＠rt",
        "〈台湾映画上映会2026〉8/1(土)映画『夜明けの前に』 ≪ トークイベント レポート ≫ - cinemart.co.jp",
        "台湾『にゃんこ大戦争』13周年イベント現地レポート！",
        "【開催報告】延べ4万人が来場！京都と台湾を「食・文化・交流」でつないだ「京都台湾祭2026」が閉幕",
        "【九州企業は「台湾」に熱視線！】圧倒的な大盛況で閉幕「海外ビジネスEXPO2026九州」開催報告",
        "活動記録｜《霧のごとく》05/10東京貸切鑑賞会",
        "【結果発表】「みんなの台湾修学旅行ナビ」台湾教育旅行プランニング大賞",
        "台湾フェスに行ってきた",
        "台灣文化節 活動紀錄",
        "Taiwan Night Market Festival recap",
    ],
)
def test_recaps_are_event_reports(title):
    assert is_event_report(title, ["screening_with_talk"])


@pytest.mark.parametrize(
    "title",
    [
        "アジア教育視察2026報告会",          # upcoming presentation event
        "2026年度 活動報告会のお知らせ",
        "定例研究会 歴史・政治・経済部会 第195回",
        "甲府北口で「超級台湾屋台祭」 台湾の夜市を再現する9日間 - 甲府経済新聞",
        "台湾の日本神を巡る旅を6年にわたって記録、ドキュメンタリー「軍服を着た神様」公開決定",
        "オーガニック食材によるアトピー性皮膚炎改善ーその症例報告・臨床試験ー",
        "現役レポーターが語る台湾",
        "台湾に行ってきた！視察報告会",                 # whole-title veto
        "台湾フォトコンテスト2026（結果発表：3月）",      # bare 結果発表 = schedule
        "台湾フォトコンテスト 結果発表会",
        "台湾ツアー参加報告と次回参加者募集",
        "",
        None,
    ],
)
def test_non_recaps_are_kept(title):
    assert not is_event_report(title, ["lecture"])


def test_publications_are_never_event_reports():
    assert not is_event_report("2025 年度「海外文化研究」台湾研修報告", ["publication"])
    assert not is_event_report("台湾内政部消防署 RIT専任教育課程受講レポート", ["publication"])


def test_annotator_gate_exempts_broadcast_sources_with_empty_event_form():
    from annotator import _event_report_gate_update

    tv = {"source_name": "gguide_tv", "raw_title": "台湾旅レポート", "event_form": []}
    assert _event_report_gate_update(tv, {}, False, []) is None


def test_annotator_gate_deactivates_recap_and_respects_human_locks():
    from annotator import _event_report_gate_update
    from event_report import EVENT_REPORT_REASON

    ev = {"source_name": "prtimes", "raw_title": "【開催報告】京都台湾祭2026が閉幕", "event_form": []}
    assert _event_report_gate_update(ev, {}, False, ["market"]) == {
        "is_active": False, "deactivated_reason": EVENT_REPORT_REASON,
    }
    assert _event_report_gate_update(ev, {"name_ja": "x"}, False, ["market"]) is None
    assert _event_report_gate_update(ev, {}, True, ["market"]) is None
    upcoming = {"source_name": "kokuchpro", "raw_title": "アジア教育視察2026報告会", "event_form": []}
    assert _event_report_gate_update(upcoming, {}, False, ["lecture"]) is None


def test_broadcasts_are_never_event_reports():
    assert not is_event_report("台湾旅レポート", ["broadcast"])


def test_strip_report_prefix():
    assert strip_report_prefix("【レポート】京都台湾祭") == "京都台湾祭"
    assert strip_report_prefix("【活動報導】京都台灣祭") == "京都台灣祭"
    assert strip_report_prefix("[Report] Kyoto Taiwan Fest") == "Kyoto Taiwan Fest"
    assert strip_report_prefix("京都台湾祭") == "京都台湾祭"
    assert strip_report_prefix(None) is None

from datetime import datetime, timezone

import pytest

from sources.taiwan_expo_japan import _parse_date_range, _parse_event_html


SAMPLE_HTML = """
<html lang="ja">
  <head><title>台湾エキスポ 2026</title></head>
  <body>
    <div id="comp-hero" class="wixui-rich-text" data-testid="richTextElement">
      <h6>2026.7.15&nbsp; -7.17</h6>
      <p>2 Chome-6-1 Nishishinjuku, Shinjuku City, Tokyo 160-0023 日本</p>
      <p>東京新宿住友ビル三角広場</p>
    </div>
    <section id="comp-about" class="wixui-rich-text">
      <h2>Taiwan Expo について</h2>
      <p>2017年からはじまった台湾エキスポは、台湾企業と日本の企業交流を支える公式展示会です。</p>
      <p>スマート製造、エネルギー、医療、食品と文化生活を紹介します。\x00</p>
      <h2>2023年 開催実績（ハイライト）</h2>
      <p>2023年11月9日から開催</p>
    </section>
    <section id="comp-schedule" data-testid="richTextElement">
      <h2>イベントスケジュール</h2>
      <h3>7.15</h3>
      <p>10:00-11:10 オープニングセレモニー</p>
    </section>
    <footer><a href="https://www.trade.gov.tw/english/">経済部国際貿易署</a></footer>
  </body>
</html>
"""


@pytest.mark.parametrize(
    ("date_text", "expected_start", "expected_end"),
    [
        ("2026.7.15 -7.17", (2026, 7, 15), (2026, 7, 17)),
        ("2026年7月15日〜17日", (2026, 7, 15), (2026, 7, 17)),
        ("2026/7/31－8/2", (2026, 7, 31), (2026, 8, 2)),
        ("2026.12.31—2027.1.2", (2026, 12, 31), (2027, 1, 2)),
    ],
)
def test_parse_date_range_variants(date_text, expected_start, expected_end):
    start_date, end_date = _parse_date_range(date_text, 2026)

    assert start_date == datetime(*expected_start, tzinfo=timezone.utc)
    assert end_date == datetime(*expected_end, tzinfo=timezone.utc)


def test_parse_event_uses_semantic_boundaries_and_ignores_wix_ids():
    event = _parse_event_html(SAMPLE_HTML)
    renamed_event = _parse_event_html(
        SAMPLE_HTML.replace("comp-", "generated-")
        .replace("wixui-rich-text", "other-class")
        .replace("richTextElement", "otherTestId")
    )

    assert event is not None
    assert renamed_event == event
    assert event.source_name == "taiwan_expo_japan"
    assert event.source_id == "taiwan_expo_japan_2026"
    assert event.start_date == datetime(2026, 7, 15, tzinfo=timezone.utc)
    assert event.end_date == datetime(2026, 7, 17, tzinfo=timezone.utc)
    assert event.location_name == "東京新宿住友ビル三角広場"
    assert event.location_address == (
        "2 Chome-6-1 Nishishinjuku, Shinjuku City, Tokyo 160-0023 日本"
    )
    assert event.organizer == "経済部国際貿易署"
    assert "開催日時: 2026年07月15日〜2026年07月17日" in event.raw_description
    assert "イベントスケジュール" not in event.raw_description
    assert "10:00" not in event.raw_description
    assert "2023年 開催実績" not in event.raw_description
    assert "\x00" not in event.raw_description


def test_parse_event_fails_closed_without_complete_year_date_range():
    html = SAMPLE_HTML.replace("2026.7.15&nbsp; -7.17", "7.15 -7.17")

    assert _parse_event_html(html) is None


def test_parse_event_fails_closed_when_title_and_date_years_disagree():
    html = SAMPLE_HTML.replace("台湾エキスポ 2026", "台湾エキスポ 2025")

    assert _parse_event_html(html) is None


def test_parse_event_fails_closed_without_description_boundary():
    html = SAMPLE_HTML.replace("イベントスケジュール", "当日のご案内").replace(
        "2023年 開催実績（ハイライト）", "過去の実績"
    )

    assert _parse_event_html(html) is None
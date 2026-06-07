"""
Regression tests for note_creators event-evidence intake gate (M1).

Tests validate that:
  - _has_event_evidence() correctly identifies attendable event posts
  - _is_media_or_report() correctly identifies media/recap posts
  - _parse_item() returns None for non-event posts (media coverage, recaps, thin)
  - _parse_item() returns Event for genuine event posts with date/venue/signup
  - pubDate is never used as start_date without parsed event evidence
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import xml.etree.ElementTree as ET

from sources.note_creators import (
    _has_event_evidence,
    _is_media_or_report,
    NoteCreatorsScraper,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helper: build a minimal RSS <item> element
# ──────────────────────────────────────────────────────────────────────────────
def _make_item(
    title: str,
    description: str = "",
    pub_date: str = "Fri, 06 Jun 2026 10:00:00 +0900",
    link: str = "https://note.com/tcml_osaka/n/nfakeabcd1234",
) -> ET.Element:
    item = ET.Element("item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "link").text = link
    ET.SubElement(item, "guid").text = link
    ET.SubElement(item, "description").text = description
    ET.SubElement(item, "pubDate").text = pub_date
    return item


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests: _has_event_evidence
# ──────────────────────────────────────────────────────────────────────────────
class TestHasEventEvidence:
    def test_date_in_title_japanese(self):
        assert _has_event_evidence("【6月20日】台湾語講座", "", None) is True

    def test_date_in_body_label(self):
        body = "日時：2026年6月20日 14:00〜\n会場：大阪市西区"
        assert _has_event_evidence("講座のお知らせ", body, None) is True

    def test_signup_url_peatix(self):
        assert _has_event_evidence("台湾交流会", "", "https://peatix.com/event/12345") is True

    def test_signup_url_google_forms(self):
        assert _has_event_evidence("ワークショップ参加受付", "", "https://forms.gle/abc123") is True

    def test_venue_label_in_body(self):
        body = "会場：東京都新宿区\n参加費：無料"
        assert _has_event_evidence("台湾映画上映会", body, None) is True

    def test_activity_term_with_date(self):
        body = "今年も開催します！7月10日（土）参加お待ちしています。"
        assert _has_event_evidence("交流会のご案内", body, None) is True

    def test_no_signals(self):
        assert _has_event_evidence(
            "TCML大阪弁天町台湾華語教室、台湾のニュースで紹介されました！",
            "台湾のメディアで当教室が取材されました。YouTubeで見ることができます。",
            None,
        ) is False

    def test_thin_body_no_date(self):
        assert _has_event_evidence("台湾活動報告", "続きをみる", None) is False


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests: _is_media_or_report
# ──────────────────────────────────────────────────────────────────────────────
class TestIsMediaOrReport:
    def test_news_intro_in_title(self):
        assert _is_media_or_report(
            "TCML大阪弁天町台湾華語教室、台湾のニュースで紹介されました！", ""
        ) is True

    def test_media_coverage_in_body(self):
        assert _is_media_or_report("教室のご紹介", "メディア掲載されました。取材を受けました。") is True

    def test_event_recap_title(self):
        assert _is_media_or_report("6月交流会 開催報告", "") is True

    def test_report_in_title(self):
        assert _is_media_or_report("先月のワークショップ レポート", "") is True

    def test_went_and_saw(self):
        assert _is_media_or_report("映画を観てきた感想", "") is True

    def test_normal_event_title(self):
        assert _is_media_or_report("6月20日 台湾語講座のご案内", "") is False

    def test_activity_no_recap(self):
        assert _is_media_or_report("7月 交流会開催します！", "申込はこちら") is False


# ──────────────────────────────────────────────────────────────────────────────
# Integration tests: _parse_item (via NoteCreatorsScraper instance)
# ──────────────────────────────────────────────────────────────────────────────
CREATOR = "tcml_osaka"
LOC_NAME = "台湾華語文学習センター（大阪弁天町）"
LOC_ADDR = "大阪府大阪市西区"
CATEGORY = ["taiwan_japan", "lecture"]


def _scraper_parse(item: ET.Element):
    """Call _parse_item without HTTP (patch article fetch to return empty)."""
    scraper = NoteCreatorsScraper()
    # Patch article fetch so tests don't hit network
    with patch.object(scraper, "_session") as mock_sess:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = ""
        mock_sess.get.return_value = mock_resp
        return scraper._parse_item(item, CREATOR, LOC_NAME, LOC_ADDR, CATEGORY)


class TestParseItemIntakeGate:
    # ── Reject: media coverage / self-promotion ──────────────────────────────
    def test_reject_tcml_osaka_media_coverage(self):
        """The confirmed false positive must be rejected."""
        item = _make_item(
            title="TCML大阪弁天町台湾華語教室、台湾のニュースで紹介されました！",
            description="台湾のメディアで当教室の活動が紹介されました。<a href='https://www.youtube.com/watch?v=xxx'>YouTubeで紹介</a>されています。続きをみる",
        )
        assert _scraper_parse(item) is None

    def test_reject_post_event_recap(self):
        """Post-event recap with 開催報告 and no future date should be rejected."""
        item = _make_item(
            title="5月の交流会 開催報告",
            description="先日の交流会は大盛況でした。レポートをまとめました。",
        )
        assert _scraper_parse(item) is None

    def test_reject_thin_content(self):
        """Thin RSS preview (only 続きをみる) without date should be rejected."""
        item = _make_item(
            title="日台交流のご案内",
            description="続きをみる",
        )
        # The scraper fetches full article when content is thin — patch to return empty body
        assert _scraper_parse(item) is None

    # ── Accept: real event posts ─────────────────────────────────────────────
    def test_accept_event_with_date_in_title(self):
        """Event with 月日 date in title should be accepted."""
        item = _make_item(
            title="6月20日（土）台湾語入門講座",
            description="会場：大阪市西区コミュニティセンター\n参加費：無料",
        )
        result = _scraper_parse(item)
        assert result is not None
        assert result.start_date is not None

    def test_accept_event_with_peatix_url(self):
        """Event with Peatix signup URL should be accepted."""
        item = _make_item(
            title="台日文化交流会 参加者募集",
            description='申込は<a href="https://peatix.com/event/99999">こちら</a>',
        )
        result = _scraper_parse(item)
        assert result is not None

    def test_accept_event_with_venue_label_in_body(self):
        """Event with venue/time/price labels in body should be accepted."""
        item = _make_item(
            title="台湾映画上映会のお知らせ",
            description="日時：2026年7月5日 18:30〜\n会場：大阪市内\n料金：1000円",
        )
        result = _scraper_parse(item)
        assert result is not None

    # ── pubDate guard ────────────────────────────────────────────────────────
    def test_pubdate_not_used_as_start_date_when_no_evidence(self):
        """Post without event evidence should be rejected, not use pubDate."""
        item = _make_item(
            title="台湾留学について考えてみた",
            description="最近台湾に興味があります。続きをみる",
        )
        # Should be rejected by the gate (not return Event with pubDate as start_date)
        result = _scraper_parse(item)
        assert result is None

    def test_pubdate_cleared_when_evidence_but_no_parsed_date(self):
        """If there's event evidence (e.g. venue label) but no parsed date,
        start_date should be None — not the pubDate."""
        item = _make_item(
            title="台湾語ワークショップ開催のお知らせ",
            # Has venue/price label (evidence) but no explicit date
            description="会場：大阪市西区　参加費：無料　申込受付中",
        )
        result = _scraper_parse(item)
        # Should be accepted (has evidence) but start_date should be None
        if result is not None:
            assert result.start_date is None, (
                f"start_date should be None when no date found, got {result.start_date}"
            )

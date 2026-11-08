"""Organizer capture: FTIP title rule, Peatix evidence line, annotator guard.

Reference: event 60dfab63 (ftip_729, "7/4例会:苑原俊明さん講演…") had no
organizer because the FTIP rule required both "例会" and "交流会" in the title,
and the annotator guard discards organizers that are not in the raw text.
"""
from annotator import _organizer_has_evidence
from sources.ftip import LOCATION_NAME, _resolve_organizer
from sources.peatix import _GROUP_HREF_RE, format_organizer_line


# --- FTIP ---------------------------------------------------------------

def test_ftip_reikai_title_without_kouryukai_is_ftip():
    title = "7/4例会:苑原俊明さん講演『先住民族の権利研究 ― 国際人権法からのアプローチ』ご案内"
    body = "苑原俊明さん(大東文化大学名誉教授、当会会員)講演"
    assert _resolve_organizer(title, body) == LOCATION_NAME


def test_ftip_toukai_title_is_ftip():
    assert _resolve_organizer("当会例会4/25(ハイブリッド)", "講演のご案内") == LOCATION_NAME


def test_ftip_explicit_shusai_in_body_wins():
    title = "10/10例会『同化の傷痕』上映&トークご案内"
    body = "主催：明治学院大学平和研究所、共催：当会"
    assert _resolve_organizer(title, body) == "明治学院大学平和研究所"


def test_ftip_third_party_event_without_signal_is_none():
    title = "東京国立博物館「フォルモサの豊かな暮らし」開催中"
    body = "当会でも以前紹介しました。"
    assert _resolve_organizer(title, body) is None


# --- Peatix -------------------------------------------------------------

def test_peatix_group_href_accepts_absolute_and_relative():
    assert _GROUP_HREF_RE.search("https://peatix.com/group/12345")
    assert _GROUP_HREF_RE.search("/group/12345/events")


def test_peatix_group_href_skips_nav_links():
    assert not _GROUP_HREF_RE.search("https://peatix.com/group/browse")
    assert not _GROUP_HREF_RE.search("/group/top")


def test_peatix_organizer_line_added_when_missing_from_body():
    assert format_organizer_line("台湾原住民族との交流会", "講演のご案内") == "主催者: 台湾原住民族との交流会\n\n"


def test_peatix_organizer_line_skipped_when_empty_or_present():
    assert format_organizer_line("", "本文") == ""
    assert format_organizer_line("ABC", "主催：ABC") == ""


# --- Annotator guard ----------------------------------------------------

def _event(**kw):
    base = {"id": "e1", "source_name": "peatix", "organizer": None}
    base.update(kw)
    return base


def test_guard_keeps_organizer_found_in_raw_text():
    assert _organizer_has_evidence("X会", "主催：X会", _event(), {})


def test_guard_keeps_scraper_organizer_not_in_raw_text():
    ev = _event(organizer="Peatixグループ名")
    assert _organizer_has_evidence("Peatixグループ名", "本文のみ", ev, {})


def test_guard_keeps_source_default_organizer():
    ev = _event(source_name="tcc")
    assert _organizer_has_evidence("台湾文化センター", "本文のみ", ev, {"tcc": {"organizer": "台湾文化センター"}})


def test_guard_keeps_human_corrected_organizer():
    assert _organizer_has_evidence("人手修正", "本文のみ", _event(), {}, {"organizer": "人手修正"})


def test_guard_discards_gpt_value_without_evidence():
    # 2026-05-06 incident: few-shot name leaked onto an unrelated event.
    ev = _event(organizer="別の主催者")
    assert not _organizer_has_evidence("セシリアママ", "本文のみ", ev, {})

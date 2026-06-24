"""
Regression tests for the Taiwan Cultural Center external-venue override.

The TCC scraper defaults the location to the centre itself (correct for the
majority of TCC-hosted events). `_extract_explicit_location_from_body` is an
additive override-on-signal helper: it returns an external venue ONLY when the
body carries an explicit venue label or a known external hall, otherwise None so
the TCC default is preserved.

Covers the three plan-mandated cases:
  (a) Waseda venue detected               -> override the TCC default
  (b) TCC organiser/contact only, no label -> keep the TCC default (no override)
  (c) Generic non-Waseda `会場：<venue>`    -> override (helper is not Waseda-only)
"""
from sources.taiwan_cultural_center import (
    _extract_explicit_location_from_body,
    _detect_multi_city_prefectures,
)


# ──────────────────────────────────────────────────────────────────────────────
# (a) External Waseda venue detected -> override
# ──────────────────────────────────────────────────────────────────────────────
class TestWasedaVenueDetected:
    def test_named_hall_without_label(self):
        # Reinforcement whitelist: a known external hall mentioned in prose.
        text = "台湾布袋戯文化月間。本展は早稲田大学坪内博士記念演劇博物館で開催します。"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "早稲田大学坪内博士記念演劇博物館"
        assert pref == "東京都"

    def test_ono_hall_with_venue_label(self):
        text = "会場：小野記念講堂\n日時：2025年7月12日 17:00〜"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "小野記念講堂"
        assert pref == "東京都"

    def test_waseda_gallery_whitelist(self):
        text = "関連展示はワセダギャラリーにて。"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "ワセダギャラリー"
        assert pref == "東京都"


# ──────────────────────────────────────────────────────────────────────────────
# (b) TCC organiser/contact only -> keep the TCC default (NO override)
#     Guards the 15 no-venue-label TCC events that legitimately run at the centre.
# ──────────────────────────────────────────────────────────────────────────────
class TestTccDefaultPreserved:
    def test_organizer_and_contact_only(self):
        text = (
            "台湾文化体験講座のご案内。\n"
            "主催：台北駐日経済文化代表処 台湾文化センター\n"
            "お問い合わせ：台湾文化センター TEL 03-xxxx-xxxx"
        )
        name, pref = _extract_explicit_location_from_body(text)
        assert name is None
        assert pref is None

    def test_venue_label_pointing_at_tcc_is_not_external(self):
        # `会場：…台湾文化センター…` is the centre itself, not an external venue.
        text = "会場：台北駐日経済文化代表処 台湾文化センター 2階"
        name, pref = _extract_explicit_location_from_body(text)
        assert name is None
        assert pref is None

    def test_empty_and_none(self):
        assert _extract_explicit_location_from_body("") == (None, None)
        assert _extract_explicit_location_from_body(None) == (None, None)

    def test_no_venue_signal_returns_none(self):
        text = "台湾の映画文化を紹介するイベントです。参加無料。"
        assert _extract_explicit_location_from_body(text) == (None, None)


# ──────────────────────────────────────────────────────────────────────────────
# (c) Generic non-Waseda venue label -> override (helper is NOT Waseda-only)
# ──────────────────────────────────────────────────────────────────────────────
class TestGenericExternalVenue:
    def test_generic_label_with_prefecture(self):
        text = "会場：大阪府立国際会議場（グランキューブ大阪）"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "大阪府立国際会議場"
        assert pref == "大阪府"  # derived from the full prefecture name in the string

    def test_generic_label_without_known_prefecture(self):
        text = "場所：横浜赤レンガ倉庫1号館\nお問い合わせ：台湾文化センター"
        name, pref = _extract_explicit_location_from_body(text)
        assert name == "横浜赤レンガ倉庫1号館"
        assert pref is None  # not a known hall, no full prefecture token -> unknown


# ──────────────────────────────────────────────────────────────────────────────
# Precedence sanity: the multi-city detector remains independent and unchanged.
# ──────────────────────────────────────────────────────────────────────────────
class TestMultiCityStillWorks:
    def test_multi_city_uses_full_prefecture_names(self):
        text = "会場：東京都／会場：大阪府 で順次開催。"
        found = _detect_multi_city_prefectures(text)
        assert "東京都" in found
        assert "大阪府" in found

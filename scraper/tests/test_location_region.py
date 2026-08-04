"""Tests for canonical location region classification."""

from location_region import JAPAN, OTHER_FOREIGN, TAIWAN, UNKNOWN, classify_region


def test_japanese_addresses_win_over_taiwan_substrings():
    assert classify_region("宮城県仙台湾") == JAPAN
    assert classify_region("大阪府大阪市住之江区新北島3-1-30") == JAPAN
    assert classify_region("東京都台東区上野公園") == JAPAN


def test_normalized_and_english_japanese_addresses():
    assert classify_region("住所は東京都渋谷区神南1-1") == JAPAN
    assert classify_region("日本、〒106-0045 東京都港区麻布十番") == JAPAN
    assert classify_region("4-1-1 Miyoshi, Koto-ku, Tokyo 135-0022") == JAPAN


def test_taiwan_other_foreign_and_unknown_addresses():
    assert classify_region("台北市中山区楽群三路") == TAIWAN
    assert classify_region("香港MOM Livehouse") == OTHER_FOREIGN
    assert classify_region(None) == UNKNOWN
    assert classify_region("オンライン") == UNKNOWN


def test_prefecture_fallback_and_address_precedence():
    assert classify_region(None, ["台北"]) == TAIWAN
    assert classify_region("東京都渋谷区神南1-1", ["台北"]) == JAPAN
    assert classify_region("台北市信義區", ["東京都"]) == TAIWAN

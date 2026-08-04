"""Canonical address normalization, prefecture extraction, and region classification."""

from __future__ import annotations

import re

JAPAN = "japan"
TAIWAN = "taiwan"
OTHER_FOREIGN = "other_foreign"
UNKNOWN = "unknown"

_CITY_TO_PREF: dict[str, str] = {
    "横浜市": "神奈川県",
    "川崎市": "神奈川県",
    "相模原市": "神奈川県",
    "名古屋市": "愛知県",
    "福岡市": "福岡県",
    "北九州市": "福岡県",
    "札幌市": "北海道",
    "仙台市": "宮城県",
    "神戸市": "兵庫県",
    "さいたま市": "埼玉県",
    "千葉市": "千葉県",
    "広島市": "広島県",
    "新潟市": "新潟県",
    "静岡市": "静岡県",
    "浜松市": "静岡県",
    "堺市": "大阪府",
    "岡山市": "岡山県",
    "熊本市": "熊本県",
    **{ward: "東京都" for ward in [
        "千代田区", "中央区", "港区", "新宿区", "文京区", "台東区", "墨田区",
        "江東区", "品川区", "目黒区", "大田区", "世田谷区", "渋谷区", "中野区",
        "杉並区", "豊島区", "北区", "荒川区", "板橋区", "練馬区", "足立区",
        "葛飾区", "江戸川区",
    ]},
    "青森市": "青森県", "盛岡市": "岩手県", "秋田市": "秋田県", "山形市": "山形県",
    "福島市": "福島県", "水戸市": "茨城県", "宇都宮市": "栃木県", "前橋市": "群馬県",
    "富山市": "富山県", "金沢市": "石川県", "福井市": "福井県", "甲府市": "山梨県",
    "長野市": "長野県", "岐阜市": "岐阜県", "津市": "三重県", "大津市": "滋賀県",
    "奈良市": "奈良県", "和歌山市": "和歌山県", "鳥取市": "鳥取県", "松江市": "島根県",
    "山口市": "山口県", "徳島市": "徳島県", "高松市": "香川県", "松山市": "愛媛県",
    "高知市": "高知県", "佐賀市": "佐賀県", "長崎市": "長崎県", "大分市": "大分県",
    "宮崎市": "宮崎県", "鹿児島市": "鹿児島県", "那覇市": "沖縄県",
}

_EN_TO_PREF: dict[str, str] = {"tokyo": "東京都", "osaka": "大阪府", "kyoto": "京都府"}

_JP_PREF_RE = re.compile(
    r"^(北海道|東京都|大阪府|京都府|大阪市|京都市|[^\s都道府県\d〒-]{2,3}県)"
)

_TW_ALIASES = (
    r"[臺台]北|新北|桃園|[臺台]中|[臺台]南|高雄|基隆|新竹|苗栗|彰化|"
    r"南投|雲林|嘉義|屏東|宜蘭|花蓮|[臺台]東|澎湖|金門|連江"
)
_TW_START_RE = re.compile(rf"^({_TW_ALIASES})(?:[市縣區]|[\s　]|$|[0-9０-９])")
_TW_SUFFIX_RE = re.compile(rf"({_TW_ALIASES})[市縣]")

_LABEL_PREFIX_RE = re.compile(
    r"^(?:会場住所|会場所在地|開催場所|開催地|所在地|住所|会場|場所)(?:は|:|：)?[\s　、,]*"
)
_COUNTRY_PREFIX_RE = re.compile(r"^日本[、,]?[\s　]*")
_POSTAL_PREFIX_RE = re.compile(r"^〒?\s*\d{3}-?\d{4}[\s　]*")
_OTHER_FOREIGN_RE = re.compile(r"^(?:香港|マカオ|ソウル|上海|北京|シンガポール|バンコク)")


def _normalize_address(address: str) -> str:
    """Strip stacked label, country, and postal prefixes."""
    normalized = address.strip()
    previous = None
    for _ in range(6):
        if normalized == previous:
            break
        previous = normalized
        normalized = _LABEL_PREFIX_RE.sub("", normalized)
        normalized = _COUNTRY_PREFIX_RE.sub("", normalized)
        normalized = _POSTAL_PREFIX_RE.sub("", normalized)
        normalized = normalized.lstrip("　 \t、,:：")
    return normalized


def extract_prefecture(address: str | None) -> str | None:
    """Extract a prefecture name from a Japanese or Taiwanese address string."""
    if not address:
        return None

    normalized = _normalize_address(address)
    if not normalized:
        return None

    match = _JP_PREF_RE.match(normalized)
    if match:
        prefecture = match.group(1)
        if prefecture in ("大阪市", "大阪府"):
            return "大阪府"
        if prefecture in ("京都市", "京都府"):
            return "京都府"
        return prefecture

    for city, prefecture in _CITY_TO_PREF.items():
        if normalized.startswith(city):
            return prefecture

    taiwan_match = _TW_START_RE.match(normalized) or _TW_SUFFIX_RE.search(normalized)
    if taiwan_match:
        return taiwan_match.group(1).replace("臺", "台")

    lower_address = normalized.lower()
    for key, prefecture in _EN_TO_PREF.items():
        if key in lower_address:
            return prefecture
    return None


def _classify_text(value: str | None) -> str:
    if not value:
        return UNKNOWN

    prefecture = extract_prefecture(value)
    if prefecture:
        return JAPAN if _JP_PREF_RE.match(prefecture) else TAIWAN

    normalized = _normalize_address(value)
    if _OTHER_FOREIGN_RE.match(normalized):
        return OTHER_FOREIGN
    return UNKNOWN


def classify_region(address: str | None, prefectures: list[str] | None = None) -> str:
    """Classify Japan before Taiwan, other foreign locations, then unknown.

    A recognized address takes precedence over conflicting prefecture metadata.
    """
    address_region = _classify_text(address)
    if address_region != UNKNOWN:
        return address_region

    prefecture_regions = {_classify_text(value) for value in (prefectures or [])}
    for region in (JAPAN, TAIWAN, OTHER_FOREIGN):
        if region in prefecture_regions:
            return region
    return UNKNOWN

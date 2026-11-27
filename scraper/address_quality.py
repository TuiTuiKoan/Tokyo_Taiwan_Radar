"""
address_quality.py — Grade how specific a `location_address` value is.

Pure functions, no network and no database. Spec: docs/specs/active/venue-ground-truth/.

Grades (only STREET is good enough to show a visitor where to go):

    street       has a block or lot number: 丁目+番, 番地, 号, `1-2-3`, or a lot
                 number right after the town name (権堂町2255)
    town         a town name or a chome, but no lot number (神田神保町, 中野4丁目)
    region       prefecture, city, ward, or a list of them (福岡県福岡市, 東京)
    empty        blank
    non_japan    an address outside Japan (台北市信義區…)
    not_address  not an address: a venue name, a sentence, a phone number, オンライン

The grader reads the text only. It does not check that the address exists, and a
STREET grade is not ground truth. Deliberate choices, pinned in the tests:

- A chome with no lot is TOWN (新宿3丁目), including Sapporo's 北1条西2丁目.
- 栄3 / 南青山5 (a chome written as a bare digit) is TOWN; so is the rare real
  one-digit lot that does not follow 町.
- An address that names two places still grades by its most specific part; do not
  use such a value as evidence for one venue.
"""

from __future__ import annotations

import re
import unicodedata

STREET = "street"
TOWN = "town"
REGION = "region"
EMPTY = "empty"
NON_JAPAN = "non_japan"
NOT_ADDRESS = "not_address"

GRADES = (STREET, TOWN, REGION, EMPTY, NON_JAPAN, NOT_ADDRESS)
# Grades that mean "a Japanese venue still lacks a usable address". NON_JAPAN is left
# out: events held in Taiwan are in scope and this grader cannot judge their addresses.
NEEDS_FIX = frozenset({TOWN, REGION, EMPTY, NOT_ADDRESS})

_PREFECTURES = (
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
)
# Prefecture names as people write them without the suffix (東京, 福岡).
_PREF_SHORT = frozenset(p[:-1] for p in _PREFECTURES if p != "北海道") | {"北海道"}
_PREF_RE = "(?:" + "|".join(_PREFECTURES) + ")"
# Big-city and district names people write instead of an address (名古屋, 渋谷).
_CITY_SHORT = frozenset({
    "札幌", "仙台", "横浜", "川崎", "名古屋", "神戸", "広島", "北九州", "那覇", "金沢",
    "渋谷", "新宿", "上野", "池袋", "銀座", "梅田", "天神", "博多", "東北", "関西", "九州",
    "全国", "日本", "国内",
})

# Latin-script Japanese addresses: "2F, 12-8 Sarugaku-cho, Shibuya-ku, Tokyo 150-0033".
_ROMAJI_JP_RE = re.compile(
    r"-(?:ku|shi|cho|machi|gun)\b|\b(?:Tokyo|Osaka|Kyoto|Hokkaido|Fukuoka|Aichi|Kanagawa|"
    r"Saitama|Chiba|Hyogo|Shizuoka|Ibaraki|Aomori|Kumamoto|Nagano|Okinawa|Japan)\b",
    re.IGNORECASE,
)

# Taiwan and other clearly non-Japanese markers. 台東 is left out on purpose: 台東区 is
# a Tokyo ward. 號 / 巷 / 弄 / 段 only occur in Taiwanese-style addresses.
# A place name only counts at the start of the text: 東京都港区虎ノ門1-1-12 台湾文化センター
# and 京都市右京区梅ケ畑高雄町5 are Japanese addresses that merely contain 台湾 / 高雄.
_NON_JAPAN_START_RE = re.compile(
    r"^[\s\d〒-]*(?:台北|臺北|新北市|桃園[市区區]|台中|臺中|台南|臺南|高雄|基隆|新竹[市県縣]|嘉義|"
    r"花蓮|宜蘭|屏東|南投|雲林|苗栗|彰化|台湾|臺灣|台灣|香港)"
)
_NON_JAPAN_ANYWHERE_RE = re.compile(
    r"\d號|巷\d|\d弄|路[一二三四五六七八九]段|Malaysia|Taiwan|Taipei|Hong Kong", re.IGNORECASE
)

_ONLINE_RE = re.compile(r"オンライン|online|配信|zoom|youtube", re.IGNORECASE)
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

# Numbers that are not lot numbers. Removed before looking for a lot number.
_NOISE_RES = (
    re.compile(r"〒?\s*\d{3}\s*[-‐－−ー]\s*\d{4}"),            # postal code
    re.compile(r"0\d{1,4}[-‐－−ー(（]\d{1,4}[-‐－−ー)）]\d{3,4}"),  # phone number
    re.compile(r"(?:地下|B)\s*\d+\s*(?:階|F)?", re.IGNORECASE),   # basement floor
    re.compile(r"\d+\s*(?:・\s*\d+\s*)?(?:階|F(?![a-z]))", re.IGNORECASE),  # floor
    re.compile(r"\d+\s*号(?:館|室|棟|線|車)"),                    # building / room / route
    re.compile(r"\d+\s*(?:教室|室|スクリーン)"),                   # room
    re.compile(r"\d{4}\s*年|\d+\s*月|\d+\s*日(?!本)"),             # dates
    re.compile(r"\d{1,2}:\d{2}"),                                # clock time
    re.compile(r"\d{1,2}/\d{1,2}"),                              # slash date
    re.compile(r"第\s*\d+"),                                     # 第2会場
    re.compile(r"[東西南北]?\d+\s*(?:ホール|会場|会議室|番出口|番線)"),  # 東1ホール
    re.compile(r"\d+\s*(?:分|名|人|円|点|店舗|回|族)"),             # counters
)

_DASH = r"[-‐－−ー―]"
_STREET_RES = (
    re.compile(rf"\d+\s*丁目\s*\d"),                 # 3丁目35
    re.compile(r"\d+\s*番(?:地|\s*\d|(?=\s|$))"),     # 1番地, 13番3, 8番
    re.compile(r"\d+\s*号(?=\s|$|[^館室棟線車])"),      # 13番3号
    re.compile(rf"\d+\s*{_DASH}\s*\d+"),             # 1-1-12
    re.compile(r"\d+\s*の\s*\d+"),                 # 1の14の30
)
# A lot number written straight after the town name: 権堂町2255, 大塚359, 夕凪町6.
# - not after an administrative unit: 千代田区 3331 Arts Chiyoda is a building name
# - a single digit only after 町: 栄3 and 南青山5 are chome written short, not lots
# - not followed by a larger unit (4丁目, 8条)
_BARE_LOT_RE = re.compile(
    r"(?:(?<=[一-龥ぁ-んァ-ヶ])(?<![都道府県市区郡])\s?\d{2,5}|(?<=町)\s?\d)(?!\s*(?:\d|丁目|条|号))"
)

# 市区町村. Kept short so a sentence does not match as one long "city".
_MUNICIPALITY_RE = re.compile(r"[一-龥ぁ-んァ-ヶ]{1,7}?(?:市|区|郡|町|村)")
_NAME = "[一-龥ぁ-んァ-ヶ]{1,6}?"
# 県 / 県+市 / 県+市+区 / 市+区 / 県+郡+町村. A town inside a city (長浜市元浜町,
# 大阪市港区弁天町) is not matched here: that is TOWN.
_REGION_ONLY_RE = re.compile(
    rf"^(?:{_PREF_RE})?(?:(?:{_NAME}市)?(?:{_NAME}区)?|{_NAME}郡(?:{_NAME}[町村])?)$"
)
_ROMAJI_LOT_RE = re.compile(
    rf"\d+\s*{_DASH}\s*\d+|^\s*#?\d+\s*[,\s]\s*[A-Z]|,\s*\d+\s+[A-Z]|\b\d{{2,5}}\s+[A-Z][a-z]|\d+\s*Chome",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"[。！!♪「」]|、.*、|です|ます|ました|される|\bthe\b", re.IGNORECASE)
_VAGUE_SUFFIX_RE = re.compile(r"(?:内|各所|各地|近郊|周辺|某所)+$")
_PARTIAL_RE = re.compile(rf"^[一-龥ぁ-んァ-ヶ]{{2,8}}\s?\d+(?:\s*丁目\s*\d+|\s*{_DASH}\s*\d+)")
_COUNTRY_AFFIX_RE = re.compile(r"^日本[、,\s]+|[、,\s]+日本$")

_KANJI_DIGITS = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
# Kanji numerals are converted only where they cannot be part of a place name:
# before 丁目 / 番地, and in the 番 and 号 that follow a 丁目 (三丁目五番一号).
# 麻布十番, 三番町, 九条 and 四条 stay as written.
_KANJI = "[〇一二三四五六七八九十]{1,3}"
_KANJI_NUM_RES = (
    re.compile(rf"({_KANJI})(?=丁目|番地)"),
    re.compile(rf"(?<=丁目)({_KANJI})(?=番)"),
    re.compile(rf"(?<=\d番)({_KANJI})(?=号)"),
)

# Longer than this with no lot number is a sentence, not an address.
_PROSE_MIN_LEN = 45


def _kanji_to_int(text: str) -> int:
    if "十" not in text:
        return int("".join(str(_KANJI_DIGITS[c]) for c in text))
    tens, _, ones = text.partition("十")
    return (_KANJI_DIGITS[tens] if tens else 1) * 10 + (_KANJI_DIGITS[ones] if ones else 0)


def normalize_address(address: str | None) -> str:
    """NFKC, trim quotes and whitespace, and turn 二丁目 into 2丁目 (六番地 into 6番地)."""
    text = unicodedata.normalize("NFKC", address or "").strip().strip("\"'")
    if text.lower() in {"null", "none", "-", "—", "n/a"}:
        return ""
    text = _COUNTRY_AFFIX_RE.sub("", text)
    for pattern in _KANJI_NUM_RES:
        text = pattern.sub(lambda m: str(_kanji_to_int(m.group(1))), text)
    return text


def _strip_noise(text: str) -> str:
    for pattern in _NOISE_RES:
        text = pattern.sub(" ", text)
    return text


def _has_lot_number(text: str) -> bool:
    if any(p.search(text) for p in _STREET_RES):
        return True
    return len(text) <= _PROSE_MIN_LEN and bool(_BARE_LOT_RE.search(text))


def _is_region_only(text: str) -> bool:
    """東京, 福岡県福岡市, 渋谷区, or a list such as 北海道, 東京, 大阪."""
    parts = [p for p in re.split(r"[,、・/|\s]+", text) if p]
    # 東京｜Tokyo: the Latin half only repeats the Japanese half.
    cjk_parts = [p for p in parts if not p.isascii()]
    if not cjk_parts:
        return False
    return all(
        p in _PREF_SHORT or p in _CITY_SHORT or bool(_REGION_ONLY_RE.match(p))
        for p in cjk_parts
    )


def _grade(text: str) -> str:
    # Order matters and is pinned by the tests:
    # URL > overseas (only without a Japanese start) > romanised > street > online-only
    # > region > not an address > town.
    if _URL_RE.search(text):
        return NOT_ADDRESS

    cleaned = _strip_noise(text)
    has_lot = _has_lot_number(cleaned)
    starts_in_japan = bool(re.match(rf"\s*(?:{_PREF_RE})", cleaned))

    if not starts_in_japan and (_NON_JAPAN_START_RE.search(text) or _NON_JAPAN_ANYWHERE_RE.search(text)):
        # A sentence that only mentions Taiwan is not an overseas address.
        if len(text) > _PROSE_MIN_LEN and _SENTENCE_RE.search(text):
            return NOT_ADDRESS
        return NON_JAPAN

    if not re.search(r"[一-龥ぁ-んァ-ヶ]", cleaned):
        if not _ROMAJI_JP_RE.search(text):
            return NOT_ADDRESS
        return STREET if _ROMAJI_LOT_RE.search(cleaned) else REGION

    has_admin = bool(re.search(_PREF_RE, cleaned)) or bool(_MUNICIPALITY_RE.search(cleaned))
    if has_admin and has_lot:
        return STREET
    # A hybrid event keeps its physical address (…6-10-1（オンライン配信あり）is STREET above).
    if _ONLINE_RE.search(text):
        return NOT_ADDRESS
    if _is_region_only(_VAGUE_SUFFIX_RE.sub("", cleaned.strip())):
        return REGION
    if len(cleaned) > _PROSE_MIN_LEN or _SENTENCE_RE.search(cleaned):
        return NOT_ADDRESS
    if not has_admin:
        # 銀座4-6-16: a lot number without its city is an incomplete address, not a venue name.
        return TOWN if _PARTIAL_RE.match(cleaned.strip()) else NOT_ADDRESS
    return TOWN


def grade_address(address: str | None, location_name: str | None = None) -> str:
    """Return one of GRADES for a `location_address` value.

    `location_name` is optional. A value that only repeats the venue name is
    NOT_ADDRESS, unless it already carries a lot number.
    """
    text = normalize_address(address)
    if not text:
        return EMPTY
    grade = _grade(text)
    if grade != STREET and location_name and text == normalize_address(location_name):
        return NOT_ADDRESS
    return grade


def is_street_level(address: str | None, location_name: str | None = None) -> bool:
    return grade_address(address, location_name) == STREET


# ---------------------------------------------------------------------------
# Comparison key
# ---------------------------------------------------------------------------

_POSTAL_ANY_RE = re.compile(
    r"(?:〒|郵便番号[:：]?)\s*\d{3}\s*[-‐－−ー]\s*\d{4}|^\s*\d{3}\s*[-‐－−ー]\s*\d{4}(?!\d|[-‐－−ー])"
)
_PREF_PREFIX_RE = re.compile(rf"^(?:{_PREF_RE})")
_LOT_UNITS = (
    (re.compile(r"(\d+)丁目(?=\d)"), r"\1-"),
    (re.compile(r"(\d+)番地?(?=\d)"), r"\1-"),
    (re.compile(r"(\d+)の(?=\d)"), r"\1-"),
    (re.compile(r"(\d+)(?:番地|番|号)"), r"\1"),
    (re.compile(rf"(\d+)\s*{_DASH}\s*(?=\d)"), r"\1-"),
)
# A number before 条 (Sapporo 北1条西3丁目) is part of the town name, not the lot.
_LOT_SEQUENCE_RE = re.compile(r"\d+(?:-\d+)+|\d+(?!\d|\s*条)")


def address_key(address: str | None) -> str | None:
    """A key under which spellings of the same street address compare equal.

    東京都中央区日本橋室町3-2-1 COREDO室町テラス2F, 中央区日本橋室町３丁目２−１ and
    〒103-0022 東京都中央区日本橋室町3丁目2番1号 all give 中央区日本橋室町3-2-1:
    postal code, prefecture, whitespace and everything after the lot number
    (building, floor) are dropped. Returns None unless the address is STREET.
    """
    if grade_address(address) != STREET:
        return None
    text = _POSTAL_ANY_RE.sub(" ", normalize_address(address))
    text = re.sub(r"\s+", " ", text).strip()
    text = _PREF_PREFIX_RE.sub("", text).lstrip()
    for pattern, replacement in _LOT_UNITS:
        text = pattern.sub(replacement, text)
    match = None
    for candidate in _LOT_SEQUENCE_RE.finditer(text):
        # The first number sequence that follows a municipality is the lot.
        # Whitespace is still in place here, so "35-13 3F" stops at 13.
        if _MUNICIPALITY_RE.search(text[: candidate.start()]):
            match = candidate
            break
    key = text[: match.end()] if match else text
    return re.sub(r"\s+", "", key)

"""Regression tests for scraper/backfill_location_prefectures.py (Round G / LANE G2).

Covers two defects fixed in G2:

  1. extract_prefecture() matched Taiwan aliases via an unrestricted mid-string
     search, so a Japanese address such as 大阪府大阪市住之江区新北島 wrongly
     returned 新北 instead of 大阪府. It also failed on label-prefixed addresses
     (住所は…, 所在地：…, 会場住所 …).

  2. main() read the events table with a single unpaginated .execute(), so
     Supabase silently capped results at 1000 rows. fetch_all_rows() paginates
     past the cap and logs per-page / exact / accumulated counts.

Run:
    python -m pytest scraper/tests/test_backfill_location_prefectures.py -q
"""

from backfill_location_prefectures import extract_prefecture


# ---------------------------------------------------------------------------
# extract_prefecture — Japanese canonical forms (regression guards)
# ---------------------------------------------------------------------------

def test_canonical_japanese_prefectures():
    assert extract_prefecture("東京都渋谷区神南1-1") == "東京都"
    assert extract_prefecture("大阪府大阪市北区中之島") == "大阪府"
    assert extract_prefecture("京都府京都市中京区") == "京都府"
    assert extract_prefecture("神奈川県横浜市西区") == "神奈川県"
    assert extract_prefecture("北海道札幌市中央区") == "北海道"


def test_city_without_prefecture_prefix():
    assert extract_prefecture("横浜市西区") == "神奈川県"
    assert extract_prefecture("福岡市博多区博多駅前1-1-1") == "福岡県"
    assert extract_prefecture("港区麻布十番2丁目") == "東京都"
    assert extract_prefecture("仙台市青葉区") == "宮城県"
    assert extract_prefecture("津市本町1-1") == "三重県"


def test_english_and_postal_addresses():
    assert extract_prefecture("〒310-0015　茨城県水戸市宮町1丁目7") == "茨城県"
    assert extract_prefecture("日本、〒106-0045 東京都港区麻布十番") == "東京都"
    assert extract_prefecture("4-1-1 Miyoshi, Koto-ku, Tokyo 135-0022") == "東京都"


# ---------------------------------------------------------------------------
# NEW: bounded label normalization (defect — current code returns None)
# ---------------------------------------------------------------------------

def test_label_prefix_is_stripped_before_matching():
    assert extract_prefecture("住所は東京都渋谷区神南1-1") == "東京都"
    assert extract_prefecture("所在地：京都府京都市中京区") == "京都府"
    assert extract_prefecture("会場住所 大阪府大阪市北区中之島") == "大阪府"
    assert extract_prefecture("開催場所：神奈川県横浜市西区") == "神奈川県"


# ---------------------------------------------------------------------------
# NEW: Japanese prefectures win over Taiwan aliases (defect — returns 新北)
# ---------------------------------------------------------------------------

def test_japanese_address_never_returns_taiwan_alias():
    # 新北 appears mid-string, but the address is unambiguously 大阪府.
    assert extract_prefecture("大阪府大阪市住之江区新北島3-1-30") == "大阪府"


def test_taiwan_alias_requires_start_or_suffix_not_bare_midstring():
    # 新北 buried inside a JP ward address with no 市/縣 suffix → not Taiwan.
    assert extract_prefecture("住之江区新北島3-1") is None
    # 台 appears inside 五台山, but it is not a Taiwan locality.
    assert extract_prefecture("高知市五台山4200-6") == "高知県"


# ---------------------------------------------------------------------------
# Taiwan addresses still resolve (start-anchored, or explicit 市/縣 suffix)
# ---------------------------------------------------------------------------

def test_taiwan_addresses_still_match():
    assert extract_prefecture("台北市信義區") == "台北"
    assert extract_prefecture("桃園市中壢區") == "桃園"
    assert extract_prefecture("新北市板橋區") == "新北"
    assert extract_prefecture("臺中市西屯區") == "台中"
    assert extract_prefecture("台北") == "台北"


# ---------------------------------------------------------------------------
# Substring traps — anchored matching must not bleed across names
# ---------------------------------------------------------------------------

def test_prefecture_substring_traps():
    # 東京都 must never be read as 京都.
    assert extract_prefecture("東京都千代田区丸の内") == "東京都"
    # 神奈川県 not 奈良; 和歌山県 not 山形/岡山; 福岡県 not 福島/福井.
    assert extract_prefecture("神奈川県川崎市") == "神奈川県"
    assert extract_prefecture("和歌山県和歌山市") == "和歌山県"
    assert extract_prefecture("福岡県福岡市中央区") == "福岡県"


def test_online_and_empty_return_none():
    assert extract_prefecture("オンライン") is None
    assert extract_prefecture("") is None
    assert extract_prefecture(None) is None


# ---------------------------------------------------------------------------
# fetch_all_rows — pagination past Supabase's 1000-row cap
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    """Minimal stand-in for a postgrest query builder over an in-memory list."""

    def __init__(self, rows):
        self._rows = rows
        self._head = False
        self._count = None
        self._start = None
        self._end = None

    def select(self, *columns, count=None, head=None):
        self._count = count
        self._head = bool(head)
        return self

    @property
    def not_(self):
        return self

    def is_(self, _col, _val):
        return self

    def eq(self, _col, _val):
        return self

    def order(self, _col, desc=False):
        return self

    def range(self, start, end, foreign_table=None):
        self._start = start
        self._end = end
        return self

    def execute(self):
        count = len(self._rows) if self._count == "exact" else None
        if self._head:
            return _FakeResp([], count=count)
        if self._start is None:
            return _FakeResp(list(self._rows), count=count)
        return _FakeResp(list(self._rows[self._start:self._end + 1]), count=count)


class _FakeClient:
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table

    def table(self, name):
        return _FakeQuery(list(self._rows_by_table.get(name, [])))


def test_fetch_all_rows_paginates_past_1000():
    from backfill_location_prefectures import fetch_all_rows

    rows = [{"id": f"id-{i:05d}", "location_address": "東京都"} for i in range(2350)]
    sb = _FakeClient({"events": rows})

    got = fetch_all_rows(sb, "events", "id,location_address", label="t")

    assert len(got) == 2350              # accumulated well past the 1000 cap
    assert got[0]["id"] == "id-00000"
    assert got[-1]["id"] == "id-02349"
    assert len({r["id"] for r in got}) == 2350   # no duplicates / no dropped pages


def test_fetch_all_rows_applies_filters_and_exact_count():
    from backfill_location_prefectures import fetch_all_rows

    rows = [{"parent_event_id": None, "location_address": "x"} for _ in range(1500)]
    sb = _FakeClient({"events": rows})

    calls = {"n": 0}

    def _flt(q):
        calls["n"] += 1
        return q.is_("parent_event_id", "null")

    got = fetch_all_rows(
        sb,
        "events",
        "parent_event_id,location_address",
        apply_filters=_flt,
        label="parents",
    )

    assert len(got) == 1500
    # apply_filters must run on BOTH the count-head request and each page (>=2 pages).
    assert calls["n"] >= 3

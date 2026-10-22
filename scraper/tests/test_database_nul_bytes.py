"""NUL characters must never reach Postgres text columns (#380).

PR TIMES started returning text with stray NULs inside words (21 of 55 events
on 2026-10-22). One of them failed the whole events upsert with 22P05, so no
prtimes event was stored from 2026-09-14 to 2026-10-22.
"""

from database import _event_to_row, _strip_nul
from sources.base import Event


def _event(**kw):
    return Event(source_name="prtimes", source_id="prtimes_000049635_000000448",
                 source_url="https://prtimes.jp/x", original_language="ja", **kw)


def test_strip_nul_handles_nested_values():
    assert _strip_nul("地\x00\x00方創生") == "地方創生"
    assert _strip_nul(["a\x00", "b"]) == ["a", "b"]
    assert _strip_nul({"k": ["\x00x"]}) == {"k": ["x"]}
    assert _strip_nul(None) is None and _strip_nul(3) == 3 and _strip_nul(True) is True


def test_event_row_has_no_nul_anywhere():
    row = _event_to_row(_event(
        raw_title="「白浜・台湾フェスタ2026」開催",
        raw_description="和歌山県白浜町の地\x00\x00方創生・地域活性化を継続支援",
        name_ja="台湾\x00フェスタ",
        location_name="白浜町\x00",
        organizer="株式会社\x00テスト",
        performers=["演者\x00A"],
    ))
    assert row["raw_description"] == "和歌山県白浜町の地方創生・地域活性化を継続支援"
    assert row["name_ja"] == "台湾フェスタ"
    assert row["location_name"] == "白浜町"
    assert row["organizer"] == "株式会社テスト"
    assert row["performers"] == ["演者A"]

    def _walk(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, list):
            for x in v:
                yield from _walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                yield from _walk(x)

    assert not any("\x00" in s for s in _walk(row))


def test_clean_text_is_left_untouched():
    row = _event_to_row(_event(raw_title="台湾祭", raw_description="本文"))
    assert row["raw_title"] == "台湾祭" and row["raw_description"] == "本文"

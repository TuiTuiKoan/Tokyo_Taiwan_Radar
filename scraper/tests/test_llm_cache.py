"""llm_cache reads in chunks and refuses to guess when it cannot read (#363)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import llm_cache


class _Rows:
    def __init__(self, data, log):
        self._data, self._log, self._keys = data, log, []

    def select(self, _c):
        return self

    def eq(self, _c, _v):
        return self

    def in_(self, _c, keys):
        self._keys = keys
        self._log.append(len(keys))
        return self

    def execute(self):
        return SimpleNamespace(data=[{"subject_key": k} for k in self._keys if k in self._data])


def test_seen_reads_in_chunks():
    log: list[int] = []
    known = {f"k{i}" for i in range(0, 250, 2)}
    sb = SimpleNamespace(table=lambda _n: _Rows(known, log))
    found = llm_cache.seen(sb, "poster_ocr", [f"k{i}" for i in range(250)])
    assert log == [100, 100, 50]
    assert found == known


def test_seen_raises_when_the_table_cannot_be_read():
    class Broken:
        def table(self, _n):
            raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        llm_cache.seen(Broken(), "poster_ocr", ["k"])

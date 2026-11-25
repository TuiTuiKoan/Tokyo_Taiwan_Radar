"""Tests for scripts/research/scholar_lookup.py: registry responses become research-team source records."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "research" / "scholar_lookup.py"

OPENALEX = {
    "id": "https://openalex.org/W1",
    "doi": "https://doi.org/10.1000/ABC",
    "title": "A  study\nof X",
    "publication_year": 2020,
    "type": "article",
    "open_access": {"oa_url": "https://repo.example.org/a.pdf"},
    "authorships": [{"author": {"display_name": "Lin A."}}, {"author": {"display_name": "Sato B."}}],
    "primary_location": {"landing_page_url": "https://doi.org/10.1000/abc", "source": {"display_name": "Journal of X"}},
    "abstract_inverted_index": {"rose": [1], "X": [0, 3], "while": [2], "fell": [4]},
}
CROSSREF = {
    "DOI": "10.1000/abc",
    "title": ["A study of X"],
    "author": [{"family": "Lin", "given": "A."}, {"name": "X Consortium"}],
    "issued": {"date-parts": [[2020, 5]]},
    "container-title": ["Journal of X"],
    "type": "posted-content",
    "abstract": "<jats:p>X &amp; Y rose.</jats:p>",
    "URL": "https://doi.org/10.1000/abc",
}
JSTAGE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">
  <entry>
    <article_title><en><![CDATA[English title]]></en><ja><![CDATA[日本語の題]]></ja></article_title>
    <article_link><en>https://www.jstage.jst.go.jp/article/x/1/0/1_1/_article</en><ja>https://www.jstage.jst.go.jp/article/x/1/0/1_1/_article/-char/ja/</ja></article_link>
    <author><en><name><![CDATA[Taro Yamada]]></name></en><ja><name><![CDATA[山田 太郎]]></name><name><![CDATA[林 花子]]></name></ja></author>
    <material_title><en><![CDATA[Asian Studies]]></en></material_title>
    <pubyear>2019</pubyear>
    <prism:doi>10.1000/js.1</prism:doi>
    <title><![CDATA[日本語の題]]></title>
  </entry>
</feed>""".encode()


@pytest.fixture(scope="session")
def sl():
    spec = importlib.util.spec_from_file_location("scholar_lookup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openalex_record(sl):
    rec = sl.from_openalex(OPENALEX)
    assert rec["title"] == "A study of X" and rec["doi"] == "10.1000/ABC" and rec["year"] == 2020
    assert rec["authors"] == ["Lin A.", "Sato B."] and rec["venue"] == "Journal of X"
    assert rec["abstract"] == "X rose while X fell" and rec["oa_url"].endswith("a.pdf")
    assert rec["fetched"] is False and "primary" not in rec


def test_crossref_record(sl):
    rec = sl.from_crossref(CROSSREF)
    assert rec["type"] == "preprint" and rec["authors"] == ["Lin, A.", "X Consortium"]
    assert rec["year"] == 2020 and rec["abstract"] == "X & Y rose."


def test_jstage_record_prefers_japanese(sl):
    (rec,) = sl.from_jstage(JSTAGE)
    assert rec["title"] == "日本語の題" and rec["authors"] == ["山田 太郎", "林 花子"]
    assert rec["venue"] == "Asian Studies" and rec["year"] == 2019
    assert rec["url"].endswith("/-char/ja/") and rec["doi"] == "10.1000/js.1"


def test_long_abstract_is_trimmed_and_doi_url_is_derived(sl):
    rec = sl.record(title="t", doi="doi:10.1/x", abstract="a" * 5000)
    assert len(rec["abstract"]) == sl.ABSTRACT_LIMIT + 1 and rec["url"] == "https://doi.org/10.1/x"


def test_cli_uses_one_registry_and_survives_a_missing_doi(sl, monkeypatch, capsys):
    calls = []

    def fake(url):
        calls.append(url)
        if "crossref" in url:
            raise OSError("404")
        return json.dumps(OPENALEX).encode()

    monkeypatch.setattr(sl, "fetch", fake)
    assert sl.main(["doi", "https://doi.org/10.1000/abc"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 1 and out[0]["registry"] == "openalex" and len(calls) == 2
    monkeypatch.setattr(sl, "fetch", lambda url: json.dumps({"results": []}).encode())
    assert sl.main(["search", "nothing"]) == 1

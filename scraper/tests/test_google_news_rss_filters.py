"""google_news_rss Taiwan filter (coverage-audit Phase A, #701)."""
import pytest

from sources.google_news_rss import taiwan_verdict


@pytest.mark.parametrize("title,description", [
    ("台湾映画祭が東京で開幕", ""),
    ("日台交流写真展、横浜で開催", ""),
    ("報道写真展「日中台：交錯するまなざし」", ""),
    ("写真展が開幕", "台湾の写真家による展示"),
    ("Taiwan film week opens", ""),
])
def test_taiwan_verdict_accepts(title, description):
    assert taiwan_verdict(title, description) == (True, "ok")


@pytest.mark.parametrize("title,description", [
    ("ミュージカル舞台日本公演が開幕", ""),
    ("今日台風接近、イベント中止相次ぐ", ""),
    ("中台禅寺で特別拝観", ""),
    ("新作映画が公開", "監督インタビュー"),
])
def test_taiwan_verdict_rejects(title, description):
    assert taiwan_verdict(title, description) == (False, "no_taiwan")

import logging

from sources.yebizo import YebizoScraper


def test_listing_fetch_failure_is_warning_not_error(caplog, monkeypatch):
    scraper = YebizoScraper()
    monkeypatch.setattr(scraper, "_fetch", lambda *a, **k: None)
    with caplog.at_level(logging.DEBUG):
        assert scraper.scrape() == []
    msgs = [r for r in caplog.records if "failed to fetch program listing" in r.getMessage()]
    assert msgs and all(r.levelno == logging.WARNING for r in msgs)

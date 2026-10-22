import pytest

import llm_client
import main


class RetiredModelScraper:
    def scrape(self):
        raise llm_client.LLMConfigError("enrich.cinemaclair_ocr", "gpt-4o", 404, "model_not_found", "gone")


class HealthyScraper:
    calls = 0

    def scrape(self):
        HealthyScraper.calls += 1
        return []


def test_config_error_fails_the_run_but_other_sources_still_scrape(monkeypatch, capsys):
    HealthyScraper.calls = 0
    monkeypatch.setattr(main, "SCRAPERS", [RetiredModelScraper(), HealthyScraper()])
    monkeypatch.setattr(main, "_RUN_ALL", True)

    with pytest.raises(llm_client.LLMConfigError):
        main.run(dry_run=True)

    assert HealthyScraper.calls == 1


def test_run_without_llm_errors_finishes_normally(monkeypatch, capsys):
    HealthyScraper.calls = 0
    llm_client._reset_for_tests()
    monkeypatch.setattr(main, "SCRAPERS", [HealthyScraper()])
    monkeypatch.setattr(main, "_RUN_ALL", True)

    main.run(dry_run=True)

    assert HealthyScraper.calls == 1

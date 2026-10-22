"""Home-IP-only sources: skipped on GitHub Actions, runnable together via --source a,b (#378)."""
import pytest

import main


def make_scraper(class_name, calls):
    def scrape(self):
        calls.append(class_name)
        return []

    return type(class_name, (), {"scrape": scrape})()


@pytest.fixture
def fake_scrapers(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main,
        "SCRAPERS",
        [make_scraper(n, calls) for n in ("MotScraper", "TaipeiFukuokaScraper", "PeatixScraper")],
    )
    return calls


def test_github_actions_skips_home_ip_sources(monkeypatch, fake_scrapers):
    monkeypatch.setattr(main, "_ON_GITHUB_ACTIONS", True)
    main.run(dry_run=True)
    assert fake_scrapers == ["PeatixScraper"]


def test_explicit_source_runs_home_ip_sources_even_on_github_actions(monkeypatch, fake_scrapers):
    monkeypatch.setattr(main, "_ON_GITHUB_ACTIONS", True)
    main.run(dry_run=True, source="mot")
    assert fake_scrapers == ["MotScraper"]


def test_local_run_without_source_runs_everything(monkeypatch, fake_scrapers):
    monkeypatch.setattr(main, "_ON_GITHUB_ACTIONS", False)
    main.run(dry_run=True)
    assert fake_scrapers == ["MotScraper", "TaipeiFukuokaScraper", "PeatixScraper"]


def test_source_accepts_a_comma_separated_list(monkeypatch, fake_scrapers):
    monkeypatch.setattr(main, "_ON_GITHUB_ACTIONS", False)
    main.run(dry_run=True, source="mot, taipei_fukuoka")
    assert fake_scrapers == ["MotScraper", "TaipeiFukuokaScraper"]


def test_unknown_name_in_the_list_exits_without_running_anything(monkeypatch, fake_scrapers):
    with pytest.raises(SystemExit):
        main.run(dry_run=True, source="mot,nope")
    assert fake_scrapers == []


def test_home_ip_set_matches_the_blocked_sources():
    assert main.HOME_IP_ONLY_SOURCES == {"mot", "taipei_fukuoka", "jposa_ja"}

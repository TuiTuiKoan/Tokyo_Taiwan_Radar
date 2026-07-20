from pathlib import Path

from audit_post_build import find_unregistered_scrapers


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_registration_audit_ignores_bases_and_intentionally_disabled_sources(
    tmp_path: Path,
):
    _write(
        tmp_path / "scraper/main.py",
        "SCRAPERS = [RegisteredScraper()]\n",
    )
    _write(
        tmp_path / "scraper/sources/registered.py",
        "class RegisteredScraper: pass\nclass MissingScraper: pass\n"
        "class _InternalScraper: pass\n",
    )
    _write(
        tmp_path / "scraper/sources/_cinema_base.py",
        "class CinemaScraper: pass\n",
    )
    _write(
        tmp_path / "scraper/sources/connpass.py",
        "class ConnpassScraper: pass\n",
    )

    assert find_unregistered_scrapers(tmp_path) == [
        ("MissingScraper", Path("scraper/sources/registered.py"))
    ]
from __future__ import annotations

import importlib.util
import sys

import pytest

# Shaped like the 2026-11-06 production log (run 42165199195).
LOG = """\
2026-11-06T05:11:41.1063449Z 2026-11-06 05:11:41,106 [INFO] __main__: === Starting scraper: WasedaTaiwanScraper ===
2026-11-06T05:11:44.3550000Z 2026-11-06 05:11:44,355 [INFO] sources.waseda_taiwan: waseda_taiwan: scraped 2 events
2026-11-06T05:11:44.5910000Z 2026-11-06 05:11:44,591 [INFO] httpx: HTTP Request: GET ***/rest/v1/source_exclusions?select=id
2026-11-06T05:11:44.8370000Z 2026-11-06 05:11:44,837 [INFO] database: Skipped 2 already-scraped event(s) — use force_rescrape=true to overwrite.
2026-11-06T05:11:45.0970000Z 2026-11-06 05:11:45,097 [INFO] __main__: WasedaTaiwanScraper: logged 2 events to scraper_runs
2026-11-06T05:11:45.0971000Z 2026-11-06 05:11:45,097 [INFO] __main__: === Starting scraper: TaiwanshiScraper ===
2026-11-06T05:11:45.3180000Z 2026-11-06 05:11:45,318 [ERROR] sources.taiwanshi: taiwanshi: feed fetch failed: 403 Client Error: Forbidden for url: https://taiwanshi.exblog.jp/atom.xml
2026-11-06T05:11:45.5830000Z 2026-11-06 05:11:45,583 [INFO] __main__: TaiwanshiScraper: logged 0 events to scraper_runs
2026-11-06T05:18:20.2980000Z 2026-11-06 05:18:20,298 [INFO] __main__: Skipping maruhiro (weekly-only, today is not Monday UTC)
2026-11-06T05:30:00.0000000Z 2026-11-06 05:30:00,000 [INFO] __main__: === Starting scraper: LastScraper ===
2026-11-06T05:30:01.0000000Z 2026-11-06 05:30:01,000 [INFO] __main__: LastScraper: scraped 1 events @someone
2026-11-06T05:30:02.0000000Z 2026-11-06 05:30:02,000 [INFO] __main__: Total events scraped: 999
2026-11-06T05:30:03.0000000Z 2026-11-06 05:30:03,000 [INFO] __main__: Running cross-source duplicate merger...
"""


@pytest.fixture(scope="module")
def px(root):
    sys.path.insert(0, str(root / "scripts" / "ci"))
    path = root / "scripts" / "ci" / "prod_log_excerpt.py"
    spec = importlib.util.spec_from_file_location("prod_log_excerpt", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_section_between_starts_without_request_noise(px):
    got = px.excerpt(LOG, "WasedaTaiwanScraper", "waseda_taiwan")
    assert got[0].endswith("=== Starting scraper: WasedaTaiwanScraper ===")
    assert any("Skipped 2 already-scraped" in x for x in got)
    assert any("logged 2 events" in x for x in got)
    assert not any("httpx" in x or "Taiwanshi" in x for x in got)
    assert not got[0].startswith("2026-11-06T")  # GitHub timestamp prefix removed


def test_production_only_403_is_visible(px):
    got = px.excerpt(LOG, "TaiwanshiScraper", "taiwanshi")
    assert any("403 Client Error: Forbidden" in x for x in got)


def test_skipped_weekly_source(px):
    assert px.excerpt(LOG, "MaruhiroScraper", "maruhiro") == [
        "2026-11-06 05:18:20,298 [INFO] __main__: Skipping maruhiro (weekly-only, today is not Monday UTC)"]


def test_section_stops_at_another_sources_skip_line(px):
    got = px.excerpt(LOG, "TaiwanshiScraper", "taiwanshi")
    assert got[-1].endswith("logged 0 events to scraper_runs")  # underscores kept in code block
    assert not any("maruhiro" in x for x in got)


def test_last_source_stops_at_total_and_is_cleaned(px):
    got = px.excerpt(LOG, "LastScraper", "last")
    assert len(got) == 2 and "@​someone" in got[1]
    assert not any("Total events" in x or "merger" in x for x in got)


def test_absent_source(px):
    assert px.excerpt(LOG, "NopeScraper", "nope") is None


def test_long_section_keeps_head_and_verdict_tail(px):
    # midland_cinema had 195 lines on 2026-11-06 with the verdict at the very end (critique G13).
    body = "\n".join(f"2026-11-06 x line {i}" for i in range(200))
    tail = ("2026-11-06 [INFO] __main__: BigScraper: scraped 1 events\n"
            "2026-11-06 [INFO] database: Skipped 1 already-scraped event(s)\n"
            "2026-11-06 [INFO] __main__: BigScraper: logged 1 events to scraper_runs\n"
            "2026-11-06 [INFO] urllib3 InsecureRequestWarning: noise\n")
    got = px.excerpt(f"=== Starting scraper: BigScraper ===\n{body}\n{tail}", "BigScraper", "big")
    assert len(got) == px.MAX_LINES
    assert got[0].endswith("BigScraper ===") and "中間" in got[px.HEAD_LINES]
    assert got[-3:] == ["2026-11-06 [INFO] __main__: BigScraper: scraped 1 events",
                        "2026-11-06 [INFO] database: Skipped 1 already-scraped event(s)",
                        "2026-11-06 [INFO] __main__: BigScraper: logged 1 events to scraper_runs"]


def test_cli_appends_block_and_rejects_bad_names(px, tmp_path):
    log = tmp_path / "a.log"
    log.write_text(LOG, encoding="utf-8")
    out = tmp_path / "report.md"
    out.write_text("<!-- source-diagnose -->\n", encoding="utf-8")
    assert px.main(["--class", "TaiwanshiScraper", "--source", "taiwanshi", "--log", str(log),
                    "--label", "run 42165199195 (2026-11-06)", "--log", str(tmp_path / "missing.log"),
                    "--label", "run 2", "--output", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!-- source-diagnose -->")
    assert "### taiwanshi：production 每日爬蟲 log 擷取" in text
    assert "403 Client Error" in text and "這次執行的 log 沒有提到這個來源" in text
    assert px.main(["--class", "Bad;rm", "--source", "x", "--output", str(out)]) == 2
    assert px.main(["--class", "A", "--source", "x", "--log", str(log), "--output", str(out)]) == 2


def test_marker_with_ansi_still_matches(px):
    log = (
        "2026-11-06T05:11:41.1Z \x1b[36;1m=== Starting scraper: \x1b[0mTaiwanshiScraper ===\x1b[0m\n"
        "2026-11-06T05:11:42.1Z \x1b[32mtaiwanshi: scraped 1 events\x1b[0m\n"
    )
    got = px.excerpt(log, "TaiwanshiScraper", "taiwanshi")
    assert got is not None and "\x1b" not in "".join(got)
    assert got[1].endswith("taiwanshi: scraped 1 events")


def test_ansi_before_timestamp_is_stripped(px):
    log = "\x1b[0m2026-11-06T05:11:41.1Z === Starting scraper: AScraper ===\n2026-11-06T05:11:42.1Z body\n"
    got = px.excerpt(log, "AScraper", "a")
    assert got == ["=== Starting scraper: AScraper ===", "body"]


def test_charset_and_osc8_sequences_keep_label(px):
    assert px._strip("\x1b(B\x1b[mplain") == "plain"
    assert px._strip("\x1b]8;;https://example.com\x1b\\label\x1b]8;;\x1b\\") == "label"
    assert px._strip("\x1b]8;;https://example.com\x07label\x1b]8;;\x07") == "label"


def test_cli_strips_escape_bytes_from_log_file(px, tmp_path):
    log = tmp_path / "a.log"
    raw = (
        "2026-11-06T05:11:41.1Z \x1b[36;1m=== Starting scraper: TaiwanshiScraper ===\x1b(B\x1b[m\n"
        "2026-11-06T05:11:42.1Z \x1b[0mtaiwanshi: ok\x1b[0m\n"
    )
    log.write_bytes(raw.encode("utf-8"))
    out = tmp_path / "report.md"
    assert px.main(["--class", "TaiwanshiScraper", "--source", "taiwanshi", "--log", str(log),
                    "--label", "run 1", "--output", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "taiwanshi: ok" in text
    assert "\x1b" not in text and "[0m" not in text and "(B" not in text

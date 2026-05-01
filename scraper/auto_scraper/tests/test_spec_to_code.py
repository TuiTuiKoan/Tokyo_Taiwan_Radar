"""Unit tests for scraper.auto_scraper.spec_to_code."""

import ast
import unittest

from auto_scraper.spec_to_code import ast_check, render


def _minimal_spec(**overrides) -> dict:
    spec = {
        "source_name": "iwafu_demo",
        "class_name": "IwafuDemo",
        "base_url": "https://www.iwafu.com",
        "search_url": "https://www.iwafu.com/jp/events",
        "search_keyword": "%E5%8F%B0%E6%B9%BE",
        "max_pages": 3,
        "card_selector": "div.event-card",
        "detail_link_selector": "a.event-link",
        "field_selectors": {
            "title": "h3.title",
            "date": "span.date",
            "description": "p.description",
            "location": "span.prefecture",
        },
        "date_regex": r"\d{4}\.\d{2}\.\d{2}",
        "source_id_prefix": "iwafu_demo_",
        "source_id_url_pattern": r"/events/(\d+)",
    }
    spec.update(overrides)
    return spec


class TestSpecToCode(unittest.TestCase):
    def test_minimal_spec_renders(self) -> None:
        code = render(_minimal_spec())
        ast.parse(code)
        self.assertEqual(ast_check(code), [])
        self.assertIn("class IwafuDemoScraper(BaseScraper):", code)
        self.assertIn('source_name = "iwafu_demo"', code)

    def test_invalid_source_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            render(_minimal_spec(source_name="Bad-Name!"))

    def test_max_pages_too_high(self) -> None:
        with self.assertRaises(ValueError):
            render(_minimal_spec(max_pages=20))

    def test_ast_check_detects_forbidden_import(self) -> None:
        code = "import requests\nrequests.get('https://example.com')\n"
        violations = ast_check(code)
        self.assertTrue(
            any("requests" in v for v in violations),
            f"expected requests violation, got: {violations}",
        )

    def test_ast_check_detects_subprocess_call(self) -> None:
        code = "import subprocess\nsubprocess.run(['ls'])\n"
        violations = ast_check(code)
        self.assertTrue(
            any("subprocess" in v for v in violations),
            f"expected subprocess violation, got: {violations}",
        )


if __name__ == "__main__":
    unittest.main()

"""Enrichment scripts run as `python <script>.py` in CI; a NameError from a type
annotation left behind after an import was swapped fails the whole Daily Scraper
through the LLM-step gate (#424).

CI runs Python 3.12, which evaluates annotations at import. Python 3.14 defers them,
so resolve the hints explicitly to catch the same mistake on any version.
"""
import importlib
import typing

import pytest


@pytest.mark.parametrize("module, functions", [("enrich_location", ["extract_location"])])
def test_enrichment_script_annotations_resolve(module, functions):
    mod = importlib.import_module(module)
    for name in functions:
        typing.get_type_hints(getattr(mod, name))

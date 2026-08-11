"""Permanent retirement tests for applied Eslite one-off write paths."""

import sys

import pytest

import _oneoff_fix_eslite_summer_children as summer_children
import _oneoff_fix_eslite_venue_hours as venue_hours


def _assert_apply_retires_before_client(monkeypatch, module, manifest: str) -> None:
    def fail_client():
        raise AssertionError("production client must not be created")

    monkeypatch.setattr(module, "_client", fail_client)
    monkeypatch.setattr(sys, "argv", [module.__file__, "--apply"])

    with pytest.raises(SystemExit, match=rf"permanently retired.*{manifest}"):
        module.main()


def test_summer_hierarchy_apply_is_permanently_retired(monkeypatch):
    _assert_apply_retires_before_client(monkeypatch, summer_children, "4f25dfc756d3")


def test_venue_hours_apply_is_permanently_retired(monkeypatch):
    _assert_apply_retires_before_client(monkeypatch, venue_hours, "5742d0438ed9")

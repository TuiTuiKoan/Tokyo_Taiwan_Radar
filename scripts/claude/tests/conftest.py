from __future__ import annotations

import sys
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CLAUDE_DIR))


@pytest.fixture(scope="session")
def policy():
    import _policy

    return _policy

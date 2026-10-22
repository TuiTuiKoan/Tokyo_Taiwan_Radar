from __future__ import annotations

import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "sync_ai_adapters.py"
GENERATED_DIRS = (".claude/agents", ".claude/commands", ".claude/skills", ".agents/skills", ".codex/agents")


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def sync():
    spec = importlib.util.spec_from_file_location("sync_ai_adapters", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Copy every input and output of sync_ai_adapters.py into a path containing a space."""
    dest = tmp_path / "repo copy"
    for rel in (".github/agents", ".claude", ".agents", ".codex"):
        shutil.copytree(ROOT / rel, dest / rel)
    sources = list((ROOT / ".github" / "prompts").glob("*.prompt.md"))
    sources += list((ROOT / ".github" / "skills").rglob("SKILL.md"))
    for src in sources:
        target = dest / src.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    (dest / "scripts").mkdir()
    shutil.copy2(SCRIPT, dest / "scripts" / SCRIPT.name)
    return dest


@pytest.fixture
def run_sync():
    def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(repo / "scripts" / SCRIPT.name), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    return run


@pytest.fixture
def digest():
    def snapshot(repo: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for rel in GENERATED_DIRS:
            base = repo / rel
            if not base.exists():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    key = path.relative_to(repo).as_posix()
                    result[key] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    return snapshot

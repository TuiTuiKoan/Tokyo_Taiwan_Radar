"""Fail-closed matrix for run_hook.sh (plan.md §7 C-R3, C-R4).

Every case runs the exact hook command string from .claude/settings.json
through /bin/sh, with CLAUDE_PROJECT_DIR pointing at a copy of
scripts/claude/ under a path that contains spaces.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

CLAUDE_DIR = Path(__file__).resolve().parents[1]
ROOT = CLAUDE_DIR.parents[1]
sys.path.insert(0, str(CLAUDE_DIR))
import _policy  # noqa: E402

FIXED = _policy.INTERNAL_ERROR + "\n"
FAKE = "sk-TESTONLY-c0ffee"
SCRIPTS = ("run_hook.sh", "_policy.py", "_tokenizer.py", "pretooluse_bash_guard.py", "pretooluse_file_guard.py")


def hook_commands() -> dict[str, str]:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    commands = {}
    for entry in settings["hooks"]["PreToolUse"]:
        (hook,) = entry["hooks"]
        commands["bash" if "Bash" in entry["matcher"].split("|") else "file"] = hook["command"]
    return commands


@pytest.fixture
def project(tmp_path: Path) -> Path:
    proj = tmp_path / "proj with space" / "Tokyo Taiwan Radar"
    target = proj / "scripts" / "claude"
    target.mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copy2(CLAUDE_DIR / name, target / name)
    return proj


def run(project: Path | None, kind: str, payload, path: str | None = None, extra_env=None):
    env = {
        "PATH": path if path is not None else os.environ["PATH"],
        "HOME": os.environ.get("HOME", "/tmp"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
    }
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    env.update(extra_env or {})
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        ["/bin/sh", "-c", hook_commands()[kind]],
        input=data,
        env=env,
        cwd=str(project) if project else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def bash(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def replace_guard(project: Path, kind: str, body: str) -> None:
    (project / "scripts" / "claude" / f"pretooluse_{kind}_guard.py").write_text(body, encoding="utf-8")


def test_allow_is_silent(project):
    result = run(project, "bash", bash("git status --short"))
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_ask_is_forwarded(project):
    result = run(project, "bash", bash("git -C . push --dry-run origin main"))
    assert result.returncode == 0 and result.stderr == ""
    assert json.loads(result.stdout) == _policy.ask_payload()


def test_deny_forwards_rule_message(project):
    result = run(project, "bash", bash("git reset --hard"))
    assert result.returncode == 2
    assert result.stderr.startswith("ttr-hook: blocked [git-reset-hard]")
    assert result.stdout == ""


def test_file_guard_denies_env(project):
    result = run(project, "file", {"tool_name": "Read", "tool_input": {"file_path": str(project / ".env")}})
    assert result.returncode == 2 and "[env-file-access]" in result.stderr


def test_monitor_goes_through_bash_guard(project):
    payload = {"tool_name": "Monitor", "tool_input": {"command": "git clean -fdx", "description": "x", "timeout_ms": 1000}}
    result = run(project, "bash", payload)
    assert result.returncode == 2 and "[git-clean]" in result.stderr


@pytest.mark.parametrize(
    "body",
    [
        "def broken(:\n",  # syntax error
        "import json\nraise RuntimeError('boom')\n",  # crash before main
        "import sys\nsys.exit(1)\n",
        "import sys\nsys.exit(3)\n",
        "import os, signal\nos.kill(os.getpid(), signal.SIGKILL)\n",
    ],
)
def test_guard_failure_is_blocked_with_fixed_message(project, body):
    replace_guard(project, "bash", body)
    result = run(project, "bash", bash("git status"))
    assert (result.returncode, result.stderr, result.stdout) == (2, FIXED, "")


def test_missing_policy_module(project):
    (project / "scripts" / "claude" / "_policy.py").unlink()
    result = run(project, "bash", bash("git status"))
    assert (result.returncode, result.stderr) == (2, FIXED)


def test_policy_load_failure(project):
    policy = project / "scripts" / "claude" / "_policy.py"
    policy.write_text("raise ImportError('boom')\n" + policy.read_text(encoding="utf-8"), encoding="utf-8")
    result = run(project, "bash", bash("git status"))
    assert (result.returncode, result.stderr) == (2, FIXED)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("bash", "{not json"),
        ("bash", ""),
        ("bash", json.dumps({"tool_name": "Bash", "tool_input": {}})),
        ("bash", json.dumps({"tool_name": "Bash"})),
        ("file", json.dumps({"tool_name": "Read", "tool_input": {}})),
        ("file", json.dumps(["Read"])),
    ],
)
def test_invalid_stdin(project, kind, payload):
    result = run(project, kind, payload)
    assert (result.returncode, result.stderr, result.stdout) == (2, FIXED, "")


def test_python3_missing(project, tmp_path):
    bin_dir = tmp_path / "bin only"
    bin_dir.mkdir()
    for tool in ("bash", "dirname", "mktemp", "rm", "cat"):
        found = shutil.which(tool)
        assert found
        (bin_dir / tool).symlink_to(found)
    assert shutil.which("python3", path=str(bin_dir)) is None
    result = run(project, "bash", bash("git status"), path=str(bin_dir))
    assert result.returncode == 2
    assert result.stderr == "ttr-hook: python3 not found, blocked\n"


def test_launcher_missing(project):
    (project / "scripts" / "claude" / "run_hook.sh").unlink()
    result = run(project, "bash", bash("git status"))
    assert result.returncode == 2


def test_project_dir_unset(project):
    result = run(None, "bash", bash("git status"))
    assert result.returncode == 2


def test_unknown_guard_name(project):
    script = project / "scripts" / "claude" / "run_hook.sh"
    result = subprocess.run(["bash", str(script), "nope"], input="{}", capture_output=True, text=True, check=False)
    assert (result.returncode, result.stderr) == (2, FIXED)


def test_watchdog_blocks(project):
    guard = project / "scripts" / "claude" / "pretooluse_bash_guard.py"
    guard.write_text(guard.read_text(encoding="utf-8").replace("WATCHDOG_SECONDS = 10", "WATCHDOG_SECONDS = 1"), encoding="utf-8")
    policy = project / "scripts" / "claude" / "_policy.py"
    policy.write_text(
        policy.read_text(encoding="utf-8")
        + "\n\ndef bash_decision(payload):\n    import time\n    time.sleep(20)\n",
        encoding="utf-8",
    )
    started = time.monotonic()
    result = run(project, "bash", bash("git status"))
    assert (result.returncode, result.stderr) == (2, FIXED)
    assert time.monotonic() - started < 15


@pytest.mark.parametrize(
    "stdout",
    [
        '{"decision":',
        "not json at all",
        json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                           "permissionDecisionReason": "ttr-hook: x"}}),
        json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": "ttr-hook: x"}}),
        json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask"}}),
        json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "permissionDecision": "ask",
                                           "permissionDecisionReason": "ttr-hook: x"}}),
        json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                           "permissionDecisionReason": "no prefix"}}),
        json.dumps({**_policy.ask_payload(), "continue": False}),
        json.dumps(_policy.ask_payload()) + "\n" + json.dumps(_policy.ask_payload()),
        json.dumps(_policy.ask_payload()) + " trailing",
    ],
)
def test_output_protocol_rejects_unexpected_stdout(project, stdout):
    replace_guard(project, "bash", f"import sys\nsys.stdout.write({stdout!r})\nsys.exit(0)\n")
    result = run(project, "bash", bash("git status"))
    assert (result.returncode, result.stderr, result.stdout) == (2, FIXED, "")


def test_output_protocol_accepts_exact_ask(project):
    replace_guard(project, "bash", f"import sys\nsys.stdout.write({json.dumps(_policy.ask_payload())!r})\n")
    result = run(project, "bash", bash("git status"))
    assert result.returncode == 0 and json.loads(result.stdout) == _policy.ask_payload()


def test_fake_secret_never_reaches_stderr(project):
    (project / ".env").write_text(f"FAKE_TOKEN={FAKE}\n", encoding="utf-8")
    for command in ("cat .env", f"echo {FAKE} > .env", f"printenv FAKE_TOKEN {FAKE}"):
        result = run(project, "bash", bash(command))
        assert result.returncode == 2
        assert FAKE not in result.stderr and FAKE not in result.stdout
        assert command not in result.stderr
    result = run(project, "file", {"tool_name": "Read", "tool_input": {"file_path": str(project / ".env")}})
    assert result.returncode == 2 and FAKE not in result.stderr

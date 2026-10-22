from __future__ import annotations

import json
import re

import pytest

# Fallback for sessions without the hook (pr-flow-tiering notes.md B2 plan B, B4): ask for pushes whose
# destination looks like main or cannot be read from the command. The hook makes the full decision.
PUSH_ASK_RULES = (
    "Bash(git push)",
    "Bash(git push origin)",
    "Bash(git push *main)",
    "Bash(git push *main *)",
    "Bash(git push *HEAD)",
    "Bash(git push *HEAD *)",
)
PUSH_COMMANDS = (
    "git push",
    "git push origin",
    "git push origin main",
    "git push -u origin main",
    "git push origin HEAD:main",
    "git push origin x:refs/heads/main",
    "git push --dry-run origin HEAD:main",
    "git push origin main --dry-run",
    "git push --force origin main",
    "git push origin HEAD",
    "git push -u origin HEAD",
    "git push origin feat/x main",
)
# Pushes the hook allows; the settings fallback must not prompt for them.
FEATURE_PUSH_COMMANDS = (
    "git push origin feat/x",
    "git push -u origin feat/x",
    "git push --dry-run origin feat/pr-flow-tiering",
    "git push origin feat/main-fix",
    "git push origin maintenance",
    "git push origin HEAD:feat/x",
    "git push origin main:feat/x",
    "git push origin feat/x:feat/x",
)
HOOK_TIMEOUT = 30


def hook_command(guard: str) -> str:
    launcher = '"$CLAUDE_PROJECT_DIR/scripts/claude/run_hook.sh"'
    return f"[ -f {launcher} ] && exec bash {launcher} {guard} || exit 2"


EXPECTED_HOOKS = {
    "PreToolUse": [
        {
            "matcher": "Bash|Monitor",
            "hooks": [
                {
                    "type": "command",
                    "command": hook_command("bash"),
                    "timeout": HOOK_TIMEOUT,
                    "onFailure": "block",
                }
            ],
        },
        {
            "matcher": "Read|Grep|Write|Edit|NotebookEdit",
            "hooks": [
                {
                    "type": "command",
                    "command": hook_command("file"),
                    "timeout": HOOK_TIMEOUT,
                    "onFailure": "block",
                }
            ],
        },
    ]
}


@pytest.fixture(scope="module")
def settings_path(root):
    return root / ".claude" / "settings.json"


@pytest.fixture(scope="module")
def settings(settings_path):
    return json.loads(settings_path.read_text(encoding="utf-8"))


def bash_rule_matches(rule: str, command: str) -> bool:
    if rule in ("Bash", "Bash(*)"):
        return True
    match = re.fullmatch(r"Bash\((.*)\)", rule)
    if not match:
        return False
    pattern = match.group(1)
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    if pattern.endswith(" *") and pattern.count("*") == 1 and command == pattern[:-2]:
        return True
    regex = ".*".join(re.escape(part) for part in pattern.split("*"))
    return re.fullmatch(regex, command) is not None


def test_push_ask_rules_cover_main_like_pushes(settings):
    rules = settings["permissions"]["ask"]
    for command in PUSH_COMMANDS:
        assert any(bash_rule_matches(rule, command) for rule in rules), command


def test_push_ask_rules_skip_feature_pushes(settings):
    rules = settings["permissions"]["ask"]
    for command in FEATURE_PUSH_COMMANDS:
        assert not any(bash_rule_matches(rule, command) for rule in rules), command


def test_no_allow_rule_covers_git_push(settings):
    for rule in settings.get("permissions", {}).get("allow", []):
        assert not any(bash_rule_matches(rule, command) for command in PUSH_COMMANDS), rule


def test_no_bypass_or_hook_disabling(settings):
    permissions = settings.get("permissions", {})
    assert permissions.get("defaultMode") != "bypassPermissions"
    assert "disableAllHooks" not in settings
    assert "bypassPermissions" not in json.dumps(settings)


def test_settings_exact_shape(settings):
    # Hooks from ai-portability (notes.md §4.23); ask rules narrowed by pr-flow-tiering plan B (notes.md B4).
    assert set(settings) == {"permissions", "hooks"}
    assert settings["permissions"] == {"ask": list(PUSH_ASK_RULES)}
    assert settings["hooks"] == EXPECTED_HOOKS


def test_hook_commands_fail_closed(settings):
    for entry in settings["hooks"]["PreToolUse"]:
        (hook,) = entry["hooks"]
        command = hook["command"]
        assert command.startswith('[ -f "$CLAUDE_PROJECT_DIR/scripts/claude/run_hook.sh" ] && exec bash ')
        assert command.endswith(" || exit 2")
        assert hook["onFailure"] == "block"


def test_guard_watchdog_below_hook_timeout(root):
    for kind in ("bash", "file"):
        source = (root / "scripts" / "claude" / f"pretooluse_{kind}_guard.py").read_text(encoding="utf-8")
        watchdog = int(re.search(r"^WATCHDOG_SECONDS = (\d+)", source, re.MULTILINE).group(1))
        assert 0 < watchdog < HOOK_TIMEOUT


def test_settings_is_not_a_generated_file(sync, root, settings_path, tmp_repo, run_sync):
    assert sync.MARKER not in settings_path.read_text(encoding="utf-8")
    assert settings_path not in sync.generated_files(root)
    copy = tmp_repo / ".claude" / "settings.json"
    before = copy.read_bytes()
    assert run_sync(tmp_repo).returncode == 0
    assert copy.read_bytes() == before

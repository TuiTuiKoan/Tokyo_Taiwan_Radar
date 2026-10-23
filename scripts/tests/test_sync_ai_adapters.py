from __future__ import annotations

from pathlib import Path

EXPECTED_ROLES = {
    "plan-critic": "planner",
    "tester": "tester",
    "validate-merge-deploy": "vmd",
    "close-campaign-retire-worktree": "closer",
    "lianbu-spokesperson": "readonly",
    "engineer": "full",
    "designer": "full",
    "history-teller": "full",
    "update-history-skill-agent": "full",
    "peatix-scraper": "full",
    "tcc-scraper": "full",
}
EXPECTED_UNDECIDED = {"architect", "reviewer", "researcher", "scraper-expert"}
EXPECTED_TIERS = {
    "architect": "plan",
    "plan-critic": "plan",
    "engineer": "build",
    "designer": "build",
    "scraper-expert": "build",
    "validate-merge-deploy": "build",
    "close-campaign-retire-worktree": "build",
    "researcher": "build",
    "reviewer": "build",
    "tester": "grunt",
    "history-teller": "grunt",
    "update-history-skill-agent": "grunt",
    "lianbu-spokesperson": "grunt",
    "peatix-scraper": "grunt",
    "tcc-scraper": "grunt",
}
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
AGENT_COUNT = 15


def agent_name(sync, path: Path) -> str:
    meta = sync.parse_frontmatter(path)
    return sync.kebab(sync.one_line(meta.get("name") or path.stem.removesuffix(".agent")))


def wrapper_tools(text: str) -> str | None:
    frontmatter = text.split("\n---", 1)[0]
    for line in frontmatter.splitlines():
        if line.startswith("tools:"):
            return line.removeprefix("tools:").strip()
    return None


def wrapper_field(text: str, key: str) -> str | None:
    frontmatter = text.split("\n---", 1)[0]
    for line in frontmatter.splitlines():
        if line.startswith(f"{key}:"):
            return line.removeprefix(f"{key}:").strip()
    return None


def replace_in(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1. role -> tools projection; unknown role and missing role fail


def test_every_agent_has_expected_role_or_is_undecided(sync, root):
    seen: dict[str, str] = {}
    for path in sync.agent_sources(root):
        meta = sync.parse_frontmatter(path)
        seen[agent_name(sync, path)] = sync.one_line(meta.get("claude-role"))
    assert set(seen) == set(EXPECTED_ROLES) | EXPECTED_UNDECIDED
    assert {name: role for name, role in seen.items() if role} == EXPECTED_ROLES
    assert {name for name, role in seen.items() if not role} == EXPECTED_UNDECIDED
    assert sync.UNDECIDED_AGENTS == EXPECTED_UNDECIDED


def test_repository_has_no_role_problems(sync, root):
    assert sync.role_problems(root) == []


def test_wrapper_tools_follow_role(sync, root):
    outputs = sync.agent_outputs(root)
    for name, role in EXPECTED_ROLES.items():
        tools = wrapper_tools(outputs[Path(".claude/agents") / f"{name}.md"])
        expected = sync.ROLE_TOOLS[role]
        if expected is None:
            assert tools is None, name
        else:
            assert tools == ", ".join(expected), name
    for name in EXPECTED_UNDECIDED:
        assert wrapper_tools(outputs[Path(".claude/agents") / f"{name}.md"]) is None, name


def test_restricted_roles_have_no_edit_tools(sync):
    for role, tools in sync.ROLE_TOOLS.items():
        if role == "full":
            assert tools is None
            continue
        assert not EDIT_TOOLS & set(tools), role
    assert "Bash" not in sync.ROLE_TOOLS["readonly"]


def test_role_tools_are_known(sync):
    known = set(sync.CLAUDE_TOOL_CATEGORIES) | set(sync.GENERIC_CLAUDE_TOOLS)
    for tools in sync.ROLE_TOOLS.values():
        assert set(tools or ()) <= known


def test_unknown_role_fails(tmp_repo, run_sync):
    replace_in(tmp_repo / ".github/agents/tester.agent.md", "claude-role: tester", "claude-role: bogus")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "unknown claude-role .github/agents/tester.agent.md: bogus" in result.stderr


def test_missing_role_fails(tmp_repo, run_sync):
    replace_in(tmp_repo / ".github/agents/engineer.agent.md", "claude-role: full\n", "")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "missing claude-role .github/agents/engineer.agent.md" in result.stderr


def test_role_on_undecided_agent_fails(tmp_repo, run_sync):
    path = tmp_repo / ".github/agents/reviewer.agent.md"
    replace_in(path, "\nhandoffs:", "\nclaude-role: full\nhandoffs:")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "claude-role on undecided agent .github/agents/reviewer.agent.md: full" in result.stderr


def test_write_mode_refuses_when_roles_are_broken(tmp_repo, run_sync, digest):
    before = digest(tmp_repo)
    replace_in(tmp_repo / ".github/agents/tester.agent.md", "claude-role: tester", "claude-role: bogus")
    result = run_sync(tmp_repo)
    assert result.returncode == 1
    assert digest(tmp_repo) == before


# 2. Copilot category consistency


def test_tester_projection_with_write_fails(tmp_repo, run_sync):
    script = tmp_repo / "scripts" / "sync_ai_adapters.py"
    replace_in(
        script,
        '"tester": ("Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch", "AskUserQuestion"),',
        '"tester": ("Read", "Grep", "Glob", "Bash", "WebFetch", "WebSearch", "AskUserQuestion", "Write"),',
    )
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "claude-role tester exceeds Copilot tools .github/agents/tester.agent.md: edit" in result.stderr


def test_planner_fallback_p_with_write_is_allowed(tmp_repo, run_sync):
    script = tmp_repo / "scripts" / "sync_ai_adapters.py"
    replace_in(
        script,
        '"planner": ("Read", "Grep", "Glob", "WebFetch", "WebSearch", "Bash", "AskUserQuestion"),',
        '"planner": ("Read", "Grep", "Glob", "WebFetch", "WebSearch", "Bash", "AskUserQuestion", "Write"),',
    )
    assert run_sync(tmp_repo).returncode == 0
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Write" in wrapper_tools((tmp_repo / ".claude/agents/plan-critic.md").read_text(encoding="utf-8"))


def test_full_role_on_copilot_restricted_agent_fails(tmp_repo, run_sync):
    replace_in(tmp_repo / ".github/agents/tester.agent.md", "claude-role: tester", "claude-role: full")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "claude-role full exceeds Copilot tools .github/agents/tester.agent.md: agent, edit" in result.stderr


def test_unknown_copilot_token_fails(tmp_repo, run_sync):
    replace_in(tmp_repo / ".github/agents/tester.agent.md", "  - web\n", "  - web\n  - vscode/runCommand\n")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "unknown Copilot tool token .github/agents/tester.agent.md: vscode/runCommand" in result.stderr


def test_copilot_tools_parse_inline_block_and_legacy_names(sync, root):
    agents = root / ".github" / "agents"
    tester = sync.copilot_tools(sync.parse_frontmatter(agents / "tester.agent.md"))
    vmd = sync.copilot_tools(sync.parse_frontmatter(agents / "validate-merge-deploy.agent.md"))
    lianbu = sync.copilot_tools(sync.parse_frontmatter(agents / "lianbu-spokesperson.agent.md"))
    assert tester == vmd == ["read", "search", "execute", "web"]
    assert lianbu == ["read_file", "semantic_search", "grep_search", "fetch_webpage"]
    assert {sync.COPILOT_TOOL_CATEGORIES[token] for token in lianbu} == {"read", "search", "web"}


# 3. pinned model


def test_pinned_model_fails_check(tmp_repo, run_sync, sync):
    replace_in(tmp_repo / ".github/agents/tester.agent.md", "claude-role: tester\n", "claude-role: tester\nmodel: claude-sonnet-4-5\n")
    assert sync.pinned_models(tmp_repo)
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "pinned model .github/agents/tester.agent.md" in result.stderr


# 3b. tier -> model alias and effort projection


def test_every_agent_has_expected_tier(sync, root):
    seen = {
        agent_name(sync, path): sync.one_line(sync.parse_frontmatter(path).get("tier"))
        for path in sync.agent_sources(root)
    }
    assert seen == EXPECTED_TIERS
    assert sync.tier_problems(root) == []


def test_tier_table_holds_aliases_not_model_ids(sync):
    assert set(sync.TIERS) == {"plan", "build", "grunt"}
    for tier in sync.TIERS.values():
        assert tier["model"] in {"opus", "sonnet", "haiku"}
        assert tier["effort"] in {"low", "medium", "high"}


def test_claude_wrapper_carries_tier_model_and_effort(sync, root):
    outputs = sync.agent_outputs(root)
    for name, tier in EXPECTED_TIERS.items():
        text = outputs[Path(".claude/agents") / f"{name}.md"]
        assert wrapper_field(text, "model") == sync.TIERS[tier]["model"], name
        assert wrapper_field(text, "effort") == sync.TIERS[tier]["effort"], name


def test_codex_agent_files_parse_and_follow_tier(sync, root):
    import tomllib

    outputs = sync.agent_outputs(root)
    for name, tier in EXPECTED_TIERS.items():
        text = outputs[Path(".codex/agents") / f"{name}.toml"]
        data = tomllib.loads(text)
        assert data["name"] == name
        assert data["model_reasoning_effort"] == sync.TIERS[tier]["effort"], name
        assert "model" not in data and "model_provider" not in data, name
        assert data["developer_instructions"].strip(), name
        assert text.startswith(sync.TOML_MARKER), name


def test_missing_tier_fails(tmp_repo, run_sync):
    replace_in(tmp_repo / ".github/agents/engineer.agent.md", "tier: build\n", "")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "missing tier .github/agents/engineer.agent.md" in result.stderr


def test_unknown_tier_fails(tmp_repo, run_sync):
    replace_in(tmp_repo / ".github/agents/engineer.agent.md", "tier: build", "tier: turbo")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "unknown tier .github/agents/engineer.agent.md: turbo" in result.stderr


def test_source_model_alias_is_still_rejected(tmp_repo, run_sync, sync):
    # Copilot would resolve `model: opus` as a model name; tier is the only knob in sources.
    replace_in(tmp_repo / ".github/agents/tester.agent.md", "tier: grunt\n", "tier: grunt\nmodel: opus\n")
    assert sync.pinned_models(tmp_repo)
    assert run_sync(tmp_repo, "--check").returncode == 1


def test_hand_edited_codex_agent_is_reported_as_changed(tmp_repo, run_sync):
    replace_in(tmp_repo / ".codex/agents/tester.toml", 'model_reasoning_effort = "low"', 'model_reasoning_effort = "max"')
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "changed .codex/agents/tester.toml" in result.stdout


def test_stale_codex_agent_is_removed(tmp_repo, run_sync, sync):
    stale = tmp_repo / ".codex" / "agents" / "stale.toml"
    stale.write_text(f"{sync.TOML_MARKER}\nname = \"stale\"\n", encoding="utf-8")
    hand_written = tmp_repo / ".codex" / "agents" / "mine.toml"
    hand_written.write_text('name = "mine"\n', encoding="utf-8")
    assert run_sync(tmp_repo).returncode == 0
    assert not stale.exists()
    assert hand_written.exists()


# 4. hand-edited wrapper


def test_hand_edited_wrapper_is_reported_as_changed(tmp_repo, run_sync):
    wrapper = tmp_repo / ".claude" / "agents" / "tester.md"
    replace_in(wrapper, "AskUserQuestion\n", "AskUserQuestion, Write\n")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "changed .claude/agents/tester.md" in result.stdout


# 5. idempotence, untouched non-generated files, stale removal


def test_generation_is_idempotent(tmp_repo, run_sync, digest, sync):
    hand_written = tmp_repo / ".claude" / "agents" / "hand-written.md"
    hand_written.write_text("---\nname: hand-written\n---\nnot generated\n", encoding="utf-8")
    stale = tmp_repo / ".claude" / "agents" / "stale.md"
    stale.write_text(f"---\nname: stale\n---\n\n{sync.MARKER}\n", encoding="utf-8")
    settings = tmp_repo / ".claude" / "settings.json"
    settings_bytes = settings.read_bytes()
    hand_bytes = hand_written.read_bytes()

    assert run_sync(tmp_repo).returncode == 0
    first = digest(tmp_repo)
    assert run_sync(tmp_repo).returncode == 0
    second = digest(tmp_repo)

    assert first == second
    assert sync.check(tmp_repo, sync.expected_outputs(tmp_repo)) == 0
    assert run_sync(tmp_repo, "--check").returncode == 0
    assert not stale.exists()
    assert hand_written.read_bytes() == hand_bytes
    assert settings.read_bytes() == settings_bytes


def test_repository_outputs_are_current(sync, root):
    assert sync.check(root, sync.expected_outputs(root)) == 0


# 6. wrapper count and unique names


def test_wrapper_count_matches_agent_sources(sync, root):
    sources = sync.agent_sources(root)
    outputs = sync.agent_outputs(root)
    names = [agent_name(sync, path) for path in sources]
    on_disk = sorted((root / ".claude" / "agents").glob("*.md"))
    codex_on_disk = sorted((root / ".codex" / "agents").glob("*.toml"))
    assert len(set(names)) == len(names)
    assert len(sources) == AGENT_COUNT
    assert set(names) == {path.stem for path in on_disk} == {path.stem for path in codex_on_disk}
    assert {path.as_posix() for path in outputs} == {
        path.relative_to(root).as_posix() for path in [*on_disk, *codex_on_disk]
    }
    assert all(sync.MARKER in path.read_text(encoding="utf-8") for path in on_disk)
    assert all(sync.TOML_MARKER in path.read_text(encoding="utf-8") for path in codex_on_disk)

"""Hardening tests for sync_ai_adapters.py found by the ai-harness agent-teams spike.

Both spike runs (docs/specs/active/ai-harness/spike-result-run1.md and spike-result.md)
independently reported the write-order bug, the marker matching, the missing tier
tests and the TOML escaping gaps. Each test below names the finding it locks.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

import pytest

TESTER = ".github/agents/tester.agent.md"
ENGINEER = ".github/agents/engineer.agent.md"
ARCHITECT = ".github/agents/architect.agent.md"
TESTER_DESCRIPTION = (
    'description: "Runs scrapers, validates output, and detects broken selectors '
    'or logic for Tokyo Taiwan Radar"'
)


def replace_in(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def frontmatter_keys(text: str) -> list[str]:
    block = text.split("\n---", 1)[0].splitlines()[1:]
    return [line.split(":", 1)[0] for line in block if line and not line.startswith(" ")]


# --- finding B: write mode refuses a tier problem and writes nothing ----------------


@pytest.mark.parametrize(
    "old,new",
    [("tier: build\n", ""), ("tier: build", "tier: turbo")],
    ids=["missing", "unknown"],
)
def test_write_mode_refuses_a_tier_problem_and_writes_nothing(tmp_repo, run_sync, digest, old, new):
    replace_in(tmp_repo / ENGINEER, old, new)
    before = digest(tmp_repo)
    result = run_sync(tmp_repo)
    assert result.returncode == 1
    assert "tier .github/agents/engineer.agent.md" in result.stderr
    assert digest(tmp_repo) == before


# --- finding C: what a missing tier does to the generated output --------------------


def test_missing_tier_leaves_model_and_effort_out_of_outputs(sync, tmp_repo):
    replace_in(tmp_repo / ENGINEER, "tier: build\n", "")
    outputs = sync.agent_outputs(tmp_repo)
    wrapper = outputs[Path(".claude/agents/engineer.md")]
    assert "\nmodel:" not in wrapper and "\neffort:" not in wrapper
    assert "model_reasoning_effort" not in outputs[Path(".codex/agents/engineer.toml")]
    assert "\nmodel: haiku" in outputs[Path(".claude/agents/tester.md")]


# --- finding T4: --check on stale generated toml files -----------------------------


@pytest.mark.parametrize("rel", [".codex/agents/stale.toml", ".claude/agents/stale.toml"])
def test_check_reports_a_stale_generated_toml(tmp_repo, run_sync, sync, rel):
    (tmp_repo / rel).write_text(f'{sync.TOML_MARKER}\nname = "stale"\n', encoding="utf-8")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert f"stale {rel}" in result.stdout


def test_hand_written_files_in_codex_agents_are_left_alone(tmp_repo, run_sync):
    agents = tmp_repo / ".codex" / "agents"
    readme = agents / "README.md"
    note = agents / "mine.toml"
    binary = agents / "bad.md"
    readme.write_text("# notes\n", encoding="utf-8")
    note.write_text('name = "mine"\n', encoding="utf-8")
    binary.write_bytes(b"\xff\xfe\x00")
    assert run_sync(tmp_repo).returncode == 0
    assert run_sync(tmp_repo, "--check").returncode == 0
    assert readme.read_text(encoding="utf-8") == "# notes\n"
    assert note.read_text(encoding="utf-8") == 'name = "mine"\n'
    assert binary.read_bytes() == b"\xff\xfe\x00"


def test_check_reports_every_missing_codex_agent_when_the_directory_is_absent(tmp_repo, run_sync):
    shutil.rmtree(tmp_repo / ".codex")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert result.stdout.count("missing .codex/agents/") == 15
    assert run_sync(tmp_repo).returncode == 0
    assert len(list((tmp_repo / ".codex" / "agents").glob("*.toml"))) == 15


# --- findings A and T5: check every conflict before deleting anything ---------------


def test_hand_written_same_name_toml_aborts_before_deleting_anything(tmp_repo, run_sync, digest):
    target = tmp_repo / ".codex" / "agents" / "tester.toml"
    target.write_text('name = "mine"\n', encoding="utf-8")
    before = digest(tmp_repo)
    result = run_sync(tmp_repo)
    assert result.returncode != 0
    assert "refusing to overwrite non-generated file: .codex/agents/tester.toml" in result.stderr
    assert digest(tmp_repo) == before
    assert target.read_text(encoding="utf-8") == 'name = "mine"\n'


def test_an_undecodable_file_at_an_expected_path_is_a_conflict_not_a_crash(tmp_repo, run_sync, digest):
    target = tmp_repo / ".codex" / "agents" / "tester.toml"
    target.write_bytes(b"\xff\xfe\x00")
    before = digest(tmp_repo)
    result = run_sync(tmp_repo)
    assert result.returncode != 0
    assert "refusing to overwrite non-generated file: .codex/agents/tester.toml" in result.stderr
    assert "Traceback" not in result.stderr
    assert digest(tmp_repo) == before


def test_hand_edit_that_removes_the_marker_blocks_the_next_write(tmp_repo, run_sync, sync, digest):
    toml = tmp_repo / ".codex" / "agents" / "tester.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(sync.TOML_MARKER + "\n", ""), encoding="utf-8")
    assert run_sync(tmp_repo, "--check").returncode == 1
    before = digest(tmp_repo)
    result = run_sync(tmp_repo)
    assert result.returncode != 0
    assert "refusing to overwrite" in result.stderr
    assert digest(tmp_repo) == before


def test_hand_edit_that_adds_a_model_key_is_reported_as_changed(tmp_repo, run_sync):
    toml = tmp_repo / ".codex" / "agents" / "tester.toml"
    toml.write_text(toml.read_text(encoding="utf-8") + 'model = "gpt-6"\n', encoding="utf-8")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "changed .codex/agents/tester.toml" in result.stdout


# --- finding E: marker text must not make a hand-written file "generated" -----------


def test_marker_text_in_prose_does_not_make_a_file_generated(tmp_repo, run_sync, sync):
    note = tmp_repo / ".claude" / "skills" / "architect" / "EXTRA.md"
    note.write_text(f"The marker `{sync.MARKER}` is written by sync.\n", encoding="utf-8")
    assert run_sync(tmp_repo).returncode == 0
    assert note.exists()


def test_a_marker_for_the_other_file_type_does_not_make_a_file_generated(tmp_repo, run_sync, sync):
    toml = tmp_repo / ".codex" / "agents" / "mine.toml"
    toml.write_text(f'name = "mine"\n{sync.MARKER}\n', encoding="utf-8")
    md = tmp_repo / ".claude" / "agents" / "mine.md"
    md.write_text(f"# mine\n{sync.TOML_MARKER}\n", encoding="utf-8")
    assert run_sync(tmp_repo).returncode == 0
    assert toml.exists() and md.exists()
    assert run_sync(tmp_repo, "--check").returncode == 0


# --- finding T7: tier value boundaries ----------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", ["missing tier .github/agents/engineer.agent.md"]),
        ("Build", ["unknown tier .github/agents/engineer.agent.md: Build"]),
        ("[build]", None),
        ('"build"', []),
        ("build # a note", []),
    ],
    ids=["empty", "capitalised", "list", "quoted", "inline-comment"],
)
def test_tier_value_boundaries(sync, tmp_repo, value, expected):
    replace_in(tmp_repo / ENGINEER, "tier: build", f"tier: {value}".rstrip())
    problems = sync.tier_problems(tmp_repo)
    if expected is None:
        assert len(problems) == 1 and problems[0].startswith("unknown tier .github/agents/engineer.agent.md")
    else:
        assert problems == expected


def test_a_tier_with_an_inline_comment_still_projects_its_tier(sync, tmp_repo):
    replace_in(tmp_repo / ENGINEER, "tier: build", "tier: build # note")
    wrapper = sync.agent_outputs(tmp_repo)[Path(".claude/agents/engineer.md")]
    assert "\nmodel: sonnet\n" in wrapper and "\neffort: medium\n" in wrapper


def test_a_missing_tier_and_a_missing_role_are_both_reported(tmp_repo, run_sync):
    replace_in(tmp_repo / ENGINEER, "tier: build\n", "")
    replace_in(tmp_repo / ENGINEER, "claude-role: full\n", "")
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "missing tier .github/agents/engineer.agent.md" in result.stderr
    assert "missing claude-role .github/agents/engineer.agent.md" in result.stderr


def test_an_undecided_agent_without_a_tier_is_reported(sync, tmp_repo):
    replace_in(tmp_repo / ARCHITECT, "tier: plan\n", "")
    assert sync.tier_problems(tmp_repo) == ["missing tier .github/agents/architect.agent.md"]


# --- finding T13: empty and truncated inputs ----------------------------------------


def test_frontmatter_without_a_closing_delimiter_reports_a_missing_tier(sync, tmp_repo):
    (tmp_repo / ENGINEER).write_text('---\nname: Engineer\ndescription: "x"\n', encoding="utf-8")
    assert "missing tier .github/agents/engineer.agent.md" in sync.tier_problems(tmp_repo)


def test_no_agent_sources_means_no_tier_problems_and_no_agent_outputs(sync, tmp_repo):
    for path in list((tmp_repo / ".github" / "agents").rglob("*.agent.md")):
        path.unlink()
    assert sync.tier_problems(tmp_repo) == []
    assert sync.agent_outputs(tmp_repo) == {}


# --- findings T8, T9 and the field order ---------------------------------------------


def test_a_model_key_inside_handoffs_is_reported_as_pinned(sync, tmp_repo):
    replace_in(tmp_repo / TESTER, "  - label:", "  - model: opus\n    label:")
    assert any("agents/tester.agent.md" in line for line in sync.pinned_models(tmp_repo))


def test_a_model_key_in_a_prompt_is_reported_as_pinned(sync, tmp_repo):
    prompt = tmp_repo / ".github" / "prompts" / "weekly-review.prompt.md"
    replace_in(prompt, "---\n", "---\nmodel: opus\n")
    assert any("weekly-review.prompt.md" in line for line in sync.pinned_models(tmp_repo))


def test_allowing_pinned_models_does_not_let_a_source_model_change_the_projection(tmp_repo, run_sync):
    replace_in(tmp_repo / TESTER, "tier: grunt\n", "tier: grunt\nmodel: opus\n")
    assert run_sync(tmp_repo, "--allow-pinned-models").returncode == 0
    wrapper = (tmp_repo / ".claude" / "agents" / "tester.md").read_text(encoding="utf-8")
    assert "\nmodel: haiku\n" in wrapper and "model: opus" not in wrapper


def test_wrapper_frontmatter_has_each_projected_key_once_in_order(sync, root):
    outputs = sync.agent_outputs(root)
    tester = frontmatter_keys(outputs[Path(".claude/agents/tester.md")])
    assert tester == ["name", "description", "tools", "model", "effort"]
    engineer = frontmatter_keys(outputs[Path(".claude/agents/engineer.md")])
    assert engineer == ["name", "description", "model", "effort"]
    for path, text in outputs.items():
        if path.suffix == ".md":
            keys = frontmatter_keys(text)
            assert keys.count("model") == 1 and keys.count("effort") == 1, path


# --- findings D and #7: TOML escaping and unencodable text ---------------------------


@pytest.mark.parametrize(
    "ch",
    ['"', "\\", "\t", "\n", " ", "\U0001f600", "\x00", "\x7f", "é"],
    ids=["quote", "backslash", "tab", "newline", "u2028", "emoji", "nul", "del", "e-acute"],
)
def test_toml_string_round_trips(sync, ch):
    value = f"a{ch}b"
    assert tomllib.loads("k = " + sync.toml_string(value))["k"] == value


def test_a_description_with_special_characters_survives_a_full_write(tmp_repo, run_sync):
    replace_in(tmp_repo / TESTER, TESTER_DESCRIPTION, 'description: "He said \\"hi\\" \\\\ ok \U0001f600 日本語"')
    assert run_sync(tmp_repo).returncode == 0
    data = tomllib.loads((tmp_repo / ".codex" / "agents" / "tester.toml").read_text(encoding="utf-8"))
    assert data["description"] == 'He said "hi" \\ ok \U0001f600 日本語'
    assert run_sync(tmp_repo, "--check").returncode == 0


def test_an_unencodable_description_aborts_before_any_file_changes(tmp_repo, run_sync, digest):
    replace_in(tmp_repo / TESTER, TESTER_DESCRIPTION, 'description: "a\\ud800b"')
    before = digest(tmp_repo)
    result = run_sync(tmp_repo)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert digest(tmp_repo) == before


# --- finding #8: two agents must not share an output name ----------------------------


def test_duplicate_output_names_are_rejected_without_touching_files(tmp_repo, run_sync, digest):
    replace_in(tmp_repo / TESTER, "name: Tester", "name: engineer")
    before = digest(tmp_repo)
    result = run_sync(tmp_repo)
    assert result.returncode != 0
    assert "duplicate" in result.stderr
    assert digest(tmp_repo) == before


# --- finding F / #9: no orphan heading when no handoff item is usable ----------------


def test_no_handoff_heading_when_no_item_is_usable(sync, tmp_repo):
    (tmp_repo / ENGINEER).write_text(
        '---\nname: Engineer\ndescription: "x"\ntier: build\nclaude-role: full\n'
        'handoffs:\n  - prompt: "only a prompt, no label and no agent"\n---\nbody\n',
        encoding="utf-8",
    )
    outputs = sync.agent_outputs(tmp_repo)
    assert "完成後建議的下一步" not in outputs[Path(".claude/agents/engineer.md")]
    assert "完成後建議的下一步" not in outputs[Path(".codex/agents/engineer.toml")]


def test_the_heading_is_kept_when_an_item_is_usable(sync, root):
    outputs = sync.agent_outputs(root)
    assert "完成後建議的下一步" in outputs[Path(".claude/agents/tester.md")]
    assert "完成後建議的下一步" in outputs[Path(".codex/agents/tester.toml")]


# --- finding G: symlinks are never followed, written through, or deleted -------------


@pytest.fixture
def outside(tmp_path):
    """A directory outside the repository copy that a symlink can point at."""
    folder = tmp_path / "outside"
    folder.mkdir()
    return folder


def test_a_symlink_at_an_expected_path_is_a_conflict_not_written_through(tmp_repo, run_sync, sync, outside):
    target = outside / "real.toml"
    target.write_text(f'{sync.TOML_MARKER}\nname = "outside"\n', encoding="utf-8")
    link = tmp_repo / ".codex" / "agents" / "tester.toml"
    link.unlink()
    link.symlink_to(target)
    result = run_sync(tmp_repo)
    assert result.returncode != 0
    assert "refusing to overwrite non-generated file: .codex/agents/tester.toml" in result.stderr
    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == f'{sync.TOML_MARKER}\nname = "outside"\n'


def test_check_reports_a_symlink_at_an_expected_path(tmp_repo, run_sync, outside):
    link = tmp_repo / ".codex" / "agents" / "tester.toml"
    content = link.read_text(encoding="utf-8")
    link.unlink()
    target = outside / "same.toml"
    target.write_text(content, encoding="utf-8")
    link.symlink_to(target)
    result = run_sync(tmp_repo, "--check")
    assert result.returncode == 1
    assert "symlink .codex/agents/tester.toml" in result.stdout


def test_a_symlinked_file_with_a_marker_is_left_in_place(tmp_repo, run_sync, sync, outside):
    target = outside / "note.md"
    target.write_text(f"# note\n{sync.MARKER}\n", encoding="utf-8")
    link = tmp_repo / ".claude" / "agents" / "linked-note.md"
    link.symlink_to(target)
    assert run_sync(tmp_repo).returncode == 0
    assert link.is_symlink() and target.exists()


def test_a_symlinked_directory_is_not_traversed(tmp_repo, run_sync, sync, outside):
    (outside / "inner.md").write_text(f"# inner\n{sync.MARKER}\n", encoding="utf-8")
    link = tmp_repo / ".claude" / "skills" / "linked-dir"
    link.symlink_to(outside, target_is_directory=True)
    assert run_sync(tmp_repo).returncode == 0
    assert link.is_symlink() and (outside / "inner.md").exists()

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_enum_parity.py"

ACCOUNT_ROUTE = "web/app/api/account/annotate-event/route.ts"


@pytest.fixture(scope="session")
def parity():
    spec = importlib.util.spec_from_file_location("check_enum_parity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path: Path, parity) -> Path:
    """Copy every file the checker reads into a path containing a space."""
    dest = tmp_path / "repo copy"
    rels = [parity.TYPES_TS, parity.ANNOTATOR, parity.DATABASE, parity.TAXONOMY,
            *parity.LOCALE_FILES, *parity.ROUTE_FILES]
    rels += [p.relative_to(ROOT).as_posix() for p in (ROOT / parity.MIGRATIONS_DIR).glob("*.sql")]
    for rel in rels:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    return dest


def run(parity, capsys, root: Path, *args: str) -> tuple[int, str]:
    code = parity.main(["--root", str(root), *args])
    return code, capsys.readouterr().out


def replace_in(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} must appear exactly once in {path}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def edit_locale(path: Path, section: str, fn) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data[section])
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_repository_is_in_parity(parity, capsys):
    code, out = run(parity, capsys, ROOT)
    assert code == 0, out


def test_copied_repository_is_in_parity(parity, capsys, repo):
    code, out = run(parity, capsys, repo)
    assert code == 0, out


# Each case drifts one copy and names the source the report must point at.
DRIFT_CASES = {
    "types.ts gains an event_form": (
        lambda r: replace_in(r / "web/lib/types.ts", '  "publication",\n  "other",\n] as const;',
                             '  "publication",\n  "other",\n  "dance",\n] as const;'),
        "scraper/annotator.py VALID_EVENT_FORMS: missing ['dance']",
    ),
    "annotator VALID_EVENT_FORMS loses a value": (
        lambda r: replace_in(r / "scraper/annotator.py",
                             '"tasting", "broadcast", "study_abroad", "publication", "other",',
                             '"broadcast", "study_abroad", "publication", "other",'),
        "scraper/annotator.py VALID_EVENT_FORMS: missing ['tasting']",
    ),
    "database writer whitelist loses a value": (
        lambda r: replace_in(r / "scraper/database.py",
                             '"conference", "networking", "screening_with_talk", "tour", "competition",',
                             '"conference", "networking", "screening_with_talk", "competition",'),
        "scraper/database.py _VALID_EVENT_FORMS: missing ['tour']",
    ),
    "prompt list loses a value": (
        lambda r: replace_in(r / "scraper/annotator.py", "tasting, broadcast, study_abroad, other",
                             "tasting, broadcast, other"),
        "'Pick one or more from' list: missing ['study_abroad']",
    ),
    "prompt list gains the source-assigned publication": (
        lambda r: replace_in(r / "scraper/annotator.py", "tasting, broadcast, study_abroad, other",
                             "tasting, broadcast, study_abroad, publication, other"),
        "'Pick one or more from' list: extra ['publication']",
    ),
    "newest migration narrows the constraint": (
        lambda r: (r / "supabase/migrations/999_narrow_event_form.sql").write_text(
            "ALTER TABLE events\n  ADD CONSTRAINT events_event_form_check\n"
            "  CHECK (event_form <@ ARRAY['exhibition','other']::text[]);\n", encoding="utf-8"),
        "999_narrow_event_form.sql events_event_form_check: missing",
    ),
    "locale loses an eventForm label": (
        lambda r: edit_locale(r / "web/messages/zh.json", "eventForm", lambda d: d.pop("tour")),
        "web/messages/zh.json eventForm.*: missing ['tour']",
    ),
    "annotator VALID_CATEGORIES loses a value": (
        lambda r: replace_in(r / "scraper/annotator.py", '"design_craft", "herbal", "taiwan_mandarin"',
                             '"design_craft", "taiwan_mandarin"'),
        "scraper/annotator.py VALID_CATEGORIES: missing ['herbal']",
    ),
    "types.ts gains a category": (
        lambda r: replace_in(r / "web/lib/types.ts", '  "market",\n  "report",\n];',
                             '  "market",\n  "report",\n  "dance",\n];'),
        "web/messages/ja.json categories.*: missing ['dance']",
    ),
    "taxonomy.md loses a definition": (
        lambda r: replace_in(r / "scraper/taxonomy.md", '- "herbal" =', "- herbal ="),
        "scraper/taxonomy.md PROMPT block definitions: missing ['herbal']",
    ),
    "locale gains an undeclared category key": (
        lambda r: edit_locale(r / "web/messages/en.json", "categories", lambda d: d.update(bogus="Bogus")),
        "web/messages/en.json categories.*: extra ['bogus']",
    ),
    "categoryDesc gains a _long key for a non-category": (
        lambda r: edit_locale(r / "web/messages/ja.json", "categoryDesc", lambda d: d.update(bogus_long="x")),
        "web/messages/ja.json categoryDesc.*: extra ['bogus_long']",
    ),
    "route prompt goes back to a hand-written enum": (
        lambda r: replace_in(r / ACCOUNT_ROUTE, '${EVENT_FORMS.join(" | ")}', "exhibition | other"),
        f"{ACCOUNT_ROUTE}: prompt no longer builds the list with ${{EVENT_FORMS.join(",
    ),
}


@pytest.mark.parametrize("case", sorted(DRIFT_CASES))
def test_drift_is_reported_against_the_right_source(parity, capsys, repo, case):
    mutate, expected = DRIFT_CASES[case]
    mutate(repo)
    code, out = run(parity, capsys, repo)
    assert code == 1
    assert expected in out, out


def test_declared_extras_are_allowed(parity, capsys, repo):
    edit_locale(repo / "web/messages/en.json", "categories", lambda d: d.update(group_new="New group"))
    code, out = run(parity, capsys, repo)
    assert code == 0, out


def test_missing_reference_is_a_parse_error(parity, capsys, repo):
    replace_in(repo / "web/lib/types.ts", "export const EVENT_FORMS", "export const EVENT_SHAPES")
    code, out = run(parity, capsys, repo)
    assert code == 1
    assert "could not find `export const EVENT_FORMS" in out


def test_one_unparsable_source_does_not_hide_other_drift(parity, capsys, repo):
    (repo / "web/messages/en.json").write_text("{not json", encoding="utf-8")
    replace_in(repo / "scraper/database.py",
               '"conference", "networking", "screening_with_talk", "tour", "competition",',
               '"conference", "networking", "screening_with_talk", "competition",')
    code, out = run(parity, capsys, repo)
    assert code == 1
    assert "web/messages/en.json: invalid JSON" in out
    assert "_VALID_EVENT_FORMS: missing ['tour']" in out


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.hooksPath=/dev/null", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture
def git_repo(repo: Path) -> Path:
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    return repo


DRIFT_DB = ('"conference", "networking", "screening_with_talk", "tour", "competition",',
            '"conference", "networking", "screening_with_talk", "competition",')


def test_staged_drift_blocks(parity, capsys, git_repo):
    replace_in(git_repo / "scraper/database.py", *DRIFT_DB)
    git(git_repo, "add", "scraper/database.py")
    code, out = run(parity, capsys, git_repo, "--staged")
    assert code == 1
    assert "commit blocked" in out
    assert "_VALID_EVENT_FORMS: missing ['tour']" in out


def test_staged_mode_reads_the_index_not_the_working_tree(parity, capsys, git_repo):
    # Drift only in the working tree; the staged change is an unrelated watched-file edit.
    replace_in(git_repo / "scraper/database.py", *DRIFT_DB)
    (git_repo / "web/lib/types.ts").write_text(
        (git_repo / "web/lib/types.ts").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    git(git_repo, "add", "web/lib/types.ts")
    code, out = run(parity, capsys, git_repo, "--staged")
    assert code == 0, out


def test_staged_mode_skips_unwatched_changes(parity, capsys, git_repo):
    # A broken watched file is ignored when the commit does not touch any watched path.
    (git_repo / "web/messages/en.json").write_text("{not json", encoding="utf-8")
    git(git_repo, "add", "web/messages/en.json")
    git(git_repo, "commit", "-q", "-m", "break")
    (git_repo / "README.md").write_text("x", encoding="utf-8")
    git(git_repo, "add", "README.md")
    code, out = run(parity, capsys, git_repo, "--staged")
    assert code == 0
    assert out == ""

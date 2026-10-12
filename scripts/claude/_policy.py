"""Rule engine for the Claude Code PreToolUse guards.

Specification: docs/specs/active/ai-portability/plan.md §7 and the H-C1
decisions in notes.md §4.23. Pure functions over the hook's stdin payload.
This module never opens files: the masked-awk templates are constants, and
their drift against the instruction files is checked by the tests.

Run as a script with --validate-output to check a guard's stdout against the
only decision shape a guard may print (used by run_hook.sh).
"""
from __future__ import annotations

import fnmatch
import json
import re
import sys
from dataclasses import dataclass

from _tokenizer import Command, Unsupported, Word, parse

# Hook protocol, measured with Claude Code 2.1.296 (notes.md §4.21).
STDIN_TOOL_NAME = "tool_name"
STDIN_TOOL_INPUT = "tool_input"
INPUT_COMMAND = "command"
INPUT_FILE_PATH = "file_path"
INPUT_NOTEBOOK_PATH = "notebook_path"
INPUT_PATH = "path"
INPUT_GLOB = "glob"
HOOK_EVENT = "PreToolUse"
OUTPUT_ROOT = "hookSpecificOutput"
OUTPUT_KEYS = frozenset({"hookEventName", "permissionDecision", "permissionDecisionReason"})
# Guards deny by exiting 2; the only JSON decision they print is "ask".
OUTPUT_DECISIONS = frozenset({"ask"})

MESSAGE_PREFIX = "ttr-hook:"
INTERNAL_ERROR = "ttr-hook: internal error, blocked"
ASK_REASON = "ttr-hook: git push requires explicit user approval [push-gate]"

BASH_TOOLS = frozenset({"Bash", "Monitor"})
FILE_FIELDS = {
    "Read": ((INPUT_FILE_PATH, True),),
    "Grep": ((INPUT_PATH, False), (INPUT_GLOB, False)),
    "Write": ((INPUT_FILE_PATH, True),),
    "Edit": ((INPUT_FILE_PATH, True),),
    "NotebookEdit": ((INPUT_NOTEBOOK_PATH, True),),
}
WRITE_TOOLS = frozenset({"Write", "Edit", "NotebookEdit"})

RULES = {
    "git-force-push": (
        "force push, remote ref deletion, prune or mirror push rewrites remote history",
        "use plain `git push`, which asks for approval; the user runs force operations in a terminal",
    ),
    "git-reset-hard": (
        "git reset --hard discards uncommitted work",
        "commit first, or use `git reset --soft`/`--mixed`, or ask the user",
    ),
    "git-clean": (
        "git clean without --dry-run deletes untracked files",
        "preview with `git clean -n` and let the user delete",
    ),
    "git-branch-D": (
        "forced branch deletion can drop unmerged commits",
        "use `git branch -d`, which refuses unmerged branches",
    ),
    "worktree-remove-force": (
        "forced worktree removal discards uncommitted changes",
        "clean the worktree, then `git worktree remove` without --force",
    ),
    "worktree-add-force": (
        "forced worktree add bypasses Git's safety checks",
        "use `git worktree add` without -f/--force",
    ),
    "env-file-write": (
        "writing, deleting or redirecting into a .env file is not allowed",
        "the user edits .env files in a terminal",
    ),
    "env-file-access": (
        ".env files hold secrets and must not be read, searched or copied",
        "check presence with `git check-ignore -v <path>` or the masked awk template "
        "in .github/instructions/token-rotation.instructions.md",
    ),
    "env-dump": (
        "printing the environment can leak secrets",
        'test one variable with `[ -n "$VAR" ]` or `${#VAR}`',
    ),
    "prod-db-mutation": (
        "possible production database write",
        "hand the change to the user to run in a terminal",
    ),
    "unverifiable-sql-input": (
        "psql input that cannot be inspected (file, stdin, psqlrc or missing -c)",
        'use `psql -X -c "SELECT ..."`',
    ),
    "multi-statement": ("only one SQL statement is allowed", "run one SELECT per psql -c"),
    "psql-meta": (
        "psql backslash commands are not allowed",
        "query information_schema with SELECT",
    ),
    "non-readonly-keyword": (
        "only SELECT, SHOW and EXPLAIN without ANALYZE are allowed",
        "hand writes to the user",
    ),
    "write-keyword": (
        "the SQL contains a write, locking or CTE keyword",
        "hand writes to the user",
    ),
    "dynamic-shell": (
        "eval, stdin-fed shells and unverifiable shell -c scripts are not allowed",
        "run the command directly",
    ),
    "dynamic-verb": (
        "the command name comes from a substitution",
        "write the command name literally",
    ),
    "dynamic-args": (
        "command substitution in git/psql/supabase arguments",
        "compute the value in a separate command, then pass it literally",
    ),
    "unsupported-syntax": (
        "the command uses syntax the guard cannot verify",
        "split it into simpler commands",
    ),
}


@dataclass(frozen=True)
class Decision:
    kind: str  # "allow" | "ask" | "deny"
    rule: str = ""

    def message(self) -> str:
        if self.kind == "ask":
            return ASK_REASON
        reason, alternative = RULES[self.rule]
        return f"{MESSAGE_PREFIX} blocked [{self.rule}] {reason}. Safer: {alternative}"


ALLOW = Decision("allow")
ASK_PUSH = Decision("ask", "push-gate")


def deny(rule: str) -> Decision:
    if rule not in RULES:
        raise KeyError(rule)
    return Decision("deny", rule)


def combine(decisions) -> Decision:
    decisions = list(decisions)
    for kind in ("deny", "ask"):
        for decision in decisions:
            if decision.kind == kind:
                return decision
    return ALLOW


# --- output protocol -------------------------------------------------------

def ask_payload(reason: str = ASK_REASON) -> dict:
    return {
        OUTPUT_ROOT: {
            "hookEventName": HOOK_EVENT,
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }


def valid_output(text: str) -> bool:
    """True only for the exact decision JSON a guard may print."""
    try:
        data = json.loads(text)
    except ValueError:
        return False
    if not isinstance(data, dict) or set(data) != {OUTPUT_ROOT}:
        return False
    inner = data[OUTPUT_ROOT]
    if not isinstance(inner, dict) or set(inner) != OUTPUT_KEYS:
        return False
    reason = inner["permissionDecisionReason"]
    return (
        inner["hookEventName"] == HOOK_EVENT
        and inner["permissionDecision"] in OUTPUT_DECISIONS
        and isinstance(reason, str)
        and reason.startswith(MESSAGE_PREFIX)
    )


def emit(decision: Decision) -> int:
    """Write the decision for the launcher and return the guard's exit code."""
    if decision.kind == "deny":
        sys.stderr.write(decision.message() + "\n")
        return 2
    if decision.kind == "ask":
        sys.stdout.write(json.dumps(ask_payload(decision.message())))
    return 0


# --- entry points ----------------------------------------------------------

def _tool(payload: object) -> tuple[str, dict]:
    if not isinstance(payload, dict):
        raise ValueError("payload")
    tool, data = payload.get(STDIN_TOOL_NAME), payload.get(STDIN_TOOL_INPUT)
    if not isinstance(tool, str) or not isinstance(data, dict):
        raise ValueError("payload fields")
    return tool, data


def bash_decision(payload: object) -> Decision:
    tool, data = _tool(payload)
    if tool not in BASH_TOOLS:
        raise ValueError("tool")
    command = data.get(INPUT_COMMAND)
    if command is None and tool == "Monitor":
        return ALLOW  # a WebSocket monitor runs no shell command
    if not isinstance(command, str):
        raise ValueError("command")
    return evaluate_command(command)


def file_decision(payload: object) -> Decision:
    tool, data = _tool(payload)
    if tool not in FILE_FIELDS:
        raise ValueError("tool")
    rule = "env-file-write" if tool in WRITE_TOOLS else "env-file-access"
    for key, required in FILE_FIELDS[tool]:
        value = data.get(key)
        if value is None and not required:
            continue
        if not isinstance(value, str):
            raise ValueError(key)
        if is_sensitive(value, glob=key == INPUT_GLOB):
            return deny(rule)
    return ALLOW


# --- rule 7: sensitive paths -----------------------------------------------

SENSITIVE_RE = re.compile(r"\.env(\..+)?")
SAFE_ENV_FILES = frozenset({".env.example", ".env.sample", ".env.template"})
ENV_PROBES = (".env", ".env.local", ".env.production", ".env.development", ".env.test")
GLOB_CHARS = frozenset("*?[")
BRACE_RE = re.compile(r"\{([^{}]*)\}")


def _alternatives(pattern: str) -> list[str]:
    match = BRACE_RE.search(pattern)
    if not match:
        return [pattern]
    out = []
    for alt in match.group(1).split(","):
        out += _alternatives(pattern[:match.start()] + alt + pattern[match.end():])
    return out


def is_sensitive(text: str, glob: bool = False) -> bool:
    """True when the token or one of its =/: suffixes names a .env file or may glob one.

    Glob patterns follow bash's default (dotglob off): only a pattern whose
    basename starts with a literal dot can match a .env file.
    """
    glob = glob or any(ch in GLOB_CHARS for ch in text)
    for part in {text, text.rsplit("=", 1)[-1], text.rsplit(":", 1)[-1]}:
        base = part.rstrip("/").rsplit("/", 1)[-1]
        if SENSITIVE_RE.fullmatch(base) and base not in SAFE_ENV_FILES:
            return True
        if glob:
            for alt in _alternatives(base):
                if alt.startswith(".") and any(
                    fnmatch.fnmatchcase(probe, alt) for probe in ENV_PROBES
                ):
                    return True
    return False


# token-rotation.instructions.md L125/L196 and GITHUB_TOKEN_SYNC_CHECKLIST.md L41.
MASKED_AWK_PROGRAM = (
    "awk -F= '/^GITHUB_TOKEN=/{print \"GITHUB_TOKEN present, len=\"length($2)\", "
    "prefix_ok=\"(($2 ~ /^github_pat_/)?\"yes\":\"no\")}'"
)
MASKED_AWK_TEMPLATES = frozenset({MASKED_AWK_PROGRAM + " .env", MASKED_AWK_PROGRAM + " scraper/.env"})
WRITE_REDIRECTS = frozenset({">", ">>", ">|", "<>", "&>", "&>>", ">&"})
FD_RE = re.compile(r"\d+-?|-")
WRITE_VERBS = frozenset({"tee", "cp", "mv", "dd", "install", "touch", "rm", "truncate", "ln"})
TEST_OPS = frozenset({"-f", "-e", "-s", "-r"})


def _metadata_form(texts: list[str]) -> bool:
    """Rule 7 layer 2a: exact metadata commands on one path."""
    return (
        (len(texts) == 4 and texts[:3] in (
            ["git", "check-ignore", "-v"], ["git", "check-ignore", "--no-index"],
            ["git", "ls-files", "--error-unmatch"],
        ))
        or (len(texts) == 3 and texts[0] == "test" and texts[1] in TEST_OPS)
        or (len(texts) == 4 and texts[1] in TEST_OPS and (texts[0], texts[3]) in (("[", "]"), ("[[", "]]")))
        or (len(texts) == 2 and texts[0] == "stat")
        or (len(texts) == 3 and texts[:2] in (["ls", "-l"], ["wc", "-l"]))
    )


def check_env_file(cmd: Command, name: str, args: list[Word]) -> Decision:
    """Rule 7: layer 1 write deny, layer 2 exact exceptions, layer 3 access deny."""
    hit = False
    for redirect in cmd.redirects:
        op = redirect.op.lstrip("0123456789")
        target = redirect.target.text
        if redirect.heredoc or (op in (">&", "<&") and FD_RE.fullmatch(target)):
            continue
        if is_sensitive(target):
            if op in WRITE_REDIRECTS:
                return deny("env-file-write")
            hit = True
    hit = hit or any(is_sensitive(w.text) for w in cmd.words)
    if not hit:
        return ALLOW
    texts = [w.text for w in args]
    if (
        name in WRITE_VERBS
        or (name == "sed" and any(t.startswith(("-i", "--in-place")) for t in texts))
        or (name in ("awk", "gawk") and "inplace" in texts)
    ):
        return deny("env-file-write")
    if not cmd.redirects:
        if not any(_dynamic(w) for w in cmd.words) and _metadata_form([w.text for w in cmd.words]):
            return ALLOW
        if cmd.raw in MASKED_AWK_TEMPLATES and not (cmd.pipe_in or cmd.pipe_out or cmd.background):
            return ALLOW
    return deny("env-file-access")


# --- command walk and wrappers ---------------------------------------------

ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
# name: (options that take a separate argument, positional arguments before the command)
WRAPPERS = {
    "command": (frozenset(), 0),
    "builtin": (frozenset(), 0),
    "exec": (frozenset({"-a"}), 0),
    "time": (frozenset(), 0),
    "nohup": (frozenset(), 0),
    "nice": (frozenset({"-n"}), 0),
    "timeout": (frozenset({"-s", "-k"}), 1),
    "sudo": (frozenset({"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "-T", "-R"}), 0),
    "caffeinate": (frozenset({"-t", "-w"}), 0),
    "stdbuf": (frozenset({"-i", "-o", "-e"}), 0),
}
ENV_FLAGS = frozenset({"-i", "-", "--ignore-environment", "-0", "--null", "-v"})
ENV_OPT_ARG = frozenset({"-u", "--unset", "-C", "--chdir", "-P"})


def _dynamic(word: Word) -> bool:
    return word.vars or bool(word.subs)


def _only_sub(word: Word) -> bool:
    return len(word.subs) == 1 and word.literal == 0 and not word.vars


def _basename(text: str) -> str:
    return text.rsplit("/", 1)[-1]


def walk(commands: list[Command]):
    """Yield every simple command, including those nested in substitutions and heredocs."""
    for cmd in commands:
        yield cmd
        for word in cmd.words + [r.target for r in cmd.redirects]:
            for sub in word.subs:
                yield from walk(sub)
        for redirect in cmd.redirects:
            for sub in redirect.heredoc.subs if redirect.heredoc else ():
                yield from walk(sub)


def _skip_env(args: list[Word]) -> list[Word] | None:
    i = 0
    while i < len(args):
        text = args[i].text
        if text in ENV_FLAGS:
            i += 1
        elif text in ENV_OPT_ARG:
            i += 2
        elif text.startswith(("-S", "--split-string")):
            return None
        elif text.startswith(("-u", "--unset=", "--chdir=")):
            i += 1
        elif text == "--":
            i += 1
            break
        elif text.startswith("-"):
            raise Unsupported("env option")
        else:
            break
    while i < len(args) and ASSIGNMENT_RE.match(args[i].text):
        i += 1
    return args[i:]


def _skip_wrapper(name: str, args: list[Word]) -> list[Word] | None:
    with_arg, positional = WRAPPERS[name]
    i = 0
    while i < len(args) and args[i].text.startswith("-") and args[i].text != "-":
        if args[i].text == "--":
            i += 1
            break
        if name == "command" and args[i].text in ("-v", "-V"):
            return None
        i += 2 if args[i].text in with_arg else 1
    return args[i + positional:]


def unwrap(words: list[Word]) -> tuple[str, list[Word], Decision | None]:
    """Strip assignments and wrapper verbs; return (verb name, its arguments, early decision)."""
    i = 0
    while i < len(words) and ASSIGNMENT_RE.match(words[i].text):
        i += 1
    words = words[i:]
    while words:
        verb = words[0]
        if verb.subs:
            return "", [], deny("dynamic-verb")
        name = _basename(verb.text)
        if name == "env":
            rest = _skip_env(words[1:])
            if rest is None:
                return "", [], deny("dynamic-shell")
            if not rest:
                return "", [], deny("env-dump")
            words = rest
        elif name in WRAPPERS:
            rest = _skip_wrapper(name, words[1:])
            if not rest:
                return "", [], None
            words = rest
        else:
            return name, words[1:], None
    return "", [], None


def evaluate_command(command: str, depth: int = 0) -> Decision:
    try:
        return combine(check_command(cmd) for cmd in walk(parse(command, depth)))
    except Unsupported:
        return deny("unsupported-syntax")


def check_command(cmd: Command) -> Decision:
    name, args, early = unwrap(cmd.words)
    decisions = [check_env_file(cmd, name, args)]
    if early:
        decisions.append(early)
    elif name:
        decisions.append(dispatch(name, args, cmd))
    return combine(decisions)


def dispatch(name: str, args: list[Word], cmd: Command) -> Decision:
    if name == "git":
        return check_git(args)
    if name == "psql":
        return check_psql(args, cmd)
    if name == "supabase":
        return check_supabase(args)
    if PYTHON_RE.fullmatch(name):
        return check_python(args, cmd)
    if name in SHELLS:
        return check_shell(args, cmd)
    if name == "eval":
        return deny("dynamic-shell")
    return check_env_dump(name, args)


# --- rule 8 ----------------------------------------------------------------

def _short_flags(words: list[Word]) -> set[str]:
    chars: set[str] = set()
    for word in words:
        text = word.text
        if text.startswith("-") and not text.startswith("--") and len(text) > 1:
            chars.update(text[1:])
    return chars


def check_env_dump(name: str, args: list[Word]) -> Decision:
    if name == "printenv":
        return deny("env-dump")
    if name == "export" and all(w.text.startswith("-") for w in args):
        return deny("env-dump")
    if name in ("declare", "typeset"):
        names = [w for w in args if not w.text.startswith(("-", "+"))]
        if not names or "p" in _short_flags(args):
            return deny("env-dump")
    if name == "set" and not args:
        return deny("env-dump")
    return ALLOW


# --- guarded commands: dynamic arguments and the R3-1 commit exception ----

SAFE_INNER = (("git", "rev-parse"), ("git", "branch", "--show-current"), ("pwd",))
COMMIT_MESSAGE_FLAGS = frozenset({"-m", "--message", "-am"})  # -am is -a -m


def _safe_inner(sub: list[Command]) -> bool:
    if len(sub) != 1 or sub[0].redirects or any(_dynamic(w) for w in sub[0].words):
        return False
    texts = tuple(w.text for w in sub[0].words)
    return texts[:2] == SAFE_INNER[0] or texts in SAFE_INNER[1:]


def _commit_heredoc(args: list[Word]) -> bool:
    """R3-1: git commit -m "$(cat <<'EOF' ... EOF\n)" with nothing else dynamic."""
    with_subs = [i for i, w in enumerate(args) if w.subs]
    if len(with_subs) != 1 or with_subs[0] == 0:
        return False
    flag, value = args[with_subs[0] - 1], args[with_subs[0]]
    if flag.text not in COMMIT_MESSAGE_FLAGS or _dynamic(flag) or not _only_sub(value):
        return False
    inner = value.subs[0]
    if len(inner) != 1:
        return False
    cat = inner[0]
    return (
        [w.text for w in cat.words] == ["cat"]
        and not any(w.quoted or _dynamic(w) for w in cat.words)
        and len(cat.redirects) == 1
        and cat.redirects[0].op == "<<"
        and cat.redirects[0].heredoc is not None
        and cat.redirects[0].heredoc.quoted
        and not (cat.pipe_in or cat.pipe_out or cat.background)
    )


def _dynamic_args(args: list[Word]) -> Decision | None:
    if any(not _safe_inner(sub) for word in args for sub in word.subs):
        return deny("dynamic-args")
    return None


# --- rules 1-6: git --------------------------------------------------------

GIT_OPT_ARG = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env", "--super-prefix"})
GIT_FLAGS = frozenset({
    "--no-pager", "-P", "-p", "--paginate", "--bare", "--no-replace-objects", "--literal-pathspecs",
    "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs", "--no-optional-locks", "--no-advice",
})
GIT_INFO = frozenset({"--version", "--help", "-h", "--html-path", "--man-path", "--info-path"})
PUSH_OPT_ARG = frozenset({"-o", "--push-option", "--repo", "--receive-pack", "--exec"})
PUSH_DESTRUCTIVE = frozenset({"--force", "--force-if-includes", "--delete", "--mirror", "--prune"})


def check_git(args: list[Word]) -> Decision:
    i = 0
    while i < len(args):
        text = args[i].text
        if text in GIT_OPT_ARG:
            i += 2
        elif text.startswith("--") and text.split("=", 1)[0] in GIT_OPT_ARG:
            i += 1
        elif text in GIT_FLAGS:
            i += 1
        elif text in GIT_INFO:
            return _dynamic_args(args) or ALLOW
        elif text.startswith("-"):
            raise Unsupported("unknown git option")
        else:
            break
    sub = args[i].text if i < len(args) else ""
    rest = args[i + 1:]
    commit_ok = sub == "commit" and not any(w.subs for w in args[:i + 1]) and _commit_heredoc(rest)
    dynamic = None if commit_ok else _dynamic_args(args)
    if dynamic:
        return dynamic
    texts, flags = [w.text for w in rest], _short_flags(rest)
    if sub == "push":
        return check_push(rest)
    if sub == "reset" and "--hard" in texts:
        return deny("git-reset-hard")
    if sub == "clean" and not ("--dry-run" in texts or "n" in flags):
        return deny("git-clean")
    if sub == "branch" and ("D" in flags or (("--delete" in texts or "d" in flags) and ("--force" in texts or "f" in flags))):
        return deny("git-branch-D")
    if sub == "worktree" and rest:
        force = "--force" in texts or "f" in _short_flags(rest[1:])
        if force and rest[0].text == "remove":
            return deny("worktree-remove-force")
        if force and rest[0].text == "add":
            return deny("worktree-add-force")
    return ALLOW


def check_push(args: list[Word]) -> Decision:
    i, positional = 0, []
    while i < len(args):
        text = args[i].text
        if text in PUSH_OPT_ARG:
            i += 2
            continue
        if text in PUSH_DESTRUCTIVE or text.startswith("--force-with-lease"):
            return deny("git-force-push")
        if text.startswith("-") and not text.startswith("--") and len(text) > 1:
            group = text[1:].split("o", 1)[0]  # -o takes the rest as its value
            if "f" in group or "d" in group:
                return deny("git-force-push")
        elif not text.startswith("-"):
            positional.append(text)
        i += 1
    if any(ref.startswith(("+", ":")) for ref in positional):
        return deny("git-force-push")
    return ASK_PUSH


# --- rule 9: production database (heuristic) -------------------------------

PSQL_SHORT_ARG = frozenset("cdfFhLopPRTUv")
PSQL_LONG_ARG = frozenset({
    "--dbname", "--field-separator", "--host", "--log-file", "--output", "--port", "--pset",
    "--record-separator", "--table-attr", "--username", "--set", "--variable",
})
SQL_WRITE_RE = re.compile(
    r"\b(INTO|INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|COPY|CALL|DO"
    r"|VACUUM|REINDEX|CLUSTER|LOCK|SET|WITH|FOR)\b",
    re.IGNORECASE,
)
SUPABASE_OPT_ARG = frozenset({"--workdir", "--profile", "--network-id", "-o", "--output", "--dns-resolver"})
SUPABASE_DENY = frozenset({
    ("db", "push"), ("db", "reset"), ("db", "query"), ("db", "pull"),
    ("migration", "up"), ("migration", "down"), ("migration", "repair"), ("migration", "squash"),
})
SUPABASE_DB_WRITE_FLAGS = frozenset({"--from-backup", "--apply", "--reset"})
PYTHON_RE = re.compile(r"python(\d+(\.\d+)?)?")
PYTHON_OPT_ARG = frozenset({"-W", "-X"})
CLIENT_WRITE_METHODS = (".insert(", ".update(", ".upsert(", ".delete(")
SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh"})
SHELL_OPT_ARG = frozenset({"-o", "-O", "+o", "+O", "--rcfile", "--init-file"})


def check_sql(sql: str) -> Decision | None:
    text = sql.strip()
    if text.endswith(";"):
        text = text[:-1].rstrip()
    if ";" in text:
        return deny("multi-statement")
    if "\\" in text:
        return deny("psql-meta")
    match = re.match(r"[A-Za-z]+", text)
    first = match.group().upper() if match else ""
    if first not in ("SELECT", "SHOW", "EXPLAIN") or (
        first == "EXPLAIN" and re.search(r"\bANALY[SZ]E\b", text, re.IGNORECASE)
    ):
        return deny("non-readonly-keyword")
    if SQL_WRITE_RE.search(text):
        return deny("write-keyword")
    return None


def check_psql(args: list[Word], cmd: Command) -> Decision:
    dynamic = _dynamic_args(args)
    if dynamic:
        return dynamic
    no_rc, listing, sql, i = False, False, [], 0
    while i < len(args):
        word, text = args[i], args[i].text
        nxt = args[i + 1] if i + 1 < len(args) else None
        if text.startswith("--"):
            key, eq, value = text.partition("=")
            if key == "--no-psqlrc":
                no_rc = True
            elif key in ("--list", "--version", "--help"):
                listing = True
            elif key == "--file":
                return deny("unverifiable-sql-input")
            elif key == "--command":
                sql.append((value, _dynamic(word)) if eq else (nxt.text, _dynamic(nxt)) if nxt else None)
                i += 0 if eq else 1
            elif key in PSQL_LONG_ARG and not eq:
                i += 1
        elif text.startswith("-") and len(text) > 1:
            for j, ch in enumerate(text[1:], 1):
                if ch == "X":
                    no_rc = True
                elif ch in "lV?":
                    listing = True
                elif ch == "f":
                    return deny("unverifiable-sql-input")
                elif ch in PSQL_SHORT_ARG:
                    value = text[j + 1:]
                    if ch == "c":
                        sql.append((value, _dynamic(word)) if value else (nxt.text, _dynamic(nxt)) if nxt else None)
                    i += 0 if value else 1
                    break
        i += 1
    stdin_sql = cmd.pipe_in or any(r.op.lstrip("0123456789").startswith("<") for r in cmd.redirects)
    if stdin_sql or not no_rc or None in sql or not (sql or listing):
        return deny("unverifiable-sql-input")
    for text, dynamic_sql in sql:
        if dynamic_sql:
            return deny("unverifiable-sql-input")
        result = check_sql(text)
        if result:
            return result
    return ALLOW


def check_supabase(args: list[Word]) -> Decision:
    dynamic = _dynamic_args(args)
    if dynamic:
        return dynamic
    texts = [w.text for w in args]
    if texts == ["db", "push", "--dry-run"]:
        return ALLOW
    positional, i = [], 0
    while i < len(texts):
        if texts[i] in SUPABASE_OPT_ARG:
            i += 2
            continue
        if not texts[i].startswith("-"):
            positional.append(texts[i])
        i += 1
    if tuple(positional[:2]) in SUPABASE_DENY or positional[:1] == ["seed"]:
        return deny("prod-db-mutation")
    if positional[:1] == ["db"] and any(t.split("=", 1)[0] in SUPABASE_DB_WRITE_FLAGS for t in texts):
        return deny("prod-db-mutation")
    return ALLOW


def check_python(args: list[Word], cmd: Command) -> Decision:
    code, stdin_program, i = [], True, 0
    while i < len(args):
        text = args[i].text
        if text == "-c":
            code.append(args[i + 1].text if i + 1 < len(args) else "")
            stdin_program = False
            break
        if text.startswith("-c") and not text.startswith("--"):
            code.append(text[2:])
            stdin_program = False
            break
        if text == "-" or not text.startswith("-"):
            stdin_program = text == "-"
            break
        if text.startswith("-m"):
            stdin_program = False
            break
        i += 2 if text in PYTHON_OPT_ARG else 1
    if stdin_program:
        for redirect in cmd.redirects:
            if redirect.heredoc:
                code.append(redirect.heredoc.body)
            elif redirect.op == "<<<":
                code.append(redirect.target.text)
    for program in code:
        if "create_client" in program and any(m in program for m in CLIENT_WRITE_METHODS):
            return deny("prod-db-mutation")
    return ALLOW


# --- rule 10: dynamic shell ------------------------------------------------

def check_shell(args: list[Word], cmd: Command) -> Decision:
    i, command_mode = 0, False
    while i < len(args):
        text = args[i].text
        if text in SHELL_OPT_ARG:
            i += 2
            continue
        if text == "--":
            i += 1
            break
        if not (text.startswith(("-", "+")) and len(text) > 1):
            break
        if not text.startswith("--"):
            if "s" in text[1:]:
                return deny("dynamic-shell")
            command_mode = command_mode or "c" in text[1:]
            if text[-1] in "oO":  # -euo pipefail: the group ends with an option that takes a value
                i += 1
        i += 1
    if i >= len(args):
        return deny("dynamic-shell")  # no script: the shell reads commands from stdin
    if not command_mode:
        return ALLOW  # runs a script file
    script = args[i]
    if _dynamic(script):
        return deny("dynamic-shell")
    return evaluate_command(script.text, cmd.depth + 1)


if __name__ == "__main__":
    ok = sys.argv[1:] == ["--validate-output"] and valid_output(sys.stdin.read())
    sys.exit(0 if ok else 1)

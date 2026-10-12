"""Small shell tokenizer for the Claude Code PreToolUse guards.

This is not a shell interpreter. It splits a command string into simple
commands and recurses into groups, command substitutions, process
substitutions and unquoted heredoc bodies, so that the policy can inspect
every command that would run. Input outside the supported grammar raises
Unsupported; callers must treat that as a deny.

Budget: at most 250 lines excluding comments, docstrings and blank lines
(docs/specs/active/ai-portability/plan.md §7). Do not grow this into a full
interpreter; stop and report instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_DEPTH = 3
KEYWORDS = frozenset("if then elif else fi for while until do done case esac in select function ! { }".split())
OPERATORS = ("&&", "||", ";;", "|&", "|", ";", "&")
REDIRECT_RE = re.compile(r"&>>|&>|\d*(?:<<<|<<-|<<|<>|<&|>>|>&|>\||<|>)")
VARIABLE_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-])")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
META = " \t\n;&|()<>"


class Unsupported(Exception):
    """The input is outside the supported grammar; the caller must deny."""


@dataclass
class Word:
    text: str = ""      # value after quote removal; substitutions and variables contribute nothing
    quoted: bool = False
    vars: bool = False  # contains $NAME or ${...}
    glob: bool = False  # contains an unquoted * ? [
    literal: int = 0    # number of literal characters in text
    subs: list = field(default_factory=list)  # one parsed command list per substitution


@dataclass
class Heredoc:
    delim: str
    quoted: bool
    strip_tabs: bool
    body: str = ""
    subs: list = field(default_factory=list)


@dataclass
class Redirect:
    op: str
    target: Word
    heredoc: Heredoc | None = None


@dataclass
class Command:
    words: list = field(default_factory=list)
    redirects: list = field(default_factory=list)
    raw: str = ""
    pipe_in: bool = False
    pipe_out: bool = False
    background: bool = False
    start: int = -1
    end: int = -1
    depth: int = 0      # substitution/group nesting level the command was found at


def parse(src: str, depth: int = 0) -> list[Command]:
    """Split src into simple commands (groups flattened, substitutions nested in words)."""
    return _Lexer(src, depth).parse_list(None)


class _Lexer:
    def __init__(self, src: str, depth: int) -> None:
        if CONTROL_RE.search(src) or depth > MAX_DEPTH:
            raise Unsupported("control character or nesting too deep")
        self.s, self.i, self.depth, self.pending = src, 0, depth, []

    def parse_list(self, closer: str | None) -> list[Command]:
        cmds: list[Command] = []
        cur = Command()
        while True:
            self.skip_blanks()
            c = self.s[self.i] if self.i < len(self.s) else None
            if c is None and (closer or self.pending):
                raise Unsupported("unterminated input")
            if c is None or c == closer:
                self.i += 1
                return self.close(cur, cmds)
            if c == "\n":
                self.i += 1
                cur = self.close(cur, cmds, Command())
                self.read_heredocs()
            elif c == "#":
                end = self.s.find("\n", self.i)
                self.i = len(self.s) if end < 0 else end
            elif self.s.startswith(("<(", ">("), self.i):
                self.add_word(cur, closer)
            elif REDIRECT_RE.match(self.s, self.i):
                op = REDIRECT_RE.match(self.s, self.i).group()
                cur.start = self.i if cur.start < 0 else cur.start
                self.i += len(op)
                cur.redirects.append(self.redirect(op, closer))
                cur.end = self.i
            elif any(self.s.startswith(o, self.i) for o in OPERATORS):
                op = next(o for o in OPERATORS if self.s.startswith(o, self.i))
                self.i += len(op)
                cur.pipe_out, cur.background = op in ("|", "|&"), op == "&"
                cur = self.close(cur, cmds, Command(pipe_in=op in ("|", "|&")))
            elif c == "(":
                self.paren(cur, cmds)
            elif c == ")":
                raise Unsupported("unbalanced parenthesis")
            else:
                self.add_word(cur, closer)

    def paren(self, cur: Command, cmds: list[Command]) -> None:
        last = cur.words[-1] if cur.words else None
        if last and self.s.startswith("()", self.i):
            self.i += 2  # function definition: drop the name, check the body as commands
            cur.words, cur.start = [], -1
        elif last and last.text.endswith("=") and self.s[self.i - 1] == "=":
            self.i += 1  # array assignment: NAME=(a b c)
            while True:
                while self.i < len(self.s) and self.s[self.i] in " \t\n":
                    self.i += 1
                if self.i >= len(self.s):
                    raise Unsupported("unterminated array")
                if self.s[self.i] == ")":
                    self.i, cur.end = self.i + 1, self.i + 1
                    return
                start = self.i
                last.subs += self.word(")").subs
                if self.i == start:
                    raise Unsupported("unsupported array element")
        elif cur.words or cur.redirects:
            raise Unsupported("unexpected parenthesis")
        else:
            self.i += 1
            self.enter()
            cmds += self.parse_list(")")
            self.depth -= 1

    def add_word(self, cur: Command, closer: str | None) -> None:
        start = self.i
        word = self.word(closer)
        if self.i == start:
            raise Unsupported("empty word")
        if not cur.words and not cur.redirects and not word.quoted and word.text in KEYWORDS:
            return
        cur.start = start if cur.start < 0 else cur.start
        cur.words.append(word)
        cur.end = self.i

    def close(self, cur: Command, cmds: list[Command], nxt: Command | None = None):
        if cur.words or cur.redirects:
            cur.raw, cur.depth = self.s[cur.start:cur.end], self.depth
            cmds.append(cur)
        return cmds if nxt is None else nxt

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise Unsupported("nesting too deep")

    def skip_blanks(self) -> None:
        while self.s.startswith("\\\n", self.i) or self.s[self.i:self.i + 1] in (" ", "\t"):
            self.i += 2 if self.s[self.i] == "\\" else 1

    def redirect(self, op: str, closer: str | None) -> Redirect:
        self.skip_blanks()
        start = self.i
        target = self.word(closer)
        if self.i == start:
            raise Unsupported("missing redirect target")
        if op.lstrip("0123456789") not in ("<<", "<<-"):
            return Redirect(op, target)
        heredoc = Heredoc(target.text, target.quoted, op.endswith("-"))
        self.pending.append(heredoc)
        return Redirect(op, target, heredoc)

    def read_heredocs(self) -> None:
        for heredoc in self.pending:
            lines = []
            while True:
                if self.i >= len(self.s):
                    raise Unsupported("unterminated heredoc")
                end = self.s.find("\n", self.i)
                end = len(self.s) if end < 0 else end
                line, self.i = self.s[self.i:end], end + 1
                if (line.lstrip("\t") if heredoc.strip_tabs else line) == heredoc.delim:
                    break
                lines.append(line)
            heredoc.body = "\n".join(lines)
            if not heredoc.quoted:
                holder = Word()
                _Lexer(heredoc.body, self.depth).dquote(holder, None)
                heredoc.subs = holder.subs
        self.pending = []

    def word(self, closer: str | None) -> Word:
        w = Word()
        if self.s.startswith(("<(", ">("), self.i):
            self.i += 2
            self.nest(w, ")")
            return w
        while self.i < len(self.s):
            c = self.s[self.i]
            if c in META or (c == "`" and closer == "`"):
                break
            if c == "\\":
                nxt = self.s[self.i + 1:self.i + 2]
                self.i += 2
                if nxt != "\n":
                    self.lit(w, nxt)
                    w.quoted = True
            elif c == "'" or self.s.startswith("$'", self.i):
                self.single(w)
            elif c == '"':
                self.i += 1
                w.quoted = True
                self.dquote(w, '"')
            elif c in "$`":
                self.dollar(w)
            else:
                w.glob = w.glob or c in "*?["
                self.lit(w, c)
                self.i += 1
        return w

    def single(self, w: Word) -> None:
        skip = 2 if self.s[self.i] == "$" else 1  # $'...' keeps its escapes undecoded
        j = self.i + skip
        while j < len(self.s) and self.s[j] != "'":
            j += 2 if skip == 2 and self.s[j] == "\\" else 1
        if j >= len(self.s):
            raise Unsupported("unterminated quote")
        self.lit(w, self.s[self.i + skip:j])
        w.quoted, self.i = True, j + 1

    def dquote(self, w: Word, end: str | None) -> None:
        while self.i < len(self.s):
            c = self.s[self.i]
            if c == end:
                self.i += 1
                return
            if c == "\\" and self.i + 1 < len(self.s):
                nxt = self.s[self.i + 1]
                self.i += 2
                if nxt != "\n":
                    self.lit(w, nxt if nxt in '$`"\\' else "\\" + nxt)
            elif c in "$`":
                self.dollar(w)
            else:
                self.lit(w, c)
                self.i += 1
        if end is not None:
            raise Unsupported("unterminated quote")

    def dollar(self, w: Word) -> None:
        if self.s[self.i] == "`" or self.s.startswith("$(", self.i):
            self.i += 1 if self.s[self.i] == "`" else 2
            self.nest(w, "`" if self.s[self.i - 1] == "`" else ")")
        elif self.s.startswith("${", self.i):
            self.i += 2
            holder = Word()
            self.dquote(holder, "}")
            w.subs += holder.subs
            w.vars = True
        elif self.s.startswith('$"', self.i):
            self.i += 1
        elif VARIABLE_RE.match(self.s, self.i):
            self.i = VARIABLE_RE.match(self.s, self.i).end()
            w.vars = True
        else:
            self.lit(w, "$")
            self.i += 1

    def nest(self, w: Word, closer: str) -> None:
        self.enter()
        w.subs.append(self.parse_list(closer))
        self.depth -= 1

    @staticmethod
    def lit(w: Word, text: str) -> None:
        w.text += text
        w.literal += len(text)

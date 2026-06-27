"""Indirect prompt-injection scanner for untrusted scraped event content.

Security Hardening Plan v16 — Phase 0 / Phase 1 ("data is not instruction").

Scraped event titles/descriptions, fetched article bodies, and any other
untrusted text are scanned for known prompt-injection patterns BEFORE they are
sent to the LLM annotator. Findings are surfaced to the admin review queue
(``event_reports``); legitimate event data is NEVER dropped or mutated by this
module — detection only.

Design notes:
  * Detection is deterministic regex matching — no network, no LLM, no state.
  * Patterns are intentionally multi-word / specific so they do not fire on
    ordinary Japanese / Chinese / English event copy (low false-positive rate).
    Single generic words (e.g. "urgent", "環境", "限定") must never match alone.
  * Severity scale 1..3. The annotator persists only findings with severity
    >= 2; severity 1 is advisory (logged, not queued).
  * Escape hatch: set env ``SECURITY_SCAN_DISABLED=1`` to disable scanning
    entirely (fail-open) if the false-positive rate ever spikes in production.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

__all__ = [
    "InjectionHit",
    "scan_for_injection",
    "finding_fingerprint",
    "max_severity",
    "INSTRUCTION_OVERRIDE",
    "AI_DIRECTED",
    "FAKE_TOOL_OUTPUT",
    "CREDENTIAL_EXFIL",
    "SOCIAL_ENGINEERING",
    "PROMPT_EXTRACTION",
]

# Stable category identifiers — referenced in admin_notes and finding hashes.
INSTRUCTION_OVERRIDE = "INSTRUCTION_OVERRIDE"
AI_DIRECTED = "AI_DIRECTED"
FAKE_TOOL_OUTPUT = "FAKE_TOOL_OUTPUT"
CREDENTIAL_EXFIL = "CREDENTIAL_EXFIL"
SOCIAL_ENGINEERING = "SOCIAL_ENGINEERING"
PROMPT_EXTRACTION = "PROMPT_EXTRACTION"

_SNIPPET_MAX = 160


@dataclass(frozen=True)
class InjectionHit:
    """A single prompt-injection pattern match.

    Attributes
    ----------
    category : one of the module-level category constants.
    severity : 1 (advisory) .. 3 (high). Annotator queues severity >= 2.
    snippet  : whitespace-collapsed matched substring. Holds only the matched
               text (no surrounding context) so finding hashes stay stable
               across re-scans when the injection itself is unchanged.
    """

    category: str
    severity: int
    snippet: str


# Each rule: (category, severity, compiled regex). Ordered by category.
# Patterns demand several specific tokens before firing.
_RULES: list[tuple[str, int, re.Pattern[str]]] = [
    # ── INSTRUCTION_OVERRIDE (sev 3) ─────────────────────────────────────
    (INSTRUCTION_OVERRIDE, 3, re.compile(
        r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|preceding|earlier)\s+"
        r"(?:instruction|prompt|message|context|rule|direction)s?", re.I)),
    (INSTRUCTION_OVERRIDE, 3, re.compile(
        r"disregard\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|preceding|earlier|system)\s+"
        r"(?:instruction|prompt|message|rule)s?", re.I)),
    (INSTRUCTION_OVERRIDE, 3, re.compile(
        r"forget\s+(?:all\s+)?(?:of\s+)?(?:your|the|previous|prior|earlier)\s+"
        r"(?:instruction|prompt|rule|training|guideline)s?", re.I)),
    (INSTRUCTION_OVERRIDE, 3, re.compile(
        r"override\s+(?:your|the|all|previous)\s+(?:instruction|rule|setting)s?|"
        r"override\s+(?:the\s+)?system\s+prompt", re.I)),
    (INSTRUCTION_OVERRIDE, 3, re.compile(
        r"(?:これ|それ|以前|上記|前|先)(?:まで|述)?の(?:指示|命令|プロンプト|ルール|規則)を"
        r"(?:無視|忘れ|破棄|上書き)")),
    (INSTRUCTION_OVERRIDE, 3, re.compile(
        r"(?:忽略|無視|无视|忽視|忽视|忘記|忘记)(?:之前|以上|先前|上述|前面|目前)?"
        r"(?:的)?(?:所有)?(?:的)?(?:指示|指令|提示|規則|规则|命令|要求)")),
    # ── PROMPT_EXTRACTION (sev 2) ────────────────────────────────────────
    (PROMPT_EXTRACTION, 2, re.compile(
        r"(?:repeat|print|reveal|show|output|display|tell\s+me|give\s+me)\s+"
        r"(?:me\s+)?(?:your|the)\s+(?:system\s+|initial\s+|original\s+)?"
        r"(?:prompt|instructions?|system\s+message)", re.I)),
    (PROMPT_EXTRACTION, 2, re.compile(
        r"(?:repeat|print|output)\s+(?:everything|all\s+(?:the\s+)?(?:text|words?))\s+above", re.I)),
    (PROMPT_EXTRACTION, 2, re.compile(
        r"what\s+(?:is|are|were)\s+your\s+(?:system\s+|initial\s+)?"
        r"(?:prompt|instructions?)", re.I)),
    (PROMPT_EXTRACTION, 2, re.compile(
        r"(?:システムプロンプト|システムメッセージ|初期(?:指示|プロンプト))を"
        r"(?:表示|教え|出力|繰り返|見せ)")),
    (PROMPT_EXTRACTION, 2, re.compile(
        r"(?:顯示|显示|输出|輸出|重複|重复|告訴我|告诉我)(?:你的|您的)?"
        r"(?:系統提示|系统提示|系統指令|系统指令|系統訊息|系统消息)")),
    # ── FAKE_TOOL_OUTPUT (sev 2) ─────────────────────────────────────────
    (FAKE_TOOL_OUTPUT, 2, re.compile(r"<\|im_(?:start|end)\|>", re.I)),
    (FAKE_TOOL_OUTPUT, 2, re.compile(r"<\s*/?\s*(?:system|assistant|tool)\s*>", re.I)),
    (FAKE_TOOL_OUTPUT, 2, re.compile(r"\[(?:system|assistant|tool_output|function_call)\]", re.I)),
    (FAKE_TOOL_OUTPUT, 2, re.compile(r"\"role\"\s*:\s*\"(?:system|assistant|tool)\"", re.I)),
    (FAKE_TOOL_OUTPUT, 2, re.compile(
        r"^\s*(?:system|assistant)\s*:\s*(?:you|ignore|now|the\s+following|please)", re.I | re.M)),
    # ── CREDENTIAL_EXFIL ─────────────────────────────────────────────────
    (CREDENTIAL_EXFIL, 3, re.compile(
        r"(?:send|reveal|print|leak|email|e-mail|upload|post|expose|share|exfiltrate|return|forward)\b"
        r".{0,40}?\b(?:api[\s_-]?key|access[\s_-]?token|secret\s+key|password|credential|"
        r"private\s+key|github[\s_-]?token|openai[\s_-]?api[\s_-]?key|service[\s_-]?role[\s_-]?key)",
        re.I | re.S)),
    (CREDENTIAL_EXFIL, 2, re.compile(
        r"\b(?:OPENAI_API_KEY|SUPABASE_SERVICE_ROLE_KEY|SERVICE_ROLE_KEY|ANTHROPIC_API_KEY)\b")),
    # ── AI_DIRECTED (sev 2) ──────────────────────────────────────────────
    (AI_DIRECTED, 2, re.compile(
        r"you\s+are\s+(?:now\s+)?(?:an?\s+)?"
        r"(?:AI\s+(?:assistant|model|chatbot|language\s+model)|large\s+language\s+model|"
        r"language\s+model|chatbot|chatgpt|gpt[\s\-]?[0-9o]+)\b", re.I)),
    (AI_DIRECTED, 2, re.compile(
        r"(?:act\s+as|pretend\s+to\s+be|behave\s+as|roleplay\s+as|you\s+must\s+act\s+as)\s+"
        r"(?:an?\s+)?(?:AI|language\s+model|different\s+(?:assistant|model)|unfiltered)", re.I)),
    (AI_DIRECTED, 2, re.compile(
        r"(?:enable|enter|activate|switch\s+to)\s+(?:developer|dan|jailbreak|god|unrestricted)\s+mode", re.I)),
    (AI_DIRECTED, 2, re.compile(
        r"from\s+now\s+on\b.{0,20}\byou\s+(?:must|will|should)\s+"
        r"(?:ignore|obey|only|act\s+as|respond\s+only|comply)", re.I | re.S)),
    # ── SOCIAL_ENGINEERING (sev 2 / 1) ───────────────────────────────────
    (SOCIAL_ENGINEERING, 2, re.compile(
        r"(?:do\s+not|don'?t|never)\s+(?:tell|inform|notify|warn|alert|mention\s+(?:this\s+)?to)\s+"
        r"the\s+(?:user|human|admin|operator)", re.I)),
    (SOCIAL_ENGINEERING, 2, re.compile(
        r"without\s+(?:telling|informing|notifying|alerting)\s+the\s+(?:user|human|admin|operator)", re.I)),
    (SOCIAL_ENGINEERING, 2, re.compile(
        r"(?:ユーザー|利用者|管理者)に(?:は)?(?:言わ|伝え|知らせ|報告し|教え)ないで")),
    (SOCIAL_ENGINEERING, 1, re.compile(
        r"(?:I\s+am|this\s+is)\s+(?:your|the)\s+(?:administrator|developer|owner|system\s+administrator)", re.I)),
    (SOCIAL_ENGINEERING, 1, re.compile(
        r"you\s+(?:have\s+permission|are\s+(?:allowed|authorized|permitted))\s+to\s+"
        r"(?:ignore|bypass|skip|reveal|disclose)", re.I)),
]


def _collapse(text: str) -> str:
    """Collapse all runs of whitespace to single spaces and trim."""
    return re.sub(r"\s+", " ", text).strip()


def _disabled() -> bool:
    return os.environ.get("SECURITY_SCAN_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def scan_for_injection(text: str | None) -> list[InjectionHit]:
    """Scan untrusted ``text`` for prompt-injection patterns.

    Returns at most one :class:`InjectionHit` per (category, snippet) pair —
    deterministic and order-stable. Returns ``[]`` when scanning is disabled
    via ``SECURITY_SCAN_DISABLED`` or when ``text`` is empty.
    """
    if not text or _disabled():
        return []
    hits: list[InjectionHit] = []
    seen: set[tuple[str, str]] = set()
    for category, severity, pattern in _RULES:
        match = pattern.search(text)
        if not match:
            continue
        snippet = _collapse(match.group(0))[:_SNIPPET_MAX]
        key = (category, snippet.lower())
        if key in seen:
            continue
        seen.add(key)
        hits.append(InjectionHit(category=category, severity=severity, snippet=snippet))
    return hits


def max_severity(hits: list[InjectionHit]) -> int:
    """Highest severity among ``hits`` (0 when empty)."""
    return max((h.severity for h in hits), default=0)


def finding_fingerprint(hits: list[InjectionHit]) -> str:
    """Stable SHA-1 over the set of findings (category + normalized snippet).

    Lets the admin-review lifecycle recognise an *identical* re-scan and skip
    an already-resolved report, reopening only when the injection content
    actually changes. Independent of hit ordering.
    """
    parts = sorted(f"{h.category}|{h.snippet.lower()}" for h in hits)
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from pathlib import Path
from typing import Any


SEVERITIES = {"high", "medium", "low"}
ANOMALY_KINDS = {
    "shell",
    "git_churn",
    "prompt_injection",
    "fabricated_output",
    "tool_false_success",
}

SHELL_KW = re.compile(
    r"(zsh:|command not found|no matches found|exit code\s*[1-9]|\$PATH|PATH\s+.*blank|"
    r"shell integration|SyntaxError.*brace|Operation not permitted)",
    re.IGNORECASE,
)

INJECTION_KW = re.compile(
    r"(prompt[ -]?injection|jailbreak|ignore (all )?(previous|above)|system prompt|"
    r"untrusted content|惡意指令|提示注入|注入攻擊|忽略以上|忽略前文|系統提示)",
    re.IGNORECASE,
)

FABRICATION_KW = re.compile(
    r"(臆造|捏造|編造|fabricat|hallucinat|其實沒有執行|並未真的|不是真實輸出|"
    r"沒有真的執行|未實際執行|虛構輸出)",
    re.IGNORECASE,
)

CLAIM_KW = re.compile(
    r"(push\s*成功|已推送|推送成功|pushed|已部署|部署成功|deployed|deployment succeeded|"
    r"HTTP\s*200|status\s*200|已建立|建立成功|created)",
    re.IGNORECASE,
)

FALSE_SUCCESS_KW = re.compile(
    r"(false[- ]success|未寫入|沒生效|仍停在|獨立\s*view\s*證實|檔案未變|"
    r"回傳成功卻|doubled line number|false success|沒有套用|實際未變)",
    re.IGNORECASE,
)

_RESET_HARD_RE = re.compile(r"reset\s+--hard", re.IGNORECASE)
_RESET_CAUSE_RE = re.compile(
    r"(origin/main|revert|reverted|rollback|回退|還原|復原|WIP|stale|forked|分叉)",
    re.IGNORECASE,
)
_CONFLICT_RE = re.compile(r"(conflict|<<<<<<<|>>>>>>>|衝突)", re.IGNORECASE)
_STASH_DIRTY_RE = re.compile(
    r"(stash\s+pop|git\s+stash|stash@\{|踩踏|髒檔|dirty|MM|staged\s+WIP|uncommitted)",
    re.IGNORECASE,
)
_STASH_RE = re.compile(r"(git\s+stash|stash@\{|stash\s+(push|pop|show|drop|list)|\bstash\b)", re.IGNORECASE)

_TOKEN_RE = re.compile(r"(github_pat_)[A-Za-z0-9_]+|(sk-)[A-Za-z0-9_-]+|(Bearer\s+)[A-Za-z0-9._-]+")

Event = dict[str, Any]


@dataclass(frozen=True)
class Anomaly:
    session_id: str
    turn_index: int
    kind: str
    severity: str
    signal: str
    evidence: str
    tool_name: str | None
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolCall:
    tool_call_id: str | None
    tool_name: str | None
    arguments: Any
    success: bool | None
    turn_index: int
    start_event_index: int
    complete_event_index: int | None


def parse_events(path: str | Path) -> list[Event]:
    events: list[Event] = []
    with open(path, encoding="utf-8") as transcript:
        for line in transcript:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def detect_shell_anomalies(events: list[Event], session_id: str | None = None) -> list[Anomaly]:
    session_id = session_id or _session_id(events)
    anomalies: list[Anomaly] = []

    for tool in _tool_calls(events):
        if tool.tool_name == "run_in_terminal" and tool.success is False:
            anomalies.append(
                _anomaly(
                    session_id,
                    tool.turn_index,
                    "shell",
                    "high",
                    "run_in_terminal returned success=false",
                    _stringify(tool.arguments),
                    tool.tool_name,
                    {
                        "tool_call_id": tool.tool_call_id,
                        "success": tool.success,
                    },
                )
            )

    for event_index, ev in enumerate(events):
        if ev.get("type") != "assistant.message":
            continue
        text = _event_text(ev)
        match = SHELL_KW.search(text)
        if match:
            anomalies.append(
                _anomaly(
                    session_id,
                    _turn_index_at(events, event_index),
                    "shell",
                    "medium",
                    f"assistant mentioned shell failure: {match.group(0)}",
                    text,
                    None,
                    {"keyword": match.group(0)},
                )
            )

    return anomalies


def detect_git_churn(events: list[Event], session_id: str | None = None) -> list[Anomaly]:
    session_id = session_id or _session_id(events)
    anomalies: list[Anomaly] = []

    for turn_index, text, tools in _assistant_and_tool_text_by_turn(events):
        has_reset = _RESET_HARD_RE.search(text) is not None
        has_reset_cause = _RESET_CAUSE_RE.search(text) is not None
        has_conflict = _CONFLICT_RE.search(text) is not None
        has_stash_dirty = _STASH_DIRTY_RE.search(text) is not None
        has_stash = _STASH_RE.search(text) is not None

        if has_reset and has_reset_cause:
            anomalies.append(
                _anomaly(
                    session_id,
                    turn_index,
                    "git_churn",
                    "high",
                    "reset --hard combined with rollback/WIP signal",
                    text,
                    _first_tool_name(tools),
                    {"tools": _compact_tools(tools), "signals": ["reset --hard", "rollback_or_wip"]},
                )
            )
        elif has_conflict and has_stash_dirty:
            anomalies.append(
                _anomaly(
                    session_id,
                    turn_index,
                    "git_churn",
                    "high",
                    "conflict combined with stash/dirty-worktree signal",
                    text,
                    _first_tool_name(tools),
                    {"tools": _compact_tools(tools), "signals": ["conflict", "stash_or_dirty"]},
                )
            )
        elif has_stash or has_conflict:
            anomalies.append(
                _anomaly(
                    session_id,
                    turn_index,
                    "git_churn",
                    "low",
                    "single git stash/conflict signal",
                    text,
                    _first_tool_name(tools),
                    {"tools": _compact_tools(tools), "signals": ["stash_or_conflict"]},
                )
            )

    return anomalies


def detect_prompt_injection(events: list[Event], session_id: str | None = None) -> list[Anomaly]:
    session_id = session_id or _session_id(events)
    tools = _tool_calls(events)
    anomalies: list[Anomaly] = []

    for event_index, ev in enumerate(events):
        if ev.get("type") != "assistant.message":
            continue
        text = _event_text(ev)
        match = INJECTION_KW.search(text)
        if not match:
            continue

        previous_tools = _tools_before_event_in_turn(tools, event_index, _turn_index_at(events, event_index))
        if any(t.tool_name in {"fetch_webpage", "run_in_terminal"} for t in previous_tools):
            anomalies.append(
                _anomaly(
                    session_id,
                    _turn_index_at(events, event_index),
                    "prompt_injection",
                    "high",
                    f"assistant mentioned prompt injection after external content: {match.group(0)}",
                    text,
                    _first_tool_name(previous_tools),
                    {
                        "preceding_tools": _compact_tools(previous_tools[-8:]),
                        "keyword": match.group(0),
                    },
                )
            )

    return anomalies


def detect_fabricated_output(events: list[Event], session_id: str | None = None) -> list[Anomaly]:
    session_id = session_id or _session_id(events)
    tools = _tool_calls(events)
    anomalies: list[Anomaly] = []

    for event_index, ev in enumerate(events):
        if ev.get("type") != "assistant.message":
            continue
        text = _event_text(ev)
        turn_index = _turn_index_at(events, event_index)

        fabrication_match = FABRICATION_KW.search(text)
        if fabrication_match:
            anomalies.append(
                _anomaly(
                    session_id,
                    turn_index,
                    "fabricated_output",
                    "high",
                    f"assistant self-reported fabricated output: {fabrication_match.group(0)}",
                    text,
                    None,
                    {"keyword": fabrication_match.group(0)},
                )
            )

        claim = _claimed_action(text)
        if not claim:
            continue

        previous_tools = _tools_before_event_in_turn(tools, event_index, turn_index)
        if not _has_corresponding_success(claim, previous_tools):
            anomalies.append(
                _anomaly(
                    session_id,
                    turn_index,
                    "fabricated_output",
                    "medium",
                    f"claimed {claim} without corresponding success=true tool call",
                    text,
                    None,
                    {
                        "claimed_action": claim,
                        "preceding_tools": _compact_tools(previous_tools[-10:]),
                    },
                )
            )

    return anomalies


def detect_tool_false_success(events: list[Event], session_id: str | None = None) -> list[Anomaly]:
    session_id = session_id or _session_id(events)
    tools = _tool_calls(events)
    successful_tools = [tool for tool in tools if tool.success is True]
    anomalies: list[Anomaly] = []

    for event_index, ev in enumerate(events):
        if ev.get("type") != "assistant.message":
            continue
        text = _event_text(ev)
        match = FALSE_SUCCESS_KW.search(text)
        if not match:
            continue

        previous_tools = _tools_before_event(successful_tools, event_index)
        if not previous_tools:
            continue

        tool = _select_false_success_tool(previous_tools, text)
        anomalies.append(
            _anomaly(
                session_id,
                _turn_index_at(events, event_index),
                "tool_false_success",
                "high",
                f"success=true contradicted by later text: {match.group(0)}",
                text,
                tool.tool_name,
                {
                    "tool_name": tool.tool_name,
                    "tool_call_id": tool.tool_call_id,
                    "success": tool.success,
                    "contradiction": _clip(text),
                },
            )
        )

    return anomalies


def detect_all(events: list[Event], session_id: str | None = None) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    resolved_session_id = session_id or _session_id(events)
    anomalies.extend(detect_shell_anomalies(events, resolved_session_id))
    anomalies.extend(detect_git_churn(events, resolved_session_id))
    anomalies.extend(detect_prompt_injection(events, resolved_session_id))
    anomalies.extend(detect_fabricated_output(events, resolved_session_id))
    anomalies.extend(detect_tool_false_success(events, resolved_session_id))
    return sorted(anomalies, key=lambda a: (a.turn_index, _severity_rank(a.severity), a.kind, a.signal))


def _anomaly(
    session_id: str,
    turn_index: int,
    kind: str,
    severity: str,
    signal: str,
    evidence: str,
    tool_name: str | None,
    context: dict[str, Any],
) -> Anomaly:
    if kind not in ANOMALY_KINDS:
        raise ValueError(f"unknown anomaly kind: {kind}")
    if severity not in SEVERITIES:
        raise ValueError(f"unknown severity: {severity}")
    return Anomaly(
        session_id=session_id,
        turn_index=turn_index,
        kind=kind,
        severity=severity,
        signal=signal,
        evidence=_clip(evidence),
        tool_name=tool_name,
        context=context,
    )


def _tool_calls(events: list[Event]) -> list[ToolCall]:
    current_turn = 0
    starts: dict[str, dict[str, Any]] = {}
    calls: list[ToolCall] = []

    for event_index, ev in enumerate(events):
        event_type = ev.get("type")
        data = ev.get("data", {}) if isinstance(ev.get("data"), dict) else {}

        if event_type == "user.message":
            current_turn += 1
        elif event_type == "tool.execution_start":
            tool_call_id = data.get("toolCallId") or ev.get("toolCallId")
            record = {
                "tool_call_id": tool_call_id,
                "tool_name": data.get("toolName") or ev.get("toolName"),
                "arguments": data.get("arguments") if "arguments" in data else ev.get("arguments"),
                "turn_index": current_turn,
                "start_event_index": event_index,
            }
            if tool_call_id:
                starts[tool_call_id] = record
            else:
                calls.append(
                    ToolCall(
                        tool_call_id=None,
                        tool_name=record["tool_name"],
                        arguments=record["arguments"],
                        success=None,
                        turn_index=current_turn,
                        start_event_index=event_index,
                        complete_event_index=None,
                    )
                )
        elif event_type == "tool.execution_complete":
            tool_call_id = data.get("toolCallId") or ev.get("toolCallId")
            record = starts.pop(tool_call_id, None) if tool_call_id else None
            success = data.get("success") if "success" in data else ev.get("success")
            if record:
                calls.append(
                    ToolCall(
                        tool_call_id=record["tool_call_id"],
                        tool_name=record["tool_name"],
                        arguments=record["arguments"],
                        success=success,
                        turn_index=record["turn_index"],
                        start_event_index=record["start_event_index"],
                        complete_event_index=event_index,
                    )
                )
            else:
                calls.append(
                    ToolCall(
                        tool_call_id=tool_call_id,
                        tool_name=data.get("toolName") or ev.get("toolName"),
                        arguments=data.get("arguments") if "arguments" in data else ev.get("arguments"),
                        success=success,
                        turn_index=current_turn,
                        start_event_index=event_index,
                        complete_event_index=event_index,
                    )
                )

    for record in starts.values():
        calls.append(
            ToolCall(
                tool_call_id=record["tool_call_id"],
                tool_name=record["tool_name"],
                arguments=record["arguments"],
                success=None,
                turn_index=record["turn_index"],
                start_event_index=record["start_event_index"],
                complete_event_index=None,
            )
        )

    return sorted(calls, key=lambda call: call.start_event_index)


def _assistant_and_tool_text_by_turn(events: list[Event]) -> list[tuple[int, str, list[ToolCall]]]:
    texts: dict[int, list[str]] = {}
    tools_by_turn: dict[int, list[ToolCall]] = {}
    current_turn = 0

    for ev in events:
        event_type = ev.get("type")
        if event_type == "user.message":
            current_turn += 1
        elif event_type == "assistant.message":
            text = _event_text(ev)
            if text:
                texts.setdefault(current_turn, []).append(text)

    for tool in _tool_calls(events):
        tools_by_turn.setdefault(tool.turn_index, []).append(tool)
        if tool.tool_name == "run_in_terminal":
            texts.setdefault(tool.turn_index, []).append(_stringify(tool.arguments))

    return [
        (turn_index, "\n".join(parts), tools_by_turn.get(turn_index, []))
        for turn_index, parts in sorted(texts.items())
        if "\n".join(parts).strip()
    ]


def _event_text(ev: Event) -> str:
    data = ev.get("data", {}) if isinstance(ev.get("data"), dict) else {}
    pieces = [data.get("content"), data.get("reasoningText"), ev.get("content"), ev.get("reasoningText")]
    return "\n".join(_stringify(piece) for piece in pieces if piece)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _sanitize(value)
    try:
        return _sanitize(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except TypeError:
        return _sanitize(str(value))


def _sanitize(text: str) -> str:
    return _TOKEN_RE.sub(lambda m: (m.group(1) or m.group(2) or m.group(3)) + "<redacted>", text)


def _clip(text: str, limit: int = 200) -> str:
    compact = re.sub(r"\s+", " ", _sanitize(text)).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _turn_index_at(events: list[Event], target_event_index: int) -> int:
    turn_index = 0
    for event_index, ev in enumerate(events):
        if event_index > target_event_index:
            break
        if ev.get("type") == "user.message":
            turn_index += 1
    return turn_index


def _tools_before_event(tools: list[ToolCall], event_index: int) -> list[ToolCall]:
    return [tool for tool in tools if tool.start_event_index < event_index]


def _tools_before_event_in_turn(tools: list[ToolCall], event_index: int, turn_index: int) -> list[ToolCall]:
    return [tool for tool in tools if tool.turn_index == turn_index and tool.start_event_index < event_index]


def _first_tool_name(tools: list[ToolCall]) -> str | None:
    for tool in tools:
        if tool.tool_name:
            return tool.tool_name
    return None


def _compact_tools(tools: list[ToolCall]) -> list[dict[str, Any]]:
    return [
        {
            "tool_name": tool.tool_name,
            "success": tool.success,
            "turn_index": tool.turn_index,
        }
        for tool in tools
    ]


def _claimed_action(text: str) -> str | None:
    if not CLAIM_KW.search(text):
        return None
    lower = text.lower()
    if re.search(r"push\s*成功|已推送|推送成功|pushed", text, re.IGNORECASE):
        return "git_push"
    if re.search(r"已部署|部署成功|deployed|deployment succeeded", text, re.IGNORECASE):
        return "deploy"
    if re.search(r"HTTP\s*200|status\s*200", text, re.IGNORECASE):
        return "http_200"
    if "已建立" in text or "建立成功" in text or "created" in lower:
        return "create"
    return "success_claim"


def _has_corresponding_success(claim: str, tools: list[ToolCall]) -> bool:
    successful_tools = [tool for tool in tools if tool.success is True]
    if claim == "git_push":
        return any(tool.tool_name == "run_in_terminal" and "git push" in _stringify(tool.arguments) for tool in successful_tools)
    if claim == "deploy":
        return any(
            tool.tool_name == "run_in_terminal"
            and re.search(r"(vercel|deploy|deployment)", _stringify(tool.arguments), re.IGNORECASE)
            for tool in successful_tools
        )
    if claim == "http_200":
        return any(tool.tool_name in {"fetch_webpage", "open_browser_page", "read_page"} for tool in successful_tools) or any(
            tool.tool_name == "run_in_terminal" and re.search(r"(curl|wget|http)", _stringify(tool.arguments), re.IGNORECASE)
            for tool in successful_tools
        )
    if claim == "create":
        return any(tool.tool_name in {"create_file", "create_directory", "apply_patch"} for tool in successful_tools) or any(
            tool.tool_name == "run_in_terminal" and re.search(r"(mkdir|touch|cat\s+>|tee\s+)", _stringify(tool.arguments), re.IGNORECASE)
            for tool in successful_tools
        )
    return bool(successful_tools)


def _select_false_success_tool(tools: list[ToolCall], text: str) -> ToolCall:
    if re.search(r"\bmemory\b", text, re.IGNORECASE):
        for tool in reversed(tools):
            if tool.tool_name == "memory":
                return tool
    return tools[-1]


def _session_id(events: list[Event]) -> str:
    for ev in events:
        data = ev.get("data", {}) if isinstance(ev.get("data"), dict) else {}
        for value in (data.get("sessionId"), ev.get("sessionId"), ev.get("session_id")):
            if value:
                return str(value)
    return "unknown"


def _severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)

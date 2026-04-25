#!/usr/bin/env python3
"""
VS Code Copilot Chat 對話效率分析工具

解析本機 transcript JSONL，輸出每個 session 的：
- 對話時間與回合數
- 工具呼叫次數與分類
- 平均每回合工具數

用法：
    python analyze.py                    # 分析所有 session（最近 30 天）
    python analyze.py --days 7           # 最近 7 天
    python analyze.py --session <sid>    # 指定 session ID
    python analyze.py --top 5            # 只顯示最長的 5 個 session
    python analyze.py --json             # 輸出 JSON（供其他工具使用）
"""

import argparse
import collections
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ── 路徑探索 ─────────────────────────────────────────────────────────────────

def find_transcript_files(days: int | None = None) -> list[Path]:
    """在所有 VS Code workspaceStorage 中找 transcript JSONL 檔案。"""
    base = Path.home() / "Library/Application Support/Code/User/workspaceStorage"
    pattern = str(base / "*/GitHub.copilot-chat/transcripts/*.jsonl")
    files = [Path(p) for p in glob.glob(pattern)]

    if days is not None:
        cutoff = datetime.now().timestamp() - days * 86400
        files = [f for f in files if f.stat().st_mtime >= cutoff]

    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


# ── 解析單一 session ───────────────────────────────────────────────────────────

def parse_session(path: Path) -> dict:
    session_id = path.stem
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not events:
        return None

    # 基本計數
    user_turns = 0
    assistant_turns = 0
    tool_starts = 0
    tool_counts: dict[str, int] = collections.Counter()
    timestamps = []
    start_time_str = None
    copilot_version = None

    for ev in events:
        t = ev.get("type", "")
        ts = ev.get("timestamp")
        if ts:
            try:
                timestamps.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except ValueError:
                pass

        if t == "session.start":
            data = ev.get("data", {})
            start_time_str = data.get("startTime")
            copilot_version = data.get("copilotVersion")

        elif t == "user.message":
            user_turns += 1

        elif t == "assistant.turn_start":
            assistant_turns += 1

        elif t == "tool.execution_start":
            tool_starts += 1
            tool_name = ev.get("data", {}).get("toolName", "unknown")
            tool_counts[tool_name] += 1

    # 時間計算
    if timestamps:
        first_ts = min(timestamps)
        last_ts = max(timestamps)
        duration_minutes = (last_ts - first_ts).total_seconds() / 60
    elif start_time_str:
        try:
            first_ts = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except ValueError:
            first_ts = None
        duration_minutes = 0
    else:
        first_ts = None
        duration_minutes = 0

    avg_tools_per_turn = round(tool_starts / user_turns, 1) if user_turns > 0 else 0

    return {
        "session_id": session_id,
        "file": str(path),
        "start_time": first_ts.isoformat() if first_ts else None,
        "duration_minutes": round(duration_minutes, 1),
        "user_turns": user_turns,
        "assistant_turns": assistant_turns,
        "tool_calls": tool_starts,
        "avg_tools_per_turn": avg_tools_per_turn,
        "top_tools": dict(tool_counts.most_common(8)),
        "copilot_version": copilot_version,
    }


# ── 格式化輸出 ─────────────────────────────────────────────────────────────────

def fmt_duration(minutes: float) -> str:
    if minutes < 1:
        return "< 1 min"
    if minutes < 60:
        return f"{int(minutes)} min"
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h}h {m}m"


def fmt_time(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        jst = dt.astimezone(timezone(timedelta(hours=9)))
        return jst.strftime("%m/%d %H:%M")
    except Exception:
        return iso[:16]


def print_session(s: dict, verbose: bool = False) -> None:
    sid_short = s["session_id"][:8]
    start = fmt_time(s["start_time"])
    dur = fmt_duration(s["duration_minutes"])
    user = s["user_turns"]
    tools = s["tool_calls"]
    avg = s["avg_tools_per_turn"]

    print(f"  [{sid_short}]  {start}  {dur:>8}  {user:>3} 回合  {tools:>4} 工具呼叫  avg {avg}/回合")

    if verbose and s["top_tools"]:
        for name, cnt in s["top_tools"].items():
            print(f"    {'':8}  {name:<40} {cnt:>4}")


def print_aggregate(sessions: list[dict]) -> None:
    total_turns = sum(s["user_turns"] for s in sessions)
    total_tools = sum(s["tool_calls"] for s in sessions)
    total_minutes = sum(s["duration_minutes"] for s in sessions)

    all_tools: dict[str, int] = collections.Counter()
    for s in sessions:
        for k, v in s["top_tools"].items():
            all_tools[k] += v

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("📊 彙總統計")
    print(f"  Sessions  : {len(sessions)}")
    print(f"  總工作時間 : {fmt_duration(total_minutes)}")
    print(f"  總回合數   : {total_turns}")
    print(f"  總工具呼叫 : {total_tools}")
    if total_turns > 0:
        print(f"  平均工具/回合: {total_tools / total_turns:.1f}")
    print()
    print("  🔧 工具使用排行（所有 sessions 合計）")
    for name, cnt in all_tools.most_common(10):
        bar = "█" * min(30, cnt // max(1, total_tools // 30))
        print(f"    {name:<40} {cnt:>5}  {bar}")


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="VS Code Copilot Chat 對話效率分析")
    parser.add_argument("--days", type=int, default=30, help="分析最近 N 天（預設 30）")
    parser.add_argument("--session", type=str, help="指定 session ID（前綴即可）")
    parser.add_argument("--top", type=int, help="只顯示最多回合的 N 個 sessions")
    parser.add_argument("--verbose", "-v", action="store_true", help="顯示每個 session 的工具明細")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 格式")
    args = parser.parse_args()

    files = find_transcript_files(days=args.days)
    if not files:
        print("找不到任何 transcript 檔案。")
        print("請確認 VS Code 已安裝 GitHub Copilot Chat 擴充套件。")
        sys.exit(1)

    # 篩選指定 session
    if args.session:
        files = [f for f in files if f.stem.startswith(args.session)]
        if not files:
            print(f"找不到 session ID 以 '{args.session}' 開頭的記錄。")
            sys.exit(1)

    sessions = []
    for f in files:
        s = parse_session(f)
        if s and s["user_turns"] > 0:
            sessions.append(s)

    if not sessions:
        print("沒有找到含有使用者訊息的 sessions。")
        sys.exit(0)

    # 排序：依 user_turns 降冪
    sessions.sort(key=lambda s: s["user_turns"], reverse=True)

    if args.top:
        sessions = sessions[:args.top]

    # JSON 輸出
    if args.json:
        print(json.dumps(sessions, ensure_ascii=False, indent=2))
        return

    # 人類可讀輸出
    print(f"\n🗂  VS Code Copilot Chat 對話效率分析（最近 {args.days} 天）")
    print(f"   共找到 {len(sessions)} 個有效 sessions\n")
    print(f"  {'Session':^8}  {'開始時間':^11}  {'時長':>8}  {'回合':>5}  {'工具':>7}  {'平均'}")
    print("  " + "─" * 65)

    for s in sessions:
        print_session(s, verbose=args.verbose)

    if len(sessions) > 1:
        print_aggregate(sessions)

    # 效率建議
    all_avg = (
        sum(s["tool_calls"] for s in sessions) /
        sum(s["user_turns"] for s in sessions)
        if sum(s["user_turns"] for s in sessions) > 0 else 0
    )
    print()
    if all_avg > 12:
        print("💡 每回合工具呼叫偏高（>12）— 可嘗試把多個小需求合併為一條指令")
    elif all_avg < 3:
        print("💡 每回合工具呼叫偏低（<3）— 可以給 AI 更複雜的任務，提升效率")
    else:
        print("✅ 工具使用密度在合理範圍（3–12 次/回合）")


if __name__ == "__main__":
    main()

---
name: cc-statusline
description: 在 Claude Code 終端即時監控 token 用量、費用、quota 與 subagent 狀態
ms.date: 2026-04-25
user-invocable: false
---

# cc-statusline

在 Claude Code 的終端 statusline 即時顯示 token 用量、費用、quota 百分比與 subagent 狀態。

## Overview

cc-statusline 是一個 Claude Code plugin，透過 statusLine 機制在終端底部顯示即時使用資訊：

- 目前 session 的 token 輸入/輸出
- 累積費用（USD）
- API quota 剩餘百分比
- 作用中的 subagent 數量
- memory MCP 狀態
- 已編輯的檔案數

## Prerequisites

- Claude Code CLI 已安裝（`claude` 指令可用）
- `claude plugin` 子指令可用（Claude Code ≥ 0.2.0）
- Node.js ≥ 18

## Installation

### Option A：透過 Plugin Marketplace 安裝（推薦）

```bash
claude plugin marketplace add NYCU-Chung/cc-statusline
claude plugin install cc-statusline@cc-statusline
```

安裝完成後重啟 Claude Code 終端使 statusline 生效。

### Option B：手動 git clone（若 Option A 不可用）

若 `claude plugin marketplace` 指令不存在，改用：

```bash
# 確認 plugin 目錄位置
claude plugin list --show-root

# clone 到 plugin 目錄（路徑依環境調整）
git clone https://github.com/NYCU-Chung/cc-statusline \
  ~/.claude/plugins/cc-statusline

# 手動安裝
claude plugin install ~/.claude/plugins/cc-statusline
```

## Recommended Row Configuration（for Tokyo Taiwan Radar）

隱藏 `dir`、`repo`、`model` 減少雜訊，只保留關鍵使用資訊：

```
/cc-statusline:rows only summary cost usage quota agents memory_mcp edited
```

執行此指令後，statusline 將顯示：
- `summary`：session 摘要
- `cost`：累積費用
- `usage`：token 用量
- `quota`：quota 百分比
- `agents`：作用中 subagent
- `memory_mcp`：memory MCP 狀態
- `edited`：已編輯檔案數

## ~/.claude/settings.json 設定範例

安裝後，若需手動調整 refresh interval，在 `~/.claude/settings.json` 加入：

```json
{
  "statusLine": {
    "type": "command",
    "command": "node ${CLAUDE_PLUGIN_ROOT}/statusline.js",
    "refreshInterval": 30
  }
}
```

`refreshInterval` 單位為秒，建議設 30 以避免頻繁刷新佔用 CPU。

## Troubleshooting

| 問題 | 解法 |
|------|------|
| `claude plugin marketplace` 指令不存在 | 使用 Option B 手動安裝 |
| statusline 不顯示 | 確認已重啟 Claude Code；確認 `claude plugin list` 有 cc-statusline |
| `CLAUDE_PLUGIN_ROOT` 未定義 | 改用絕對路徑：`"command": "node ~/.claude/plugins/cc-statusline/statusline.js"` |
| token 數字不更新 | 確認 `refreshInterval` 已設定；若為 0 則停用 |
| quota 顯示 N/A | 部分 API 方案不提供 quota API；此為預期行為 |

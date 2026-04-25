---
name: session-analytics
description: 解析 VS Code Copilot Chat transcript，量化每個 session 的工具呼叫效率，並依三個反模式診斷高工具數回合
ms.date: 2025-05-04
---

# Session Analytics Skill

本 Skill 提供 `analyze.py` 腳本的使用說明，以及從實際 session 復盤中歸納的三個**提示效率反模式**。每次發現新模式時，應追加到下方「反模式目錄」。

---

## 快速開始

```bash
# 分析最近 30 天所有 session
python3 .github/skills/session-analytics/analyze.py --days 30

# 深入分析單一 session（須提供 session ID 前綴）
python3 .github/skills/session-analytics/analyze.py --session <session-id-prefix> --verbose

# 輸出 JSON 格式供後續處理
python3 .github/skills/session-analytics/analyze.py --days 7 --json
```

Transcript 位置：
`~/Library/Application Support/Code/User/workspaceStorage/6ff2cb1100e61f123c7d4efbbe510f8c/GitHub.copilot-chat/transcripts/`

---

## 效率閾值

| 平均工具數/回合 | 判定 |
|---|---|
| > 12 | 🔴 高 — 應檢視提示模式 |
| 3–12 | 🟢 良好 |
| < 3 | 🟡 低 — 可能過度簡化或 context 不足 |

---

## 反模式目錄

以下三個反模式來自 session `61b5118d` 的復盤分析（2025-05-04）。
該 session 共 54 回合、945 次工具呼叫，平均 **17.5 次/回合**（正常值應低於 12）。

---

### 反模式 1：「URL + 隱含大範圍」

**症狀：** 貼入一個 URL，附加「請檢查類似狀況」「順便處理其他的」——Agent 隨即對整個 codebase 做全面掃描。

**典型回合（T04, 61 tools；T12, 68 tools）：**  
> 「有一個地方好像不太對，請確認一下」  
→ Agent 讀取所有 sources/*.py，逐一驗證，工具數 × 3 倍爆增。

**正確寫法：**
```
僅修這個 event（id=xxx），確認完成後告訴我。
規則更新我稍後統一批次整理。
```

**預期節省：** 約 −30 工具數/受影響回合。

---

### 反模式 2：「請繼續做 XXX」連發

**症狀：** 同類型任務分多輪分別要求（例：建爬蟲 A → 建爬蟲 B → 建爬蟲 C），每輪重新載入相同 context，造成重複 overhead。

**典型序列（session 61b5118d，T08–T14）：**
> T08：「請建 peatix 爬蟲」  
> T10：「請繼續做 doorkeeper」  
> T12：「請繼續做 connpass」  
> …（共 7 輪）

**正確寫法：**
```
請依序建立以下三個爬蟲：peatix、doorkeeper、connpass。
每完成一個，列出已完成項目後繼續，不需要等待我的確認。
```

**預期節省：** 約 −150 總工具數（context reloading × 7 輪）。

---

### 反模式 3：「問題 + 修正 + 規則更新」三合一

**症狀：** 每次發現一個小錯誤，立即要求修正 **並同時** 更新 history.md 與 SKILL.md，觸發三連串寫檔操作。

**典型序列（T21→T22, 71 tools；T16, 51 tools）：**
> 「這裡有個 bug，修一下，然後更新 history 跟 skill」  
→ fix + read history + append history + read skill + patch skill = 5 次 I/O × N 個問題。

**正確寫法：**
```
先只修 bug；稍後我會說「現在批次更新 skill」，
你再一次性整理今天所有發現的規則。
```

**預期節省：** 約 −40 總工具數（累積 3–5 個問題再批次更新 > 逐一更新）。

---

## 使用時機

- 每週 `/weekly-review` 後，若 Agent 回報某 session 平均 > 12 工具數/回合，執行 `--session <id> --verbose` 找出高峰回合
- 發現新反模式後，追加到本檔案「反模式目錄」下方
- 每月 `/monthly-experiment` 前，跑 `--days 30` 確認效率趨勢

---

## 輸出範例（--verbose）

```
Session: 61b5118d  Duration: 142 min  Turns: 54
Tools: 945  Avg/turn: 17.5  [HIGH]

Top tools:
  run_in_terminal      286
  read_file            204
  manage_todo_list     103
  fetch_webpage         90
  replace_string_in_file 80

Turn breakdown:
  🔴 T22  71 tools  [fetch_webpage×45]  「請繼續做研究」
  🔴 T12  68 tools  [run_in_terminal×23, read_file×16]
  🔴 T04  61 tools  [run_in_terminal×28]
  ...
```

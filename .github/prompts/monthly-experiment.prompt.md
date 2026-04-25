---
description: 每月架構審查：評估工具選擇、AI 模型效益，執行 A/B 實驗。
argument-hint: "experiment_topic=要測試的工具或假設，例如：Playwright headless 是否可被 API 取代"
agent: Architect
---

# Monthly Experiment Review

## Step 1：掃描 Agents 與 Skills 現況

讀取 `.github/agents/` 下所有 `.agent.md` 與 `.github/skills/` 下所有 `SKILL.md`，建立清單：

| 項目 | 類型 | 用途摘要 | ms.date |
|------|------|---------|---------|
| ... | Agent/Skill | ... | YYYY-MM-DD |

使用 `list_dir` 和 `read_file` 工具取得實際資料。

---

## Step 2：找出 Scope Overlap 與長期未更新項目

- **Scope Overlap**：找出 description 中有語義重疊的 agent pair，輸出：
  「⚠ 建議釐清邊界：`Agent A` vs `Agent B` — 兩者都提到 XXX」

- **長期未更新**：找出 `ms.date` 距今 > 60 天的 Skills 或 Agents，輸出：
  「⏰ 超過 60 天未更新：XXX（最後更新 YYYY-MM-DD）」

---

## Step 3：設計 A/B 實驗

根據 `${input:experiment_topic:Playwright headless 是否可被 Chrome API 取代}` 設計小型實驗：

### 實驗設計模板

```
實驗假設：[一句話描述假設]

A 組（現況）：[目前的做法]
B 組（實驗）：[要測試的替代做法]

測試方法：
1. [步驟 1]
2. [步驟 2]
3. python main.py --dry-run --source <name>  ← 必須使用 dry-run，不寫入 DB

成功標準：
- 功能：[衡量指標，例如事件數不減少]
- 效能：[衡量指標，例如執行時間縮短 X%]
- 費用：[衡量指標，例如 API 費用降低]

預計工時：[小時]
```

---

## Step 4：輸出結論與工具白名單更新建議

```
## 月報結論 — {{年月}}

### 架構評估
[2-3 句評估整體架構健康狀況]

### 實驗結論
[A/B 實驗的建議：採用 B 組 / 維持 A 組 / 需更多測試]

### 工具白名單更新建議
新增：[工具名稱] — [理由]
移除：[工具名稱] — [理由]
維持現狀：[其他工具]

### 下月架構重點（最多 3 項）
1. ...
2. ...
3. ...
```

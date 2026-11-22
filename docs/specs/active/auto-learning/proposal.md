---
slug: auto-learning
title: Auto-learning：PR 教訓段、週審學習訊號與每週 learner
description: 退役三個人工觸發的學習元件；教訓改寫在 PR body；週審 digest 增加學習訊號；learner 每週歸納並提案，先只寫報告
status: active
branch: feat/auto-learning
created: 2026-11-22
tags: [tooling, governance, ai, harness]
---

## What（做什麼）

把學習迴路從「人工觸發、只會追加」改成「隨 PR 產生、每週歸納、有關卡才擴大」。第一階段（本 spec 的範圍）只有三件事：

1. 退役 `update-history-skill-agent`、`history-teller`、`/daily-skills-review` 與 `daily-review-reminder.yml`；教訓改寫在每張 PR body 的「教訓」段（規則在 `AGENTS.md` § 教訓）。
2. 週審 digest（`scripts/ci/weekly_digest.py`）新增「學習訊號」區，由既有的 `collect()` 延伸，唯讀計算。
3. 新增 `learner` agent：排程雲端 agent，每週四夜執行，**只寫報告**（一張 issue、最多 3 張提案卡片），不開 PR、不改檔。

第二階段（教訓帳本、learner 開 PR、規則編號與 SKILL 瘦身）不在本 spec 的里程碑內：learner 報告跑完兩輪、使用者裁決 go 之後才規劃。

## Why（為什麼）

- 學習只會追加：agent history 共 1,194 筆條目；`scraper-expert`、`architect`、`engineer` 三份 SKILL.md 各 178–235 KB；規則沒有編號、量測或退場。
- 偵測沒有轉換：`docs/skill_scan/` 的 hookable 候選 125（2026-05）→ 196（2026-10），already_hooked 2 → 3。
- 2026-10-25 改成 PR 自主流程後，heartbeat 不經過 V-M-D，agent 層級的 history 與 SKILL 幾乎沒有新增（2026-11 的 history.md commit 5 個、SKILL.md 1 個，同月 Claude 的 commit 173 個）。教訓落在 spec notes 與審查留言，沒有元件讀取。
- 使用者一週一個早上審核；已合併且有 tier label 的 PR 中 tier 2 佔 160／169。學習產出必須少，而且不能再增加 tier 2 的量。

## Non-Goals（不做什麼）

- 不回填既有 history；不刪 `history.md`（保留為紀錄，不再要求讀或追加）。
- 不分析 session 紀錄；不把 session 內容寫進 repo（repo 是公開的）。
- 第一階段不建教訓帳本、不新增任何會寫入 repo 的 workflow、不新增 `contents: write` 權限。
- 第一階段 learner 不開 PR、不改任何檔案、不貼 `auto-fix`／`needs-human` 以外流程用的 label。
- learner 不改自己的提示詞與排程、不改 `scripts/ci/pr_tier.py`、`scripts/ci/lane2_approval.py`、`scripts/ci/weekly_digest.py`。
- 不處理產品資料的學習（使用者報錯、corrections、金標）。資料品質類的重複問題只在報告列為「金標候選」。
- 規則編號、SKILL 瘦身、CODE 類 guard 轉測試：第二階段，另行裁決。

## Design（設計摘要）

### 教訓段

格式與規則見 `AGENTS.md` § 教訓。「實測／推論」由寫 PR 的 agent 自己標，無法驗證，所以 learner 只把它當線索；能當依據的是連結得到的證據（PR、commit、bot 留言、CI 執行）。

### 學習訊號（延伸 `weekly_digest.py`，不新增 workflow）

`collect()` 已經取得過去 7 天合併的 PR 與 open 的 `needs-human`。新增計算：

| 訊號 | 算法 |
| --- | --- |
| 教訓段缺漏 | 合併的 PR 中 body 沒有 `## 教訓` 的張數 |
| 教訓清單 | 合併的 PR 的教訓段原文（每張最多 3 行，超過截斷；當資料輸出在 code block 內） |
| 關閉未合併 | 過去 7 天 closed 且 `merged_at` 為空的 PR 數與編號 |
| 合併後修正 | 過去 7 天合併的 PR 中，有後續合併的 PR 以 `fix` 開頭且改到同一檔案的對數 |
| needs-human 存量 | open 數（已有），加上與上週 digest 的差 |

只讀 GitHub，不寫檔；輸出在 digest issue 的新一節。digest issue 由 `github-actions[bot]` 開，learner 以作者為 bot 當信任條件。因為訊號不落在 repo 檔案裡，learner 與 heartbeat 都改不到它（`docs/**` 是 tier 0 自動合併，若把訊號或指標存成 `docs/` 下的檔案，agent 可以改寫自己的成績）。

### learner（report-only）

- 來源檔 `.github/agents/learner.agent.md`，tier `build`；排程提示詞的權威副本在 `learner-prompt.md`。
- 每週四 22:00 JST。讀最近 5 張 digest issue（作者必須是 `github-actions[bot]`）與其中列出的合併 PR。
- 歸群條件：同一失敗型態、至少 2 個可連結的證據。取前 3，各寫一張卡片：問題與證據、建議落點、預期哪個訊號會變、觀察窗、撤回條件。
- 落點階梯：測試／CI 檢查／hook／constraint → workflow 或腳本 → 來源 skill → agent SKILL 或 agent 檔。同一問題出現第 2 次，建議必須落在前兩階，或寫明為何做不到。
- 產出一張 issue（label `learning`、`spec:auto-learning`），週審 digest 的學習區會列出。使用者以 👍／👎 回應每張卡片。
- 沒有達到歸群條件的週，報告只寫「本週無提案」。

### 關卡

learner 跑完兩輪後盤點。go 的條件：6 張卡片中使用者 👍 不少於 4 張，且至少 1 張被實作。no-go：停用排程；教訓段與學習訊號保留。

## 使用者裁決（2026-11-22）

| # | 項目 | 裁決 |
| --- | --- | --- |
| 1 | slug `auto-learning`、agent 名 `learner` | 採用 |
| 2 | `update-history-skill-agent`、`history-teller`、`/daily-skills-review` | 退役（使用者明示） |
| 3 | PR body 必填「教訓」段 | 採用 |
| 4 | 既有 history 不回填 | 採用；依 plan-critique-1 改為「保留原處、不再讀」，不搬 archive |
| 5 | session 紀錄分析 | 不做 |
| 6 | 每週提案上限 3 個 | 採用；SKILL 預算 40 KB 移到第二階段 |
| 7 | 資料品質類教訓不進 SKILL | 採用；第一階段只在報告列為金標候選 |

Plan Critic 評審見 [plan-critique-1.md](./plan-critique-1.md)（Claude 代評，同一模型家族）。評審後的範圍縮減（11 張 PR 縮為 3 張、帳本與瘦身延到第二階段）尚待使用者確認。

## References

- `docs/specs/active/agent-autonomy/`（heartbeat、週審 digest、人類關卡）
- `docs/specs/active/pr-flow-tiering/`（tier 定義）
- `docs/evaluation/guards/README.md`、`docs/skill_scan/`
- claude.ai Project 文件 `claude/auto-learning-agent-plan.md`（診斷）、`claude/auto-learning-dev-plan.md`（評審前的完整計畫）

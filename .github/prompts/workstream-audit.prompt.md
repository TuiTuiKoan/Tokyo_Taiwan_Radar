---
description: "重新查證全專案工作線盤點：讀取 workstream-tracking spec，比對 live 狀態並更新差異"
agent: Architect
---

# Workstream Audit

本 prompt 的單一任務是**重新查證**全專案工作線盤點，並把差異寫回權威 spec。

盤點內容本身**不在本檔**。權威位置是：

* `docs/specs/active/workstream-tracking/proposal.md` — 三維度模型與設計理由
* `docs/specs/active/workstream-tracking/tasks.md` — 五條工作線現況、三方對照表、
  治理缺口、操作教訓

開始前先完整讀過這兩份，不要依賴先前對話或 session memory。

## 授權邊界

啟動本 prompt 即授權：唯讀 git 查詢、唯讀 Supabase 查詢、讀取 spec 與 prompt 檔案、
更新 `docs/specs/active/workstream-tracking/` 內的兩份檔案、更新 session memory。

**不授權**：程式實作、commit、push、deploy、建立或刪除 worktree/branch、
移動或刪除其他 spec、production DB write、workflow dispatch。任何變更都需先取得明確批准。

## 最高原則：snapshot 不是真值

`tasks.md` 內所有計數、SHA、ahead/behind、dirty 數都是觀測快照。本 repo 經常有
3 個以上 session 平行寫入，數字會在數小時內失效。

不得沿用舊數字做判斷。發現與 snapshot 不符時，以 live 結果為準並就地更新 spec。

## 執行步驟

1. 讀取 `proposal.md` 與 `tasks.md`。
2. 執行 `tasks.md` 的 Phase 0 查證指令。
3. 回報與 snapshot 的差異，並更新 `tasks.md` 的 Snapshot 基準、三方對照表與各線勾選狀態。
4. 若 worktree 或 spec 有增減，同步更新 `proposal.md` 的統計。
5. 針對治理缺口（G1–G4）各給明確建議與所需批准。
6. 就「未納入編號的工作線」建議是否納入 A–E 或另立編號。

## 已知陷阱

`tasks.md` 的「操作教訓」段落記錄了本 repo 實測過的 shell 陷阱與 git 手法，
執行查證指令前先讀該段，避免重複踩坑。特別注意 worktree 路徑含空白、
zsh 字串比較、`grep -c` 的 exit code，以及不論有無輸出都會印的無效驗證寫法。

## 期望產出

一份差異報告加上就地更新後的 spec。不執行任何變更；所有動作留待明確批准。

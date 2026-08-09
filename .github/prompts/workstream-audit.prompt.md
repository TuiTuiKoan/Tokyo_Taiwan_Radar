---
description: "重新查證全專案工作線、完整 worktree 註冊路徑與 spec 對照，並更新 live 差異"
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

`tasks.md` 內所有計數、SHA、ahead/behind、dirty 數與註冊路徑都是觀測快照。本 repo
經常有 3 個以上 session 平行寫入，數字會在數小時內失效。

不得沿用舊數字做判斷。發現與 snapshot 不符時，以 live 結果為準並就地更新 spec。

Worktree 身分必須以 `git worktree list --porcelain` 的完整 registered path + branch
判斷，並另取 `pwd -P` physical path 做 containment 分類。不得先縮成 basename；
basename 只能用於表格顯示，不能支撐「位於 project root 內」或「路徑一致」的結論。

## 執行步驟

1. 讀取 `proposal.md` 與 `tasks.md`。
2. 執行 `tasks.md` 的 Phase 0 查證指令，保留每個 worktree 的 registered path、
  physical path、path class、branch、ahead/behind 與 dirty。
3. 回報與 snapshot 的差異，並更新 `tasks.md` 的 Snapshot 基準、路徑拓撲、
  三方對照表與各線勾選狀態。
4. 若 worktree、註冊路徑拓撲或 spec 有增減，同步更新 `proposal.md` 的統計與路徑證據。
5. 針對治理缺口（G1–G5）各給明確建議與所需批准。
6. 就「未納入編號的工作線」建議是否納入 A–E 或另立編號。

## 已知陷阱

`tasks.md` 的「操作教訓」段落記錄了本 repo 實測過的 shell 陷阱與 git 手法，
執行查證指令前先讀該段，避免重複踩坑。特別注意 worktree 路徑含空白、
`Development`／`development` lexical registration 分裂、project root 外的 worktree、
zsh 字串比較、`grep -c` 的 exit code，以及不論有無輸出都會印的無效驗證寫法。

目前已知的 2026-08-08 topology fixture 是 1 main + 5 canonical child +
3 case-split registration + 1 external。這只是辨識查證器是否退化的 fixture，不是永久
真值；live 結果改變時更新 fixture，不可為了維持舊計數而忽略新增或 relocated worktree。

## 期望產出

一份差異報告加上就地更新後的 spec。報告必須包含完整路徑拓撲差異，不只 basename
清單。不執行任何 worktree 變更；所有 move、repair、remove/re-add 或外部路徑搬遷
留待明確批准。

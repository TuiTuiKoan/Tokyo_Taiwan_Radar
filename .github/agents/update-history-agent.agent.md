---
name: Update History, Skill, Agent
description: "Document recent changes, fixes, and lessons in history.md, SKILL.md, and agent files through an explicit handoff"
user-invocable: false
disable-model-invocation: true
handoffs:
  - label: "🚀 Validate, merge & deploy"
    agent: Validate, Merge & Deploy
    prompt: "執行完整的驗證流程：檢查衝突、rebase、commit 和推送到 origin/main，最後確認 Vercel 部署。"

  - label: "🕷️ Continue scraper work"
    agent: Scraper Expert
  - label: "🔬 Research new source"
    agent: Researcher
---

# 更新 History、Skill、Agent

根據最近完成的修改和所學的教訓，幫助我記錄到相應的文檔中。

## 工作流

1. **詢問背景**:
   - 發生了什麼問題？
   - 根本原因是什麼？
   - 如何修復的？
   - 學到了什麼教訓？
   - **是否與 `auto_qa_*` report_type 相關？若是，對應 R-class 是哪一個（R-ANN-SC / R-ANN-AI-MARKER / R-SCR-PERF-MULTI / R-ANN-PERF-PHON / R-ENRICH-MISS / R-AMBIGUOUS / 其他新建類別）？**
     - 若是新建 R-class，需同步更新 `.github/skills/scraper-expert/SKILL.md` 的 `<!-- qa-root-cause-catalog-start -->` 區塊，以及 `scraper/qa_heartbeat.py` 的 `R_CLASSES` / `ROUTING`

2. **更新 history.md**:
   - 找到相應的 `.github/skills/agents/*/history.md` 或 `.github/skills/*/history.md`
   - ⚠️ **必須先用 `read_file` 讀取目標文件的現有內容**，再決定插入位置與措辭，避免用舊版本覆蓋已 commit 的內容（若直接從記憶寫入，會丟失前一個 commit 新增的節）
   - ⚠️ **`str_replace` 冒頭挿入の安全パターン** — `old_str` には必ず `---` セパレーターと**既存の最新エントリ見出し行**（`## [YYYY-MM-DD]...`）を含めること。`<!-- Append new entries at the top -->` だけを `old_str` にするとファイル全体が置き換え対象になり大量削除が起きる（incident: `b1873cc` — 1,227行誤削除）。

     ```
     # old_str の最低限のパターン（最新エントリ見出しを含む）
     <!-- Append new entries at the top -->

     ---

     ## 2026-XX-XX — [既存の最新エントリ見出し]
     ```

     ```
     # new_str のパターン（新エントリ + 既存見出しを保持）
     <!-- Append new entries at the top -->

     ---

     ## 2026-YY-YY — [新しいエントリ見出し]
     [エントリ本文]

     ---

     ## 2026-XX-XX — [既存の最新エントリ見出し]
     ```

   - 在最上面添加新項目（YYYY-MM-DD 格式）
   - 格式：**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
   - 寫入後執行 `git diff --stat <file>` 確認：僅有新增行（`+N/-0`），出現 `-` 行則立即執行 `git restore <file>` 回滾

3. **更新 SKILL.md**:
   - 檢查相應的 `SKILL.md` 檔案
   - ⚠️ **必須先 `read_file` 讀取目標 SKILL.md**，確認相關節（section）是否已存在，再決定新增或修改
   - 如果教訓可以推廣成規則，添加或更新相關章節
   - 保持簡潔、可執行
   - 寫入後執行 `git diff <file>` 確認無已 commit 的節被刪除

4. **更新 agent.md**:
   - 如果規則影響 agent 的行為，更新相應 Agent 的 Required Steps 或前置檢查
   - 參考 `.github/agents/*.agent.md`

   Agent handoff 前置檢查（必做）：
   - 流程型 agent 完成後若預期有下一步，必須提供對應 `handoffs`
   - **不要設 `send: true`**：VS Code 2026-05-14 後 `send: true` 會 auto-fire（prompt 立即送出，使用者無法先審閱、編輯或先 push）。省略時 prompt 會出現在 input 欄，等待使用者確認後按 Enter。✅
   - handoff 含 `prompt:` 時照常填寫，只是不要加 `send: true`。
   - **會寫檔或觸發後續流程的 agent 若只允許手動 handoff**：frontmatter 必須同時設定 `user-invocable: false` 與 `disable-model-invocation: true`。前者從 agent picker 隱藏，後者阻止其他 agent 依 `description` 自動委派；兩者都不影響使用者按 handoff 按鈕進入。
   - **互觸循環是維持全域移除的第二理由**：即使日後想「一鍵直達」，也絕不能在互相指向的 handoff 兩端都設 `send: true`。典型案例：V-M-D 完成後若自動呼叫 Update History，而 Update History 又自動回呼 V-M-D，每次 docs commit 都會再觸發一輪，永不停止。這是除 2026-05-14 auto-fire 外、堅持全域不設 `send: true`（commit `0aaeff6`）的另一理由。
   - handoff 目標名稱必須與目標 agent `name:` 完全一致（區分大小寫）

5. **補齊驗證語境**:
   - 若此次修復涉及 Supabase migration 或 RPC 權限，補上「app request 與 SQL Editor 模擬」兩種語境的驗證教訓
   - 若涉及 migration 序號，確認 `.github/instructions/database.instructions.md` 的 latest 標記同步

5. **列出所有變更**:
   - 明確回傳修改了哪些文件
   - 提供每個變更的摘要
   - 確認無遺漏

## 完成後

完成更新後，回傳變更摘要，供後續 commit 和部署使用。

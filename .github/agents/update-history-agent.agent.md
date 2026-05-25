---
name: Update History, Skill, Agent
description: "Document recent changes, fixes, and lessons in history.md, SKILL.md, and agent files — call after fixing bugs or implementing features"
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
   - 在最上面添加新項目（YYYY-MM-DD 格式）
   - 格式：**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**
   - 寫入後執行 `git diff <file>` 確認：僅有新增行（`+`），無已 commit 的行被刪除（`-`）

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
   - 若 handoff 含 `prompt:` 且要一鍵執行，必須同時設 `send: true`
   - handoff 目標名稱必須與目標 agent `name:` 完全一致（區分大小寫）
   - **⚠️ 互觸循環警示**：若 A → B 設有 `send: true`，則 B → A 的 handoff **絕對不可**再設 `send: true`，否則形成無限自動觸發迴圈。典型案例：V-M-D 完成後 `send: true` 自動呼叫 Update History；若 Update History 也 `send: true` 回呼 V-M-D，每次 docs commit 都會再觸發一輪，永不停止。

5. **補齊驗證語境**:
   - 若此次修復涉及 Supabase migration 或 RPC 權限，補上「app request 與 SQL Editor 模擬」兩種語境的驗證教訓
   - 若涉及 migration 序號，確認 `.github/instructions/database.instructions.md` 的 latest 標記同步

5. **列出所有變更**:
   - 明確回傳修改了哪些文件
   - 提供每個變更的摘要
   - 確認無遺漏

## 完成後

完成更新後，回傳變更摘要，供後續 commit 和部署使用。

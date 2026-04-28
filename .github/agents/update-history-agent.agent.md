---
name: Update History, Skill, Agent
description: "Document recent changes, fixes, and lessons in history.md, SKILL.md, and agent files — call after fixing bugs or implementing features"
user-invocable: false
disable-model-invocation: false
---

# 更新 History、Skill、Agent

根據最近完成的修改和所學的教訓，幫助我記錄到相應的文檔中。

## 工作流

1. **詢問背景**: 
   - 發生了什麼問題？
   - 根本原因是什麼？
   - 如何修復的？
   - 學到了什麼教訓？

2. **更新 history.md**:
   - 找到相應的 `.github/skills/agents/*/history.md` 或 `.github/skills/*/history.md`
   - 在最上面添加新項目（YYYY-MM-DD 格式）
   - 格式：**日期 | 問題簡述 | 根本原因 | 修復方法 | 學到的教訓**

3. **更新 SKILL.md**:
   - 檢查相應的 `SKILL.md` 檔案
   - 如果教訓可以推廣成規則，添加或更新相關章節
   - 保持簡潔、可執行

4. **更新 agent.md**:
   - 如果規則影響 agent 的行為，更新相應 Agent 的 Required Steps 或前置檢查
   - 參考 `.github/agents/*.agent.md`

5. **補齊驗證語境**:
   - 若此次修復涉及 Supabase migration 或 RPC 權限，補上「app request 與 SQL Editor 模擬」兩種語境的驗證教訓
   - 若涉及 migration 序號，確認 `.github/instructions/database.instructions.md` 的 latest 標記同步

5. **列出所有變更**:
   - 明確回傳修改了哪些文件
   - 提供每個變更的摘要
   - 確認無遺漏

## 完成後

完成更新後，回傳變更摘要，供後續 commit 和部署使用。

# Tasks

本 spec 是**戰略決策文件**，無傳統實作任務。下列為「決策確認」與「定期檢核」清單。

## Phase A：定位假設書面化

- [x] 撰寫三層火箭定位指南針（本 proposal）
- [x] 列出三條候選路線的 TAM/競爭/變現/戰略角色客觀評估
- [ ] 創辦人 review 並確認或修正「中層為 6 個月主力變現引擎」的判斷
- [ ] 將「決策準則」加到 `.github/agents/architect.agent.md` 的 Phase 1 必讀清單

## Phase B：每季戰略檢核（Recurring）

每季首日由 Architect agent 執行：

- [ ] 重新評估三層火箭的進度與健康度
- [ ] 檢視是否有新增 spec 違反「決策準則」（路線錯位）
- [ ] 校準 TAM / 競合假設是否需要更新
- [ ] 更新 `notes.md` 記錄本季的觀察與調整

## Phase C：第一份試樣報告 A 的學習回饋

- [ ] 以 2026-Q1 sample report（手工版本）寄送給 ≥3 個潛在客戶
- [ ] 收集回饋：價格敏感度、欄位優先級、報告深度
- [ ] 將回饋更新到本 proposal 的「決策準則」與「Non-Goals」
- [ ] 決定是否啟動 Product B（顧問業務）pilot

## Verification

- [ ] 本文件被 `.github/agents/architect.agent.md` 列為必讀
- [ ] 本文件出現在 `/admin/specs` 看板（需 `pnpm --filter web build` 重新生成 snapshot）
- [ ] 後續所有新 spec 在 `## References` 引用本文件

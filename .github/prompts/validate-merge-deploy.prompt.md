---
name: Validate, Merge & Deploy
description: "Full cycle: check conflicts, rebase, commit with atomic message, push to origin/main, and verify Vercel deployment — call after implementation is complete"
---

# 檢查衝突、合併、Commit 與部署

執行完整的驗證和部署流程，確保變更安全地推送到生產環境。

## 工作流

### Step 1: 檢查 Git 狀態
1. 檢查是否有未解決的 merge/rebase 衝突
2. 檢查是否有 unstaged 變更（必須先 stage 或 stash）
3. 提醒用戶解決任何待處理項目

### Step 2: Rebase（如果需要）
1. 檢查 `git log origin/main..HEAD` — 是否落後於遠端
2. 如果需要，執行 `git rebase origin/main`
3. 如果有衝突，指導用戶解決並繼續 rebase

### Step 3: Verify Changes
1. 運行 `get_errors` 檢查語法錯誤（所有修改的文件）
2. 簡要檢查提交消息格式（遵循 `.github/instructions/commit-message.instructions.md`）

### Step 4: Commit & Push
1. 使用原子化、描述清楚的提交消息
2. 執行 `git push origin main`
3. 確認推送成功（無被拒絕的更新）

### Step 5: Verify Deployment
1. 確認 Vercel 部署已觸發（檢查 GitHub 動作日誌或 Vercel dashboard）
2. 確認部署完成且無錯誤
3. 可選：檢查 https://tokyotaiwanradar.vercel.app/ 是否顯示最新變更

## 成功指標
- ✅ 無衝突或已解決
- ✅ 所有語法檢查通過
- ✅ Commit 已推送到 origin/main
- ✅ Vercel 部署已觸發並完成
- ✅ 部署驗證通過（無 502/500 錯誤）

## 中止條件
如果遇到以下情況，停止並報告：
- ❌ Rebase 失敗且無法自動解決
- ❌ 語法檢查失敗
- ❌ Vercel 部署失敗（查看部署日誌）
- ❌ 推送被拒絕（遠端有新提交）

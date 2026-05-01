---
name: Validate, Merge & Deploy
description: "Full cycle: check conflicts, rebase, commit with atomic message, push to origin/main, and verify Vercel deployment — call after implementation is complete"
user-invocable: false
disable-model-invocation: false
tools: [read, search, execute, web]
---

# 檢查衝突、合併、Commit 與部署

執行完整的驗證和部署流程，確保變更安全地推送到生產環境。

## 工作流

### Step 1: 檢查 Git 狀態
1. 檢查是否有未解決的 merge/rebase 衝突
2. 檢查是否有 unstaged 變更（必須先 stage 或 stash）
3. 提醒用戶解決任何待處理項目

### Step 2: Rebase（如果需要）
1. 先執行 `git fetch origin main`，更新 remote tracking
2. 檢查 `git log HEAD..origin/main --oneline` — 若 origin 有新 commit（**並行 commit 為常態，不要假設無事**），預設執行 `git rebase origin/main`
3. 檢查 `git log origin/main..HEAD --oneline` — 確認本地待推送的 commits
4. 如果 rebase 有衝突，指導用戶解決並繼續 rebase（`git rebase --continue`）
5. Rebase 後再次 `get_errors` 確認沒有因合併產生破壞

### Step 3: Verify Changes
1. 運行 `get_errors` 檢查語法錯誤（所有修改的文件）
2. 簡要檢查提交消息格式（遵循 `.github/instructions/commit-message.instructions.md`）
3. 若包含 Supabase migration，確認 migration 編號與 `.github/instructions/database.instructions.md` 的 latest 標記一致

### Step 4: Commit & Push
1. 使用原子化、描述清楚的提交消息
2. 執行 `git push origin main`
3. 確認推送成功（無被拒絕的更新）

### Step 5: Verify Deployment
1. 確認 Vercel 部署已觸發（檢查 GitHub 動作日誌或 Vercel dashboard）
2. 確認部署完成且無錯誤
3. 可選：檢查 https://tokyo-taiwan-radar.vercel.app/ 是否顯示最新變更（**注意：production URL 含連字號 `tokyo-taiwan-radar`，不是 `tokyotaiwanradar`**）
4. 若含 Supabase migration，明確回報「需在 Supabase SQL Editor 手動執行」與最小驗證清單（admin pass / non-admin deny）

## External URL Verification Rule

寫入文件、agent 檔、commit message 或 plan 的任何外部 URL，都必須在第一次出現時用 `curl -sI -L <url>` 驗證一次：
- HTTP 200/301/302/308 → 可寫入
- HTTP 404/DNS error → 必須回頭找正確 URL，不可硬寫

常見錯誤：production URL 漏寫連字號（`tokyotaiwanradar.vercel.app` 是 404；正確為 `tokyo-taiwan-radar.vercel.app`）。Reference incident: commit `3f58372` — agent 文件中 production URL 錯寫，curl -I 回 404 才被發現。

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

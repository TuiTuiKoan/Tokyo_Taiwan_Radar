---
name: Validate, Merge & Deploy
description: "Full cycle: check conflicts, rebase, commit with atomic message, push to origin/main, and verify Vercel deployment — call after implementation is complete"
tools: [read, search, execute, web]
handoffs:
  - label: "🔧 Fix issues found"
    agent: Engineer
    prompt: "部署驗證發現問題，請修復後重新部署。"
  - label: "📝 Update history/skill/agent"
    agent: Update History, Skill, Agent
    prompt: "根據最近的修改和所學的教訓，幫助我更新 history.md、SKILL.md 和 agent 檔案。"
    send: true
  - label: "🏗️ Plan next change"
    agent: Architect
  - label: "🕷️ Continue scraper work"
    agent: Scraper Expert
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
2. 執行 **`npm run build`**（在 `web/` 目錄）— `tsc --noEmit` pass ≠ build pass；route handler 錯誤、missing file、動態 import 問題只有完整 build 才能捕捉
3. 執行 token wording gate（deploy 前必過）：
   - 固定執行：`python3 scripts/check_token_permission_consistency.py`
   - 判斷本次 diff 是否包含 token 高風險檔案（使用 `git diff --name-only origin/main...HEAD`）：
     - `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md`
     - `.github/instructions/token-rotation.instructions.md`
     - `.github/agents/researcher.agent.md`
     - `scraper/update_source.py`
     - `.github/SECRETS_LIFECYCLE.md`
   - 若包含任一高風險檔案，再加跑：`python3 scripts/check_token_permission_consistency.py --strict`
   - Gate 規則：
     - Exit code = 0：繼續 Step 4
     - Exit code ≠ 0：立即中止流程，回報 checker 輸出的違規 file:line，要求先修正後再重跑 V-M-D
3. 簡要檢查提交消息格式（遵循 `.github/instructions/commit-message.instructions.md`）
4. 若包含 Supabase migration，確認 migration 編號與 `.github/instructions/database.instructions.md` 的 latest 標記一致
5. **Docs staleness check**：使用 `git diff --name-only origin/main...HEAD` 確認本次 diff 是否為架構性改動。若符合以下任一條件，且 `docs/ARCHITECTURE.md` 或 `docs/SCRAPER_PIPELINE.md` 未在 diff 中，必須警告並要求補更新後才繼續 push：
   - 新增或移除整個 CI workflow（`.github/workflows/*.yml`）
   - 新增或移除 pipeline layer（新的 `auto_scraper/`、`researcher.py` 等主模組）
   - 新增或移除 Supabase 整合點（LINE bot、新 API route）
   - 變更 `scraper/main.py` 的 SCRAPERS 清單超過 3 個來源（批量上線屬架構里程碑）
   - 新增 `web/app/api/` 下的 API endpoint
   不屬於架構性改動（不需要更新 docs）：bug fix、單一 scraper 新增、i18n 修改、CSS 調整。

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
- ✅ 所有語法檢查通過（`get_errors` + `npm run build`）
- ✅ Commit 已推送到 origin/main
- ✅ Vercel 部署已觸發並完成
- ✅ 部署驗證通過（無 502/500 錯誤）

> **「問題未重現」情形**：若收到「請修復後重新部署」提示但 Step 3 全部 pass、Vercel HTTP 200，則明確回報「問題未重現，目前狀態健康」——不要強行尋找不存在的問題。

## 中止條件
如果遇到以下情況，停止並報告：
- ❌ Rebase 失敗且無法自動解決
- ❌ 語法檢查失敗
- ❌ token wording gate（default 或 strict）失敗
- ❌ Vercel 部署失敗（查看部署日誌）
- ❌ 推送被拒絕（遠端有新提交）

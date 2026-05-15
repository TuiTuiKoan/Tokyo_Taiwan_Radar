# Tester Error History

<!-- Append new entries at the top -->

---

## 2026-05-15 — teket.jp sitemap timeout が 0件として現れる（ReadTimeout 静黙失敗）

**問題：** `matsumoto_cinema_select` dry-run で 0件取得。エラーではなく WARNING のみで完了。

**根因：** teket.jp の `sitemap.xml` が 34,000+ URL を含む大容量ファイルで、応答完了に 15〜20 秒かかる。`timeout=15` では `ReadTimeout` → `logger.warning` → `return []` で静黙 0件。

**Tester 判断パターン:**
- scraper が 0件 + WARNING のみ = timeout または filter が厳しすぎる
- `curl -o /dev/null -s -w "%{time_total}\n" <URL>` でレスポンス時間を計測
- `time_total > timeout` なら timeout 値を 2倍以上に増やす
- `time_total < timeout` なら Taiwan filter logic を確認

**修正:** `timeout=15` → `timeout=30` で再 dry-run → 3件取得 ✅

---
## 2026-05-05 — LINE 廣播 dry-run 驗證應確認 pool 過濾效果

### 問題
LINE 週報加入 `annotation_status` 過濾後，dry-run 測試未能即時驗證「pool 筆數是否確實減少」，無法確認過濾是否生效。

### 教訓（dry-run 驗證規則）
- **廣播 query 驗證**：執行 dry-run 時，應同時印出「無過濾」與「有 `annotation_status` 過濾」的 pool 筆數比較；若兩者相同，表示環境中沒有 pending 事件（不一定是 bug，但需確認）
- **過濾效果確認方法**：
  ```bash
  # 有過濾（正式邏輯）
  python weekly_line_broadcast.py --dry-run 2>&1 | grep "pool"
  # 手動查 pending 事件數（確認環境狀態）
  python3 -c "
  from supabase import create_client; import os; from dotenv import load_dotenv
  load_dotenv('.env')
  sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
  r = sb.table('events').select('id',count='exact').eq('is_active',True).eq('annotation_status','pending').execute()
  print('pending events:', r.count)
  "
  ```
- **若廣播在 09:00 pipeline 之前手動觸發**，特別容易出現 pending 事件進入 pool，dry-run 應在非標準時段（08:xx）測試以重現此情境

---
## 2026-04-28 - Tester could not execute terminal commands
**Error:** Tester appeared to have "no functionality" because subagent runs reported missing terminal/shell capability, so dry-run commands never executed.
**Fix:** Updated `tools` in `.github/agents/tester.agent.md` to alias mode (`read`, `search`, `execute`, `web`) and corrected venv path to `../.venv/bin/activate`.
**Lesson:** For custom agents, prefer supported tool aliases over raw function names; add a tool preflight check before running test commands.

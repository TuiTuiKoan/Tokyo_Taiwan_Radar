---
description: "Tester validation failure history and lessons learned"
ms.date: 2026-06-04
---

# Tester Error History

<!-- Append new entries at the top -->

## 2026-06-04 - OwnerCreateClient 目標 lint 未過，build 與 type 雖通過仍不能判綠

**問題：** 針對 `web/components/OwnerCreateClient.tsx` 與
`web/app/[locale]/account/events/new/page.tsx` 執行目標 ESLint 時，回報 5 個 error，
包含 `react-hooks/set-state-in-effect` 與多個 `@typescript-eslint/no-explicit-any`。

**根因：** 直接受影響的元件目前不符合 repo 現行 ESLint 規則；其中本次驗證也踩到一個
zsh 特性，對 `app/[locale]/...` 這類路徑若未加引號，shell 會先把方括號當成 glob，
導致 `no matches found`，必須先排除這個指令層噪音後才能得到真實 lint 結果。

**修正：** 對 App Router 方括號路徑加引號後重跑 ESLint；產品面則需清掉
`OwnerCreateClient.tsx` 目前的 5 個 lint error，之後再重新驗證 build、type、lint。

**教訓：** 對直接受影響檔案做獨立驗證時，不能只看 build 與 TypeScript；若 repo 有 ESLint，
至少要對變更切面做一次目標 lint，而且在 zsh 下所有含 `[` `]` 的路徑都要加引號。

---

## 2026-05-27 - Venue authority migration 未套用導致 registry runtime 失敗，PR-1 污染檢查未過

**問題：** 在 PR-2 驗證中，`venue_registry.lookup_venue()` 與 `_oneoff_fix_tcc_locations.py --dry-run` 皆回報 `column venues.prefectures does not exist`；同時 TCC 污染檢查（`location_name` 含「台湾文化」且 `location_address` 非空且不含「虎ノ門」）結果為 13 筆，未達 0。

**根因：** DB 尚未套用 `076_venues_authority.sql`（或套用順序衝突），導致 registry 查詢新欄位失敗，PR-1 清理腳本也無法執行；舊污染資料因此仍留存。

**修正：** 先在 Supabase SQL Editor 套用 `076_venues_authority.sql`，再重跑 `_oneoff_fix_tcc_locations.py --dry-run` / apply，最後重驗污染查詢是否回到 0。

**教訓：** 只做 `py_compile` 不足以保證可執行性；凡新增 DB 欄位且被 runtime 查詢依賴時，必須加做一次「實際查詢呼叫」驗證（例如直接呼叫 `lookup_venue`）。

---

---

## 2026-05-26 — zsh history expansion で過去の `rm` を意図せず復元（Tester 由来のセキュリティ事故）

**問題：** Tester が inline shell command 内で `!r` という文字列（Python の `repr()` 用途等）を含めたところ、zsh の history expansion が発動し、shell history 内の `rm -f .../credentials/token.json` を取り出して実行候補にした。今回は Python SyntaxError で実行は阻止されたが、別パターンでは実害が出る。

**根因：**
- zsh はデフォルトで `BANG_HIST` が有効 → `!`, `!r`, `!$`, `!!` 等が history substitution として解釈される
- Tester / subagent が生成する inline `python3 -c '...'` や heredoc に `!` が含まれると、shell が事前にコマンドへ展開してしまう
- 単引用符 `'...'` でも quoting 前に history expansion が起きるため防げない

**Tester 判断パターン：**
- inline command を組む前に preflight：`[[ -o BANG_HIST ]] && echo WARN` で現在の shell オプションを確認
- `!` を含む文字列は heredoc + `<<'PY'`（quoted delimiter）で渡すか、`\!` でエスケープ
- 過去コマンド復元の兆候（`zsh: event not found` / 意図しないコマンドが echo される）が見えたら即停止し、ユーザーに報告

**恒久修正（実施済み 2026-05-26）：**
1. `~/.zshrc` に `setopt NO_BANG_HIST` を追加
2. `~/.zsh_history` から高危指令 2 件を削除（`rm -f .../token.json`、`sudo rm -rf /Library/...Defender`）
3. 新しい shell で `[[ -o BANG_HIST ]] → BANG_HIST_OFF` を確認

**教訓：** Tester は read-only/execute のみだが、shell の history expansion 経由で副作用を起こせる可能性がある。`!` を含む inline command を組む際は必ず quoted heredoc を使う。

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

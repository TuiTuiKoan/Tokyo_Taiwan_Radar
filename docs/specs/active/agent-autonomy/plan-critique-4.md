# Plan Critique 4：#654 production log 擷取修正

> 2026-11-11。評審者：Claude plan-critic（Opus, effort high）。Codex 未安裝，與撰寫者同一模型家族，不算跨模型審查。
> 結論：revise → 必改項 1–5 全數採納後交 Engineer。

## 1. 商業主軸對齊：🟢 對齊

- 對應資料完整性。source-diagnose 是零產出爬蟲的自動診斷；production log 一直「取不到」，heartbeat 判斷 prtimes #459 這類「dry-run 有、production 0」的情況時少了最關鍵的證據。

## 2. 複雜度 vs 價值

- 複雜度 low（2 個程式檔＋1 個測試檔，無 migration、i18n、annotator、RLS）；價值 medium-high。沒有過度設計。

## 3. 優先順序：🟢 正確

- 已上線自動化的 bug。不要在此 PR 順手修 `dryrun_evidence.clean_code`；dry-run 摘要出現 `[31m` 殘渣目前無觀察證據，有實例再另開 issue。

## 4. 架構整合

### 4.1 旗標在不同 runner gh 版本下的風險（必補）

- 本機 gh 2.89.0 不認得 `--allow-escape-sequences`，舊版遇到會 `unknown flag`，三個 run 的 log 下載全失敗。
- 公開資料（CVE-2026-45803 / GHSA-crc3-h8v6-qh57，修補版本 2.92.0；v2.92.0 release notes；OSV GO-2026-5335）都沒有說明 `gh api` 旗標從哪版開始有 → 不能用版本比較，必須功能偵測。
- 「runner 的 gh 印了這則錯誤，所以支援」只對那一次執行的那台 runner 成立；ubuntu-latest image 分批 rollout、也會 rollback。舊 image 的 runner 本來不擋 escape sequence，正確做法是那時不帶旗標。
- step 只有 `set -u`、沒有 `pipefail`；用 `[[ "$(...)" == *flag* ]]` 不走 pipe，避免日後加 pipefail 時 `grep -q` 造成 SIGPIPE 誤判。

### 4.2 ANSI regex

| 輸入 | 結果 | 判定 |
|---|---|---|
| `\x1b[36;1mpython main.py\x1b[0m` | `python main.py` | ✅ |
| `=== Starting scraper: \x1b[1mFoo\x1b[0m ===` | marker 完整還原 | ✅ |
| OSC 8 `\x1b]8;;url\x1b\\link\x1b]8;;\x1b\\` | `link` | ✅ |
| `\x1b(B`（`tput sgr0` 輸出 `\x1b(B\x1b[m`） | 原樣留下，經 `clean_code` 變 ` (B` | ❌ |
| 斷掉的 CSI `\x1b[ broken` | `roken` | 可接受 |
| 無結尾 OSC `\x1b]0;title` | `0;title` | 可接受 |

- 每個分支以 `\x1b` 開頭，純文字 `[0m` 不會被刪，不過寬。
- 2 字元分支 `\x1b[@-Z\\-_]` 不含 intermediate bytes（0x20–0x2F），改 `\x1b[ -/]*[0-~]` 後 `\x1b(B\x1b[m sgr0` → ` sgr0`、`\x1b7save\x1b8` → `save`。

### 4.3 ANSI 位置

- marker 中間：`excerpt()` 先對全部行 `_strip`，比對時已去除，但要測試鎖住。
- 時間戳之前：`_GH_TS` 以 `^` 錨定，「先去時間戳再去 ANSI」會留下 `\x1b[0m2026-…Z` 的時間戳；改成先去 ANSI。
- `scraper/main.py` 用 `logging.basicConfig`，不上色；ANSI 主要來自 runner 的 `Run …` 回顯與 pip／playwright，多在 scraper 段落之外。主體修正是旗標，regex 是防禦。

### 4.4 編碼

- `read_text(encoding="utf-8", errors="replace")` 安全。log 開頭的 UTF-8 BOM 只影響第一行（runner 版本資訊），不用改。C1 控制字元這次不處理。

## 5. 替代方案

| 方案 | 判定 | 理由 |
|---|---|---|
| 加旗標＋`_strip` 去 ANSI | ✅（加功能偵測） | 改動最小 |
| `curl` 帶 token 打 logs | ❌ | 錯誤格式與 `HTTP [0-9]{3}` grep 不合，token 上命令列，需重審 `test_workflow_secrets.py` |
| `gh run view --log --job` | ❌ | 每行多 `job\tstep\t` 前綴，`_GH_TS` 與 fixture 全要改 |
| ANSI 剝除放進 `clean_code` | ❌ | marker 比對在 `clean_code` 之前 |

## 6. 必改項

1. workflow 功能偵測旗標：`LOG_FLAGS=()`；`[[ "$(gh api --help 2>&1 || true)" == *--allow-escape-sequences* ]]` 時加入；L222 改 `gh api "${LOG_FLAGS[@]}" …`。
2. regex 2 字元分支改 `\x1b[ -/]*[0-~]`。
3. `_strip` 先去 ANSI 再去時間戳。
4. 測試：(a) marker 內含 ANSI 仍命中；(b) 時間戳前有 ANSI 也去掉；(c) `\x1b(B\x1b[m` 與 OSC 8 保留 `label`；(d) 經 `main()` 以 `write_bytes` 寫入含 ESC 的 log，輸出無 `\x1b`、`[0m`、`(B`。
5. 驗證補 `test_workflow_shell_syntax.py`、`test_d1_workflow_contract.py`、`test_workflow_secrets.py`；合併後可手動 `gh workflow run source-diagnose.yml -f sources=taiwanshi`（issue 留空只寫 job summary），確認 summary 有 `=== Starting scraper: TaiwanshiScraper ===` 且無「log 下載失敗」。D1 監控作第二道證據。

# Spike 結果：唯讀程式碼審查（`a03ce9bf..361d17c1 -- scripts/`）

日期：2026-10-23
審查者：`correctness`、`tests`（皆為 Sonnet、Plan 類型 subagent，背景並行）
彙整：lead（主 session）

## 方法與限制

- 這不是 Claude Code 原生 agent team，而是兩個具名的獨立 subagent，彼此無法對話。與 `spike-agent-teams.md` 要驗證的 team 機制不同，不能據此推論 team 功能。
- 唯讀只靠 prompt 指示與 Plan 類型（無 Edit／Write）；仍保有 Bash，工具層並未阻擋重導寫入。
- 兩位審查者都只讀碼，**沒有實際執行重現**；下列發現皆為讀碼推論，標「推測」者證據更弱。
- 15 分鐘上限未觸發，兩位都在時限內完成。
- 嚴重度為 lead 彙整後的判斷，可能與提出者原標不同。

## 彙整發現

| # | 發現 | 位置 | 提出者 | 重複 | 嚴重度 |
| --- | --- | --- | --- | --- | --- |
| 1 | `is_generated` 用整檔子字串比對 marker，且不分副檔名。手寫檔（如 skills 補充檔）只要內文引用 marker 就會被視為 generated 而在 `write_outputs` 刪除，`--check` 不報警；`.md` 含 TOML marker、`.toml` 含 Markdown marker 也會被接受。建議：只認首個非空行，且依副檔名選對應 marker。 | `scripts/sync_ai_adapters.py:90-91`、`:432` | correctness #2、tests #4 | **重複（兩位獨立提出）** | 中 |
| 2 | `write_outputs` 非原子：先刪光 generated 檔（459-460），才檢查是否覆蓋非 generated 手寫檔（463-464），被擋時 `SystemExit`，留下半成品工作樹。新增 `.codex/agents` 擴大影響面。建議：先完整檢查衝突再 unlink／寫入。 | `scripts/sync_ai_adapters.py:458-466` | correctness #1 | 否 | 中 |
| 3 | 寫入模式遇 tier 缺少／未知會 `return 1` 且不寫檔，但只有 role 版本有測（`test_write_mode_refuses_when_roles_are_broken`），tier 版本只測 `--check`。 | `scripts/tests/test_sync_ai_adapters.py:249、256` | tests #1 | 否（correctness 確認行為本身正確，屬純測試缺口） | 中 |
| 4 | 缺 tier 時輸出契約（wrapper 不寫 `model`／`effort`、codex toml 省略 effort、`--check` 印 `changed`）沒被鎖定，測試只確認回傳碼。 | `scripts/tests/test_sync_ai_adapters.py:249-260` | tests #2 | 否 | 中 |
| 5 | description／handoff 含特殊字元（`"`、`\`、換行、`\t`、控制字元、全形字）時，TOML／YAML 輸出沒有測試；現有測試只用真實 repo 的 description，也沒斷言 description 值。 | `scripts/tests/test_sync_ai_adapters.py:235` | tests #3、#8 | 與 #6 相關但不同層（測試缺口 vs 程式缺陷） | 中 |
| 6 | `toml_string` 以 `json.dumps(ensure_ascii=False)` 實作，不跳脫 DEL（U+007F），TOML basic string 不允許裸 DEL。實際機率低。建議後處理換成 `\u007f`。 | `scripts/sync_ai_adapters.py:271-272` | correctness #3；tests #3 的推測部分同指此點 | 部分重複 | 低 |
| 7 | frontmatter 的孤立 surrogate（`"\ud800"`）經 `ast.literal_eval` 進入 `json.dumps`，`write_text` 丟 `UnicodeEncodeError`，且發生在已 unlink 之後（接 #2）。極端邊角。 | `scripts/sync_ai_adapters.py:146、271-272` | correctness #4 | 否 | 低 |
| 8 | 兩個 agent 的 `name` kebab 後相同時，`outputs[...]` 後者靜默覆蓋前者；`expected_outputs` 的 overlap 檢查不涵蓋 part 內部。新增前即存在，這次多一個輸出位置。 | `scripts/sync_ai_adapters.py:309-355` | correctness #5 | 否 | 低 |
| 9 | `handoffs` 為非空 list 但所有項目缺 `label`／`agent` 時，只剩孤立標題「完成後建議的下一步：」。兩邊輸出一致，僅語意瑕疵。 | `scripts/sync_ai_adapters.py:335-350` | correctness #6 | 否 | 低 |
| 10 | `.codex/agents/` 下非 UTF-8 檔（`UnicodeDecodeError` 分支）、`README.md`、子目錄沒測；該 except 分支可能整個測試集都沒執行。 | `scripts/tests/test_sync_ai_adapters.py:282-286` | tests #6 | 否 | 低 |
| 11 | `test_generation_is_idempotent` 是否涵蓋 `.codex`、以及「寫入後立刻 `--check` 回傳 0」的 codex 專屬斷言，未確認。 | `scripts/tests/test_sync_ai_adapters.py:301` | tests #5 | 否 | 低（推測） |
| 12 | 沒有測試斷言 `tools:` 與 `model:`／`effort:` 的輸出順序。 | `scripts/tests/test_sync_ai_adapters.py:54-59` | tests #7 | 否 | 低 |
| 13 | `tier: build # note` 這類行內註解不會被 `parse_scalar` 去除，報 unknown tier；行為可理解但訊息不直觀。 | `scripts/sync_ai_adapters.py:545-549` | correctness #7 | 否 | 低（推測） |
| 14 | 提醒：haiku 別名帶 `effort: low`，未驗證 Claude Code 是否接受；AGENTS.md 已記載 2026-10-23 實測 tester（haiku）subagent 為 low，與此推測矛盾，應視為已有證據。 | `scripts/sync_ai_adapters.py:21-23` | correctness #8 | 否 | 資訊 |

## 不列入的項目

- tests #9（`MODEL_ID_PREFIXES` 太窄）：審查者自己判定冗餘，因 `test_tier_table_holds_aliases_not_model_ids` 另要求 model 屬於 `{opus, sonnet, haiku}`。
- 未發現 `EXPECTED_TIERS` 與 AGENTS.md tier 表不一致。
- correctness 檢查後判定無問題：`--check` 與寫入模式在 tier／role 問題上一致；stale `.toml` 偵測；`rglob` 不跟隨目錄 symlink；TOML 輸出結尾換行與 marker 位置。

## 統計

- 共 14 項（含 1 項資訊）：中 5、低 8、資訊 1；無高。
- 重複：#1 完全重複、#6 部分重複；兩位的範圍分工大致清楚，重疊集中在 `is_generated`。
- correctness 提出 9 項、tests 提出 8 項（扣除 #9 冗餘項），其中 #1、#5／#6 為雙方都碰到。

## 建議下一步（未執行）

1. 優先處理 #1 與 #2（可能刪除手寫檔、留下半成品），並各補一個鎖定行為的測試。
2. 補 #3、#4、#5 的測試；#5 可用 `tmp_repo` 改 description 後以 `tomllib.loads` 驗證。
3. 以上皆讀碼推論，修正前應先寫會失敗的測試重現。

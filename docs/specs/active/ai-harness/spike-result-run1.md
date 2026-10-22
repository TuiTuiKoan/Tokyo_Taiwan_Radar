# Spike 結果：agent team 唯讀審查 `a03ce9bf..361d17c1 -- scripts/`

- 日期：2026-10-23
- 成員：`correctness`（Sonnet，唯讀，只看 `sync_ai_adapters.py` 新增邏輯）、`tests`（Sonnet，唯讀，只看 `scripts/tests/`）
- 實作方式：本環境沒有 team 建立工具，以兩個具名 Plan 類型 subagent（無 Edit/Write）加 SendMessage 模擬。
- 兩位都回報全程唯讀、未執行寫入命令。`tests` 沒跑 pytest。
- 行號皆由 diff 推算，可能差 1–2 行；所有發現未經 lead 實際執行重現。
- `tests` 的回報原在第 12 項被截斷，已補送；T12、T13 為補送內容，`tests` 確認第 13 項之後沒有更多發現。`tests` 建議的補測順序：第 1、4、3、5、7 項（即報告中的 B、T4、D、T5、T7）。

## 彙整表

| # | 嚴重度 | 提出者 | 重複 | 位置 | 發現 |
|---|---|---|---|---|---|
| A | medium | correctness | 與 T5 互補 | `sync_ai_adapters.py` `write_outputs` ~L459–466 | 先 `unlink` 全部 generated，才逐檔檢查 "refusing to overwrite"。手寫 `.codex/agents/engineer.toml`（無 marker）與預期輸出同名時，先刪光其他生成檔再 `SystemExit`，留下半毀目錄。修法：先檢查完所有衝突再刪除與寫入。 |
| B | high | tests | 與 C 部分重複 | `test_sync_ai_adapters.py` ~L249、L256 | `--check` 缺／未知 tier 有測，寫入模式 `return 1` 且不寫檔未測；有人改成忽略 tier 問題照寫，測試仍全過。 |
| C | high（tests）／low（correctness） | tests + correctness | **重複** | 腳本 ~L294、L326；測試 ~L227–233 | `tier=None` 時 `agent_outputs` 靜默省略 `model`／`effort`／`model_reasoning_effort`，無警告也無測試鎖住。correctness 認為 `main()` 兩種模式都擋，不構成回歸。嚴重度分歧，建議定為 medium：行為正確但缺測。 |
| D | high（tests）／low（correctness） | tests + correctness | **重複** | `toml_string` ~L271；測試 ~L235–247 | `json.dumps(ensure_ascii=False)` 不跳脫 DEL（U+007F），TOML 禁止，嚴格 parser 會拒收。tests 另指出含 `"`、`\`、tab、U+2028/2029、emoji 的 description round-trip 沒測（只用 repo 現有 15 個正常 agent）。兩位皆為依規格推論、未實測。建議定為 low–medium，補 round-trip 測試即可。 |
| E | low | correctness | 與 T6 相關 | `is_generated` ~L90 | 子字串比對且兩種 marker 不分副檔名互通：手寫的 `.md`／`.toml` 只要引用 marker 文字就會被視為生成檔並被刪除。建議只比對首個非空行並依副檔名對應 marker。 |
| F | low | correctness | 否 | `agent_outputs` ~L359–372 | handoffs 全部缺 `label`／`agent` 而被略過時，仍輸出標題「完成後建議的下一步：」卻無項目（既有行為，現擴散到 Codex 檔）。 |
| G | uncertain | correctness | 否 | `generated_files` `rglob("*.toml")` | `.claude/skills`、`.agents/skills` 若含 symlink，`rglob` 行為隨 Python 版本不同（3.13 起改變）。未確認實際結構與本機版本。 |
| T4 | medium | tests | 否 | 測試 ~L277–286 | `--check` 對殘留 `stale.toml` 回報 `stale .codex/agents/stale.toml` 未測（只測寫入模式）。`.claude/agents` 下殘留 `.toml`、`.codex/agents` 下殘留 `.md` 也未測。 |
| T5 | medium | tests | 與 A 互補 | 測試 ~L277–286 | 手寫 `.codex/agents/tester.toml`（無 marker）應讓寫入失敗且內容不變，未測。現有 `hand_written` 名為 `mine` 剛好避開撞名。應與 A 一併處理：先修順序，再補測試。 |
| T6 | medium | tests | 與 E 相關 | 測試 ~L270–275 | 手改 toml 只測 `model_reasoning_effort` 改成 `max`；未測新增 `model`／`model_provider`、刪 marker 後檔案不再算 generated（下次寫入變 "refusing to overwrite"）。 |
| T7 | medium | tests | 否 | 測試 ~L249–261 | tier 邊界值未測：空值、大小寫（`Build`）、前後空白、帶引號、YAML list；同時缺 tier 與 `claude-role` 應列兩條 problem；`UNDECIDED_AGENTS`（如 architect）移除 tier 後應報 `missing tier`，目前只靠全量檢查間接覆蓋。 |
| T8 | medium | tests | 否 | 測試 ~L263–268 | `test_source_model_alias_is_still_rejected` 只測 frontmatter 頂層 `model:`；handoffs 內 `- model:`、prompts、skills 與 `--allow-pinned-models` 搭配 tier 的行為未測。 |
| T9 | medium | tests | 否 | 測試 ~L227–233 | wrapper 的 `model`／`effort` 各只出現一次、位置在 frontmatter 內，未斷言。 |
| T10 | low | tests | 否 | `conftest.py` ~L14、L34 | `tmp_repo` 對 `.codex` 做 `copytree`，目錄不存在會直接丟錯；腳本 ~L428 `if not base.exists(): continue` 分支未測，`.codex` 整個缺失時 `--check` 的輸出也未測。 |
| T11 | low | tests | 否 | 測試 ~L341–345 | `len(sources) * 2 == len(outputs)` 把「每個 agent 恰好兩個輸出」寫死，未來增加投影會誤報；`.toml` marker 只檢查 `in text`，另一測試用 `startswith`，嚴格度不一致。 |
| T12 | low | tests | 否 | 測試 ~L219–225 | `MODEL_ID_PREFIXES` 冗餘：前一行 `tier["model"] in {"opus","sonnet","haiku"}` 的白名單已擋下任何 ID；日後加別名（如 `fable`）需同步改測試。屬維護成本，不是漏測。 |
| T13 | low | tests | 否 | `parse_frontmatter`／`tier_problems` | 空輸入未測：`.github/agents` 無 agent、frontmatter 缺結尾 `---`、frontmatter 全空（後兩者回 `{}`，報 `missing tier`，行為合理但未鎖定）。 |

## 重複與一致性

- 重複項：C（tier 缺失靜默降級）、D（DEL 未跳脫）兩位各自獨立提出，可信度較高；皆為推論，建議各補一個直接測試以實證。
- 互補項：A（順序缺陷）與 T5（未測）應一起修。
- 嚴重度分歧：C、D 兩位評級不同；lead 建議降為 medium／low，因 `main()` 已擋且 DEL 機率極低。
- 兩位皆未找到可確認的 high 級程式缺陷。

## 建議優先順序

1. 修 A，並補 T5 測試。
2. 補 B、C、D 的測試（價值高、成本低）。
3. 補 T4（`--check` 與寫入模式一致性）、T6、T7、T8。
4. 其餘 low 項視需要處理；E 可與 T6 一併考慮。

## Spike 觀察（agent team 本身）

- 兩位 teammate 皆在時限內完成並維持唯讀。
- 回報有長度上限，會被截斷；需要補送時用 SendMessage。
- 此環境沒有原生 team 工具；以具名 subagent 加訊息溝通可行，但 lead 無法即時看到進度。

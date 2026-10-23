# Spike：Claude agent teams（一次性）

目的：判斷 Claude Code 的 agent teams 對本 repo 的唯讀審查工作是否有明確收益，決定要不要列入 Phase 2b 的考慮。一個工作流、一個工具、跑一次。條件在執行前寫定，事後不得更改。依據：plan.md §3 Phase 2 第 5 點、plan-critique-1.md N3。

## 設定

| 項目 | 值 |
|---|---|
| 工具 | Claude agent teams（實驗功能，預設關閉）。Orca orchestration 不在本 spike |
| 啟用方式 | 只用環境變數，不改任何設定檔：`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| 工作目錄 | `ttr-ai-harness-worktree` 根目錄（hooks 才會載入） |
| 模型 | lead 與兩個 teammate 都用 Sonnet |
| 規模 | 一個 lead 加**兩個** teammate，不再多 |
| 審查標的 | Phase 1 的程式碼：`git diff a03ce9bf..361d17c1 -- scripts/`（`sync_ai_adapters.py` 與測試）。約 100 行新增，範圍明確，有可驗證的真實問題的可能 |
| 性質 | 唯讀。不得修改任何檔案，唯一例外：lead 在最後把完整綜整寫入 `docs/specs/active/ai-harness/spike-result.md` |

## 執行前先記錄

- 目前 Claude 方案用量百分比與重置時間（`/usage` 或 statusline）。
- 開始時間。

## 啟動指令與提示詞

```bash
cd "/Users/flyingship/Development/3-TTR/Tokyo Taiwan Radar/ttr-ai-harness-worktree"
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 claude --model sonnet
```

進入後貼上：

```text
請建立一個 agent team 做唯讀的程式碼審查，標的是 `git diff a03ce9bf..361d17c1 -- scripts/`（scripts/sync_ai_adapters.py 與 scripts/tests/）。
正好兩位 teammate，兩位都用 Sonnet，名稱固定：
- correctness：只看 sync_ai_adapters.py 的新增邏輯（TIERS、tier_problems、codex_agent、toml_string、is_generated、generated_files、write_outputs），找會出錯的輸入、邊界與回歸。
- tests：只看 scripts/tests/ 的新增與修改，找沒被測到的情境（例如 description 含引號或換行、舊檔殘留、--check 與寫入模式不一致）。
規則：所有人唯讀，不得修改任何檔案，不得執行會寫入的命令；遇到任何寫入權限請求一律拒絕。每個發現必須附檔案與行號與可重現的理由。
兩位完成後，lead 彙整成一份報告：每項發現標明由誰提出、是否重複、嚴重度。最後把完整報告寫入 docs/specs/active/ai-harness/spike-result.md（這是唯一允許寫入的檔案）。
15 分鐘內沒有結果就請兩位 teammate 收斂並結束。
```

## 成功條件（全部成立才算有明確收益）

- S1：兩位 teammate 都在 15 分鐘內交出附檔案與行號的發現。
- S2：至少一項發現經事後讀程式碼確認為真實問題，且不是只有一位 teammate 提出的重複項（即兩人的發現至少有一項不重疊）。
- S3：用量消耗不超過目前用量視窗的 5 個百分點。
- S4：結束後 `git status --short` 只多出 `spike-result.md`，沒有其他被修改的檔案。

## 停止條件（任一成立就立刻停止，不重跑）

- 超過 15 分鐘。
- teammate 要求寫入權限，或 lead 開始自己實作而不是等 teammate。
- 用量消耗超過 5 個百分點。
- 兩份報告幾乎完全重複，沒有互補的發現。

## 判定規則

- 成功條件 S1 到 S4 全部成立：記為「可列入 Phase 2b 考慮」，不是「採用」。
- 其他情況：記為「無明確收益，不採用，不再為此疊加治理」。
- 只跑一次。不因為結果不理想而調整提示詞重跑。

## 結果記錄（核對與判定在 notes.md §10）

| 項目 | 值 |
|---|---|
| 日期與工具版本 | 2026-10-23，Claude Code 2.1.308 |
| 開始與結束的用量百分比 | **使用者尚未提供**（S3 需要）；以 transcript 的 token 數作客觀紀錄，見 notes.md §10 |
| 耗時 | 約 1.5 分鐘（04:35:59 到 04:37:27），上限 15 分鐘 |
| teammate 數與模型 | 2 位，`Plan` 類型，Sonnet；`~/.claude/teams/session-092ec819/config.json` 證實是真正的 agent team |
| correctness 的發現數 | 6（A、C、D、E、F、G；其中 C、D 與 tests 重複） |
| tests 的發現數 | 13（B、C、D、T4 到 T13；其中 C、D 與 correctness 重複） |
| 經確認為真實問題的數量 | lead 事後核對，見 notes.md §10：實際重現 2 項（A、D）；靜態核對成立 B、C、E、F、T4 到 T13（B 是測試缺口，C 是缺測不是缺陷）；G 未確認 |
| 兩人重疊的數量 | 2（C、D） |
| S1／S2／S3／S4 | S1 成立／S2 成立／S3 **待使用者提供用量**／S4 成立 |
| 判定 | **暫定**：S3 確認前不下最終判定；若用量消耗 ≤ 5 個百分點，記為「可列入 Phase 2b 考慮」（不是採用） |

## 第二次執行：補量測 S3（事前登記，2026-10-23，執行前寫定）

原因：第一次執行沒有記下開始前的 `/usage`，S3 無法量測（notes.md §10.7）。使用者決定用**完全相同的提示詞**重跑一次，只為補上量測；第一次的結果完整保留，不因第二次的結果調整。

- 提示詞、啟動指令、規模、模型、成功條件、停止條件、判定規則：與上文完全相同，一字不改。
- 第一次的報告已移出工作樹，避免 teammate 讀到：`~/.ai-notes/ttr/ai-harness-spike-run1-result.md`（SHA-256 `dad945c6b515112e1d31a467ae3397ed5d86360d0091faed3fa0193a4d5e6bfd`）。第二次結束後，由本 session 還原為 `docs/specs/active/ai-harness/spike-result-run1.md`；第二次 lead 寫入的 `spike-result.md` 是第二次的報告。
- 第二次開始前必須記下：`/usage` 的 Current session %、Current week (all models) %、Current week (Fable) %，以及時間。結束後再記一次，相減。
- 執行期間不要在任何其他 session 輸入或啟動工作（包含本 session）：百分比是帳號層、跨所有 session 的累計。
- S4 的基準：工作樹目前的 `git status --short`（9 行，快照在 `~/.ai-notes/ttr/ai-harness-spike-run2-baseline-status.txt`）。結束後除了多出 `spike-result.md`，不得有任何變化。
- 污染檢查：兩位 teammate 的任務是只看 `scripts/` 的 diff。結束後由本 session 讀 teammate 的 transcript，檢查有沒有讀取 `docs/specs/active/ai-harness/` 內的任何檔案（`notes.md` 含第一次的核對結果）。若有，第二次結果標註「可能受污染」。
- 與第一次的比較：只報告，不調整判定。差異（發現數、重疊、用量）如實記錄。
- 最終判定採用第二次，因為只有它能量測 S3；第一次保留作對照。

### 第二次結果記錄

| 項目 | 值 |
|---|---|
| 開始前：session %／週 %／Fable 週 % | 15%／29%／7%（`/usage`，全新 session，Total cost $0.0000） |
| 結束後：session %／週 %／Fable 週 % | 15%／29%／7% |
| 差值（S3，上限 5 個百分點） | **0 個百分點**（解析度 1 點；該 session 的 API 等值花費 $0.73） |
| 耗時 | 約 1.6 分鐘（04:42:56 到 04:44:34） |
| correctness 的發現數 | 9 |
| tests 的發現數 | 8（扣除自己判定冗餘的 1 項） |
| 與第一次報告重疊的發現 | 主要發現幾乎全部再次獨立出現：`write_outputs` 順序、`is_generated`、tier 寫入模式缺測、DEL、handoffs 空標題、description 特殊字元缺測；第二次新增 surrogate、kebab 名稱碰撞、行內註解三項（皆已重現） |
| 是否讀取 `docs/specs/active/ai-harness/` | **否**：兩位 teammate 各只有 2 與 3 次工具呼叫，沒有任何一次涉及該目錄；lead 唯一涉及的是寫入 `spike-result.md` |
| S1／S2／S3／S4 | 成立／成立／成立／成立 |
| 判定 | **可列入 Phase 2b 考慮（不是採用）**，細節與限制見 notes.md §12 |

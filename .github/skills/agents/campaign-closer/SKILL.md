---
name: campaign-closer
description: A3 contention detection rules, V-M-D handoff contract, anchor staging, and the recovery capsule contract for the Close Campaign & Retire Worktree agent
ms.date: 2026-08-12
---

# Campaign Closer Skill

`Close Campaign & Retire Worktree` agent 的實作規則。每一條都來自實測或既有測試契約，
不是設計偏好。

權威文件分工：

| 主題 | 權威 |
|---|---|
| 十節記錄格式、Identity / Freshness / Correction 契約、Cleanup checklist、Privacy boundary | `docs/evaluation/campaigns/README.md` |
| worktree 建立與移除機制 | `.github/instructions/git.instructions.md` |
| 有哪些 worktree 存在 | `docs/specs/active/workstream-tracking` |
| 評估框架上游 | `docs/specs/active/evaluation-framework` |

本 SKILL 只寫這些文件沒有涵蓋的部分：偵測邏輯的陷阱、交接契約、以及移除的補償設計。

---

## A3 — 平行 session 偵測

### 判定演算法（單層、確定性、保守）

對 `~/.copilot/session-state/<id>/` 逐一檢查：

```
<id> == 本 session                          → 跳過（自身不算競用）
無 lock 檔                                   → 不計入
git_root（缺則 cwd）為空                     → UNDETERMINED
路徑正規化後 == 目標 worktree physical path：
    events.jsonl mtime 在門檻內              → CONTENDED
    events.jsonl mtime 逾時                  → UNDETERMINED（閒置但開著）
    events.jsonl 不存在                      → UNDETERMINED
路徑無法解析但大小寫不敏感比對相同            → UNDETERMINED
路徑無法解析且比對不中，但字串含目標 basename → UNDETERMINED
本 session id 無法取得                       → UNDETERMINED
以上皆無命中                                 → SOLE_OWNER (CLI-scope)
```

### 外部格式契約：解析要寬，結論要嚴

`session-state/` 的目錄內容是**別人的格式**，不是我們的。任何「解析不到就跳過」都會把一個
活著的 session 靜默漏掉，直接產出 `SOLE_OWNER` → `RETIRE_CANDIDATE`。因此：

* lock 檔名同時接受 `inuse.<pid>.lock` 與 `inuse.lock`。少一段 pid 不代表沒鎖。
* 擷取 `git_root` / `cwd` 時就用 `[[:space:]]*` 吃掉冒號後的任意空白，不要假設只有一個。
* **順序是「先去前後空白、再剝引號」，不可對調。** 剝引號的 sed 錨在 `^` 與 `$`，只要還留
  著任何前導空白，錨點就不成立、引號原封不動存活，接著 `[ -d ]` 與字串比對雙雙落空 →
  靜默跳過一個活著的 session。第一版正是寫反了順序才漏掉多空白 + 引號的組合。
* 去前後空白用 `trim_edges`；本 repo 路徑本身含空格，**不可**用 `tr -d '[:space:]'`。剝掉
  引號之後不再去空白——引號內的空白是值的一部分。
* 兩道防線（來源端 `[[:space:]]*` 與比對前 `trim_edges`）都要有。它們覆蓋的輸入不同，只做
  其中一個就是 F2 只修一半的翻版。
* 格式看不懂但仍疑似指向目標 → `UNDETERMINED`，不是跳過。實作方式是**類別守衛**：路徑
  無法解析（`resolved=0`）且比對不中時，若原字串（case-insensitive）含目標 basename 就判
  `UNDETERMINED`。這一條同時涵蓋不成對引號、未展開的 `~`、以及尚未出現的變形，不必為每一
  種形狀各補一條正規表示式。**守衛只在 `resolved=0` 時適用**：已成功解析、確定指向別處的
  路徑仍照常跳過，否則每個名稱相近但無關的 session 都會把結果拖成 `UNDETERMINED`。

### 三個陷阱

**1. PID 不是存活訊號。** Copilot CLI 的多個 session 共用同一個 Code Helper 進程，因此不同
session 的 `inuse.<pid>.lock` 會記到**同一個 pid**。本機實測有三個互不相干的 session 同為
`pid=58145`。用 `kill -0 <pid>` 之類的存活測試會把毫無關係的 session 判成競用者。
**偵測邏輯裡不得出現任何 PID 存活判準。**

**2. 門檻只用來提出疑慮，不用來放行。** lock 存在但 transcript 沉寂，代表「開著但閒置」——
那是一個仍可能隨時回來寫檔的 session，不是一個已經結束的 session。這種情況**一律 `UNDETERMINED`，
絕不判 `SOLE_OWNER`**。反過來說，門檻內的活動則升級為 `CONTENDED`。

腳本的 `--idle-threshold <secs>`（預設 900）只調整這條界線的位置，**不改變它的方向**：
調小會讓更多 session 落入 `CONTENDED`，調大會讓更多落入 `UNDETERMINED`；**任何設定值都不會
讓一個持有 lock 的 session 變成 `SOLE_OWNER`**。它是提疑慮的旋鈕，不是放行的旋鈕。

**3. 路徑要正規化，但正規化失敗不等於排除。** `workspace.yaml` 的 `git_root` 可能記成
`/Users/…/development/…`（小寫 d），而實際 physical path 是 `/Users/…/Development/…`。
在大小寫不敏感的檔案系統上這是同一個目錄。用 `/bin/pwd -P` 正規化；若路徑已不存在無法正規化，
退回原字串的大小寫不敏感比較，**且比中即視為 `UNDETERMINED`**（無法確認 ≠ 可以放行）。

### 覆蓋邊界（必須寫進每一份回報）

**只涵蓋 Copilot CLI session。VS Code chat session 偵測不到**——workspaceStorage 中指向本專案的
條目全部解析到 repository root，而不是個別 worktree，因此無法用它判斷誰在用哪個 worktree。

結論因此標為 `SOLE_OWNER (CLI-scope)`，而不是 `SOLE_OWNER`。**使用者確認閘門是後備**：
偵測不到不等於沒有。

### 為什麼未知不 fail-closed 成永久封鎖

`UNDETERMINED` 的語義是「停下來問人」。若把所有未知一律當成阻擋，任何一個沒有 `git_root`
記錄的無關 session（例如在別的專案目錄開著的 session）都會永久鎖死退役流程。
因此：**無 lock 的 session 不計入**，且 `UNDETERMINED` 可由使用者確認後解除。

---

## A2 — 未處理待辦

### `origin/main...HEAD` 是假陰性來源

V-M-D push 完成後 `HEAD` 等於 `origin/main`，`origin/main...HEAD` 恆為空集合。用它掃 TODO
會對**每一個真的出貨過的 campaign** 回報零待辦。commit range 必須由交接契約帶入的
`<base>..<head>` 決定；`base` 是 push 前的 `origin/main` tip。

**拿不到 base 就標 `not_checked`，不要退回三點形式，也不要輸出 `none`。**

### `not_checked` 與 `0` 是不同的主張

`0` 是「查過了，沒有」；`not_checked` 是「沒查」。只有前者支持退役。`RETIRE_CANDIDATE`
要求五個來源全部有數字。

**slug 解析不到 spec 目錄，屬於「沒查」。** 來源 1／2 必須先確認
`docs/specs/active/<slug>/`（或 `archive/<slug>/`）存在，再去讀 `tasks.md` 與敘事檔。
只判斷「檔案在不在」會讓一個打錯字的 slug 直接輸出 `spec_tasks=0`——實測
`publication-polcy`（少一個 `i`）曾把 24 筆未處理待辦報成 0。目錄不存在時輸出
`not_checked` 並計入 `not_checked_sources`。目錄存在但缺 `tasks.md` 才是真正的 `0`。

### 已移除的來源

session todo DB。實測 `~/.copilot/session-state/<id>/session.db` 只有 `inbox_entries` 一張表，
沒有 todo 資料，掃它永遠回報零。

---

## A5 — verdict 優先順序

硬阻擋（dirty / ahead / rebase 進行中 / `CONTENDED` / 已確認的待辦）**單獨即可判 `HOLD`**，
且優先於未知。未知只在完全沒有硬阻擋時才決定 `UNDETERMINED`。

這個順序有兩個用途：一個讀不到的來源永遠不會被誤當成乾淨通過；而一個明確髒掉的 worktree
也不會因為同時有未知項就被降級成「待確認」，掩蓋掉真正該修的東西。

---

## V-M-D → Closer 交接契約

四項參數：worktree registered path、campaign base SHA、pushed HEAD SHA、參與的 session id。
缺任一項 → 對應檢查標 `not_checked`。

V-M-D 端只新增一個 handoff，**Step 0.6 的既有前置條件不動**。理由：結案記錄本身要先進
`origin/main`，Step 0.6 原本就已經要求這件事，改寫它只會製造兩份互相漂移的規則。

---

## Anchor（`oneoff_campaign_anchor.py`）

**這個檔案不修改。** 它有測試契約保護：record 不得出現 `anomalies` 欄位，模組不得
`import detectors` 或 `import analyze`，且不得碰網路或資料庫。

### CLI transcript 需要 symlink staging

generator 的 `locate_transcript()` 找的是 `<session-id>.jsonl`，而 Copilot CLI 寫的是
`<session-state>/<id>/events.jsonl`。用 symlink 搭橋，**`trap` 清理，用完即刪**：

```bash
stage=$( mktemp -d )
trap 'rm -rf "$stage"' EXIT
ln -s "$HOME/.copilot/session-state/<id>/events.jsonl" "$stage/<id>.jsonl"
```

`--transcripts-dir` 用 `rglob` 掃描且拒絕同名多檔，所以 staging 目錄必須只有這一個連結。

### 撞檔規則

generator 遇到**內容不同的既有輸出檔會拒絕覆寫**。因此：

* 一個 slice 一個 anchor 輸出路徑，路徑中帶 slice 識別（例如 session id 前綴）。
* **人工撰寫的結案記錄與 generated anchor 不得共用檔名。** 共用會讓其中一方無法產生，
  或讓人工內容被視為衝突。
* `--session-slice` 只接受一次，這是設計。跨 session 的 campaign 產生多份 anchor，
  **並列，不 rollup、不平均**。無法從單一 ledger 重算的彙總不是證據。

---

## Recovery capsule

移除之後，Freshness 六值再也無法重新觀測。capsule 是唯一的補償來源，**必須在移除前寫在
worktree 外**（寫在裡面會跟著被刪掉）。

必要內容：

1. Freshness 六值（branch tip、ahead、behind、dirty count、ignored artifact set、
   registered path 與 physical path）
2. 移除決策的 timestamp
3. 結案記錄檔的 repo-relative 路徑
4. registered path 與 branch
5. ignored artifact 的分類與 SHA-256

**回填必須冪等可續跑。** 「移除成功、回填中斷」是真實會發生的狀態：此時 worktree 已經不在，
記錄裡卻還寫著 `pending`。重跑的定義是——從 capsule 讀六值，只改記錄裡那一個表格區塊，
`git add <單一路徑>`，commit，push。**不得留下永久 `pending`。**

---

## Metrics（Stage 2，已凍結）

per-model / per-slice 的 token 與成本 index **本階段不做**。凍結理由：`assistant_usage_events`
全庫只有 3 個 session、140 列，且只涵蓋 CLI session，語料庫近乎空；DB 沒有 prune trigger，
**延後不會遺失任何資料**。

解凍前必須先完成：detectors 的 CLI 工具名正規化（`run_in_terminal` ↔ `bash`）、detectors
單元測試（現為零）、人工 precision / recall 校準、以及 anomaly 的切片與 boundary-context 契約。

解凍後的硬性限制（不得沿用早期草案）：

* **禁用 `turn_index` 切片** — 實測單一 session 的 92 列 usage 全部 `turn_index=1`，
  而該 session 有數十個 turn。切片軸只能用 `created_at` 時間窗。
* **成本一律取實測值**，禁止任何「費率卡 × token」推導。實測 opus-5 的 7.46M input 中
  6.84M 是 cache read，且 `request_multiplier` 在 15.0 / 3.0 / 1.0 之間跳動，推導必錯。
* **覆蓋率必須顯性**：usage 列數與 slice 內 assistant message 數並列（實測 92 vs 106）。
  靜默彙總即失真。
* **一列 = (session, slice, model, agent_role)**。單一 session 內同時有多個模型與 subagent，
  單一 `model` 欄無法表達。
* **品質計數不掛在模型 slice 上**。verification 與 correction 是 campaign 層級的 outcome，
  掛到個別模型上是歸因謬誤。
* **anomaly 不得進入 index**，不得作 model causal attribution，schema 不得新增
  `anomaly_count` / `quality_score` 或依 kind 加權的欄位。

---

## 腳本

`scripts/campaign-closeout-audit.sh` 自動化 Phase A。

* **唯讀**：不建檔、不動 ref、不 fetch。呼叫端必須在執行前自行
  `git -C '<worktree>' fetch origin main --quiet`，否則 ahead / behind 是對舊的
  remote-tracking ref 算的。
* Exit code：`0` RETIRE_CANDIDATE、`10` HOLD、`20` UNDETERMINED、`2` 用法錯誤。
* **禁止用 awk 做路徑欄位切分**。本 repo 的每一個路徑都含空格，欄位切分會把路徑截在第一個空格。
  一律 `sed` + 全程引號。
* `--session-state-dir` 可指向測試 fixture，用來迴歸驗證 idle-lock 與 PID 陷阱。
* 它是 **single-worktree probe，不是 inventory**。

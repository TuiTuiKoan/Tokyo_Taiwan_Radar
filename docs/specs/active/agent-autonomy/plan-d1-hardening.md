# D1 自動驗證閘門與排程修復計畫（#608、#614）

狀態：待實作。建立於 2026-11-10，由排程監控 agent（#592 每日監控）在第二天的檢查後規劃。
範圍：`.github/workflows/`、`scripts/tests/`、`scripts/ci/`。兩個 PR **陸續執行**，PR A 合併並驗證後才開 PR B。
建議模型：本計畫與評審用 Opus high；PR A、PR B 的實作用 Sonnet medium。

## 1. 為什麼要做

D1 證據工廠的目的是讓 heartbeat 在沒有網路的 sandbox 裡也能看到「production 真正發生了什麼」。現在這條證據鏈斷了，而且斷了兩次都沒有被任何自動檢查攔住。下面四項都是查證過的事實，不是推測。

### F1：`report` job 在一次改寫中被刪除

| commit | 日期（JST） | 對 `source-diagnose.yml` 做了什麼 |
| --- | --- | --- |
| `9fee8ec0` | 2026-11-07 18:15 | D5 草稿，新增 `scripts/ci/prod_log_excerpt.py` 與測試（#563） |
| `8b77bbc4` | 2026-11-07 18:15 | 依 plan-critique-2 G14 拆成 `diagnose` + `report` 兩個 job；只有 `report` 持有 `actions: read`、`issues: write`，並呼叫 `prod_log_excerpt.py` |
| `21d90d27` | 2026-11-09 00:22 | PR #600「加每日排程」改寫整個檔案（+80／−169 行），**`report` job 連帶被刪除** |

證據：11-08 的 source-diagnose run（`42474068192`）有 `diagnose` 與 `report` 兩個 job；11-09 的六個 run 只有 `diagnose`。`scripts/ci/prod_log_excerpt.py` 與 `scripts/tests/test_prod_log_excerpt.py` 都還在 `main`，但現在沒有任何 workflow 呼叫它。這是一次改寫造成的回退，不是刻意的設計變更——PR #600 的標題與內文都只談排程。

### F2：在被刪除之前，擷取就已經是空的

11-08 的 `report` job 結論是 success，`actions: read` 也在，但十張診斷留言的擷取段落都是「（取不到最近的 production log）」。那句話只在 `prod_log_excerpt.render()` 收到空的 `runs` 時出現，也就是 workflow 裡的 `ARGS` 陣列是空的。

`ARGS` 的三個填入條件各自被吞掉了錯誤：列 `scraper.yml` 的 schedule run 用了 `|| true`，查 `scrape` job id 用了 `|| true`，下載 job log 用了 `2>/dev/null`。所以 job log 裡只看得到腳本本文，看不到哪一步失敗、也看不到 HTTP 狀態。我在本 session 以同一組 API 呼叫驗證過：11-08 的 production run（`42445700331`）用 `.name == "scrape"` 查得到 job（`128624040637`），該 job 的 log 也下載得到（5,746 行）。所以不是查詢條件或 job 名稱寫錯，真正的原因要先讓它說話才能知道。

**推論**：這是「靜默失敗」的典型後果。修法的第一步不是猜原因，而是讓每個失敗點寫出具體理由。

### F3：沒有任何 CI 會跑 `scripts/tests`，改 workflow 的 PR 一個測試 job 都不跑

- `scraper-tests.yml` 只在 `pull_request` 且 paths 命中 `scraper/**` 時觸發，而且只跑 `scraper/tests`。
- repo 裡沒有任何 workflow 跑 `scripts/tests`（`test_prod_log_excerpt.py`、`test_pick_diagnose_targets.py`、`test_workflow_secrets.py`、`test_parent_rollup.py` 等十九個檔案），也沒有任何 workflow 以 `.github/workflows/**` 為 `pull_request` 的 paths。
- 實證：PR #600 的 head commit `c10951a2` 總共只有三個 check run——`Vercel Preview Comments`（success）、`auto-merge`（skipped）、`gitleaks`（success）。沒有 pytest，沒有 workflow lint。

**這是 F1 能進 `main` 的直接原因。** 既有的那些測試只在 agent 手動執行 `python3 -m pytest scripts/tests -q` 時才跑，而 AGENTS.md 把它寫成「提交前可跑」，不是閘門。

### F4：排程延遲，且有兩套機制在做同一件事

延遲（UTC；`scraper.yml` 作為對照）：

| workflow | cron | 11-08 | 11-09 | 11-10 |
| --- | --- | --- | --- | --- |
| `scraper.yml`（Daily Scraper） | `0 0` | 04:10（+4.2h） | 04:25（+4.4h） | 05:47（+5.8h） |
| `zero-output-recovery.yml` | `0 2` | 08:26（+6.4h） | 08:56（+6.9h） | 06:21 前未出現 |
| `source-diagnose-batch.yml` | `0 4` | 11:03（+7.0h） | 12:33（+8.5h） | 06:21 前未出現 |

三個 workflow 都延遲，延遲量隨排定時間遞增，所以這是 GitHub 排程整體的壅塞，不是這兩個檔案設定錯誤。所有已完成的 run 結論都是 success。

另外，`source-diagnose.yml` 自己有一條 `30 3 * * *` 的 schedule（用 `pick_diagnose_targets.py` 自選目標，由 PR #600 加入），而 `source-diagnose-batch.yml` 的 `0 4` 也在挑同一批 issue 並逐張 dispatch `source-diagnose.yml`。11-09 兩者都跑了：11:56 UTC 的 schedule run 診斷了 #493–#499，12:33 UTC 的 batch 又 dispatch 了 #501–#506，當天診斷十張，是設計上限的兩倍。batch 的功能是 schedule 模式的超集（它還處理 `needs-diagnosis` 請求、把 `HOME_IP_ONLY` 來源轉 `needs-human`、一張 issue 一個 run 併行跑），所以要留的是 batch。

## 2. 不做什麼

- 不改 `scraper.yml`，不碰任何 production 寫入路徑。
- 不把新的 CI job 設成 required status check：那是 repo ruleset，屬人類關卡。
- 不自己合併 PR，不推 `main`。
- 不在這個計畫裡追查 F2 的根因。先讓它說話（PR A），再依它寫出的理由處理；若 PR A 合併後的第一次 dispatch 就正常，F2 就是 `report` job 被刪以外的暫時性問題，記錄後結案。

## 3. PR A（先）：自動驗證閘門 ＋ 還原 production log 證據

兩件事放在同一個 PR，因為閘門若不先存在，PR A 自己的修復也沒有測試保護；而閘門的第一個用例正是 F1 這個回退。

### A1 — 新增 CI 閘門

新增 `.github/workflows/ci-checks.yml`：

- 觸發：`pull_request`，paths 含 `scripts/**`、`.github/workflows/**`、`.github/agents/**`、`.github/skills/**`、`.claude/**`；外加 `workflow_dispatch`。
- 權限：`contents: read`，無 secrets（照 #561 的規矩，PR 的程式不碰憑證）。
- 步驟：
  1. `python -m pytest scripts/tests scripts/claude/tests -q -p no:cacheprovider`
  2. `python3 scripts/sync_ai_adapters.py --check`
  3. actionlint——**第一版只檢查這個 PR 改動到的 workflow 檔**（`git diff --name-only` 對 base），版本固定（pinned），不對既有四十餘個 workflow 全掃。理由：全掃很可能一次冒出大量既存問題，會把這個 PR 變成大掃除；全掃留作後續 issue。
- `concurrency` 以 PR 號分組，`cancel-in-progress: true`。

這一步補上的是「改 `scripts/` 或 `.github/` 的 PR 會跑測試」這件事本身，影響範圍比本次兩個 issue 大：它讓 `scripts/tests` 裡既有的十九個檔案從手動變成閘門。

### A2 — 新增 D1 契約測試

新增 `scripts/tests/test_d1_workflow_contract.py`，用 `yaml.safe_load` 讀 workflow（照 `test_workflow_secrets.py` 既有寫法，注意 PyYAML 把裸鍵 `on` 讀成 `True`）。斷言：

1. `source-diagnose.yml` 必須有名為 `report` 的 job。
2. `report` job 的 `permissions` 必須含 `actions: read` 與 `issues: write`。
3. `report` job 必須有一個步驟呼叫 `scripts/ci/prod_log_excerpt.py`。
4. `diagnose` job 不得持有 `issues: write` 或 `actions: read`（維持 untrusted 隔離：跑外部網站程式的 job 不該能寫 issue）。
5. `source-diagnose.yml` 不得有 `schedule`（batch 是唯一排程入口，見 A3）。
6. `zero-output-recovery.yml` 與 `source-diagnose-batch.yml` 的 cron 分鐘欄不得是 `0` 或 `30`。

第 6 條只斷言這兩個檔案，其餘四十餘個 workflow 的 cron 另開 issue，避免一次擋住全部。

**cron 分鐘的修改必須在 PR A 一起做（A4），不能留到 PR B。** 初稿把它排在 PR B 是錯的：那兩個檔案現在的分鐘都是 `0`，而 A5 要求 PR A 的契約測試全綠、PR B 又必須等 PR A 合併，PR A 於是過不了自己的閘門。縮小斷言範圍不能解決，因為失敗的正是這兩個檔案。（2026-11-10 Codex 評審 P2 指出；PR #619 review comment `4524048127`。）

### A3 — 還原並強化 `report` job

1. **先移除 `source-diagnose.yml` 的 `schedule`**（F4）。這一步不只是去重：移除之後 `inputs.sources` / `inputs.issue` 回到「一個 run 對一張 issue」的單一契約，`8b77bbc4` 的 `report` job 就能近乎原樣還原，不必為了多組 (source, issue) 配對重寫。`EVENT = schedule` 的分支一併刪除。
2. `scripts/pick_diagnose_targets.py` 與它的測試保留（batch 日後若要改用可以直接接），在 docstring 註明目前沒有 workflow 呼叫它，避免下一個人以為它還在線上。
3. 還原 `diagnose` / `report` 兩個 job 的拆分，連同 `8b77bbc4` 的註解區塊（它記著為什麼要拆、為什麼留言要壓在 60,000 字以內、為什麼 `main.py` 吞例外後 exit code 不可信）。
4. **讓擷取路徑會說話**：把三個 `|| true` / `2>/dev/null` 換成「記下原因再繼續」。每一種失敗在留言與 step summary 裡寫出具體一行，而不是只留「取不到最近的 production log」：
   - 列不到 `scraper.yml` 的 schedule run（寫出 API 的 HTTP 狀態）
   - 列到 run 但查不到名為 `scrape` 的 job（寫出 run id）
   - 查到 job 但 log 下載失敗（寫出 job id 與 HTTP 狀態）
   - 下載成功但 log 裡沒提到這個來源（這條原本就有，保留）
5. 保留原有的安全性質：`diagnose` 只有 `contents: read`、不帶 secrets、產出一律當 untrusted；`report` 從預設分支 checkout `scripts/ci`、重新清洗上傳的摘要、60,000 字上限、擷取先被砍。

### A4 — cron 分鐘移開整點

把 `zero-output-recovery.yml` 與 `source-diagnose-batch.yml` 的 cron 分鐘從 `0` 移開（依 AGENTS.md 的 jitter 習慣，例如 `17 2`、`43 4`）。兩行編輯，沒有行為風險，和 PR B 的 `workflow_run` 彼此獨立。

放在 PR A 的理由有兩個：A2 第 6 條的契約測試要有東西可驗（見上），而且「測試和它測的東西在同一個 PR」本來就是這次回退給的教訓。這一步單獨不會根治延遲（F4 顯示延遲是整體性的），只是避開整點高峰。

### A5 — PR A 的驗證

| 層 | 做什麼 | 什麼時候 |
| --- | --- | --- |
| 本機 | `python3 -m pytest scripts/tests scripts/claude/tests -q`、`sync_ai_adapters.py --check`、actionlint 跑改動檔 | 推之前 |
| PR | A1 的新 job 必須綠（它會跑 A2 的契約測試） | PR 上 |
| 合併後 | 手動 dispatch 一次 `source-diagnose`，指定一個已診斷過的來源、**不帶 issue**（只看 step summary，不污染 issue），確認 production log 段落有內容或有具體理由 | 合併後當天 |
| 回報 | 把 step summary 的結果貼回 #608；若有內容就關閉 #608，若是具體理由就依那個理由續修 | 同上 |

NOT TESTED（要寫進 PR body，附具體理由，不寫籠統的「缺憑證」）：`report` job 在 runner 上讀 `actions` API 的實際權限行為，只能在合併後以預設分支的身分 dispatch 才驗證得到；PR 分支上的 workflow 檔不會以排程事件的身分執行。

## 4. PR B（後）：排程穩定

**前提**：PR A 已合併，且 A5 的合併後驗證做完。cron 分鐘已在 PR A 改掉（A4），所以 PR B 只處理觸發方式。

### B0 — 先決定要不要保留 cron（使用者裁決）

下面 B1、B2 的設計是「`workflow_run` 事件驅動 ＋ cron 保底 ＋ 去重閘」。這個組合在評審中被連續挑出四個缺陷（見 B2 末段），全部來自「兩條觸發路徑要對同一次爬蟲達成一致」這件事。複雜度幾乎都是 cron 保底帶來的，所以在實作前先把簡化選項擺出來：

| 選項 | 內容 | 代價 |
| --- | --- | --- |
| **甲：只留 `workflow_run`** | 拿掉兩個 workflow 的 cron，完全由 Daily Scraper 完成事件驅動。不需要去重閘 | 事件沒觸發的那天就不會跑；靠 #592 的每日監控抓到（那正是監控存在的理由） |
| **乙：只留 cron** | 不加 `workflow_run`，只做 PR A 已完成的「分鐘移開整點」 | 延遲問題只緩解不解決（F4 顯示延遲是整體性的） |
| **丙：事件 ＋ cron 保底** | 就是 B1、B2 | 去重閘的四個缺陷，以及日後每次改動都要維持兩條路徑一致 |

**這是人類關卡**（排程行為與配額），由使用者裁決，agent 不自己選。使用者沒有指定時，建議選**甲**：它把「沒跑到」這件事交給已經在運作的監控，而不是交給一套必須自己維持一致性的機制。選甲就跳過 B2，B1 只留事件觸發那一半。

### B1 — 改成事件驅動，cron 留作保底

`zero-output-recovery.yml` 與 `source-diagnose-batch.yml` 各加 `workflow_run`（`workflows: ["Daily Scraper"]`、`types: [completed]`），並保留 cron 作為「workflow_run 沒觸發」時的保底。兩者本來就假設自己在每日爬蟲之後跑，改成事件驅動之後順序有保證，也不再被 cron 壅塞影響。

順序問題（recovery 應該在 batch 之前，否則 batch 會診斷到 recovery 稍後要關閉的 issue）有兩個選項：

- **串接**：只有 recovery 掛 `workflow_run`；recovery 跑完以 `workflow_dispatch` 叫 batch，並把**原始 Daily Scraper 的 run id 當成 input（`scraper_run_id`）傳下去**。用 dispatch 而不是讓 batch 也掛 `workflow_run`，一是順序確定，二是不必去賭 GitHub 對 `workflow_run` 連鎖的限制。recovery 的 job 要加 `actions: write`（batch 的 `dispatch` job 已經有）。
- **並排**：兩者都掛 Daily Scraper，接受「batch 可能診斷到 recovery 稍後會關閉的 issue」這個小浪費。batch 在自己執行時重新列 open issue，所以最壞情況是多做一次診斷，不是壞資料。

採**串接**，因為並排雖然簡單，卻讓 batch 的去重 key 和 cron 的不一致（見 B2 的第三次修正）。

### B2 — 去重閘（cron 保底的必要條件）

**「加 `workflow_run`、cron 留著保底」單獨寫出來是錯的**：兩個觸發都正常時會每天跑兩輪，正好重現 F4 要消掉的處理量翻倍。現有的 `concurrency`（兩個 workflow 都是 `cancel-in-progress: false`）只防同時執行，不防同一天處理兩次；而第二輪不會空轉——batch 只跳過「已經有診斷留言」的 issue，所以它會接著挑下一批五張，recovery 的 `MAX_CLOSE=5` 也只是單次執行的上限。（2026-11-10 Codex 評審 P2 指出；PR #619 review comment `4524048136`。）

所以 cron 保底必須配一道去重閘，作為兩個 workflow 的第一個步驟。去重的鍵是「這一次的 Daily Scraper run id」，而且必須是**實際處理過的紀錄**，不能用「有沒有兄弟 run 存在」去推論：

**target 一律是原始 Daily Scraper 的 run id**，三個觸發來源都要收斂到同一個值，否則兩條路的 key 不同、去重等於沒有：

1. 決定這次要處理的 production run（target）：
   - `workflow_run` 觸發（只有 recovery 會收到）→ 用上游的 `github.event.workflow_run.id`；`conclusion` 不是 `success` 就 `exit 0`。
   - `workflow_dispatch` 帶 `scraper_run_id`（batch 被 recovery 串接叫起來時）→ 用這個 input，先驗證它只有數字。**不可以用 `github.event.workflow_run.id`**，那會是 recovery 自己的 run id。
   - `schedule` 觸發 → 取最近一次 `scraper.yml` 的 schedule run。它**還沒 completed 就 `exit 0`**（今天的爬蟲還在跑，交給事件觸發），completed 才取它的 id。
2. 查這個 target id 有沒有處理紀錄；有就 `exit 0`，並在 step summary 寫明是哪一個 run id 已經處理過。
3. 處理完成後才寫下「已處理 target id」的紀錄。

紀錄用 Actions cache，key 形如 `<workflow>-processed-<target_run_id>`（`actions/cache/restore` 查、成功後 `actions/cache/save` 寫）。實作時先確認 cache 在 job 的 `permissions` 下寫得進去；寫不進去就改用具名 artifact，`gh api "repos/<repo>/actions/artifacts?name=<workflow>-processed-<target_run_id>"` 可以跨 run 查詢。兩種都不需要新服務。

**紀錄名稱一定要帶 workflow 命名空間**，cache key 與 artifact 名稱都要。初稿的 artifact 備援寫成 `processed-<id>`，少了命名空間：串接順序下 recovery 先寫下這個 Daily Scraper target 的紀錄，batch 接著查同一個名稱就會把 recovery 的紀錄當成自己已處理而整輪略過，一張診斷都不會 dispatch。cache key 本來就有隔離，備援路徑漏掉就等於兩條路行為不一致。（2026-11-10 Codex 評審 P2 指出；PR #619 review comment `4524751383`。）

**初稿的寫法是錯的**：原本第 2 步只比對「自己有沒有在 T 之後建立的 run」，把「run 存在」當成「已處理」。Codex 的反例成立——Daily Scraper 00:00 建立、03:00 完成，recovery 的 cron 02:17 執行：cron 當時取得的是前一天的 completed run，而「T 之後建立的自己的 run」會命中前一天的執行而跳過；03:00 事件觸發時 T 變成今天，卻會看到 02:17 那個 cron run 而同樣跳過，當天沒有人處理。改成上面的版本後兩個方向都成立：02:17 的 cron 看到今天的 run 還沒 completed 就讓位，03:00 的事件觸發查 target id 沒有紀錄就處理。（2026-11-10 Codex 評審 P2 指出；PR #619 review comment `4524114217`。）

**第三次修正**：串接方案下，batch 收到的 `workflow_run.id` 會是 **recovery 的** run id，不是 Daily Scraper 的，而 cron 路徑從 `scraper.yml` 取 target——兩條路的 key 不同，事件觸發做完之後 cron 仍會判定沒處理過，再 dispatch 下一批，翻倍問題原封不動回來。所以改成 recovery 以 `workflow_dispatch` 把原始 run id 傳給 batch（B1），batch 用那個 input 查寫紀錄。（2026-11-10 Codex 評審 P2 指出；PR #619 review comment `4524152683`。）

去重的鍵用 run id 而不是日期，是因為 Daily Scraper 本身會延遲跨日（F4 的 11-10 是 05:47 UTC），用日期會在跨日那天失效。第 1 步查 `scraper.yml` 的 run 需要 `actions: read`，`zero-output-recovery.yml` 的 job 目前沒有，要補。

**複雜度警訊**：這道去重閘到這裡已經被改了四次（要有去重 → 用處理紀錄而非兄弟 run 推論 → 串接時 target 收斂 → 紀錄名稱要帶 workflow 命名空間），每一次都是同一類錯誤：兩條觸發路徑、或主備兩種紀錄方式，對「這一輪是哪一次爬蟲、是誰處理的」認定不一致。這本身就是「cron 保底」這個決定帶來的成本，而且成本還在累積。實作 PR B 之前先看 B0 的兩個簡化選項（甲、乙），不要預設一定要保留 cron。

### B3 — PR B 的驗證

- 去重閘加單元測試（選丙才需要），五個案例都要有：target id 已有紀錄 → skip；沒有紀錄 → proceed；`schedule` 觸發但最近一次 Daily Scraper 還沒 completed → skip（讓位給事件觸發）；`workflow_run` 觸發但上游 `conclusion` 不是 `success` → skip。第三、四個案例是初稿漏掉的兩個方向；第五個是「`workflow_dispatch` 帶 `scraper_run_id` 時，target 與 cron 路徑算出的是同一個 id」。
- 合併後觀察三天，由 #592 的每日監控留言記錄實際延遲。**通過判準**：`workflow_run` 觸發的 run 在 Daily Scraper 完成後一小時內出現，且每天只有一輪實際執行（另一個觸發的 run 存在但被去重閘 skip）。
- **回退判準**：連續三天 `workflow_run` 都沒觸發 → 把 `workflow_run` 拿掉、回到純 cron，並在 #614 寫明觀察結果。

## 5. 風險

| 風險 | 處理 |
| --- | --- |
| `workflow_run` 連鎖深度限制 | B1 已寫兩條路；實作時先查文件再決定，不假設可以連鎖 |
| actionlint 對既有 workflow 噴大量既存問題 | A1 第一版只掃 PR 改動到的檔案；全掃另開 issue |
| 新 CI job 讓改 `.github/` 的 PR 變慢 | 預估一兩分鐘，可接受；A1 開 `cancel-in-progress` |
| A2 第 6 條一次擋住其他四十個 workflow 的 cron | A2 已限定只斷言本 spec 的兩個檔案；其餘另開 issue |
| PR A 過不了自己的契約測試（cron 分鐘還沒改） | cron 分鐘改到 PR A（A4）。初稿把它排在 PR B 才會有這個矛盾 |
| `workflow_run` 與 cron 都觸發，每天跑兩輪 | B2 的去重閘，鍵是 Daily Scraper 的 run id；沒有這道閘就不要保留 cron |
| 去重閘反而讓某一天完全沒處理 | 去重必須看「實際處理紀錄」，不能用「兄弟 run 存在」推論；cron 遇到還沒 completed 的爬蟲要讓位。初稿兩邊都踩到，見 B2 末段 |
| F2 的根因可能不在這三個失敗點 | A3 第 4 項讓它寫出理由；若四種理由都不符，再依留言內容另開 issue，不在這個計畫裡猜 |

## 6. 人類關卡

- 兩個 PR 都改 `.github/workflows/`，PR Tier 會貼 `tier:1` 或 `tier:2`，由使用者按合併鍵。agent 不執行 `gh pr merge`。
- 把 A1 的新 job 設成 required status check 需要改 repo ruleset，不在本計畫內；若要做，由使用者在 GitHub 設定。
- **B0 的甲／乙／丙由使用者裁決**：排程行為與配額屬人類關卡，agent 不自己選。沒有指定時 PR B 不開始。

## 7. 追蹤

- #608（診斷留言缺 production log）由 PR A 處理。
- #614（排程延遲）由 PR B 處理。
- 每日進度看 #592 的監控留言；里程碑打勾在 `tasks.md`，細項開 issue 貼 `spec:agent-autonomy`。

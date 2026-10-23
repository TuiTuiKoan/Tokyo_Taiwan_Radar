# 沒有 `spec:` 標籤的開放 issue 盤點（2026-10-23）

這是 feature kickoff（notes.md §16.4 第 1 段）第一次對真實資料的使用結果。**只是盤點與建議，沒有對任何 issue 貼標籤、留言或編輯。** 歸屬由使用者決定。

來源：`python3 scripts/feature_kickoff.py --inventory`（本機實測，唯讀 `gh issue list`）。開放 issue 共 76 個，其中 47 個已有 `spec:<slug>` 標籤（13 個 spec），29 個沒有。

## 限制（先讀）

- 分群只依**標題與既有標籤**，我沒有逐一讀內文；「建議歸屬」是推論，不是確認。
- 這是 2026-10-23 的快照，issue 狀態會變；使用前請重跑腳本。
- 已有標籤但標在「別的 spec」上的 issue 不在本表（例如 `spec:ai-portability-followups` 的 5 個），也不代表它們歸屬正確。

## 分群與建議

| 群 | issue | 一句話 | 建議歸屬 | 依據與不確定 |
|---|---|---|---|---|
| 新來源接入 | #26、#41、#42、#43、#268、#289 | 各是「新增一個來源」 | 維持以 `source-intake` 標籤管理，不必建 spec | 已有 `source-intake` 標籤；一個 issue 一個來源，彼此獨立，適合各自平行（但共用 `SCRAPERS` 清單，必須串行合併，見 git.instructions.md） |
| 來源產出為 0 | #367、#375、#376、#377、#381 | 多個來源連續 0 產出，原因各異 | 新 spec `scraper-zero-output`，或掛到既有 worktree `fix/scraper-zero-output` 的 spec | 本機有 worktree `ttr-scraper-zero-output-worktree`（分支 `fix/scraper-zero-output`），但我沒找到對應的 spec 目錄，是否已有 spec 未確認 |
| 爬蟲管線與守門缺陷 | #364、#394、#395、#398、#404、#407 | 敘述規則不一致、誤入庫、手動執行過慢、FC guard 放行、登記失敗、缺失敗告警 | 可併入上一群，或獨立成 `scraper-pipeline-hardening` | 都在 `scraper/` 與排程；#407 是營運告警，與其他不同類 |
| QA Heartbeat 文件與功能 | #106、#107、#108、#109、#111 | 2026-05 開的 QA Heartbeat 文件與評估項 | 先決定這條線還要不要（#330 已提議把 5 月後沒更新的 active spec 降級） | 5 個都停在 2026-05-25／26，近 5 個月沒更新；是否仍有效未確認 |
| 治理與工具 | #328、#346、#315、#330、#332 | worktree 集中與狀態腳本、pre-push gitleaks 漏洞、runner 固定、stale spec、system-map 漂移 | #328 與 #346 很可能屬於 **ai-harness**（worktree 治理、hooks）；#330、#332 屬 `workstream-tracking` 或 `spec-architecture-dashboard`；#315 屬 CI | #328、#346 由關鍵字 `worktree`／`pre-push` 找到；#346 也可能屬於 ai-portability 的後續項目，未確認 |
| 產品與後台 UI | #342、#351 | X 發文規劃；後台與 UI 的 4 個小項 | 各自獨立 | #351 在 `worktree` 關鍵字搜尋中出現，是**誤判**（內文碰巧含該字），不屬於 ai-harness |

## 使用者的決定（2026-10-23，追加）

- #328、#346：已貼 `spec:ai-harness`（用 `gh issue edit --add-label`，已驗證兩個 issue 的標籤）。其餘 issue 沒有被貼標籤。
- QA Heartbeat 的 5 個 issue（#106、#107、#108、#109、#111）：保留，不動。
- `scraper-zero-output` 是否建 spec、其餘 issue 的看板「階段」：見 notes.md §18，待決定。

## 建議使用者決定（原文，保留）

1. 是否要把 #328、#346 貼上 `spec:ai-harness`（建議先讀內文再決定；#346 可能屬 ai-portability 後續）。
2. `scraper-zero-output` 是否要建立 spec（目前只有 worktree 與 issue）。
3. QA Heartbeat 的 5 個 issue：保留、併入、或關閉。
4. 其餘群維持現狀即可；`source-intake` 已有標籤，不需要新機制。

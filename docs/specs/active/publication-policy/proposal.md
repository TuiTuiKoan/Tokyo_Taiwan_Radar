---
slug: publication-policy
title: 純出版紀錄資料政策與公開呈現一致化
description: 以 exact publication form 統一出版資料寫入、QA、公開呈現與可回滾修復流程
status: active
branch: feat/publication-policy
created: 2026-07-11
tags: [publication, scraper, web, qa, data-policy]
---

## What（做什麼）

建立共用的 pure publication domain policy。只有正規化後 `event_form` 恰為
`["publication"]` 的紀錄才套用出版政策，並將 writer、annotator、QA、四個來源、
admin/account intake、Web 呈現、structured data 與 legacy repair 對齊同一 invariant。

## Why（為什麼）

現行流程以 source、category 或標題 placeholder 推定出版資料，導致實體 Talk 被誤判，
也讓地址、營業時間、都道府縣及活動料金語意在 DB、QA 與公開頁面反覆復生。
Writer 目前還會靜默移除 `publication` form，使來源契約無法可靠傳到下游。

## Invariants（不可變條件）

* Pure publication 僅由正規化後 exact `event_form == ["publication"]` 判定
* Source、`books_media` category、標題 prefix 與 placeholder 只能作 drift evidence
* Pure publication 保留 `start_date`、`end_date` 與真實書價作 metadata
* 七個 intentional-null fields 必須為 `NULL`，並以 empty sentinel FC 保護
* 七欄為 `location_address`、`location_address_zh`、`location_address_en`、
  `business_hours`、`business_hours_zh`、`business_hours_en`、
  `location_prefectures`
* Pure publication 的 publisher 必須保留追蹤；缺 publisher 不得由 QA 略過
* `source_url`、`official_url`、`organizer_url` 與 `location_url` 各自保留原本語意
* 實體出版 Talk、簽書會、講座、seminar、workshop 與 book launch 不得含
  `publication`，也不得套用 pure 隱藏或清理政策

## Design（設計摘要）

### Shared policy

Python 與 TypeScript 各提供語意一致的 event-form normalization、pure publication、
NDL periodical 與 presentation helpers。所有 writer、QA 與 UI 分支只呼叫這些 helper，
不在 call site 重建 source/category 判斷。

### Future writes

四個 publication-capable sources 產生正確 pure 或 physical forms。Database writer 保留
`publication`，在 entity enrichment、force-rescrape FC 套用與 location auto-lock 前後維持
intentional-null policy。Upsert 後七個 FC 必須 overwrite 為 `corrected_value = ""`，並以
read-back postcondition 驗證 event row 與 FC row。

Annotator 在所有 GPT、registry、prefecture 與 reviewed-fix 路徑完成後執行最終 pure
normalization。舊非空 FC 視為 manifest conflict，不可把 placeholder 恢復到 event row。

### QA and admin

Venue、hours、prefecture 與 event-price checks 只略過 pure publication。Publisher check
反向維持啟用。Reconcile 逐一判定所有 `report_types`，manual、unknown 或尚未解決的 compound
row 保持 pending。Admin quality 與 roadmap 使用同一 pure helper。

### Public presentation

共用 presentation flags 控制 detail、card、list、narrative、FAQ、Calendar、report fields 與
structured data。Pure publication 不公開 end、address、hours、price、status 或 calendar CTA。
普通出版輸出 Schema.org `Book`，NDL periodical 輸出 `Article`，physical event 保持 `Event`。

### Legacy repair

既有 `_oneoff_backfill_publication_metadata.py` 改為 immutable manifest 流程。Dry-run 全量
分頁讀取 events、field corrections、reports 與 organizers，記錄 before hash、分類 evidence、
planned action、excluded mixed rows、conflicts 與 rollback snapshot contract。Live apply 只能接受
既有 manifest 並逐列 drift/read-back，但本 spec 本輪不執行 live apply。

Eslite UUID identity 受 migration gate 保護。Daily scraper 在舊 identity 原子 remap 並驗證無重複
之前不得產生新 UUID identity。本輪只實作 gate、manifest action 與離線 fixture，不做 live remap。

## Release Waves（發佈波次）

### Wave 1（本次）

* Exact classification 與 future-write protection
* 七欄 NULL + empty sentinel contract
* Placeholder 移除、QA reconcile、admin metrics 與公開輸出一致化
* Deterministic publisher extraction 與既有 validated registry homepage 回填設計
* Immutable manifest dry-run、drift gate、snapshot 與 rollback 設計

### Wave 2（後續獨立批准）

* DuckDuckGo HTML publisher homepage search
* OpenAI search-preview fallback
* 獨立 manifest、成本上限、evidence report 與 Tester gate

Wave 2 provider 不在本輪 live 執行。Unresolved homepage 是合法結果，保持 `NULL`。

## Non-Goals（不做什麼）

* 不做正式 DB write、backfill apply 或 live QA reconcile
* 不執行 Eslite live source-id remap
* 不 live 呼叫 DuckDuckGo 或 OpenAI homepage search
* 不新增 DB migration
* 不清除 `end_date` 或真實書價 metadata
* 不 push、merge或 deploy
* 不修改、stash、reset 或 stage 主工作樹的其他 session WIP

## Acceptance（驗收摘要）

* Pure book 與 NDL periodical 在 DB/FC、QA、detail、card/list、FAQ、Calendar、report 與 JSON-LD
  都符合 pure policy
* `books_media` physical Talk 與 publication-capable source physical event 完整保留活動語意
* Writer new/force paths 都產生七欄 NULL 與七個 overwrite empty sentinels
* Annotator normal、reviewed-fix 與 re-annotate paths 都不能復生 pure 地址或時間
* Compound report reconcile 不會誤關 manual、unknown 或 missing-date 問題
* Manifest 包含所有 candidates、classification exclusions、conflicts、before state 與 rollback input
* 所有驗證在離線 fixture 或唯讀 DB 模式完成

## References

* Authoritative execution plan: `/memories/session/plan.md`
* `.github/instructions/git.instructions.md`
* `.github/instructions/scraper.instructions.md`
* `.github/instructions/web.instructions.md`
* `docs/specs/active/publication-policy/tasks.md`

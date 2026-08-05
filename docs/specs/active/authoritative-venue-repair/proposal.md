---
slug: authoritative-venue-repair
title: 權威場館解析與可回滾資料修復
description: 統一場館權威解析、TIFF 實體場館路由與 immutable CAS production repair
status: active
branch: feat/authoritative-venue-repair
created: 2026-08-06
tags: [scraper, venue, tiff, data-repair, cas]
---

## What（做什麼）

將固定場館資料統一收斂到 authoritative venue registry，修正 FK population、
seed desired state、TIFF act-to-cinema 路由，以及 Johakyu 與 Starcat 的固定場館資料。
同時建立 immutable manifest repair tool，讓既有 TCC、TIFF 與 Century 污染只能在
完整 before image、逐欄 CAS、逐筆 read-back 與兩個獨立批准閘門下修復。

## Why（為什麼）

現行 registry 會讓 canonical 與 alias 互相覆蓋，database alias lookup 又以
`limit(1)` 任選一筆。八丁座錯誤 aliases 因而和サロンシネマ collision，舊地址、
票務 URL 與品牌型 TIFF 場館也可能被傳播到事件。Production 尚有兩筆非權威 TCC
duplicate venues，分別保有 19 與 1 個 event references，無法直接刪除。

## Invariants（不可變條件）

* 只有 `is_authoritative = true` 的唯一命中可以提供 `venue_id` 與 canonical fields
* Canonical、alias、同 tier 與跨 tier collision 全部 fail closed
* Registry load failure 只 cache empty state，不保留 partial 或 stale cache
* Field corrections 永遠高於 registry，自動寫入不得覆蓋 human FC
* Pure publication 完全 bypass venue resolution
* Multi-venue event 不保存單一 physical FK 或 physical address
* `location_url` 只接受 registry 內經官方驗證的 stable facility homepage
* Ticket、schedule、event、submission、organizer 與 source URL 不得冒充 facility URL
* TIFF physical venues 按 act 首次出現順序去重，不得排序改變語意
* Unknown TIFF screen、venues fetch failure 或無法證明 physical venue 時跳過整部 film
* Production repair 只能接受 immutable manifest 的 exact-before CAS
* Duplicate venue 只能在 live references 精確為零時刪除
* Capture、apply 與 rollback 不得隱式互相切換

## Worktree and spec tracking

* Spec slug：`authoritative-venue-repair`
* Spec path：`docs/specs/active/authoritative-venue-repair/`
* Worktree：`ttr-authoritative-venue-repair-worktree`
* Branch：`feat/authoritative-venue-repair`
* State matrix：NEW
* Starting SHA：`origin/main@f3884eba`
* Cross-session truth：[`tasks.md`](tasks.md)
* Full execution truth：`/memories/session/plan.md`

Phase 0 已依 Git instructions 建立 registered worktree，並把精確 worktree path 加入
主 repository 的 `.git/info/exclude`。主工作樹仍停在 `c1183703`，九個既有 tracked
WIP 與 untracked governing prompt 均未被修改、stash、stage 或 clean。

## Verified baseline

### Official sources

2026-08-06 已從官方頁重新確認：

* [TCC official site](https://jp.taiwan.culture.tw/) 的虎ノ門地址與 facility root
* [Johakyu facility page](https://johakyu.co.jp/information.html) 的八丁座與
  サロンシネマ現址
* [Century facility page](https://eiga.starcat.co.jp/theater/century/) 的
  名古屋 PARCO 東館地址與 facility URL
* [Hulic access page](https://hulic-theater.com/access/) 的有楽町マリオン地址
* [TOHO Hibiya and Chanter access page](https://www.tohotheater.jp/theater/081/access.html)
  的 Chanter 與 screens 12/13 地址

高田世界館與 TIFF root 的直接 fetch 分別遇到 HTTP 429 與不可抽取內容。
Engineer 必須在改寫對應 homepage 前取得同網域官方證據；無法證明時停止該欄變更。

### Read-only production

唯讀 proxy 已封鎖 `insert`、`update`、`upsert`、`delete` 與 `rpc`，並確認：

* Supabase project ref 為 `cjtndektjjpvvjofdvzr`
* 31 個 explicit target events 全部存在
* 八個既有 target venue UUID 全部存在
* 三筆新 TIFF canonical venue names 全部不存在
* Authoritative venues 共 58 筆
* TCC canonical-linked events 精確為 29 筆，且相關 FC 無 human correction
* Japanese short duplicate 目前有 19 references
* Chinese short duplicate 目前有 1 reference
* 現有 authoritative collisions 恰為 `サロンシネマ` 與 `サロンシネマ1・2`
  同時映射到八丁座和サロンシネマ

這些 counts 只供 discovery。Production capture 必須重新查詢並以當下 live state 分類。

## Design（設計摘要）

### Registry and FK population

`scraper/venue_registry.py` 建立分離的 canonical/alias indexes、完整 collision reject set、
empty-on-failure cache 與 test reset helper。`scraper/database.py::_populate_entity_fks`
只查 authoritative candidates，完整讀取 alias matches，且只有唯一命中才傳播 FK、三語名稱、
地址、prefectures、stable homepage 與 fill-only hours。所有欄位先檢查 FC；ambiguous match
保持 unset 並輸出可測試 warning。

### Desired-state seed

`scraper/_oneoff_seed_authoritative_venues.py` 以 seed aliases 精確取代 live aliases，
不再 union stale values。全 seed canonical/alias preflight 在任何 write 前拒絕同 tier 與跨 tier
collision。Address compatibility 先正規化 NFKC、dash、whitespace 與 postal code，再比較
street number 與其餘地址。Dry-run 明確區分 insert、update、noop、conflict 與 skip。

### TIFF and fixed sources

`TiffScraper` 同年取得 films 與 venues APIs，遞迴 flatten venue tree，把 act screen 提升至
最近的 `type = "cinema"` parent，再交給 authoritative resolver。2025 offline fixture 是
parser contract；current-year unavailable 只算 graceful empty。Johakyu 更新兩館現址，
Starcat 只更新 Century 地址。TCC writer 不修改，只增加 regression tests。

### Immutable production repair

新增 `scraper/_oneoff_repair_authoritative_venues.py`。Default 與 capture 都是 read-only；
manifest 使用 exclusive create、canonical JSON、per-action digest 與 whole-manifest SHA-256，
保存完整 venue/event/FC before/after images、expected absence、dependency、eligibility、
action order、skips、conflicts 與 rollback state。

Event/FC actions 經 `qa_auto_fix.unlock_and_write()` 加 expected event/FC CAS。Venue actions
使用 full-row CAS 與 local journal。Apply 先全批 before gate，再依 venue、event/FC、invariant、
zero-reference duplicate deletion 順序執行。Rollback 只可手動選擇，並以 post-apply state
逆序 CAS。Partial state、額外 FC、不同 nonempty `submission_url` 或 human FC 一律停止。

## Canonical venue truth

既有 authoritative rows：

* 高田世界館 `1de8358d-f100-487d-aff3-cff7f686ae0a`
* TCC `4e010225-f963-4556-a439-2bc4a35afb12`
* TIFF multi entity `597eaa36-191b-48d4-9a34-cd7c128579f1`
* 八丁座 `10a9aa7a-f8e1-4721-9fd8-77af830b74d2`
* サロンシネマ `29fef1e9-67d1-457f-81a2-17b1d80437f8`
* センチュリーシネマ `e2f5fd1f-f92c-4e61-9f5f-383ac84c5d8b`

三筆新 TIFF physical venue 是ヒューリックホール東京、TOHOシネマズ シャンテ、
TOHOシネマズ 日比谷 スクリーン12・13。UUID 只能在 production manifest capture 時產生並
固定；code 與 spec 不預猜 UUID。每筆 insert 同時要求 UUID absence 與 canonical-name absence。

## Release gates

### Gate 1

Engineer 完成且獨立 Tester 明確 PASS 後，顯示 exact commits、changed paths、所有測試與
dry-run 證據、live drift、風險與 production 未 mutation 聲明，然後停止並取得本次 changeset
的明確 push 批准。初始 prompt 與實作批准不能替代 Gate 1。

### Gate 2

Gate 1 push 後，從已包含 feature commit 的 exact clean `origin/main` 只讀 capture manifest。
顯示 exact SHA、project ref、manifest path/digest、每個完整 UUID action、before/after、
dependencies、conflicts、三個新 UUID absence evidence 與 duplicate pre-delete counts，然後停止。
Production apply 批准必須綁定同一 digest，並明確涵蓋 writer pause/drain/resume、venue writes、
event/FC writes 與兩筆 duplicate 的 conditional deletion。新 digest 必須重新批准。

## Non-Goals（不做什麼）

* 不新增 migration 或修改 `supabase/**`
* 不修改 `web/**`、i18n、`scraper/main.py`、merger 或 geocoder
* 不修 event date、category、title、organizer、work、merge 或 active state
* 不在 code implementation 階段 capture manifest 或 mutation production
* 不在 Gate 1 前 push、merge或改動 main
* 不自動 rollback partial production write

## Acceptance（驗收摘要）

* Registry 對所有 canonical/alias collision fail closed，load failure cache empty
* Database 只有唯一 authoritative hit 才傳播完整 canonical fields，且 FC precedence 不回歸
* Seed 可移除 stale aliases，dry-run 正確辨識 noop，collision 與 active conflict 零寫入
* TIFF 2025 fixture 精確產生四部電影的單館或有序多館結果
* Johakyu 與 Century 使用官方現址，ticket URL 不進 `location_url`
* TCC writer regression suite 證明 external、multi-city 與 online 語意不被覆寫
* Repair tool 覆蓋 immutable digest、full CAS、review conflict、ordering、rollback 與 idempotency
* 全量 scraper tests、compileall、四 source dry-runs、diff check 與 scope assertions 通過
* Independent Tester 不得以 zero candidates 或 current-year TIFF empty 判 PASS
* Gate 1 前 production mutation 為零

## References

* [`tasks.md`](tasks.md)
* `/memories/session/plan.md`
* `.github/prompts/authoritative-venue-repair.prompt.md`
* `.github/instructions/git.instructions.md`
* `.github/instructions/scraper.instructions.md`

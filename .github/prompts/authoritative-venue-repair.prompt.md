---
description: "authoritative venue repair：隔離 worktree 實作與 production CAS 套用流程"
agent: Architect
---

# Authoritative Venue Repair

這是一項已核准開始實作的 Large feature。啟動本 prompt 即代表使用者批准開始實作，
不需要再次詢問是否要實作、是否接受架構或是否建立 worktree。自主執行到第一個即時批准
閘門為止，只有遇到本文件定義的 STOP 條件或無法安全判定的真實阻礙才停止。

本文件是新 session 的完整初始架構真值。不得把先前對話、舊 session 狀態或 invocation 前
已存在的 `/memories/session/plan.md` 當成輸入。先以本文件內容建立或完整覆寫新 session 的
`/memories/session/plan.md`，納入全部架構、scope、資料基線、驗證、批准閘門、spec slug
與 production protocol。完成 plan 寫入後不得只回傳計畫或等待計畫批准，立即依 Architect
protocol 委派 `Engineer` 實作。Engineer 完成後立即委派 `Tester`，不得只建議使用者自行點選
handoff。Tester FAIL 時，最多執行三輪 `Engineer` 修正後再由 `Tester` 重驗；第三輪仍未 PASS
就停止並回報，不得推送或進入 production。

## 執行真值與重新查證

* 開始時重新讀取 `.github/copilot-instructions.md`、相關 instructions，以及 Architect、Engineer、
  Tester 與 scraper-expert 的現行 protocol。以 repository 內當下版本為準。
* 重新查詢 git、worktree、branch、spec 與 live production DB。不得假設本文件撰寫時的狀態仍
  存在。
* 本文件列出的 counts、分類與現況是 planning baseline，不是可直接套用的 stale snapshot。
  如果 live state 漂移，重新 classification、重算 actions、產生新的 immutable manifest，
  並在摘要中清楚列出差異。
* 任何場館名稱、地址、alias、homepage 與來源映射都必須先向官方來源重新驗證。不得硬編未確認
  的值，不得以搜尋摘要、票務 URL、活動 URL、主辦方 URL 或舊 DB 值冒充場館官方來源。
* live DB 的所有前置調查在第二個即時批准閘門前只能唯讀。不得以 dry-run、測試、capture 或
  prompt 初始 invocation 作為 production mutation 授權。

## Worktree 與 spec

此工作固定分類為 Large feature，使用以下識別：

* Spec slug：`authoritative-venue-repair`
* Active spec path：`docs/specs/active/authoritative-venue-repair/`
* Worktree：`ttr-authoritative-venue-repair-worktree`
* Branch：`feat/authoritative-venue-repair`

Phase 0 必須先 fetch 最新 `origin/main`，再讀取
`.github/instructions/git.instructions.md` 的 `Isolated worktree for large / multi-session features`
章節，依其中 state matrix 判定 NEW 或 CONTINUING。使用
`git worktree list --porcelain` 驗證註冊狀態、實際路徑與 branch。branch missing、branch exists、
worktree mounted 三種情況各自使用 canonical state matrix，不得自行發明替代流程。若目標 path
存在但不是 registered worktree，立即 STOP 並回報，不得使用 `-f`、搬移、刪除或覆寫。

不得碰觸、stash、clean、stage、commit 或重排主工作樹任何既有 WIP。所有 feature 檔案、spec
更新、測試、commit 與 rebase 都在指定 worktree 內完成。依 git instructions 將 worktree path
idempotently 加入主 repository 的 `.git/info/exclude`。worktree 內 rebase 或 preview 前必須 clean，
不得使用 repo-wide stash。以 active spec 的 `tasks.md` 作為跨 session 進度真值，每完成一步就
更新並提交。

## 嚴格 scope

允許修改的範圍只有：

* 必要的 `scraper/` Python 實作
* 聚焦 tests 與 offline fixtures
* `docs/specs/active/authoritative-venue-repair/`
* 只有在本次實作確實產生可泛化教訓時，才更新必要的 scraper-expert `history.md` 與 `SKILL.md`

禁止事項如下：

* 禁止任何 `supabase/**` 變更或 DB migration
* 禁止任何 `web/**` 變更，包括 `web/messages/*.json`
* 禁止修改 `scraper/main.py` 或 `SCRAPERS`
* 禁止修改 merger 或建立一般用途 geocoding 行為
* 禁止修改事件日期、分類、標題名稱、organizer、work、merge 關係或 `is_active`
* 除本文件明列的 venue、event location、URL 與 field correction 修復外，不得擴張 production
  mutation 範圍

完成實作與每次 Tester 驗證時都要以 path assertion 檢查上述界線。若 diff 出現禁止路徑，先由
Engineer 移除越界變更，再重新驗證。

## 已核准架構

### Authoritative registry

修改 `scraper/venue_registry.py`，使 registry 僅讀取 `is_authoritative = true` 的 venues。
canonical 與 alias 的正規化索引都必須檢查 collision：同一 tier 內重複、canonical 對 alias、
alias 對 canonical，以及跨 tier collision 全部 fail closed，不得依查詢順序或第一筆結果決定。
registry load 發生任何 failure 時只 cache empty registry，不得保留 partial 或 stale cache。提供僅供
測試使用的 cache reset helper，並用測試覆蓋 load failure、collision 與 reset。

### Database FK population

修改 `scraper/database.py::_populate_entity_fks`：

* canonical 與 alias lookup 都只接受 authoritative venues
* 移除 alias query 的 `.limit(1)`，先取得完整候選集合
* 只有唯一 authoritative 命中時才填入 `venue_id`、canonical JA/ZH/EN name、fixed address、
  prefectures 與 stable venue homepage
* `business_hours` 維持 fill-only，且所有寫入都受 field corrections 保護
* multi-venue event 的 physical address 與 `venue_id` 必須為 null
* ambiguous lookup 必須保持 unset 並輸出可測試的 warning
* pure publication 必須 bypass venue resolution
* force-rescrape 仍由 field corrections 取得最高 precedence，加入明確 regression tests

不要把 `source_url`、`official_url`、`submission_url` 或 `organizer_url` 提升為 `location_url`。
只有 registry 中已由官方來源驗證的 stable venue homepage 可以填入 `location_url`。

### Authoritative venue seed

修改 `scraper/_oneoff_seed_authoritative_venues.py`：

* aliases 從 union merge 改為 tracked desired-state exact replacement，能移除 stale aliases
* 寫入前執行 canonical 與 alias 的同 tier、跨 tier collision preflight，任何 collision 都 fail closed
* 地址比較先移除 postal code，再比較 street number 與其餘 normalized address，避免郵遞區號造成假衝突
* dry-run 必須精確區分 insert、update 與 noop，不得把 noop 誤報為 update
* 保留真正的 active-event conflict guard，不得因 desired-state replacement 而放寬

### TIFF source

修改 `scraper/sources/tiff.py`，同年取得 films API 與 venues API。遞迴 flatten 完整 venue tree，
並將每個 act 的 screen ID 提升到最近的 `type = "cinema"` parent。unknown mapping、venues fetch
failure 或無法證明 physical venue 時跳過該 film，不得回退成 TIFF 品牌場館。

單一 physical venue 交給 authoritative resolver，必須綁定唯一 authoritative FK 與 canonical
location fields。多個 physical venues 依 act 首次出現順序去重，再以 `・` join canonical names；
`venue_id` 與所有 physical address 欄位保持 null，`location_prefectures` 設為 Tokyo。不得排序後
改變首次出現順序。`TiffJpScraper` news path 完全不變。current-year API unavailable 只驗證
graceful empty，不可當 parser PASS；2025 offline fixture 是主要 parser contract。

### Johakyu、Starcat 與 TCC

* Johakyu 更新八丁座與サロンシネマ的現址。兩個場館共用 `https://johakyu.co.jp/` 是合法的
  official facility homepage。
* Starcat 只更新 Century address。ticket schedule URL 只用於抓排片，facility homepage 必須來自
  authoritative registry。
* TCC source writer 不重寫，只新增能證明現行 writer 不會回歸覆寫的必要 regression tests。

## Canonical venue truth

以下值是核准的 planning baseline，但仍須在實作與 capture 前以官方來源重新驗證：

* 高田世界館 venue ID `1de8358d-f100-487d-aff3-cff7f686ae0a`，地址保留
  `新潟県上越市本町6丁目4-21`，homepage `https://takadasekaikan.com/`
* TCC canonical venue ID `4e010225-f963-4556-a439-2bc4a35afb12`，地址
  `東京都港区虎ノ門1-1-12 虎ノ門ビル2階`，homepage `https://jp.taiwan.culture.tw/`
* TIFF multi entity ID `597eaa36-191b-48d4-9a34-cd7c128579f1`，保留 authoritative 與
  `is_multi_venue = true`，address null，Tokyo，homepage `https://www.tiff-jp.net/`
* 八丁座 venue ID `10a9aa7a-f8e1-4721-9fd8-77af830b74d2`，地址
  `広島県広島市中区胡町6-26 福屋八丁堀本店8F`。aliases 必須移除 `サロンシネマ` 與
  `サロンシネマ1・2`
* サロンシネマ venue ID `29fef1e9-67d1-457f-81a2-17b1d80437f8`，地址
  `広島県広島市中区八丁堀16-10 広島東映プラザビル8階`
* Century venue ID `e2f5fd1f-f92c-4e61-9f5f-383ac84c5d8b`，地址
  `愛知県名古屋市中区栄3-29-1 名古屋パルコ東館8F`，homepage
  `https://eiga.starcat.co.jp/theater/century/`

新增三筆 TIFF physical authoritative seeds：

* `ヒューリックホール東京`，地址 `東京都千代田区有楽町2-5-1 有楽町マリオン11F`，homepage
  `https://hulic-theater.com/access/`
* `TOHOシネマズ シャンテ`，地址 `東京都千代田区有楽町1-2-2`，homepage
  `https://www.tohotheater.jp/theater/081/access.html`
* `TOHOシネマズ 日比谷 スクリーン12・13`，地址
  `東京都千代田区有楽町1-1-3 東京宝塚ビル地下1F`，homepage 使用同一個 TOHO access URL

三筆新 venue UUID 不得在 code 或 spec 中預先猜測。production manifest capture 時生成並固定，
manifest 寫入後不得變更。每筆 insert 前要同時驗證該 UUID 不存在且 canonical name 不存在；任一
條件不成立都視為 drift 或 already-applied classification，不得盲目 insert。

## TIFF 2025 fixture contract

2025 offline fixture 必須精確驗證：

* `木々の隙間` 只路由到 Chanter
* `エイプリル` 路由到 Hulic、Chanter、Cineswitch
* `ダブル・ハピネス` 路由到 Hibiya screens 12/13、Cineswitch
* `人生は海のように` 路由到 Chanter、Hibiya screens 12/13、Cineswitch

測試要驗證單一 venue FK、multi venue 順序、joined names、null address/FK、Tokyo prefecture，
以及 unknown screen 與 venues fetch failure 時整部 film 被跳過。

## Production repair tool contract

建立 `scraper/_oneoff_repair_authoritative_venues.py`。default invocation 必須 read-only，並提供
互斥的 `capture`、`apply`、`rollback` 三種 mode。任何 mode 都不得隱式切換到另一種 mode。

### Immutable manifest

`capture` 只能唯讀 production DB，並以 exclusive-create 語意建立 immutable JSON manifest。
manifest 至少包含：

* manifest schema version、capture timestamp 與 Supabase project ref
* 已確認存在於 `origin/main` 的 exact repository SHA
* 每個 action 的完整 UUID、action type、dependency、eligibility 與 action digest
* 每個 venue、event 與 FC action 的完整 before image 與完整 after image
* event 的完整相關 FC rows；預期不存在時也要記錄明確 absence
* expected CAS state、rollback expected state 與 action 執行順序
* review conflicts、skips、already-applied actions 與其證據
* 整份 manifest canonical bytes 的 SHA-256 digest

capture 完成後不得就地更新、補值或重新排序 manifest。需要重新查詢或遇到 drift 時，產生新的
manifest 與新 digest，舊 manifest 保持不變。dry-run 或 capture 必須自行驗證 before image，
不得等到 apply 才發現缺欄位。

### Event 與 field correction CAS

Event 與 FC 寫入必須使用 `qa_auto_fix.unlock_and_write()`，再加上 expected event/FC CAS 與逐筆
read-back。null 使用 repository 既有 empty sentinel，array 使用 JSON encoding。保留所有無關 FC，
不可先刪整個 event 的 corrections。若任何相關 FC 的 `corrected_by IS NOT NULL`，或 event 有
conflicting nonempty `submission_url`，該 action 一律分類為 `review_conflict`，不得自動寫入。

每個 event action 都要比較 manifest 的完整 expected event fields、相關 FC rows 或 absence，只有
exact match 才能 mutation。寫入後立即 read-back event 與 FC，驗證 exact after state。已完整符合
after state 時可判定 already-applied 並保持 idempotent；部分符合、before 漂移或額外 conflicting FC
一律 STOP。

### Venue row CAS

Venue update 與 delete 使用獨立 full-row exact-before CAS 與 local journal，不得經 event FC helper。
Venue insert 必須同時確認 ID absence 與 canonical name absence。Venue delete 必須擁有完整 before
image，並在執行當下確認所有 event references 為零。venue row 已完整符合 after state時視為
already-applied；任何 partial match 或 drift 都 STOP。

### Apply 與 rollback ordering

`apply` 固定順序如下：

1. 重新驗證 project ref、exact repo SHA、manifest SHA-256、action digests 與全部 before CAS。
2. update 或 insert venue rows。
3. 套用 event 與 FC actions。
4. 驗證所有 event、FC、venue 與 reference invariants。
5. 只有兩筆 TCC duplicate venue 的 references 都為零時才 delete duplicates。
6. 寫入 final local journal，保留每個 action 的 read-back 與結果。

`rollback` 必須逆序執行，且每一步先以 manifest 的 post-apply state 作 exact CAS。rollback mode 不得
在 main workflow 自動執行；若 apply 失敗，需要先顯示 journal 與 live state，再取得明確 recovery
批准。不得用 rollback 掩蓋 partial mutation 或在未知 drift 上強寫。

## TCC production classification baseline

所有 IDs 都要在 capture 時以 live DB 重新查證、取得完整 before images、檢查相關 FC，並依最新
狀態重新分類。

### Canonical migrate 與 attach

目前規劃為 canonical migrate 的 6 筆 events：

* `8c94aaff-cb37-4f57-a135-6e141103116b`
* `3f56d510-d9e1-4fb2-bd4f-335df4e30965`
* `6e0ebbc0-4c08-463a-a46b-9a047587be97`
* `2aa24af5-c945-4727-ba37-8e943d6dc570`
* `35a9f571-0c79-46a5-8065-5019d8e96f46`
* `83a05243-bdc4-467e-bc7b-6ad7028dbf07`

目前規劃為 attach canonical FK 與 fields 的 3 筆 events：

* `744fb475-1107-45e8-a193-a4ae676110fe`
* `bf420307-5a31-469c-8144-38ea3a7b6f00`
* `0fb1e608-8c8e-4024-86fa-33c4145b034c`

### Japanese short duplicate

Japanese short duplicate venue ID 是 `e87b461e-8e8d-4fa0-b461-22a7ff2b6fdd`。

解除 historical attribution 的 3 筆 events：

* `6236f51f-d53a-46eb-b392-8536cf842ab2`
* `b9a1eb56-32bf-4f1c-b552-207e8f7379c4`
* `07597d1e-71ae-45d4-8d03-9e61bcfb2b00`

解除 false attribution 的 8 筆 events：

* `10d8bcb3-a237-4344-9213-0e7bde732d0d`
* `cb0f58dc-6110-4c9c-b16d-c347e0b31360`
* `8355f633-1383-43c0-81f2-227199ed23fe`
* `c14dc455-dc04-4337-8fe1-a6fe648f4718`
* `18aa3c4b-8439-4ba4-a1ef-a257b35295ca`
* `f1088869-d2b6-4881-ac4c-f8103450fc0f`
* `d18339d5-350a-420b-9cd3-218a3a7391e4`
* `081b1743-40a0-44af-9adc-eb1e512c86ad`

解除 multi/non-event attribution 的 2 筆 events：

* `6794648b-39e3-4f07-8378-08ccb581307f`
* `51f7cd44-1a45-4f01-af24-0d6750536f41`

6 migrate 與 13 unlink 完成後，Japanese short duplicate 的 references 必須精確為零，才能執行
delete。任何未列出的 reference 都是 drift，必須停止 delete 並重新 classification。

### Chinese short duplicate

Chinese short duplicate venue ID 是 `124ca4f6-448c-4fd2-894b-5aab2fbcb456`。Event
`e94e8dd2-c684-4d71-8509-7c4541250efe` 要解除 venue link，但保留 historical location text。
只有 reference 歸零且 full-row delete CAS 成立時才能刪除 duplicate row。

### Online grant 與 URL rehome

Online grant event `dec284a5-983a-4149-a093-b24dd6212a9a` 必須符合：

* `venue_id`、address、address translations、prefectures 與 `location_url` 全部為 null
* localized location names 分別為 `オンライン`、`線上`、`Online`
* grant application URL 搬到 `submission_url`
* 修正 malformed system FC 的 null 與 array sentinel，不碰 human FC

URL rehome baseline：

* `3f56d510-d9e1-4fb2-bd4f-335df4e30965` 的 Forms URL 搬到 `submission_url`，
  `location_url` 改為 TCC root
* `8c94aaff-cb37-4f57-a135-6e141103116b` 的 Peatix URL 搬到 `submission_url`，
  `location_url` 改為 TCC root
* `51f7cd44-1a45-4f01-af24-0d6750536f41` 的 Peatix URL 搬到 `submission_url`，
  `location_url` 設 null
* `dec284a5-983a-4149-a093-b24dd6212a9a` 的 grant URL 搬到 `submission_url`，
  `location_url` 設 null

任何 target 已有不同且 nonempty 的 `submission_url` 都是 `review_conflict`，不得覆寫。

### Canonical-linked 29 reclassification

capture 必須查出當下所有 canonical-linked 29 baseline records 的完整集合，不得只處理 allowlist
中的 rows。每筆都要 capture、重新分類並提供 eligibility evidence。只有同時符合以下條件者可以
canonicalize：

* current Toranomon venue
* 不是 online，也不是 multi-venue
* Tokyo-only
* localized location names 不代表其他機構
* localized addresses 為 current、null 或已知 stale Minami-Aoyama
* 沒有 human field correction

Hokkaido、Osaka、Kyoto、Hachioji、Mita、Kanagawa 或任何其他 distinct locale fields 一律分類為
`review_conflict`，不得自動寫。若 live count 不是 29，不得強求湊數；列出新增、消失或改變的 rows，
依同一 eligibility 規則產生新 manifest。

## TIFF production event repair baseline

* Parent `d21b8f8d-03ea-4cf7-8227-4417836f5f43` 保留 TIFF multi entity
  `597eaa36-191b-48d4-9a34-cd7c128579f1`，所有 physical addresses 為 null
* `e2aa2c15-9aea-4f8a-b754-4691f937f9cd` 綁定 Chanter single FK 與 canonical fields
* `603fce9e-f48f-4307-9462-7939f99dc5a8` 設為三個 physical names，FK 與 addresses 為 null
* `f7b8a599-efd8-4982-b480-a896cd4080f1` 設為 Hibiya screens 12/13 加 Cineswitch，
  FK 與 addresses 為 null
* `d0d85c6e-7b33-4477-9055-e9f18bde4861` 設為 Chanter 加 Hibiya screens 12/13 加
  Cineswitch，FK 與 addresses 為 null

joined names 的順序必須與 2025 fixture 首次 act 出現順序相同。每筆 event 與 FC 都依 manifest
before CAS 寫入，不得只比對 `venue_id`。

## Century production event repair baseline

* Event `4a372b17-ca36-4e61-a9db-2a93323ad88e` 保留 Century FK，並以 exact CAS rewrite
  old-address system FC
* Event `d3bff09a-bb0e-4991-afc0-21376d62400d` attach Century FK、canonical fields 與必要 locks

兩筆都必須使用完整 UUID，不得以 prefix 查詢或輸出。第二筆若已存在 conflicting human FC 或
不同 nonempty submission URL，改列 `review_conflict`。

## 實作與驗證 protocol

### Phase 0: 建立或續接隔離工作區

1. 依 state matrix 從最新 `origin/main` 建立或續接指定 worktree 與 branch。
2. 建立或續接 active spec，將本文件完整架構拆成 proposal、tasks 與可驗證 acceptance criteria。
3. 在 `/memories/session/plan.md` 記錄 spec slug，後續 session 以 committed `tasks.md` 重新 hydrate。
4. 確認主工作樹既有 dirty WIP 完全未被修改或 stash。

### Phase 1: Engineer 實作

1. 立即委派 Engineer 在指定 worktree 實作 registry、database FK population、seed desired-state、
   TIFF routing、Johakyu、Starcat、repair tool、tests 與 fixtures。
2. Engineer 先讀所有將修改的檔案與現有 tests，使用小步變更與 focused tests。不得接觸 production
   mutation。
3. 每完成一個 task 就更新 active spec `tasks.md` 並 commit。commit 只能包含本 feature scope。
4. 實作期間對 live DB 的查詢只能唯讀，且任何發現的 drift 必須回寫 spec 的 classification notes，
   不得偷偷擴大 allowlist。

### Phase 2: Tester 驗證與修正迴圈

Engineer 完成後立即委派 Tester。Tester 必須執行並保存可稽核結果：

* registry focused tests
* database FK population 與 force-rescrape FC precedence focused tests
* seed desired-state、collision、address normalization 與 dry-run classification focused tests
* TIFF 2025 offline fixture routing 與 failure-path focused tests
* Johakyu 與 Starcat focused tests
* repair tool capture/apply/rollback、CAS、idempotency、drift、review conflict 與 ordering focused tests
* TCC writer regression tests
* `python -m compileall -q .`
* broader `python -m pytest tests`
* source dry-runs：`tiff`、`johakyu`、`starcat_cinema`、`taiwan_cultural_center`
* `git diff --check`
* path assertions：沒有 `web/**`、`supabase/**` 或 `scraper/main.py` diff

current-year TIFF unavailable 只能記為 graceful empty。2025 offline fixtures 才能證明 parser 與 routing。
任何 required target 只有 zero candidates、測試 fixture 未實際 exercise、mock 沒有驗證 mutation
payload，或 production classification 未讀到 target row，都必須標記 `INCONCLUSIVE`，不可 PASS。

Tester 若 FAIL 或 INCONCLUSIVE，立即把完整 failure evidence 交回 Engineer。最多三輪 Engineer
修正與 Tester 重驗，每輪重跑失敗的 focused checks，最後一輪還要重跑完整 validation set。只有
Tester 明確 PASS 且 scope assertion PASS 才能進入第一個即時批准閘門。

### Gate 1: Git push 明確批准

Tester PASS 後先顯示完整 Changes Log 與 Test Report，至少包含 exact commits、所有 changed paths、
測試命令與結果、dry-run 結果、未解風險、live drift observations，以及 production 尚未 mutation
的明確聲明。然後停止並取得當下、明確、只針對本次 validated changes 的 git push 批准。

初始 prompt invocation、開始實作批准、plan 批准、過去對話中的一般性批准或 production apply
批准都不能替代這個 gate。未取得 Gate 1 批准不得 commit 到 main、push、merge 或 capture manifest。

取得 Gate 1 批准後，交給 V-M-D 執行 conflict check、fetch、clean-worktree rebase、完整 validation、
scope-safe fast-forward push。禁止 merge commit 與 force push。完成後執行 fetch 並確認 exact
`origin/main` SHA，證明 validated feature commit 已包含在該 SHA。後續 capture 必須從這個 exact
SHA 的 clean code 執行，manifest 也必須記錄同一 SHA。若 origin 在確認期間再次前進，重新驗證
是否仍包含 feature commit，並將 capture SHA 更新為實際執行 code 的 exact `origin/main` SHA。

### Phase 3: Read-only production manifest capture

Gate 1 完成且 exact `origin/main` SHA 已確認後，才執行 read-only `capture`。capture 前重新讀取 live
DB、官方來源與 project ref，依本文件 eligibility 重新 classification。不得沿用測試 fixture、舊
query output 或先前 manifest 的 before images。

capture 完成後驗證 manifest immutable、所有 action digest 與整體 SHA-256。向使用者顯示：

* exact `origin/main` SHA 與 Supabase project ref
* manifest path、SHA-256 digest 與 capture timestamp
* 每個 action 的完整 action summary，不可只顯示 aggregate counts
* 每個 venue/event/FC action 的完整 UUID、action type、before/after 摘要與 dependency
* 三筆新 TIFF venue 的固定 UUID 與 ID/name absence evidence
* all skips、already-applied、drift 與 `review_conflict`，包含 canonical-linked reclassification 結果
* Japanese 與 Chinese TCC duplicate 的 pre-delete reference counts
* dry-run eligibility、CAS 與 rollback readiness 結果

### Gate 2: Production apply 明確批准

顯示完整 capture 結果後停止，取得第二次當下且明確的 production apply 批准。批准文字必須清楚
涵蓋同一 manifest digest，以及以下完整 mutation scope：

* pause、drain 與 resume 所有實際使用 service-role 的 writers
* authoritative venue updates 與三筆 TIFF venue inserts
* event 與 field correction updates
* Japanese short duplicate `e87b461e-8e8d-4fa0-b461-22a7ff2b6fdd` 的條件式 deletion
* Chinese short duplicate `124ca4f6-448c-4fd2-894b-5aab2fbcb456` 的條件式 deletion

Gate 1 與 Gate 2 是兩個不同時間點、不同內容的批准，絕對不能省略、預先取得、合併成一個問題，
或以初始 prompt invocation 代替。若 manifest 因 drift 重建，新 digest 必須重新取得 Gate 2 批准。

### Phase 4: Production CAS apply

取得 Gate 2 批准後依序執行：

1. 從 repository、workflow、scheduler 與 live runtime 重新盤點所有會使用 service-role 寫入 events、
   field corrections 或 venues 的實際 writers。
2. pause 並 drain 這些 writers，確認沒有 in-flight writes。不得假設 Admin maintenance lock 會阻止
   scraper、cron、GitHub Actions、server action 或其他 service-role writer。
3. pause 後重新讀取 project ref、repo SHA、manifest digest、全部 before images、FC rows、venue refs
   與 conflicts。任何 drift 都 STOP，不得套用部分 actions；需要新 manifest 與新 Gate 2 批准。
4. 依 manifest 固定順序執行 CAS apply 與逐筆 read-back。
5. 驗證全部 authoritative uniqueness、alias collision、venue/event/FC exact states、TIFF routing、TCC
   reference counts、URL placement、null sentinel 與 unrelated FC preservation invariants。
6. 只有 duplicate references 為零時，才依 full-row CAS 刪除兩筆 TCC duplicate rows。
7. 完成 final journal 後，以同一 manifest 再執行一次 apply，結果必須全為 noop/already-applied，
   不得產生任何 mutation。
8. resume 所有 writers，確認排程與服務恢復，監看第一個 writer run，檢查沒有把修復值覆寫、重建
   aliases、重新掛回 duplicate FK 或產生新的 FC pollution。
9. 立即委派 production Tester 進行唯讀 read-back，驗證 manifest action 全部 exact、duplicates 已在
   zero-reference 條件下刪除、writer 首跑無回歸，以及所有 production invariants。

若 production Tester 無法 exercise 目標、只得到 zero candidates、讀不到任一 allowlisted UUID，或
無法確認第一個 writer run，結果是 `INCONCLUSIVE`，不可 PASS。若 apply 或 read-back FAIL，保留
journal 與證據，停止進一步 mutation；不得在沒有新明確批准時 rollback、重跑或改寫 manifest。

## 最終回報

只有 production Tester PASS 後才能宣告完成。最終 Changes Log 必須列出：

* spec、branch、worktree 與 exact `origin/main` SHA
* code commits 與 changed paths
* pre-push Tester commands 與結果
* manifest path、SHA-256 digest、project ref 與 action totals
* 完整 applied、already-applied、skipped 與 review-conflict summaries
* writer pause/drain/resume 與首跑監控證據
* production Tester read-back 結果
* 未解 conflicts、人工 follow-up 與 rollback artifact 位置

不得把 capture 成功、command exit code 0、zero candidates 或第二次 apply noop 單獨描述為整體 PASS。
整體 PASS 必須同時具備 code Tester PASS、兩個獨立批准、exact SHA capture、CAS apply、完整 invariants、
idempotency、writer resume monitoring 與 production Tester read-back。

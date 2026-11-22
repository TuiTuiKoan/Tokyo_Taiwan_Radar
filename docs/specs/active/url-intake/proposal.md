---
slug: url-intake
title: 單一連結收錄（URL intake）
status: active
branch: feat/url-intake
created: 2026-11-22
tags: [scraper, ci]
---

> v2（2026-11-22）：依 `plan-critique-1.md` 修訂。處理結果見該檔末表。

## What（做什麼）

使用者看到一個台灣相關活動的連結，開一張 issue 貼上連結，就能把這一筆活動送進既有管線（`events` → 隔天的 merger／annotator／enrich → 網站），不必替這個網站寫 CI 爬蟲。

```
issue 內文含 URL ＋ label `url-intake`              → 預覽
  url-intake.yml
    fetch job（無 secrets、無 token）：抓頁面 → JSON artifact（不可信）
    db job（production）：重新驗證 artifact → 查重 → 在 issue 留言預覽（不寫 DB）

使用者在同一張 issue 貼 label `url-intake:approved` → 寫入
    fetch job：重抓
    db job：查重 → upsert_events（source_name=url_intake, annotation_status=pending）→ 留言結果並關閉 issue

隔天 09:00 JST 的 scraper.yml：merger → annotator → enrich → IndexNow（與所有來源相同）
```

使用者也可以從 Actions 頁面執行 `workflow_dispatch`（輸入 `url`、`apply`、選填 `issue`）。

## Why（為什麼）

- 2026-11-22：新聞通信調査会的報道寫真展「日中台：交錯するまなざし」只發在共同通信 PR Wire，不在任何來源（#701）。一次性的活動不值得寫爬蟲，而後台手動新增要人工填全部欄位。
- 這條路徑只需要一個 URL，欄位由 annotator 補，和其他來源走同一條管線。
- 收錄紀錄也是「來源缺口」的訊號：留言會標出同網域已收錄幾次。

## Non-Goals（不做什麼）

- 不做一般使用者的投稿入口（IA 的 `/submit`，P3）。
- 不做多筆、列表頁、Playwright（需要 JS 渲染的頁面第一版會回報「正文太短」）。
- 不在 workflow 裡跑 annotator：每日管線在標註後還有 enrich 與 IndexNow，單獨呼叫會漏步驟（critique #4）。
- 不寫 `image_url`（頁面提供的圖片網址未經驗證）。
- 不改後台手動新增（`manual`）的行為。

## Design（設計）

### D1 `scraper/ingest_url.py`

| 子命令 | 網路 | DB | 用途 |
|---|---|---|---|
| `fetch --url-env NAME --out F` | 有 | 無 | 從環境變數讀 issue 內文或 URL，取出第一個合法 URL，抓頁面、抽取，寫 JSON |
| `preview --in F` | 無 | 讀 | 驗證 JSON、查重，印出 markdown 預覽 |
| `apply --in F` | 無 | 寫 | 查重、插入一筆 `pending`，印出 markdown 結果 |

- **URL 正規化**：scheme 只允許 http(s)；去掉 fragment、`utm_*`、`fbclid`、`gclid` 等追蹤參數；拒絕帳密、IP 字面值、`localhost` 與內部網域。
- **SSRF**：自己處理 redirect（最多 5 跳），每一跳都把 host 解析成 IP，所有 IP 必須 `is_global`；回應上限 2 MB；timeout 20 秒。fetch job 本身沒有任何憑證，這一層是縱深防禦。
- **`source_id`** = `url_` + 正規化 URL 的 SHA-1 前 16 碼。
- **抽取**：標題取 `og:title` → `<title>` → 第一個 `<h1>`；正文先移除 `script`、`style`、`nav`、`header`、`footer`、`aside`、`form`，再取 `main` → `article` → `body`；上限 8,000 字，少於 200 字則拒收。
- **`raw_description`** 開頭加 `収録元: <URL>`，再接正文。日期、地點、分類、三語交給 annotator。
- **`original_language`**：含假名 → `ja`；否則含漢字 → `zh`；否則 `en`。
- **artifact 驗證**：只接受固定欄位與型別，長度重新截斷，URL 重新正規化。
- **查重**（preview 與 apply 都做；任一查詢失敗即中止，不寫入）：`source_url` 或 `official_url` 等於原始或正規化 URL、`secondary_source_urls` 含其中之一、或 `(url_intake, source_id)` 已存在 → 回報既有活動頁。標題相似的重複交給 merger。
- **可能重複**（#712，只在預覽顯示，不擋）：取標題中的引號名稱（「台湾音市 NEXT 2026」），沒有引號就取去掉「| 網站名」後最長的片段，比對 active 活動的 `raw_title`／`name_ja`，最多列 5 筆給人判斷。起因：#710 的 towershibuya.jp 頁面，活動早已由 PR TIMES 收錄，網址查重抓不到。
- **寫入後確認**：以 `(source_name, source_id)` 再查一次；查不到時回報「被 source_exclusions 規則擋下或寫入失敗」，workflow 以失敗結束。
- **留言跳脫**：標題、正文摘錄移除 HTML 註解、跳脫 markdown 符號、把 `@` 換成全形，避免偽造標記或 mention。
- **injection_guard**：預覽列出 `security.injection_guard` 的命中類別，供使用者核准前判斷。

### D2 annotator 與 merger

- `url_intake` 加入 `_RELEVANCE_GATE_EXEMPT_SOURCES`：使用者核准就是範圍判斷（AGENTS.md 人類關卡「活動範圍判斷」）。這次的展覽標題沒有「台湾」，正是會被閘門誤停用的類型。
- merger：`url_intake` 加入 `_NEWS_SOURCES`（以日期＋地點比對，被正式來源吸收），`SOURCE_PRIORITY` 設 100，低於 `user_submission`（99）與未列出的來源（預設 99）。

### D3 `.github/workflows/url-intake.yml`

- 觸發：`issues: [labeled]`、`workflow_dispatch`。
- **fetch job**：`permissions: contents: read`，`persist-credentials: false`，沒有任何 secret 或 token。issue 內文經 `env:` 傳入，不展開在 shell。
- **db job**：`environment: production`（部署分支只允許 main），`permissions: contents: read, issues: write`。checkout 預設分支，把 artifact 當資料讀。
- job 層 `if`：
  - 預覽：`label.name == 'url-intake'`，或 dispatch 且 `apply == false`。
  - 寫入：`label.name == 'url-intake:approved'` 且 `sender.login == repository_owner` 且 `sender.type == 'User'`；或 dispatch 且 `apply == true` 且 `actor == repository_owner`。
- `concurrency: url-intake-<issue 或 run id>`，不取消進行中的 run。
- 留言寫出觸發者（sender），寫入成功後關閉 issue。

### 人類關卡對應

| 項目 | 誰做 |
|---|---|
| 開 issue、貼 `url-intake` label、讀預覽 | agent 可自己做（不寫 DB） |
| 貼 `url-intake:approved`、以 `apply: true` 執行 dispatch | **只有使用者**（production 寫入）。agent 不做 |
| 本 PR（新增 workflow） | Tier 2，使用者合併 |

### 殘餘風險

- **閘門靠規則，不靠技術**：如果 agent 用的 GitHub 憑證就是使用者本人的 token，workflow 分不出貼 label 的是人還是 agent；`sender.type == 'User'` 只擋得住 bot 帳號。required reviewers 也擋不住（同一個 token 可以核准 pending deployment）。可接受的理由：影響範圍是一筆可停用的 `pending` 列，留言會記下 sender。對應的 hook patch 屬「權限與防線」，另開 issue 交使用者決定。
- **prompt injection**：頁面正文會進 annotator 的 prompt，和所有來源相同；預覽顯示 injection_guard 結果。

## 決定紀錄

- source_name 用新的 `url_intake`，不沿用 `manual`：可分開統計，也只讓「經使用者核准的連結」豁免相關性閘門。
- 寫入後不立即標註，等每日管線：最多晚一天上線，換來與其他來源完全相同的處理步驟。急的時候使用者可以手動執行 `Annotate Now`。
- 保留 workflow 內預覽（critique #3 建議移除）：雲端 agent 常被來源站擋（#531），在 Actions 跑才看得到真實頁面，使用者週審時也能直接在 issue 上看。

## 之後（另開 issue）

- hook patch：擋下 agent 貼 `url-intake:approved` 與以 `apply=true` dispatch。
- 同網域收錄 ≥ 2 次時自動開 `source-intake` issue。
- agent 端預檢 skill：收到連結 → 查重 → 開 issue 並貼 `url-intake`，停在預覽。
- 需要 JS 渲染的頁面（Playwright fallback）。

## References

- #701（共同通信 PR Wire 來源缺口）
- `docs/specs/active/agent-autonomy/proposal.md`（人類關卡、證據工廠）
- `.github/workflows/source-diagnose.yml`、`pr-dryrun-evidence.yml`（不可信內容與 secrets 分離）

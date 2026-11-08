---
slug: sentry-stacktrace
title: Sentry 每筆錯誤都帶 Stack Trace（code mapping 可連到 GitHub）
status: active
branch: feat/sentry-stacktrace
created: 2026-11-08
tags: [scraper, web, infra]
---

## What（做什麼）

讓 Sentry 收到的每一筆錯誤都有 Stack Trace，GitHub code mapping 才能從 issue 直接點到出錯的那一行。範圍包含 Python scraper 與 Next.js web。

## Why（為什麼）

2026-11-08 盤點 Sentry project `javascript-nextjs-1q` 的 issue：

- Python 的 event 全部只有 Message 區塊，沒有 Stack Trace。例：`KG+: failed to fetch WP types: 403`（`scraper/sources/kgplus_kyotographie.py:142`）、`RetiredModelScraper: scraper failed`（`scraper/main.py:489`）。
- 原因一：`scraper/` 有 124 個 `logger.error`，只有 5 處帶 `exc_info`。83 個寫在 `except` 裡但沒帶 traceback；40 個寫在 `except` 外，本來就沒有例外物件。
- 原因二：只有 `main.py` 初始化 Sentry，`annotator.py`、`merger.py` 等由 workflow 直接執行的腳本出錯不會進 Sentry。
- 原因三：所有 event 的 environment 都是 `production`，本機執行也一樣。`RetiredModelScraper` 其實是 `tests/test_main_llm_config_error.py` 的假 scraper，在 #542 之前從本機 pytest 漏進來。
- Web：2026-11-08 以帶 DSN 的 `next build` 實測，main 的產出裡沒有任何 client／server chunk 含 Sentry，也沒有 instrumentation 檔，**web 端 Sentry 完全沒有運作**，目前 project 裡的 event 全部來自 Python。原因：沒有 `instrumentation.ts`，Next.js 16 下 `sentry.server.config.ts`／`sentry.edge.config.ts` 不會被載入，server 端錯誤沒進 Sentry；Turbopack 不會注入舊的 `sentry.client.config.ts`；沒有 `app/global-error.tsx`；`withSentryConfig` 沒有 `org`／`project`，source map 傳不上去，前端 stack trace 是壓縮過的程式碼。

## Non-Goals（不做什麼）

- 不修各個錯誤本身（KG+ 403、`gpt-4o` model_not_found 等）；它們另開 issue。
- 不調整 Sentry 告警規則、取樣率、配額。
- 不開 Session Replay。
- 不在 repo 內建立或修改 Sentry project、DSN、auth token；這是 Sentry 後台與平台 secrets 的人類關卡。

## Design（設計摘要與決定）

拆成 4 個 PR，彼此獨立，可任意順序合併。

| PR | 分支 | 內容 |
| --- | --- | --- |
| A | `feat/sentry-stacktrace` | `scraper/observability.py` 的 `init_sentry(component)`；`main.py` 與 7 個 workflow 直接執行的腳本呼叫它；本 spec |
| B | `feat/sentry-workflow-dsn` | 把 `SENTRY_DSN` 加到執行上述腳本的 workflow step env（scraper、merger、annotate-now、enrich-and-annotate、refetch-thin-events、error-recovery） |
| C | `feat/sentry-exception-logging` | `except` 內的 `logger.error(...)` 改成 `logger.exception(...)`；新增防退化測試 |
| D | `feat/sentry-web-instrumentation` | `instrumentation.ts`、`instrumentation-client.ts`、`app/global-error.tsx`、`withSentryConfig` 補 `org`／`project` |

決定與理由（依 autonomy policy 採建議值，不另詢問）：

- **`attach_stacktrace=True`**：最小改動就能讓 except 外的 40 處也帶呼叫位置堆疊。
- **environment 用 `GITHUB_ACTIONS` 判斷**：Actions 上是 `production`，其他是 `local`；`SENTRY_ENVIRONMENT` 可覆蓋。不用 `local` 以外的名稱，避免使用者要在 Sentry 多設篩選。
- **release 用 `GITHUB_SHA`**：本機留給 SDK 從 git 偵測。
- **`component` tag**：同一個 DSN 下能依腳本篩選。
- **先涵蓋 workflow 直接執行、最常出錯的 7 個腳本**（annotator、merger、enrich_location、enrich_addresses、enrich_ocr_event、auto_qa、refetch_thin_events）。`error_recovery.py`、`qa_auto_fix.py` 與報表、eval 類腳本先不加，觀察幾週再決定（後續 issue）。
- **PR B 獨立出來**：它改變哪些 workflow step 拿得到 secret，屬於 autonomy policy 的「secrets」人類關卡。獨立成一個 Tier 2 PR，讓使用者可以只合併程式碼、延後或拒絕這一個；合併按鈕就是套用 patch 的動作。DSN 本身已以 `NEXT_PUBLIC_SENTRY_DSN` 出現在前端 bundle，敏感度低，但仍依規則交使用者決定。
- **PR C 用 AST 腳本批次改寫**：只改「寫在 `except` handler 裡（不含其中的巢狀 def／lambda）、沒有 `exc_info`、呼叫者是 `logger`／`logging`」的 `.error()`，**只換方法名**，參數與訊息不變，所以 log 文字、caplog 斷言、Sentry issue 標題都不變。排除 `_oneoff_*.py` 一次性腳本。防退化測試以 AST 掃描 `scraper/`（排除 `tests/` 與 `_oneoff_*`），有新的違規就失敗；刻意不要 traceback 時寫 `exc_info=False`。
- **PR C 的已知影響**：Sentry 會改用例外的堆疊分組，既有的純文字 issue 會停止增加、出現同內容的新 issue；log 之後再 `raise` 的 handler 仍會送兩筆（改動前也是），新的那筆會帶 chained cause。
- **PR D 依 @sentry/nextjs 11 官方 manual setup**：`sentry.client.config.ts` 改名為 `instrumentation-client.ts` 並 export `onRouterTransitionStart`；`instrumentation.ts` 依 runtime 載入 server／edge config（OG image 用 edge runtime，edge config 保留）並 export `onRequestError`；`app/global-error.tsx` 是唯一的錯誤邊界，自帶 `<html><body>`；`org`／`project` 從 `SENTRY_ORG`／`SENTRY_PROJECT` 環境變數讀，預設為目前的 slug，不寫死 auth token。environment 用 `VERCEL_ENV`（production／preview），讓 Preview 部署不混進 production。

## 人類關卡（交使用者）

1. 合併 PR A–D（皆 Tier 2）。
2. Sentry 後台：不分離 project（避免動 secrets）。`javascript-nextjs-1q` 設兩條 code mapping：web `./` → `web/`；Python 依第一筆新 event 的 frame 路徑設定。確認 Vercel 有 `SENTRY_AUTH_TOKEN`。
3. （選項）日後若要把 Python 分到獨立 project：`deps-verify.yml` 目前用 `SENTRY_DSN` 寫 `NEXT_PUBLIC_SENTRY_DSN`，要先替 web 另設 secret，否則 web 的 build 與 CSP 會指向 Python project。

## 評審

- [plan-critique-1.md](plan-critique-1.md)（Claude 代評，Codex 無法啟動），處置見該檔末段。

## 驗證方式

- PR A／C：`scraper/tests` 全數通過；`tests/test_observability.py` 用記憶體 transport 確認 `logger.error` 與 `logger.exception` 送出的 event 都有 frames，且關掉 `attach_stacktrace` 時測試會失敗。
- PR D：`pnpm lint`、`tsc --noEmit`、`next build`。
- 合併後：Sentry 新 event 出現 Stack Trace 區塊，frame 旁有 GitHub 連結。

# Plan Critique 1

評審者：Claude（同一模型家族，Codex 無法啟動）· 2026-11-08 · 對象：`proposal.md` 初稿、PR A 實作、PR B diff、web 現況

**必須修改**
- PR B 漏了 `error-recovery.yml` 的 `python annotator.py --limit 150` 這一步。annotator 已經呼叫 `init_sentry`，這一步卻沒有 DSN，跑出的錯誤進不了 Sentry。
- proposal 和 PR C 實作對不上：proposal 寫「移除尾端 %s」，worktree 實作卻保留了。應改 proposal，明定保留 %s。保留後 `getMessage()`、caplog 斷言和 Sentry 標題都不變，比較安全。
- 人類關卡第 2 步把 `SENTRY_DSN` 換成 Python project 之後，`deps-verify.yml` 仍拿它寫 `NEXT_PUBLIC_SENTRY_DSN`，web 的 build 和 CSP 會指向 Python project。關卡應加一步：web 改用獨立的 secret。

**建議**
- PR C 的範圍太大。53 檔裡有 `_oneoff_*`、backfill 這類不送 Sentry 的腳本，改了只會多出 log 雜訊。PR A 的 `attach_stacktrace` 已經能帶呼叫位置，PR C 只多給出拋出例外的那一層。替代做法是在 observability.py 用 `before_send` 從 `sys.exc_info()` 補 exception，只改一處，log 和 caplog 都不受影響。
- 本來就會發生的失敗（403/404）應比照 yebizo 的先例降為 warning，不要加 traceback。另外 issue 分組會從依訊息改成依例外，舊 issue 會斷掉，新 issue 會一次湧進來，應先告知使用者。
- 有 4 處 handler 在 log 之後 re-raise。DedupeIntegration 只擋同一個例外物件；改用 `raise X from e` 拋新例外時會送兩筆，測試應涵蓋這 4 處。
- 「涵蓋會寫 production 的腳本」說法不精確：`error_recovery.py`、`qa_auto_fix.py` 也寫 DB，卻沒涵蓋。應改寫說法，或把它們納入。
- PR D：
  - `instrumentation-client.ts` 要 export `onRouterTransitionStart`，`instrumentation.ts` 要 export `onRequestError = Sentry.captureRequestError`。
  - 3 個 OG image 用 edge runtime，edge config 必須保留。
  - repo 沒有任何 `error.tsx`，global-error 是唯一的錯誤邊界，要自帶 `<html><body>`。
  - Vercel Preview 的 NODE_ENV 也是 production，會照常上報。PR D 應寫明 environment 的命名規則。

**可忽略**
- PR B 拆成獨立 PR 作為 secrets 關卡是合理的，成本也低。
- environment 判斷：Python 不在 Vercel 上跑。其他 CI 只有 pr-dryrun-evidence 會跑 main.py，它沒有 DSN。本機用 act 會設 `GITHUB_ACTIONS`，屬邊緣情況。
- 8 個 entrypoint 都不用 thread 或 subprocess，scraper 裡也沒有直接呼叫 `capture_message`。LoggingIntegration 預設 ERROR 等級才送 event，和計畫一致。

## 處置（作者回覆）

| 意見 | 處置 |
| --- | --- |
| PR B 漏 `error-recovery.yml` | 採納，補上 |
| proposal 與實作不符（%s） | 採納，proposal 改為「只換方法名，參數與訊息不變」 |
| 分離 Python project 會讓 web DSN 指錯 | 採納，改為「不分離 project」：同一個 project 設兩條 code mapping，不動 secrets。分離改列為選項，需另設 web 專用 secret |
| PR C 範圍／before_send 替代 | 部分採納：排除 `_oneoff_*.py`（一次性腳本）。不採 `before_send`：從 `sys.exc_info()` 在 hook 裡補 exception 依賴 SDK 內部呼叫順序，`logger.exception` 是標準寫法，可讀性與可測性較好 |
| 403/404 降為 warning | 不在本 spec 範圍（屬各來源判斷），PR C 說明分組變動並另開 issue |
| re-raise 會送兩筆 | 接受現狀：改動前同樣是兩筆（其中一筆沒有堆疊），新的一筆會帶 chained cause；在 PR C 說明 |
| 涵蓋範圍說法 | 採納，改寫為「workflow 直接執行、目前最常出錯的 7 個腳本」，`error_recovery.py`、`qa_auto_fix.py` 列為後續 |
| PR D 細節 | 全數採納 |

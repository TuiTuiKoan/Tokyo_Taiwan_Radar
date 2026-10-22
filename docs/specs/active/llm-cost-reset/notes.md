# Notes — 2026-10-22 盤點

以下數字來自 production 唯讀查詢（Supabase `cjtndektjjpvvjofdvzr`）與 OpenAI dashboard（使用者提供）。成本以 dashboard 為準。

## OpenAI dashboard（使用者提供）

- 2026-04-01～08-02：$97.21，`gpt-4o-search-preview`（大多是 web search 呼叫費）佔 70%。
- 2026-08-01～10-22：$49.76；8 月 $29.76；10-01～10-22 $10.11。search 支出約 08-20 停止。
- 目前支出以 gpt-4o（enrich_poster）為主；annotator 的 gpt-4o-mini 約七成 input tokens 已命中 prompt cache。

## `scraper_runs`（repo 帳本）

| source | 月份 | 執行次數 | events_processed | cost_usd |
| --- | --- | --- | --- | --- |
| annotator | 2026-07 | 63 | 769 | 2.26 |
| annotator | 2026-08 | 59 | 1459 | 3.94 |
| annotator | 2026-09 | 33 | 774 | 2.09 |
| annotator | 2026-10 | 37 | 788 | 2.18 |
| researcher | 2026-07 | 91 | 52 | 30.02 |
| researcher | 2026-08 | 93 | 40 | 19.57 |
| researcher | 2026-09 | 95 | 0 | 0.00 |
| researcher | 2026-10 | 64 | 0 | 0.00 |

所有列 `success = true`。enrich 系列、qa、web 都沒有紀錄。

## `research_sources` 的實作率（#318 去留依據）

- researcher 的分類（`academic_lecture`、`art_exhibition`、`books_media`、`cinema_screening`、`community_social`、`food_retail`、`fukuoka`、`gender_society`、`geopolitics_policy`、`kansai`、`music_live`、`tech_business`…）自 2026-06 起只有 3 筆走到 `implemented`：`tech_business` 06-26、`event_listing` 07-03、`media` 07-10。
- discovery_accounts：`note_creator` implemented 4 筆（04-29～05-03）、`peatix_organizer` implemented 6 筆（05-15），之後沒有；最後一筆 candidate 是 07-20。

## 缺地址事件（enrich_addresses 改寫依據）

- `is_active` 且有 `location_name`、沒有具體地址（排除 gguide_tv 與線上）：511 筆，312 個不同場館名稱。
- 其中未來活動（`coalesce(end_date, start_date) >= now()`）只有 26 筆。
- `venues` 表 425 筆，只有 54 筆有 address、58 筆 `is_authoritative`；以完全相同名稱或 alias 比對命中 0 筆（未經 `venue_registry` 的正規化，實作時以 `lookup_venue_for_location` 重測）。
- 相同 `location_name` 的其他事件只有單一具體地址：85 筆可沿用；有多個地址：46 筆（不沿用）。

## #325 狀態（2026-10-22）

Eval session 的 worktree 只有 commit `95101f2e docs(specs): split the remaining evaluation-framework work into issues`，#325 尚未動工，沒有改 `venue_registry.py`。本 spec 只唯讀呼叫 `lookup_venue_for_location`；M1 動工前再確認一次。

## OpenAI 呼叫點（2026-10-22 grep）

scraper：`annotator.py`（1558、1575、4187、4221、5176）、`discovery_accounts.py`（256、316）、`enrich_addresses.py`（76）、`qa_auto_fix.py`（100）、`enrich_location.py`（64）、`enrich_poster.py`（196）、`weekly_line_broadcast.py`（232）、`qa_heartbeat.py`（149）、`researcher.py`（408）、`sources/cinemaclair.py`（198）、`auto_scraper/generate.py`（388）、`auto_scraper/auto_research.py`（273）、`eval_annotator.py`（77、93）。另有三個 `_oneoff_*.py` 不納入。

web：`api/admin/extract-from-image`、`api/upload-with-qr`、`api/admin/annotate-event`、`api/line-webhook`、`api/account/annotate-event`、`api/account/extract-from-image`。

M1 移除 researcher（1）、discovery_accounts（2）、qa_auto_fix 備援（1）、enrich_addresses（1）後，剩 scraper 15 個、web 6 個，共 21 個。

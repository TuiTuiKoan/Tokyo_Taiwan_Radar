---
name: architect
description: Planning principles, model selection, and scope rules for the Architect agent
applyTo: .github/agents/architect.agent.md
---

# Architect Skills

Read this at the start of every session before producing any plan.

## Planning
- Always check whether a new feature requires a DB schema change. If yes, mark Step 1 as a manual migration with verification SQL.
- Identify all code paths affected by a data model change — not just the obvious one (a new column needs both the table AND every writer that populates it).
- Never ship a plan with an untested API or signature change. Include an explicit smoke-test step.
- Confirm that all pending migrations are applied before designing features that build on them.

## Scope
- State explicitly what is NOT in scope. Ambiguous scope = scope creep = breaking changes.
- List every affected file path explicitly — vague descriptions ("the scraper files") are not acceptable.

## After Identifying a Planning Mistake
1. Append an entry to `.github/skills/architect/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.

## Classifier Keywords
- Avoid single-character or title words (博士, 先生, 教授) in category keyword lists — they appear as proper nouns (person names) and trigger false positives. Prefer compound terms: 「博士課程」「博士論文」「教授法」.
- After adding a new category with new keywords, run a dry-run of `backfill_categories.py` and manually inspect every match before applying to DB.
- When a backfill produces a suspicious tag (e.g., a plant-walk event tagged `academic`), trace which keyword triggered it and tighten the rule immediately.

## AI Model Selection
- Verify model capabilities before designing features requiring real-time data (web search, live prices, current events). `gpt-4o-mini` and `gpt-4o` have no web browsing. Use `gpt-4o-search-preview` or a real search API for current data.
- "Plausible-looking output" ≠ "real data access." A model without search access will hallucinate convincing-looking URLs.

## Online Location Standard
- **Canonical online event representation**: `location_name = 'オンライン'`, `location_address = 'オンライン'`. **Both columns must be set; neither should be NULL.** DB also requires `location_address_zh = '線上'`, `location_address_en = 'Online'`.
- All scrapers must normalize online markers **before** building the `Event` object. Use `_ONLINE_RE` pattern: `r'(?:online|オンライン|ライブ配信|配信のみ|[Zz][Oo][Oo][Mm])'`.
- The web `location=online` filter queries `location_name ILIKE '%オンライン%'` (location_address is redundant for filtering but must still be set).
- The `location=other_japan` filter must exclude online events via BOTH `location_name NOT ILIKE '%オンライン%'` AND `location_address NOT ILIKE '%オンライン%'`.
- `AdminEventTable.tsx` `other_japan` filter must also check `!addr.includes('オンライン')` before accepting the event.
- Variants like `'オンライン（Zoom）'` must be canonicalized to `'オンライン'`.

## Online Events (Peatix)
- Peatix renders online-only events as `LOCATION\n\nOnline event` (single line, no address group). The two-part regex `LOCATION\n\n(.+)\n\n(.+)` will NOT match — always add a separate `loc_online_m` check BEFORE the two-part regex.
- Set an `is_confirmed_online` flag immediately on match and **skip all CSS and regex address fallbacks** — description body text often mentions a venue as a conditional/secondary option and must never be used as `location_address`.
- For confirmed online events: `location_name = 'オンライン'`, `location_address = 'オンライン'`.
- The final body-text online fallback must also set `location_address = 'オンライン'`, NOT `None`.

## Address Verification
- **Never change a hardcoded address based on a DB value alone.** The DB may contain AI-hallucinated addresses from `backfill_locations.py` or the annotator. Always verify against the official source website first.
- Every hardcoded `location_address` in a scraper must include a comment citing the verification URL and date, e.g.:
  ```python
  # Verified: https://jp.taiwan.culture.tw/cp.aspx?n=362 (2026-04-26)
  location_address = "東京都港区虎ノ門1-1-12 虎ノ門ビル2階"
  ```
- When a user questions a displayed address, use `fetch_webpage` on the official source URL before drawing any conclusion.
- If `backfill_locations.py` has run on a source with a known fixed address, audit those DB records — AI-generated translations may contain hallucinated street numbers.

## i18n Completeness
- After writing or reviewing any TSX file with visible UI text, run the CJK audit before approving: `python3 -c "import os, re; [print(f+':'+str(i)+':'+l.strip()) for root,_,files in os.walk('web') for f in files if f.endswith('.tsx') for i,l in enumerate(open(os.path.join(root,f)).readlines(),1) if re.search(r'[\u4e00-\u9fff\u3040-\u30ff]',l) and not any(p in l for p in ['t(','tFilters(','tCat(','tEvent(','getEvent','MARKERS','//',"'//"])]" 2>/dev/null`
- Module-level consts that include translated strings CANNOT use `useTranslations()` (React hook rules). Either move the const inside the component function, or pass the translation function as a parameter.
- Every new i18n key must be added to ALL THREE `messages/*.json` files simultaneously — never add to just zh.json.
- When an admin page uses `getTranslations("admin")`, check if it also needs `getTranslations("general")` for shared strings (footer, error banners).
## i18n Regression Prevention (CRITICAL)
- **翻譯 JSON 只能新增、修改，絕不刪除 key**，除非確認全 codebase 所有 TSX/TS 都已移除該 key 的引用。
- **Scraper / DB / Agent 等非 web commit 不得修改 `web/messages/*.json`**。如果 AI 在同一 commit 中捆綁了翻譯修改，必須 split commit 或手動 revert 翻譯部分。
- 每次修改翻譯後，執行 key 完整性驗證：
  ```bash
  python3 -c "import json; a=set(json.load(open('web/messages/zh.json')).keys()); b=set(json.load(open('web/messages/en.json')).keys()); c=set(json.load(open('web/messages/ja.json')).keys()); print('zh-en diff:', a-b); print('zh-ja diff:', a-c)"`
  ```
- 若懷疑翻譯被洗掉，立即執行：`git log --oneline --since="3 days ago" -- 'web/messages/*.json'` 逐一檢查可疑 commit 的 diff（`git show <hash> -- 'web/messages/*.json' | grep '^-'`）。
- **根本防護**：`categories` namespace 中的 group_ 標籤（`group_arts`/`group_lifestyle`/`group_knowledge`/`group_society`/`group_archive`）和晚期新增的子分類（`competition`/`indigenous`/`history`/`urban`/`workshop`）是歷史上最常被意外洗掉的 key，每次 web 功能發布前必須確認這些 key 存在。

## Reviewed Event Translation Guard (CRITICAL)
- **`reviewed` 狀態的活動不應有 `name_zh = NULL` 或 `name_en = NULL`**。若有，後台 AdminEventTable 會顯示紅色 ⚠ 徽章提醒管理員。
- **永遠不要在翻譯欄位未填齊的情況下將活動標記為 `reviewed`**。完整欄位清單：`name_zh`、`name_en`（必要）；`description_zh`、`description_en`（建議）。
- `annotator.py` 的 `--fix-reviewed` 旗標可自動修復缺少翻譯的 reviewed 活動（僅補翻譯欄位，保留 category 和 `annotation_status = "reviewed"`）。
- **daily CI 已設定每日自動執行 `python annotator.py --fix-reviewed`**，作為背景防護網。
- 設計涉及 `annotation_status` 流程的功能時，必須考慮 reviewed 活動跳出翻譯流程的問題。
## Prompt Efficiency (User-Side Rules)

When plans involve multiple similar tasks or iterative fixes, guide the user toward these batching patterns to avoid unnecessary tool overhead:

- **Scope creep via URL**: If a user pastes a URL and asks to "check similar cases", clarify scope first. Do NOT do a full codebase scan unless explicitly requested. Ask: "只修這個？還是要檢查所有同類？"
- **Sequential same-type tasks**: When the user says "請繼續做 XXX" for each item, propose batching: "建議一次列出全部，我依序完成後統一回報" to avoid repeated context reloading.
- **Fix + rule update coupling**: When discovering a bug, fix it first. Defer history/skill updates to a dedicated batch step. Recommend: "先修完所有 bug，稍後一次批次更新 skill 和 history。"

See `.github/skills/session-analytics/SKILL.md` for the full anti-pattern catalogue and efficiency thresholds.

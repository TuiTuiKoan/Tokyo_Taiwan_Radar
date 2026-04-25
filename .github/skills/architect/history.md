# Architect Error History

<!-- Append new entries at the top -->

---
## 2026-04-26 — AI confidently reversed a correct scraper address to a wrong one (×2 errors)
**Error:** The taiwan_cultural_center scraper hardcoded `location_address = "東京都港区虎ノ門1-1-12"`. A user questioned whether this matched the DB value `南青山3-10-33`. Without verifying the official source, Architect incorrectly agreed the DB value was correct and committed `fix(scraper): correct … from 虎ノ門 to 南青山` (commit 2cbb8b8). In the same session, the `backfill_locations.py` pipeline had previously generated hallucinated addresses (`南青山3-10-33`, `南青山2-1-1`) via OpenAI for 2 events, which were stored as fact in the DB. The real address, confirmed at https://jp.taiwan.culture.tw/cp.aspx?n=362, is **〒105-0001 東京都港区虎ノ門1-1-12 虎ノ門ビル2階**.
**Fix:**
1. Reverted scraper to correct address `東京都港区虎ノ門1-1-12 虎ノ門ビル2階` with source URL in comment.
2. Patched 2 DB events (`f7ff56ca`, `e646c256`) — all three locale fields — to the verified address.
3. Amended/replaced the bad commit.
**Lesson:** **Never accept a hardcoded address change based on a DB value alone.** The DB may itself be wrong (backfill AI hallucination). Always verify against the official source URL before any address change. Every hardcoded address in a scraper must cite the verification URL in a comment. Added "Address Verification" rule to SKILL.md.

---
## 2026-04-25 — Repeated hardcoded CJK strings across admin components (multi-session)
**Error:** Over three sessions, 30+ hardcoded Traditional Chinese strings were found across 6 admin TSX files and 2 page files. Problems accumulated because each new feature/admin component was written with hardcoded zh strings instead of `t()` calls, and the audit/test step was skipped. The issues were only discovered when users switched to English or Japanese mode and saw Chinese labels:
- Stats cards: `活動總數`, `待標注`, `註冊用戶`, `擁有角色的用戶`, `待審問題回報`, `status = pending`
- AdminEventTable filter bar: 時間範圍, 地點, 標注狀態 labels + all options (22 strings)
- AdminReportsTable: `有料`/`無料` in a module-level const (couldn't use hooks; required passing `tEvent` as param)
- AdminResearchTable: status labels, URL valid/invalid badges, tooltip
- AdminSourcesTable: STATUS_FILTERS filter button labels
- Footer: `營運維護：對對觀 2026`
- Stats error banner: `scraper_runs 表尚未建立`

**Fix:** Replaced all hardcoded zh strings with `t()` / `tFilters()` / `tEvent()` calls. Added new i18n keys to all three `messages/*.json` files simultaneously. Fixed module-scope const limitation in AdminReportsTable by passing `tEvent` as a function parameter.

**Lesson:** After writing ANY TSX file with visible text, run the CJK audit script before committing. Module-level consts that contain UI strings cannot use `useTranslations()` — either move them inside the component function, or pass the translation function as a parameter. → Added i18n rules to web.instructions.md and SKILL.md.

---
## 2026-04-25 — classifier keyword "博士" caused false `academic` tag on nature event
**Error:** Added `"博士"` to the `academic` keyword list in `classifier.py` as part of the new-category rollout. A nature/flower-walk event at 高知県立牧野植物園 was tagged `['academic']` instead of `['nature', 'tech', 'tourism']` because its description contained「牧野博士ゆかりの桜」— a proper noun (person's name), not an academic context.
**Fix:** Removed `"博士"` from the `academic` rule. Re-classified the event and confirmed no other active events were affected.
**Lesson:** When designing classifier keyword lists, avoid person-title words (博士, 先生, 教授 as names) and other common words that can appear in non-academic contexts as proper nouns. Prefer compound terms (e.g., 「博士課程」「博士論文」) or context-specific phrases. → Added rule to SKILL.md under Classifier Keywords.

---
## 2026-04-25 — researcher.py used model without web browsing capability
**Error:** Designed `researcher.py` using `gpt-4o-mini` to simulate web research across 5 categories. Did not verify model capabilities first. Result: all discovered URLs were hallucinated (404s, wrong pages, non-existent organizations) in daily research reports.
**Fix:** Rewrote with `gpt-4o-search-preview` (real Bing search) + 5 parallel `CategoryAgent` instances via `ThreadPoolExecutor` + Playwright URL verification on every discovered source.
**Lesson:** Before designing any AI feature requiring real-time data, verify the model’s tool/capability list. → Added "AI Model Selection" rule to SKILL.md.

---
## 2026-04-23 — Monitoring stack shipped without confirming migration state
**Error:** Designed and handed off the full monitoring stack (scraper_runs table, /admin/stats page, Sentry) without first confirming that pending migrations 006 and 007 had been applied in the Supabase project. On first load, the stats page showed an error banner and the event_reports admin tab was broken.
**Fix:** Retrospectively identified missing migrations as Step 1 (manual) in the remediation plan.
**Lesson:** Check migration state as Phase 1 research whenever a feature assumes or extends DB schema. → Added to SKILL.md under Planning.

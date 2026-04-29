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
1. Append an entry to `.github/skills/agents/architect/history.md` (newest at top).
2. If the lesson generalizes, add a rule to this file.

## Category Union Change Guard

After any plan that touches `web/lib/types.ts` Category union:
- `multi_replace_string_in_file` `oldString` for union type changes must include **≥3 lines** before and after the target member — insufficient context silently truncates adjacent union members (see: `retail` removed when `drama` added, commit `f9e6b52`)
- Plan must include an explicit post-change verify step: `cd web && npx tsc --noEmit`, confirming **all** prior union members still compile
- Vercel build failure from a TypeScript error does **not** take the site down — it serves the previous build silently. Regression is invisible to users until manually checked.
- All 6 locations must be updated in the same commit (union, CATEGORIES, CATEGORY_GROUPS, zh/en/ja messages). See Engineer SKILL.md § Category Update Protocol for the full list.


- `sources/{name}/` — per-scraper platform profile（有 `applyTo: scraper/sources/*.py`）
- `agents/{name}/` — per-agent operational rules
- top-level — workflow/tooling skills only（local-preview, cc-statusline, session-analytics）
- 任何新的 per-source skill **必須** 放在 `sources/` 子目錄下，不可直接放頂層

## SQL Privilege Syntax Guard
- For PostgreSQL privilege statements, verify object-type syntax before finalizing migration SQL.
- View privilege revocation should use `REVOKE ... ON TABLE <view_name> ...`, not `ON VIEW`.
- For Supabase Security Advisor fixes, validate these statements line-by-line before execution:
  - `GRANT ... ON ...`
  - `REVOKE ... ON ...`
  - `ALTER VIEW ... SET (...)`
- If SQL Editor reports a syntax error, resolve by exact failing line first; do not change security model design until syntax is confirmed valid.

## Supabase RPC Auth Context Guard
- For `SECURITY DEFINER` RPC functions that gate admin access, do not rely only on `request.jwt.claim.sub`.
- Use `auth.uid()` as the primary identity source for real app requests, then fallback to claim only for SQL Editor simulation: `coalesce(auth.uid(), v_sub::uuid)`.
- Keep the function deterministic and explicit: `set search_path = pg_catalog`, schema-qualify cross-schema objects (`public.user_roles`, `auth.users`).
- Preserve strict denial path: when no effective user id or role mismatch, raise `42501` (`admin privileges required`).
- Before approving migration rollout, verify four cases:
  - app admin request: PASS
  - app non-admin request: DENY 42501
  - SQL Editor with `request.jwt.claim.sub` set to admin uid: PASS
  - SQL Editor without claim injection: DENY 42501

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

## Cross-Platform Environment Variables

When a feature spans **both GitHub Actions and Vercel** (e.g., LINE broadcast runs in GitHub Actions; LINE webhook runs on Vercel), each platform needs its own copy of every required secret.

**GitHub Actions secrets ≠ Vercel environment variables.** They are completely separate systems and do not share values automatically.

### LINE bot deployment checklist
Both of the following must be set in **both** platforms before the feature goes live:

| Variable | GitHub Actions Secrets | Vercel Env Vars |
|---|---|---|
| `LINE_CHANNEL_TOKEN` | ✅ (for broadcast) | ✅ (for webhook signature) |
| `LINE_CHANNEL_SECRET` | ✅ (for broadcast) | ✅ (for webhook signature) |

Setting a secret in only one platform silently breaks the other side. Webhook 401 failures are especially hard to detect because LINE does **not** retry failed webhook deliveries — events are permanently lost.

### General rule for cross-platform features
In the Verification section of any plan involving both CI (GitHub Actions) and web hosting (Vercel), explicitly list:
1. Which env vars are needed on **Vercel** (web-facing features: webhooks, API routes)
2. Which env vars are needed in **GitHub Actions** (CI/cron features: scrapers, broadcasts)
3. Any vars that are needed in both (shared secrets like LINE credentials)
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

## Migration Verification Protocol
- For any `SECURITY DEFINER` RPC or privilege-critical migration, establish a **four-quadrant verification matrix**:
  - App request with admin user (real auth.uid())
  - App request with non-admin user (real auth.uid())
  - SQL Editor with claim-injected admin uid (`request.jwt.claim.sub = '<admin_uuid>'`)
  - SQL Editor without claim injection (no auth context)
- Create an executable SQL smoke test suite (e.g., `027_smoke_test.sql`) with temp tables to avoid manual UUID copy-paste errors.
- Generate a verification report (e.g., `027_VERIFICATION_REPORT.md`) documenting:
  - Test date and status (ALL TESTS PASSED or FAILING with step number)
  - Each test's code line reference and expected result
  - Security architecture diagram (e.g., "Prefer auth.uid(), fallback to claim with exception handler, then role gate")
  - Deployment readiness checklist
- Mark migration as "PRODUCTION READY" only after all four quadrants + return type validation pass.

## Scraper Source Registration Audit
- Monthly audit: Compare `sources/` directory against `SCRAPERS` list in `scraper/main.py` to find unregistered source files.
  - Command: `comm -23 <(find sources/ -name '*.py' | xargs -I {} basename {} .py | grep -v '^__' | sort) <(grep 'Scraper()' scraper/main.py | sed 's/.*\(.*\)Scraper().*/\1/' | sort)`
- When a new scraper source file is created, immediately register it in `SCRAPERS` and run `python main.py --dry-run --source <name>` to verify event count is non-zero or document expected reason (offline season, no Taiwan matches, festival in October).
- Do not rely on CI discovery or daily cron to catch missing registrations — manual registration is mandatory at commit time.

## Cinema Official URL Extraction
- Cinema scrapers must extract `official_url` from the film detail page using one of:
  - Link with text "チケット" or "購入" (ticket/purchase keywords)
  - Href pattern containing `/ticket/` or `/purchase/` (domain-agnostic)
- Always verify extracted URL domain is not a third-party ticket vendor (e.g., Playplay, Peatix reseller, Rakuten Ticket) — maintain a domain whitelist of known official cinema URLs.
- When adding `official_url` extraction to an existing scraper, immediately backfill validation:
  1. Run scraper with `--dry-run` and manually inspect first 5 events
  2. Confirm URLs are valid, resolve without 404, and point to official pages (not redirects to vendor)
  3. Only then commit and push to production
- For Google Search fallback in film title lookup: always prioritize `name_ja` (Japanese title) regardless of current request locale. Google Search ranks results by search query locale, not result locale — using a locale-specific name variable will cause wrong film matches and incorrect `official_url` extraction.

## Prompt Efficiency (User-Side Rules)

When plans involve multiple similar tasks or iterative fixes, guide the user toward these batching patterns to avoid unnecessary tool overhead:

- **Scope creep via URL**: If a user pastes a URL and asks to "check similar cases", clarify scope first. Do NOT do a full codebase scan unless explicitly requested. Ask: "只修這個？還是要檢查所有同類？"
- **Sequential same-type tasks**: When the user says "請繼續做 XXX" for each item, propose batching: "建議一次列出全部，我依序完成後統一回報" to avoid repeated context reloading.
- **Fix + rule update coupling**: When discovering a bug, fix it first. Defer history/skill updates to a dedicated batch step. Recommend: "先修完所有 bug，稍後一次批次更新 skill 和 history。"

See `.github/skills/session-analytics/SKILL.md` for the full anti-pattern catalogue and efficiency thresholds.

## Agent Handoff Design

When designing agent workflows that need one-click handoff buttons:

### `.prompt.md` vs `.agent.md` Distinction
- **`.prompt.md`** — One-off tasks invoked via `/` command or skill menus. No persistent role, no tool restrictions per task. Use for: "Generate test cases", "Create README", "Summarize metrics".
- **`.agent.md`** — Persistent agent persona with role, tools, and instructions. Use for: long-running workflows, role-based tool restrictions, or handoff chains. Can be invoked via agent picker or as handoff target.
- **Handoffs only route to `.agent.md` files** — the `agent:` field in `handoffs:` must reference an `.agent.md` file's `name`, NOT a `.prompt.md` filename.

### Handoff Frontmatter Format
```yaml
handoffs:
  - label: "🔧 Button text"
    agent: AgentNameFromFile        # Must match .agent.md name exactly
    prompt: "Chinese instruction"    # Pre-filled when user clicks
    send: false                       # Optional, default false
    model: "Claude Sonnet 4.5 (copilot)"  # Optional, inherits agent default if omitted
```

### Subagent Configuration for Handoff Targets
When creating an agent **only for handoff invocation** (not for manual picker):
```yaml
---
name: My Handoff Agent
description: "Brief role description"
user-invocable: false               # Hide from agent picker
disable-model-invocation: false     # But allow handoff invocation
tools: [read, search, execute, web] # Minimal necessary tools
---
```

### Best Practices
1. **Name consistency**: Agent `name:` in frontmatter must match the handoff `agent:` field exactly (case-sensitive).
2. **Chinese instructions in prompt**: Always include `prompt:` field with clear Chinese task description to ensure context transfer.
3. **Workflow grouping**: If two agents form a natural sequence (e.g., Plan → Implement → Review), add all three as handoffs in each agent to enable any→any routing.
4. **Testing**: After adding handoffs, verify in VS Code: restart Copilot Chat, check that buttons appear, test context passing via `prompt:` field.


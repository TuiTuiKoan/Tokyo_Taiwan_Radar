---
name: Engineer
description: "Full-stack implementation, CI/CD, and deployment for Tokyo Taiwan Radar"
model: claude-sonnet-4-5
handoffs:
  - label: "🏗️ Plan this first"
    agent: Architect
  - label: "🧪 Test the result"
    agent: Tester
  - label: "📝 Update history/skill/agent"
    agent: Update History, Skill, Agent
    prompt: "根據最近的修改和所學的教訓，幫助我更新 history.md、SKILL.md 和 agent 檔案。"
  - label: "🚀 Validate, merge & deploy"
    agent: Validate, Merge & Deploy
    prompt: "執行完整的驗證流程：檢查衝突、rebase、commit 和推送到 origin/main，最後確認 Vercel 部署。"
---

# Engineer

Executes full-stack implementation across the scraper (Python), web (Next.js 16), database (Supabase migrations), and CI/CD (GitHub Actions). Owns the full change lifecycle from reading existing code to verifying the deployed result.

## Session Start Checklist
1. Read `.github/skills/agents/engineer/SKILL.md` — apply all rules before starting.

## After Fixing Any Error
1. Append an entry to `.github/skills/agents/engineer/history.md` (newest at top): date, error, fix, lesson.
2. If the lesson generalizes, add or update a rule in `SKILL.md`.

## Available Handoffs

- **🏗️ Plan this first** — Before writing code, hand off to Architect to review design.
- **🧪 Test the result** — After implementation, hand off to Tester for validation.
- **📝 Update history/skill/agent** — After fixes or features, document the lessons learned.
- **🚀 Validate, merge & deploy** — When ready to ship, hand off for full deploy cycle.

## Role

- Read before writing — always understand existing code before modifying it
- Make the smallest correct change that satisfies the requirement
- Run tests and check for errors after every significant change
- Notify the user before: `git push`, DB migrations, secret changes, or Vercel deployments

## Token Permission Consistency

When changing any `GITHUB_TOKEN` / `--create-issue` behavior or documentation:

1. Keep permission wording consistent everywhere:
  - Fine-grained PAT: `Issues: write + Metadata: read`
  - Classic token: `repo` scope
2. Update code + docs + agent references in one batch (no partial wording updates).
3. Treat `docs/GITHUB_TOKEN_SYNC_CHECKLIST.md` as the canonical checklist source.

## Required Steps

### Step 1: Understand

1. Read `.github/copilot-instructions.md` and the relevant `*.instructions.md` for the area being changed.
2. Read all files that will be modified; understand the existing patterns.
3. Check for TypeScript/lint errors before starting: use `get_errors`.
4. Clarify any ambiguities with `vscode_askQuestions` before writing a single line.

### Step 2: Implement

1. Follow the conventions in `.github/instructions/` for the relevant domain.
2. Make changes using `replace_string_in_file` or `multi_replace_string_in_file` (prefer multi for independent edits).
3. For new files, use `create_file` — never create files unless strictly necessary.
4. Do NOT add comments, docstrings, or extra error handling beyond what was asked.
5. **Filter-option sync:** When adding a value to a TypeScript union, DB enum, or i18n file that is also used in a `<select>` dropdown, always add the matching `<option>` element in the same commit. Check every `<select>` whose value type includes the new key.
6. **Annotation status label consistency:** When displaying `annotation_status` anywhere (badge, dropdown option, column header), always use the **short-form i18n keys**: `t("filterAnnotatedShort")`, `t("filterReviewedShort")`, `t("filterErrorShort")`, `t("filterPendingShort")`. The long-form family (`annotated`, `reviewed`, `error`, `pending`) has been deleted from all message files — do not recreate it.
7. **Category group picker three-file rule:** `AdminEventForm.tsx`, `ReportSection.tsx`, and `AdminReportsTable.tsx` all share the same category group picker layout (`grid-cols-[4.5rem_1fr]`). Any layout change to any one of these three files must be applied to all three in the same commit. Never use a mixed `flex-wrap` layout with label+tags in the same row.
8. **AdminSourcesTable derived-counts consistency rule:** When modifying the `AdminSourcesTable` status filter (adding/removing `<option>` or a `getFilteredSources` branch), update **all three** locations that share the same filter predicate: `getFilteredSources`, `typeCountMap` statusFiltered, `eventCountByType` statusFiltered. Missing any one causes stale counts in the dropdown. Extract a shared `statusFiltered` array rather than duplicating the predicate inline.
8. **Multi-locale field editing rule:** When a UI component lets a user view or correct a field that maps to localized DB columns (`*_ja`, `*_zh`, `*_en`), **always expose all three locale variants simultaneously** with language labels (中文 / English / 日本語). Never show only the current locale. The Japanese original is often correct; only a specific translation may be wrong. See `ReportSection.tsx` + `SKILL.md §Multi-locale Edit Pattern` for the canonical type/state/render pattern.
9. **Cinema scrapers — Movie Title Lookup:** When implementing or updating a cinema scraper (`category=["movie"]`), always call `lookup_movie_titles(name_ja)` from `scraper/movie_title_lookup.py` before constructing `Event()`. See `SKILL.md § Movie Title Lookup Pattern` for the canonical pattern and exemptions.
10. **gguide_tv name_zh/name_en manual patch rule:** When patching name_zh or name_en for events from `gguide_tv` source, ALWAYS verify against Wikipedia or IMDb first — Japanese broadcasters use localized titles that differ from official Taiwanese titles. Never translate raw_title directly. See `SKILL.md § gguide_tv 特殊規則`.
11. **enrich_movie_titles() description sync rule:** When `enrich_movie_titles()` updates `name_zh` or `name_en`, also patch `description_zh` and `description_en` to replace the old title inside bracket pairs. Use bracket-aware replacement only (never bare string replace). See `SKILL.md § enrich_movie_titles() 連動 description 規則`.
12. **SEO metadata rules:** When modifying `app/robots.ts`, `app/sitemap.ts`, or any `generateMetadata` function: (a) use plain `createClient(URL, ANON_KEY)` in static route handlers — never SSR cookie client; (b) delete any `export const metadata` when converting to `generateMetadata`; (c) use locale-aware site names (zh/ja/en); (d) include `x-default` in `alternates.languages`; (e) always add `NEXT_PUBLIC_SITE_URL` fallback. See `SKILL.md § SEO / Metadata`.
13. **Next.js 16 proxy.ts rule:** NEVER create `web/middleware.ts`. Next.js 16 uses `proxy.ts` as the sole middleware entry point — both files co-existing causes immediate Vercel build failure. All middleware logic (headers, redirects, auth guards, locale detection) must go inside `proxy.ts`, appended after the existing intlMiddleware/supabase/admin flow. **Non-locale route exclusion:** Any route that should NOT be locale-prefixed must be excluded in the `proxy.ts` matcher regex — this includes static files in `web/public/` AND non-locale routes (e.g. `/r/*` short redirects, API routes, webhook endpoints). Without exclusion, i18n middleware 307-redirects all requests to `/zh/<path>` returning 404. See `SKILL.md § AEO — proxy.ts Non-locale route exclusion rule`.
14. **JSON-LD Event schema:** When adding structured data to event detail pages, inject `<script type="application/ld+json">` at the top of `<article>`. Use server component props directly — no extra DB query. Convert `null` fields to `undefined` before serializing. See `SKILL.md § JSON-LD Event schema 注入`.
15. **ISR page rules:** When adding `export const revalidate` to a page (e.g., event detail): (a) use plain `createClient(URL, ANON_KEY)` for ALL Supabase queries — any `cookies()` call forces dynamic and kills ISR; (b) move all auth-dependent UI (`isAdmin`, `isSaved`, `user`) to client components with `useEffect`; (c) pass `initialSaved={false}` to `SaveButton` and let it self-fetch on mount; (d) use `.eq("is_active", true)` query filter instead of server-side `if (!is_active && !isAdmin) notFound()`. See `SKILL.md § ISR（Incremental Static Regeneration）頁面規則`.
16. **OG Image Edge runtime rules:** `opengraph-image.tsx` uses `export const runtime = "edge"`. Never use `fetch(url, { next: { revalidate } })` or any `next: {}` fetch extension — Edge runtime only supports plain Web APIs. Always use bare `fetch(url)`. For Google Fonts CSS parsing, use `/src:\s*url\(/` (with `\s*`) — the CSS spec allows whitespace after the colon. See `SKILL.md § OG Image（opengraph-image.tsx）— Edge Runtime 規則`.
17. **Supabase Python client `order()` rule:** In Python scraper code, the correct syntax is `.order("col", desc=True)`. **Never use** `.order("col", ascending=False)` (pandas-style — not supported). Using `ascending=` causes a silent TypeError or unexpected sort, breaking CI.
17. **zsh git add bracket paths:** Paths containing `[...]` (e.g. `web/app/[locale]/page.tsx`) must be wrapped in single quotes when passed to any shell command: `git add 'web/app/[locale]/page.tsx'`. Without quotes, zsh expands brackets as glob patterns and the command fails with `no matches found`.
18. **Inline Python safety:** Never use `python3 -c "..."` or heredoc `python3 << 'PY' ... PY` for scripts that contain f-strings with `{`/`}`. Shell history pollution can inject code into f-string braces. If inline Python fails with SyntaxError pointing at a brace, immediately switch to `create_file /tmp/<name>.py` + `python3 /tmp/<name>.py`.
17. **Location filter three-file sync rule:** When changing the location filter options (values, labels, or detection logic), **always update all three files in the same commit**: `FilterBar.tsx` (options + i18n keys), `web/app/[locale]/page.tsx` (server-side OR query), `AdminEventTable.tsx` (state union type + marker arrays + `getFiltered` + `sourceCountMap`). The `filterLocation` state type must exactly match the option values — TypeScript will not catch unknown values, they silently return zero results. Use `ilike` marker lists per region; avoid NOT logic. See `SKILL.md § Location Filter Three-File Sync Rule`.
17. **Next.js 16 `params` must be awaited:** When creating or editing ANY file-based route (`page.tsx`, `layout.tsx`, `route.ts`, `opengraph-image.tsx`, `generateMetadata`, `generateStaticParams`), always type `params` as `Promise<{...}>` and `await params`. TypeScript does NOT report a type error if `await` is omitted — `Promise<T>` destructures silently and returns `undefined` at runtime, causing DB query failures or route 500s. See `SKILL.md § Next.js 16 — params 必須 await`.
18. **Satori emoji 禁用規則**：`opengraph-image.tsx` 及所有使用 `ImageResponse`/Satori 的路由，**嚴禁使用任何 emoji**（包含看起來普通的 📅📍，以及 ZWJ 序列 🏳️‍🌈、regional indicator 🇹🇼）。Satori 遇到不支援 emoji 時靜默失敗：HTTP 200 + `content-length: 0`，不拋任何錯誤。一律改用 ASCII 文字標籤（`DATE`、`AT`、`FILM`、`ART` 等）。See `SKILL.md § OG Image（opengraph-image.tsx）— Edge Runtime 規則`。
19. **AEO（AI Engine Optimization）完整實作規則：** 新建網站或執行重大 SEO 工作時，必須實作完整 AEO 清單：(a) `web/public/llms.txt`（AI 引擎索引文件）；(b) `robots.ts` 明確許可 GPTBot、PerplexityBot 等主流 AI 爬蟲；(c) root `layout.tsx` 注入 `WebSite + SearchAction + Organization` JSON-LD（`@graph` 格式）；(d) 事件詳情頁注入 `BreadcrumbList` JSON-LD；(e) 日期欄位用 `<time dateTime>` 包裹；(f) `sitemap.ts` 各頁 `alternates.languages` 補上 `x-default`。新增任何 `public/` 靜態文件後必須同步更新 `proxy.ts` matcher 排除規則。See `SKILL.md § AEO（AI Engine Optimization）`。
20. **Auto-QA 寫入 `event_reports` 共用佇列規則：** 新增任何自動化內容品質檢查時，findings 必須寫入 `event_reports`，於 `report_types[]` 使用 `auto_*` 前綴（例：`auto_qa_simplified_zh`、`auto_qa_missing_address`）。**禁止**為自動檢查另建 admin 佇列——重用 `/admin/reports` 的 confirm/dismiss UI。Insert 前必須對「同 event_id + 同 `auto_*` 類型」的既有記錄去重——**檢查 ALL statuses**（`pending`、`confirmed`、`dismissed`），不只 `pending`。已 confirmed/dismissed 的報告代表 admin 已審核，auto_qa 不得重建。單次執行中以 in-memory set 再去重一次。See `SKILL.md § Scraper Implementation` and engineer `history.md` 2026-05-01 / 2026-05-05.
21. **`SIMP_RE` / `_SIMP_TO_TRAD` 字元新增規則：** 加字前必須先確認該字的繁體中文／日文對應**是不同字形**。透過 CC-CEDICT 或 kanji.jitenon.jp 查證後才能加入。反例：`亮` 在繁簡日完全相同（`照亮` 為合法繁體），加入後會在 `auto_qa.py` 與 annotator 兩處產生 false positive。新增字元時必須同步更新 `annotator.py._SIMP_TO_TRAD` 和 `auto_qa.py.SIMP_RE`。See `SKILL.md § Scraper Implementation` and scraper-expert `history.md` 2026-05-01.
22. **Cron slot rotation modulo wrap 規則：** 當 N 個 weekday 驅動 `(DAY-1) % M` slot 選擇器且 `M < N` 時，第 M+1..N 天會 silently 重跑 slot 0..(N-M-1)。slot 為 idempotent（search + `skip_hint` dedup）時可接受；slot 需要固定 cadence（例：Peatix slot 3 僅週四）時不可接受——必須以 `DISCOVERY_SLOT` env override 額外 cron entry，或提高 `SLOT_COUNT`。See `SKILL.md § Scraper Implementation` and engineer `history.md` 2026-05-01.
23. **Category label-only rename rule:** When renaming a category's display label (zh/en/ja text) without changing the `Category` union value, **only update the three `messages/*.json` files** — do NOT touch `types.ts`, `CATEGORIES`, or `CATEGORY_GROUPS`. Running `cd web && npx tsc --noEmit` is optional (no type change), but still recommended as a sanity check. i18n JSON files containing CJK characters must be edited with a Python `json` module script, not `replace_string_in_file`.
24. **Person name enrichment (all events):** `python annotator.py --enrich-person-names` fixes wrong phonetic name translations for ALL events, not just movies. Movie events use eiga.com structured cast/crew lookup (`strict=False`); non-movie events use katakana regex extraction + Wikipedia (`strict=True` to prevent false positives). See `SKILL.md § Person Name Lookup Pattern`.
25. **`name_ja` preservation rule:** The annotator NEVER overwrites `name_ja` with GPT output. Parent events: `update_data["name_ja"]` always uses `event.get("name_ja") or raw_title`. Sub-events: on re-annotation, the annotator pre-fetches existing sub-events by `parent_event_id` and preserves their `name_ja`/`raw_title` if already set (`existing or gpt_output`). This prevents GPT from rewriting katakana person names to kanji (e.g. `チャン・ツィイー` → `章子怡`). Sub-event `name_ja`/`description_ja` must use original Japanese text from the source — movie titles as Japanese release names, person names in original katakana/kanji. Translation corrections only apply to `*_zh`/`*_en` fields. See `SKILL.md § Annotator — name_ja Preservation & Sub-event Original Naming`.
26. **i18n namespace placement rule:** When adding a key to `web/messages/*.json`, always place it under the correct namespace: `data["<namespace>"]["key"] = value`. Never use `data["key"] = value` (top-level). next-intl `t("key")` only searches under the namespace declared in `useTranslations("<namespace>")` — missing keys silently render as the key name string (no error). Confirm namespace from the component's `useTranslations()` call: FilterBar options → `filters`; category labels → `categories`. After adding, verify with `grep -n "key" web/messages/zh.json` that the line number is in the expected block. See `SKILL.md § i18n JSON File Editing`.
27. **Admin quality check exclusion rule:** When adding a quality check query to `/admin/quality`, always exclude event formats that inherently don't match the check criteria — at DB query level (`.not()`), not in client-side JS. Examples: `competition`/`scholarship` → no physical venue (exclude from missing-location check); `gguide_tv` → no location (exclude from missing-location). The check's comparison field must match the field the detail page renders (e.g., `location_name IS NULL`, not `location_address IS NULL`).
28. **Simplified→Traditional conversion covers ALL `*_zh` fields:** `_to_trad()` is applied to `name_zh`, `description_zh`, `business_hours_zh` directly, and to `location_name_zh`/`location_address_zh` via `_loc_zh()`. When adding a new `*_zh` field to the annotator, always wrap it with `_to_trad()`. New simplified chars discovered in production → update both `annotator.py._SIMP_TO_TRAD` and `auto_qa.py.SIMP_RE`.
29. **RLS cross-status query guard:** When an SSR page queries a related record (parent event, linked entity) that could have `is_active = false`, the anon-key client will **silently return null** — no error, no warning. Use service role key for such lookups: `createClient(URL, SUPABASE_SERVICE_ROLE_KEY)`. Only `select` the minimum required fields; **never** use `select("*")` with service role. `SUPABASE_SERVICE_ROLE_KEY` must never be passed to a Client Component. See `SKILL.md § Admin Quality Page` and architect agent for the full pattern.
30. **Sticky filter + bulk action container rule:** Filter bar and bulk action bar in admin list pages must be wrapped in a **single** `sticky top-14 z-20` container. Separate sticky elements for each bar cause jittering on scroll. See `SKILL.md § Bulk Action Pattern`.
31. **Pipeline parity rule:** Any post-processing step added to CI workflow (`scraper.yml`) must also be called in `main.py`'s normal (non-dry-run) flow. Current full pipeline: scrape → merger → annotate → `enrich_movie_titles()` → `enrich_person_names()` → IndexNow. Enrich functions are idempotent — double execution in main.py + CI is safe. See `SKILL.md § Python`.
32. **Admin correction two-tier protection:** When building or modifying a confirm-report flow that resets `annotation_status` to `pending`, verify both tiers are intact: (a) P0 — `_ai_or_existing()` preserves non-null DB values during normal re-annotation; (b) P1 — `field_corrections` table records explicit admin overrides that persist across unlimited re-annotations (including `--all`). `confirm-report.ts` must write to BOTH `events` table AND `field_corrections` table. See `SKILL.md § Admin Correction Protection — Two-Tier Pattern`.
33. **next-intl `getTranslations()` namespace verification:** After adding any `getTranslations("namespace")` or `useTranslations("namespace")` call, ALWAYS verify the namespace and all keys exist in ALL 3 message files (`zh.json`, `en.json`, `ja.json`). next-intl silently renders the raw key string (e.g. `organizerType.commercial_brand`) for missing keys — no error, no warning, no build failure. Verify with `grep -n "namespace" web/messages/zh.json`.

### Step 3: Verify

1. Run `get_errors` on all modified files.
2. For scraper changes: `cd scraper && python main.py --dry-run --source <name>`
3. For web changes: `cd web && npx tsc --noEmit` then `npm run build` (local only, not deploy)
4. For DB migrations: review SQL against `.github/instructions/database.instructions.md` conventions; do NOT apply without user confirmation.
5. **After modifying `annotator.py` SYSTEM_PROMPT or `_SIMP_TO_TRAD` char map:** verify every `*_zh` field description says "Traditional Chinese (繁體中文)". After any batch re-annotation **or** char map change, run a full-DB scan on ALL `*_zh` fields:
   ```python
   import re, os; from dotenv import load_dotenv; from supabase import create_client
   load_dotenv('.env'); sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
   SIMP = re.compile(r'[东来这发会说时问门关对长进现与实变内还单层达诺厅络设联馆园个记构传经验弥统种学数编价乡网]')
   ZH = ['name_zh','description_zh','location_name_zh','location_address_zh','business_hours_zh']
   res = sb.table('events').select('id,is_active,' + ','.join(ZH)).execute()
   bad = [(e['id'][:8], e['is_active'], f, e[f]) for e in res.data for f in ZH if SIMP.search(e.get(f) or '')]
   print(f'Bad: {len(bad)}'); [print(f'  {i} active={a} [{f}] {v!r}') for i,a,f,v in bad]
   ```
   Any new char found → add to `_SIMP_TO_TRAD` AND `auto_qa.py.SIMP_RE` AND DB-patch all affected rows.
6. **GitHub Actions workflows:** Any `with:` field whose value is a pure `${{ expression }}` must be quoted (`path: "${{ ... }}"`). Bare expressions cause YAML schema validator warnings.

### Step 4: Deploy (requires explicit user approval)

1. **Stop and notify the user** before any of these actions:
   - `git push` or `git push --force`
   - Applying a Supabase migration (SQL editor or CLI)
   - `npx vercel --prod`
   - Modifying `.env` or secrets
2. After approval: proceed with the deployment action and report the outcome.

---

Proceed with the user's request following the Required Steps.

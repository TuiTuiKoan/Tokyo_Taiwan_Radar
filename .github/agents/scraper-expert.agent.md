---
name: Scraper Expert
description: "Builds, debugs, and validates scrapers for Tokyo Taiwan Radar — dispatches to per-source subagents (scope: all of Japan)"
model: claude-sonnet-4-5
agents:
  - TCC Scraper
  - Peatix Scraper
  - Community Platforms Scraper
handoffs:
  - label: "🧪 Run tests"
    agent: Tester
  - label: "🏗️ Review architecture"
    agent: Architect
  - label: "📝 Update history/skill/agent"
    agent: Update History, Skill, Agent
    prompt: "根據最近的修改和所學的教訓，幫助我更新 history.md、SKILL.md 和 agent 檔案。"
  - label: "🚀 Validate, merge & deploy"
    agent: Validate, Merge & Deploy
    prompt: "執行完整的驗證流程：檢查衝突、rebase、commit 和推送到 origin/main，最後確認 Vercel 部署。"
---

# Scraper Expert

Builds and debugs scrapers for all data sources. Dispatches to per-source subagents (TCC Scraper, Peatix Scraper) for source-specific work. For new sources without a dedicated subagent, implements directly.

> **Geographic Scope**: All of Japan（全日本）. Events in Osaka, Kyoto, Fukuoka, Sapporo, and all other regions are in scope — not only Tokyo.
>
> **Taiwan-venue exception**: Events held **in Taiwan** but explicitly targeting Japanese visitors (e.g. ファムトリップ, 日台交流ツアー, 日本人向け, 日本発) are **in scope**. Categorize as `tourism` and/or `taiwan_japan`. Use the real Taiwan address as `location_address` — do not convert to Japanese format.

## Session Start Checklist
1. Read `.github/skills/scraper-expert/SKILL.md` — apply all rules before starting.
2. Run the Worktree 確認閘門 below before editing any scraper.
3. If a per-source skill exists (`.github/skills/sources/<source_name>/SKILL.md`), read it too.

## Worktree 確認閘門

任何實作工作開始前，必須先向使用者確認在哪個 worktree 進行，得到明確答覆才動工。不得自行推定，也不得因為只改一個 selector 而跳過。

主工作樹（`Tokyo Taiwan Radar`／`main`）**僅供治理與盤點使用**。不得在此修改 `scraper/`。`main.py` 的 `SCRAPERS` 清單是共用清單，在主工作樹編輯尤其容易被平行 session 的 stash 踩踏。

實行方式一律以 `.github/instructions/git.instructions.md` § Worktree confirmation gate 為準。

## After Fixing a Scraper Bug
1. Append an entry to `.github/skills/scraper-expert/history.md` (newest at top): date, error, fix, lesson.
2. If the lesson generalizes, add or update a rule in `.github/skills/scraper-expert/SKILL.md`.
3. Append an entry to `.github/skills/sources/<source_name>/history.md` with the same format.
4. If the lesson is source-specific, add or update a rule in the per-source `SKILL.md`.

## Role

- Select the correct subagent for the target source
- For new sources: create `scraper/sources/<source_name>.py` extending `BaseScraper`
- For bugs: isolate the failing tier (date extraction, selector, dedup key) and fix the smallest unit
- Validate with `--dry-run` before handing off to Tester
- After fixing venue or address issues, verify every user-facing surface that renders the same event, including narrative summary, FAQ, calendar export, and address card, so postal codes and other display-only artifacts stay consistent.
- When a fixed physical venue event lacks `business_hours`, preserve current and stored event-specific schedules plus every `field_corrections` lock, including empty sentinels. Only then may the annotator fill stable general hours from an authoritative venue record backed by the venue or operator's first-party `アクセス`, store, visitor-information, or `営業時間` page. Never guess hours or promote a tenant or restaurant exception to the whole venue.
- Apply the Hybrid Venue Verification checklist below to every physical-plus-online event.

### Hybrid Venue Verification

1. Classify pure online only from affirmative evidence that no physical attendance option exists. Pure online uses `location_name='オンライン'`, `location_name_zh='線上'`, `location_name_en='Online'`, with `location_address`, address translations, and `location_prefectures` null. An online keyword alone is not proof.
2. Detect hybrid across every category and `event_form`, not only `performing_arts`. Physical signals include `会場観覧`, `現地`, `対面`, a physical venue or address, non-null `venue_id`, localized physical venue or address fields, and explicit simultaneous venue plus stream or online-registration information.
3. For hybrid events, retain the existing `venue_id`, physical address and known translations, and formal `location_prefectures`. Store localized joined names as `<venue> / オンライン`, `<venue zh> / 線上`, and `<venue en> / Online`; one `オンライン` token must not erase stronger physical evidence.
4. Keep URL ownership separate: `location_url` is the physical venue's official homepage; `submission_url` is the online registration or stream signup link; `official_url` is a verified first-party page dedicated to the event; `source_url` remains the original scraped page; `organizer_url` is the organizer homepage or, when no dedicated organizer site exists, its SNS profile. Performer SNS remains in `performer_url` or `performer_urls[]`. Never move a signup URL into `location_url` or erase provenance.
5. Before a manual repair, inspect existing FC rows and rewrite or remove contradictory locks before relying on re-annotation. Lock every manually changed field and verify matching audit rows. For event `70cf7002-06ee-45aa-815f-3422c999b5f5`, the minimum audited set is `location_name`, `location_name_zh`, `location_name_en`, `location_address`, `location_prefectures`, `location_url`, and `submission_url`; lock address translations only when changed.
6. Validate detail venue and address rows, region filtering, FAQ, narrative, SEO output, and the five independent `location_url`, `submission_url`, `official_url`, `source_url`, and `organizer_url` links. Use `70cf7002-06ee-45aa-815f-3422c999b5f5` as the positive hybrid fixture, expecting `誠品生活日本橋内 イベントスペース「FORUM」 / オンライン`, the physical address, `東京都`, and its `venue_id`. Use an online-only event with no physical evidence as the negative fixture and expect the pure-online canonical values.

## hanmoto publication-specific

- `performer` must come from the book author when the source is publication-style.
- `official_url` should point to the book's official detail page when available.
- `organizer_url` should point to the publisher home page.
- Pure publication means exact `event_form == ["publication"]` only; do not infer pure from category/source/title.
- Pure publication rows keep exactly these intentional-null fields: `location_address`, `location_address_zh`, `location_address_en`, `business_hours`, `business_hours_zh`, `business_hours_en`, and `location_prefectures`.
- Preserve real DB prices (`is_paid`, `price_info`, `price_amount`); hide pure-publication prices only in UI and JSON-LD. Price fields, `location_name`, and `location_url` are outside the seven-field NULL/clear policy.
- Publisher (`organizer`) is still required for pure publication rows.
- Physical launch/talk/signing/lecture/workshop events must not include `publication` in `event_form`.
- For hanmoto date fallback, prefer `発売日` first and `登録日` second.

## Required Phases

### Phase 1: Select Source

1. Read `.github/instructions/scraper.instructions.md` — BaseScraper interface, conventions, date extraction rules.
2. Identify the target source from the user request.
3. Dispatch to the appropriate subagent if one exists:
   - **TCC Scraper** → `taiwan_cultural_center`
   - **Peatix Scraper** → `peatix`
   - **Community Platforms Scraper** → `connpass` or `doorkeeper`
4. Otherwise proceed directly in Phase 2.

### Phase 2: Develop / Debug

1. Read the relevant source file in full before making any changes.
2. Read `scraper/sources/base.py` for the `Event` dataclass fields.
3. For new sources: copy the pattern from an existing scraper; register the new class in `SCRAPERS` in `main.py`.
    - **auto-scraper 生成 branch は 24 時間以内にマージする**: `SCRAPERS` リストと `main.py` の import は全員が同じ行を編集する hot spot。branch を放置すると main 側に複数の scraper 追加コミットが積まれ、マージ時に手動 conflict 解決が必要になる（commit `7cedc68` の Artist Cafe 事例）。
4. For bugs: run `python main.py --dry-run --source <name> 2>&1` first to reproduce the failure, then fix.
5. Keep `raw_title` and `raw_description` unchanged — never overwrite original scraped text.
6. Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when the event date differs from the post date.
7. **`start_date` / `end_date` type**: always `datetime.datetime`, never `datetime.date`. `dedup_events` calls `.date()` on the value.
8. **When editing `main.py` for any reason**: run the SCRAPERS audit (Phase 3 step 4) immediately after — even chore/refactor commits can silently drop registrations.
    9. **Substring keyword false positives**: `"台湾" in text` matches `仙台湾` (Sendai Bay). Any scraper that uses substring keyword filtering must maintain a `_FALSE_POSITIVE_PATTERNS` regex and strip those patterns before re-checking. See `## gguide_tv-specific` in SKILL.md for the implementation pattern.
    10. **Keyword filter scope — exclude 関連記事 section**: For Wix/SPA scrapers that use full-page text (`page.inner_text("body")`), truncate at `"関連記事"` before the Taiwan keyword check. Scanning the full page can cause false positives when unrelated events appear in the "related articles" footer. Pattern: `check_text = page_text[:page_text.find("関連記事")]` (guard: only truncate if index > 200). See `## Keyword filter — exclude non-article sections` in SKILL.md.
    11. **google_news_rss — do NOT remove from SCRAPERS to suppress noisy articles**: Use query precision (`上映会` not `上映`) and `_is_yahoo_aggregation()` to filter. Removing the entire scraper loses all Taiwan-event news coverage.
    12. **google_news_rss URL decoding**: `news.google.com/rss/articles/...` URLs must be decoded via `googlenewsdecoder.new_decoderv1(url, interval=0)` (add `googlenewsdecoder>=0.1.6` to `requirements.txt`). Do NOT base64-decode the path (encrypted protobuf) and do NOT use `requests.get()` (returns HTTP 400). The RSS `<description>` href is ALSO a Google News URL — always decode the `<link>` URL, not the description href. Set `_STALE_DAYS = 21` — Google News URLs expire in ~2–3 weeks.
    13. **Annotator NAME WRITING RULES**: Titles must be self-contained without reading the description. Generic words (`オフ会`, `ライブ`, `上映会`, `展示`, `イベント`, `セミナー`, `勉強会`) must be prefixed with the organiser/topic when they appear alone. Sub-event titles must also be independently understandable. If a DB event has a generic title, reset `annotation_status = 'pending'` and re-run `annotator.py`.
    14. **`annotator.py` VALID_CATEGORIES 同步守則 (Three-Location Sync Rule)**: Whenever `web/lib/types.ts` gains a new `Category`, THREE places in `annotator.py` must be updated atomically: (1) `VALID_CATEGORIES` list, (2) SYSTEM_PROMPT categories list (the comma-separated line), (3) SYSTEM_PROMPT category definitions. Skipping any one causes GPT to fall back to the nearest existing category silently (e.g. `tv_program` missing → GPT picks `movie`). Run audit: `python3 -c "from annotator import VALID_CATEGORIES; import re; ts=open('../web/lib/types.ts').read(); types=[x.strip().strip('|\"') for x in re.findall(r'\| \"(\w+)\"', ts)]; missing=[t for t in types if t not in VALID_CATEGORIES]; print('Missing:', missing or 'ALL CLEAR')"` before any annotator commit.
    15. **`location_address` must NEVER equal `location_name`**: Annotator's `_ai_or_existing()` keeps any non-null scraper-written `location_address` without checking if it equals `location_name`. A venue name echoed as address permanently blocks the PARENT VENUE ADDRESS RULE. Rules: (a) If a real street address is found in the text, use it only when it differs from the venue name. (b) Otherwise set `location_address = None`. (c) NEVER use `location_address = venue` / `location_address = location_name` as a fallback. After fixing any location bug, scan all scrapers: `grep -rn "location_address.*=.*venue\b\|location_address.*location_name" scraper/sources/`
    16. **二手聚合源（thin-pointer sources）— A1/A2/A2b/A3 パターン**: note.com / SNS 投稿などが「他機構のイベントを代わりに宣伝」する scraper では以下を必ず実装すること（`note_creators.py` が参照実装）。
        - **A1**: RSS/HTML preview の truncation guard は `endswith("続きをみる")` で判定（`== "続きをみる"` では不十分）。`_is_truncated(text)` = `text.endswith("続きをみる") or len(text) < 120`。
        - **A2**: `base.py.extract_first_party_url(body, exclude_hosts)` は candidate URL を返す。Destination を確認し、第一方の活動専用頁は `official_url`、signup／stream／ticket は `submission_url`、organizer homepage／SNS は `organizer_url` に分類する。`source_url` は元の投稿／scraped page provenance のまま保持し、helper 名や「詳細／申込」anchor だけで field を決めない。
        - **A2b**: Verified candidate が外部機構の event destination または organizer destination を示す場合、正しく `official_url` または `organizer_url` に route した上で `effective_location_name = None` にしてよい。これにより `_auto_lock_location` が投稿者 profile の教室住所を FC lock するのを防ぐ。非 signup URL を一律 `official_url` と呼んではならない。
        - **A3**: `base.py.fetch_ref_text(url, verify_ssl=not tw_insecure_domain(url))` で公式ページの本文を取得し `raw_description` に追記。台湾 `.edu.tw`/`.gov.tw` ドメインは `tw_insecure_domain()` で検出し `verify_ssl=False` で取得（OWASP: 白名單ドメインのみ、唯讀 GET）。A3 fail-safe: ref < 200 字 → fallback 回 note 全文、活動建立を阻断しない。
        - 詳細パターンは SKILL.md `## Note Creator Source Guard` 参照。

    17. **Headline Rewrite Source-List Sync Guard**: Any PR that modifies `scraper/annotator.py`'s `_HEADLINE_REWRITE_SOURCES` frozenset MUST also update the SYSTEM_PROMPT NEWS HEADLINE REWRITE RULE / SALIENT SUBJECT RULE「applies only to: ...」source list to include the same sources. The two lists must stay in sync — if they diverge, the source is allowed to be rewritten in code but GPT never receives the rewrite instruction, so it silently copies the generic blog/news headline verbatim (incident `cceca5a2`: `note_creators` 泛標題「台湾のポスター展」照抄, 内文の「二二八国家記念館」欠落). See SKILL.md `## Annotator — Headline Rewrite Sources & Blog Source Guard`.

  18. **CMS/WordPress 活動頁主辦與講者欄位檢查（必做）**: 如果來源頁是 WordPress 或類 CMS 結構，人物/主辦欄位不得只抓單一 label。開發時至少驗證 `講演者`、`講師`、`登壇者`、`司会`、`報告者`、`主催`（必要時 `共催`）是否都能覆蓋，並把 `主催:` / `講師:` 明確寫入 `raw_description`。若線上事件觸發 `auto_qa_missing_organizer` 或 `auto_qa_missing_performers`，先回查 scraper label fallback，而不是先改前端顯示邏輯。

  19. **`gguide_tv` report 誤判防護（劇情中的「報告」≠ 活動報導）**: 若事件來源是 `gguide_tv`，不得僅因 raw_description 內出現單詞 `報告` 就注入 `report` category 或加上 `【レポート】` 接頭辭。電視劇劇情簡介常出現 `交際の報告`、`上司に報告` 等語境，這是劇情文本而非活動報導。`report` 判定對 `gguide_tv` 必須以節目型態/ジャンル為主（如 `報道`、`ドキュメンタリー`），不可直接套用 generic keyword trigger。

  20. **`google_news_rss` 配信記事欄位補齊（手動修復標準）**: 若 `raw_description` 明確含有平台/價格/出演者訊號（例如 `BS11+`、`見放題・単品レンタル配信`、`演じたのは`），但 `location_name` / `business_hours` / `is_paid` / `price_info` / `performers` 為空，必須手動回填並立刻 FC lock。`business_hours` 僅保留單行可讀格式（`YYYY年M月D日から配信中`），避免把整段新聞文本塞入 UI。若 `field_corrections.corrected_by` 型別不明，先只寫 `event_id/field_name/corrected_value`，避免 `22P02`。

  21. **`google_news_rss` 台灣限定串流新聞停用規則**: 若條目本質只是台灣境內平台上架/配信新聞，沒有日本場地、在日參與性或本站要保留的常設價值，**不要**因 `name_ja` 含 `配信`、`end_date=NULL`、`event_form=[]` 就保留在 active pool。這類薄內容 `report` 條目的標準處理是直接 `is_active=false`，並寫 `deactivated_reason='out_of_scope: Taiwan-only streaming news article — not a Japan event'`。同類 active 候選若 `<20`，優先單筆手動 patch，不先擴大成 scraper/backfill 專案。

  22. **系列活動子活動缺漏／窄標題修復（content-stable，禁止砍光重建）**: 修「parent 少一筆子活動」或「子活動卡在窄標題（如『講演1』）」時，先確認 annotator 子活動 `source_id` 是位置序號 `_subN`。**不要**靠重跑 annotator 或「刪光全部子活動再 upsert」來補——GPT 對複雜 program list 輸出順序不穩，會 silent 覆寫既鄰 `_sub2`〜`_subN`。正確流程：① 用標題＋`start_date` 匹配既有子活動 → 復用原 `source_id`；② 缺漏項才 append 到目前最大 `_subN` 之後；③ 同日既有子活動若是 bundle（開幕イベント、公演＋解説），確認 GPT 拆出的 component 命中並 skip duplicate；④ 手動修正子活動後 FC lock，且確認 sub-event upsert 尊重 `field_corrections`（非文字欄位用 DB-native）。詳見 SKILL.md `## annotator sub-events — reliability limits`。
1. Run `cd scraper && python main.py --dry-run --source <name> 2>&1 | head -80`.
2. Verify: `start_date` is populated, not the publish date; `category` values are canonical; no unhandled exceptions.
3. **For `gguide_tv` events specifically**: confirm `tv_program` appears in `category`. If `movie` appears alone (without `tv_program`), the annotator's `_inject_keyword_categories` was bypassed — check that `raw_description` contains `放送:` / `ジャンル:` markers.
4. Run `get_errors` on changed Python files.
4. **⚡ Combined Post-Build Audit — 必須（スキップ禁止）**: Run the audit from SKILL.md `## ⚡ Combined Post-Build Audit` section. It checks BOTH:
   - SCRAPERS registration in `main.py`
   - `research_sources.scraper_source_name` is non-null for all `implemented` rows

   **Must print `🎉 ALL CLEAR` before proceeding to Phase 4.** If any `❌` line appears, fix it immediately — do not defer to later. This audit has caught the same omission 3+ times (walkerplus, tsutaya_portal, …); it is not optional.

   The audit also replaces the standalone SCRAPERS-only audit — run the combined version every time `main.py` is touched.
5. **Run merger dry-run**: `cd scraper && python merger.py --dry-run 2>&1` — confirm any detected cross-source duplicates are intentional. New sources that report events with article-style titles (e.g. RSS feeds, press release scrapers) may match existing official events via Pass 2 (date-range + location-overlap). If a new source should participate in Pass 2 matching, add it to `_NEWS_SOURCES` in `merger.py`.
6. Hand off to Tester for full pipeline validation.

### Phase 4: Document

**Always run this phase after Phase 3 passes — for both new sources AND bug fixes.**

#### New source

1. Create `.github/skills/sources/<source_name>/SKILL.md` with:
   - YAML frontmatter: `name`, `description`, `applyTo: scraper/sources/<source_name>.py`
   - Platform profile table (Site URL, API/Rendering, Auth, Rate limit, Source name, Source ID format)
   - Field mappings table
   - Taiwan relevance filter rules
   - Date extraction notes
   - Troubleshooting table
   - `## Pending Rules` footer
2. Create `.github/skills/sources/<source_name>/history.md` with a `## YYYY-MM-DD` entry describing any non-obvious decisions made during initial implementation.
3. Add a `## <source_name>-specific` section to `.github/skills/agents/scraper-expert/SKILL.md` with the top 3–5 rules that a future agent must know.
4. Update `research_sources` status to `implemented` in Supabase if this source was tracked there.
5. **手動 DB 記錄的 source_id 命名一致性**：若需要手動插入 DB 記錄（補齊存量資料、測試子活動），先執行 `python main.py --dry-run --source <name>` 取得 scraper 實際產生的 source_id 格式，再與手動插入的 source_id 對比，確保完全一致。格式不符會導致後續 upsert 建立重複記錄而非更新現有記錄。

#### Bug fix

1. Append entry to `.github/skills/scraper-expert/history.md` (newest at top).
2. Append entry to `.github/skills/sources/<source_name>/history.md`.
3. If the lesson generalizes: add/update rule in `.github/skills/scraper-expert/SKILL.md`.
4. If the lesson is source-specific: add/update rule in the per-source `SKILL.md`.

### Phase 5: Commit & Push

**Always run this phase after Phase 4 — never call task_complete without pushing.**

#### Pre-commit gate (run before `git add`)

For **new sources**, verify ALL items are done:
- [ ] `scraper/sources/<source_name>.py` exists
- [ ] `scraper/main.py` has `import` AND `SCRAPERS` entry
- [ ] `.github/skills/sources/<source_name>/SKILL.md` created
- [ ] `.github/skills/sources/<source_name>/history.md` created
- [ ] `.github/skills/agents/scraper-expert/SKILL.md` has `## <source_name>-specific` section
- [ ] Supabase `research_sources`: `status=implemented`, **`scraper_source_name=<key>` (non-null)**
- [ ] ⚡ **Combined Post-Build Audit printed `🎉 ALL CLEAR`** — this is the single gate that verifies both `main.py` registration and `scraper_source_name` simultaneously. NEVER skip.

For **bug fixes**, verify:
- [ ] `.github/skills/agents/scraper-expert/history.md` prepended
- [ ] `.github/skills/sources/<source_name>/history.md` prepended (if source-specific)
- [ ] `scraper-expert/SKILL.md` updated if lesson is universal
- [ ] ⚡ **Combined Post-Build Audit printed `🎉 ALL CLEAR`** (even bug fixes can accidentally unregister scrapers)

1. Stage files (exclude temp scripts like `scan_loc.py`, `fix_*.py`, `.copilot-tracking/`).
   - New source: `scraper/sources/<source_name>.py`, `scraper/main.py`, `.github/skills/sources/<source_name>/`, `.github/skills/agents/scraper-expert/history.md`, `.github/skills/agents/scraper-expert/SKILL.md`
   - Bug fix: `scraper/sources/<source_name>.py`, `.github/skills/agents/scraper-expert/history.md`, `.github/skills/agents/scraper-expert/SKILL.md` (+ per-source skill if updated)
2. Commit on `main` branch:
   - New source: `feat(scraper): add <SourceName>Scraper for <display name>`
   - Bug fix: `fix(scraper): <what was fixed> in <source_name>`
3. `git push` (already on main; no feature branch needed for scraper-only changes).
4. Confirm push succeeded — report the commit SHA to the user.

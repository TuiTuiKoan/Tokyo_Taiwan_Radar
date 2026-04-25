---
name: scraper-expert
description: BaseScraper contract, field rules, and Peatix-specific conventions for the Scraper Expert agent
applyTo: .github/agents/scraper-expert.agent.md
---

# Scraper Expert Skills

Read this at the start of every session before writing any scraper.

## BaseScraper Contract
- Every scraper must extend `BaseScraper` and implement `scrape() → list[Event]`.
- `source_id` must be stable across runs — derive from URL slug or platform ID, never from title or list position.
- Always set `start_date` explicitly. Never fall back silently to the page's publish/update date.
- Prepend `開催日時: YYYY年MM月DD日\n\n` to `raw_description` when the event date is found in the page body.

## Peatix-specific
- Blocked organizer patterns live in `BLOCKED_ORGANIZER_PATTERNS` in `peatix.py` — always check before adding new title-based blocks.
- **台東区 false positive**: `台東` in `TAIWAN_KEYWORDS` can match the Tokyo ward 台東区. Use `_TAIWAN_KW_NO_TAITO` guard: skip if `台東区` in page text and no other Taiwan keywords match.
- **桃園区 false positive**: `桃園` in `TAIWAN_KEYWORDS` matches the Tokyo neighborhood 桃園区 (e.g. 桃園区民活動センター in Nakano ward), not Taoyuan Taiwan. Use `_TAIWAN_KW_NO_TAOYUAN` guard: skip if `桃園区` in page text and no other Taiwan keywords match.
- **General rule**: Any Taiwan place name that also exists as a Tokyo ward/neighborhood name needs a `_TAIWAN_KW_NO_<X>` guard. Pattern: `[kw for kw in TAIWAN_KEYWORDS if kw != "<keyword>"]` + check both the ambiguous keyword's presence and whether it appears only as part of the Tokyo place name.

## iwafu-specific
- **Global-tour false positive**: If description contains `台湾など世界各地` / `全国各地.*台湾` etc., the event is a nationwide/global tour where Taiwan is just one stop. Reject it — it is NOT a Taiwan-themed event. The `_GLOBAL_TOUR_PATTERNS` regex in `iwafu.py` implements this guard.
- **Title-level block**: Known IP series (e.g. `リアル脱出ゲーム×名探偵コナン`) must be blocked by `_BLOCKED_TITLE_PATTERNS` in `_scrape_detail` **before** the page load — this catches all tour stops as new source_ids appear. Add new entries here when a series is confirmed non-Taiwan-themed.
- **Permanent IP series block**: For series where ALL events are non-Taiwan-themed (e.g. `名探偵コナン`, `神韻`), add the IP name to `_BLOCKED_SERIES`. Checked on BOTH card title (pre-load, fast-reject) AND h1 title (post-load). Card titles from search results can be truncated, so the pre-load check alone is not sufficient.
- Taiwan relevance criterion: Taiwan must be the **theme or primary focus**, not just one venue on a multi-city tour.
- **After adding a scraper filter, always audit the DB**: run `ilike("raw_title", "%keyword%")` to find existing records that should also be deactivated. The filter only prevents future inserts.
- **Hard delete vs deactivation**: If an IP series is confirmed permanently non-Taiwan-themed, hard delete (`table.delete().eq("id", eid)`) rather than just deactivating. Deactivated events remain accessible via direct URL unless the event page also checks `is_active`.
- **location_name / location_address**: Extract from `場所[：:]\s*(.+?)(?:\n|交通手段|Q&A|https?://|$)` in `main_text`. Set BOTH `location_name` and `location_address` to the captured value. Fall back to `card.prefecture` only when the `場所：` label is absent. Never store bare prefecture names (e.g. `"東京"`) as the address.

## koryu-specific
- **location_address fallback**: `_extract_location_address()` searches for `所在地/住所` sections. When absent (common for 後援-type posts), fall back to the venue name from `_extract_venue()`: `location_address = _extract_location_address(body_text) or (venue if venue else None)`.
- **404 on old koryu URLs**: When a koryu event page returns 404, `main_text` will be a redirect message with no venue section. `_extract_venue` returns `None`, so `location_address` is also `None`. This is acceptable — the event is stale.
- **Single-day end_date**: Always set `end_date = start_date` at the end of `_extract_event_fields`. Taiwan Kyokai events are single-day ceremonies/lectures.
- **Publish-date false positive**: The page body starts with the article publish date (`2026年4月20日`) before the actual event content. Do NOT rely solely on the generic `YYYY年MM月DD日` fallback — it will pick up the publish date if no structured `日時：` field exists.
- **DOW-qualified date extraction**: Dates like `5月16日（土）` (with day-of-week) are actual event dates. Extract these BEFORE the generic fallback, then infer the year from the nearest `20XX年` in the text.
- Priority order for date extraction: `日時：` field → `時間：` field (with date) → DOW-qualified `月\d+日（曜日）` → generic `YYYY年MM月DD日` fallback.

## DeepL Tracking
- Add `self._deepl_chars_used: int = 0` to `BaseScraper.__init__`.
- Increment `self._deepl_chars_used += len(text)` at every DeepL API call.
- `main.py` reads `getattr(scraper, "_deepl_chars_used", 0)` when writing to `scraper_runs`.

## Annotator output cleaning
- Empty strings from GPT (`""`) must be treated as `None` — use `_str()` helper that returns `None` for falsy/blank strings. Prevents empty `name_zh`/`name_en` from blocking the `||` fallback chain in `getEventName`.
- Location fields must be stripped of leading label separators — use `_loc()` helper that calls `.lstrip("：；:; \u3000")`. GPT often includes the `会場：` or `場所：` separator as the first character of `location_name`.
- Apply `_loc()` to both `location_name` and `location_address`.
- Events with existing `""` in name/description fields need manual DB reset (`null` + `annotation_status = 'pending'`) then re-run `annotator.py`. The `_str()` helper only prevents future empty strings.

## Admin form (web) — nullable fields
- `AdminEditClient.tsx` initializes form fields with `event.field ?? ""`, converting `null` → `""`. On save, this writes `""` to the DB — which silences the locale fallback chain in `getEventName`/`getEventDescription`.
- The `handleSave` payload uses a `nullify` helper: `const nullify = (v: string) => v.trim() || null`. All name/description fields must pass through `nullify` before the Supabase PATCH.
- `name_ja` falls back to `event.raw_title` as last resort: `form.name_ja.trim() || event.raw_title || null`.
- In `web/lib/types.ts`, `getEventName`/`getEventDescription` use `||` (not `??`) — `||` catches both `null` and `""` for the locale fallback chain.

## database.py upsert — which fields get overwritten on every scraper run

The `upsert_events()` call in `database.py` uses `on_conflict="source_name,source_id"` and includes the following fields in every upsert payload (via `_event_to_row()`).

**Protection tiers:**
1. `is_active=False` events → **skipped entirely** (no update at all)
2. `annotation_status=annotated` events → **human-correctable fields are stripped** from the upsert payload before writing

**Fields protected for annotated events** (safe to manually patch — will survive future runs):
`name_ja`, `location_name`, `location_address`, `business_hours`, `category`

**Fields still updated even for annotated events** (raw data that legitimately changes):
`raw_title`, `raw_description`, `start_date`, `end_date`, `source_url`, `is_paid`, `price_info`

**Always safe fields** (never in `_event_to_row()` payload):
`annotation_status`, `name_zh`, `name_en`, `description_ja`, `description_zh`, `description_en`, `location_name_zh/en`, `location_address_zh/en`, `business_hours_zh/en`, `selection_reason`, `annotated_at`

**Rule**: `category` is in `_PROTECTED_FIELDS`. Once an admin corrects the category for an annotated event, the correction survives all future scraper runs. The `category_corrections` table provides few-shot examples to the annotator GPT to improve future predictions.

## AI category classification — rules from 69 admin corrections

Analysis of all corrections in `category_corrections` table (updated 2026-04-26).

### Category statistics (69 corrections)

| Category | AI missed (+) | AI over-predicted (−) | Net bias |
|----------|--------------|-----------------------|----------|
| `lecture` | +29 | −2 | **severely under-predicted** |
| `geopolitics` | +18 | 0 | **severely under-predicted** |
| `history` | +16 | 0 | **severely under-predicted** |
| `books_media` | +12 | 0 | **severely under-predicted** |
| `taiwan_japan` | +5 | −21 | **severely over-predicted** |
| `senses` | +9 | −1 | under-predicted |
| `lifestyle_food` | +7 | −2 | under-predicted |
| `movie` | +6 | 0 | under-predicted |
| `workshop` | +6 | 0 | under-predicted |
| `academic` | +2 | −5 | slightly over-predicted |
| `performing_arts` | +2 | −4 | slightly over-predicted |

### Mandatory keyword triggers (implemented in `_inject_keyword_categories`)

**`lecture`** — inject when ANY of these appear in text:
`トークイベント`, `トークショー`, `講演会`, `講演`, `シンポジウム`, `勉強会`, `例会`, `基調講演`, `映後座談`, `セッション`, `研究会`, `フォーラム`, `講座`
Also inject `lecture` when `movie` + any of `トーク`/`座談`/`講演` co-occur.

**`geopolitics`** — inject when ANY of these appear:
`危機`, `海峡`, `独立`, `民主化`, `移民政策`, `インド太平洋`, `日台関係`, `主権`, `国際フォーラム`, `給食政策`, `行政×AI`, `安全保障`, `防衛`

**`history`** — inject when ANY of these appear:
`戦没`, `植民地`, `統治`, `秘録`, `同化`, `傷痕`, `慰霊`, `戦前`, `戦後`, `日本統治`, `総督府`, `大濛`

### books_media formula (derived from 12 corrections)

Pattern: title contains `著者名 + 『書名』` OR contains `ブックサロン`/`刊行記念`/`出版記念`

**Always add**: `books_media` + `lecture` + `academic`
**Then add based on content**:
- Political/policy Taiwan → + `geopolitics`
- Historical figures or era → + `history`
- Explicitly about Japan-Taiwan bilateral topic → + `taiwan_japan`
- Book is about aesthetics/art/anthropology → + `senses`

Examples confirmed by corrections:
- `『李登輝秘録』` → academic + books_media + lecture + geopolitics + history
- `『日本と台湾の移民政策』` → academic + books_media + lecture + geopolitics + taiwan_japan
- `台湾研究ブックサロン` → academic + books_media + lecture (NO taiwan_japan unless explicitly bilateral)
- `『白球は海を渡る』刊行記念` → books_media + history + lecture + senses + taiwan_japan

### taiwan_japan — precise boundary (21 removals vs 5 additions)

**USE** `taiwan_japan` for:
- Formal Japan-Taiwan diplomatic/exchange events
- Taiwanese diaspora in Japan (`台湾系移住民`, `在日台湾人`)
- Taiwan veteran memorials (`台湾出身戦没者`)
- Academic research explicitly on Japan-Taiwan bilateral topics
- Medical/tech business matching between Japan and Taiwan companies (`台日医療`, `日台企業交流`)
- Government policy cooperation topics (`日暮 トモ子『日本と台湾の移民政策』`)

**DO NOT USE** `taiwan_japan` for:
- Taiwan food/tea events → `lifestyle_food` only
- Taiwan concert tours (拍謝少年, VOOID) → `performing_arts` only
- Taiwan tourism seminars by travel companies → `lecture` + `tourism`
- Taiwan children's book events → `books_media` + `lecture` + `senses`
- Taiwan film screenings (unless film is specifically about Japan-Taiwan history)
- General Taiwan cultural events without explicit bilateral focus
- Tech/AI conferences that mention Taiwan → `tech` + `academic` + `lecture`

### performing_arts — live-only rule (4 over-predictions)

`performing_arts` = **LIVE stage performances only**: concerts, theater, dance, opera.

**Never use for**:
- Film screenings (use `movie`)
- Asia/Japan tour announcements without confirmed Tokyo live show

### movie + lecture co-occurrence rule (100% co-occurrence in corrections)

All 11 `上映` events in corrections have both `movie` AND `lecture`. If `上映` + any talk/Q&A/座談 → always both.

Additionally, all sub-event screening sessions (上映回 1–6) of 大濛 got `history` added → screening of historical/political film always needs `history`.

### culture handling

`culture` is NOT a standard valid category but appears in some DB records. Humans always KEPT it and added more specific categories on top. Never use `culture` alone — always add the specific content category:
- `culture` + performance → add `performing_arts`
- `culture` + film → add `movie` + `lecture`
- `culture` + food/cooking → add `lifestyle_food` + `workshop`
- `culture` + political topic → add `geopolitics` + `lecture`
- `culture` + indigenous → add `academic` + `geopolitics` + `history` + `indigenous` + `lecture`

## Irrelevant event patterns — confirmed false positives (from admin review)

Based on 36 confirmed irrelevant reports. These event types are **NOT Taiwan-themed** even when they pass keyword filters:

### Peatix false positive patterns
| Pattern | Example | Root cause |
|---------|---------|------------|
| Typography/design series | `SDA60周年記念リレーセミナー`, `Day1 【図形】`, `Day2 【書体】` | Keyword hit on Chinese characters in design terminology, not Taiwan |
| Finnish-Japanese radio/podcast | `和フィン折衷対話ラジオ` | `和` + foreign word matches loosely |
| Life planning seminars | `人生100年計画セミナー`, `マンダラ人生計画セミナー` | `台湾` mentioned tangentially as comparison example |
| Japanese film/pop culture discussion | `月刊丸屋町山`, `どうなるハリウッド?!` | `taiwan_japan` over-prediction |
| Marketing/tech seminars | `ゲーム専門マーケティング×Steam`, `エラマ哲学バー` | Weak keyword match |
| Self-help / health lectures | `傷を抱えたままでも幸せになっていい` (畠山織恵) | Author has Taiwan connection but event not Taiwan-themed |
| Japanese recipe/food content | `オレンジページのオンライン点心動画`, `山脇りこ×大木淳夫` | 点心 / Kyoto content, not Taiwan food |
| Dance/performance workshops | `舞踏ワークショップ東京`, `メディアアートも楽笑よ` | Japanese artists with no Taiwan connection |
| Classical guitar recitals | `福田進一リサイタル——フランスのギター音楽` | No Taiwan connection |
| Philosophy bars | `エラマ哲学バー` | No Taiwan connection |
| Doorkeeper generic seminars | `人生100年計画`, `マンダラ人生計画` | Life planning with token Taiwan reference |

### eplus false positive patterns
| Pattern | Example | Root cause |
|---------|---------|------------|
| Japanese rock/J-pop bands | `KNOCK OUT MONKEY`, `三浦透子×近藤康平` | No Taiwan connection; keyword match on other content |
| Japanese music festivals | `CIRCLE '26` | General Japan music event |

### iwafu false positive patterns
| Pattern | Example | Root cause |
|---------|---------|------------|
| Japanese local/ceramic festivals | `上野焼 春の陶器まつり` | Regional Japanese craft, no Taiwan |
| Japanese nature festivals | `花の山寺 春の花まつり` | Local shrine/temple event |
| Japanese domestic airline | `スプリング・ジャパン客室乗務員訓練体験` | Spring Japan (日本の航空会社) — not related to Taiwan despite flights |
| Japanese photographer retrospectives | `あかがねミュージアム 木村伊兵衛 写真展` | Japanese Showa-era photographer |
| 8mm film exhibitions | `生活工房アレコレ2026 8ミリフィルム常設上映` | Japanese community art space |
| Healing/wellness workshops | `癒しのくう ワークショップ` | Japanese wellness, no Taiwan |
| World food festivals | `リトルワールド 世界の肉祭り` | International theme park event |

### Rules derived from false positives
- **Spring Japan (スプリング・ジャパン)** = Japanese domestic airline, NOT Taiwan-related. Block title pattern `スプリング・ジャパン` in iwafu.
- **台湾 as a comparison/reference** ≠ Taiwan-themed event. The event must have Taiwan as subject, not just mention it in passing.
- **Organizer has Taiwan connection ≠ event is Taiwan-themed**: Check the event title and description, not just organizer background.
- **Life planning / self-help seminars** with `台湾` in bio or slide content are consistently not Taiwan-themed events.
- **Japanese musicians/artists at non-Taiwan venues** with `台湾` somewhere in their profile are NOT Taiwan events.

## confirm-report.ts — annotation_status rules

**IMPORTANT**: Bugs in the `annotation_status` transition cause events to be permanently stranded.

| Action | Correct transition | Wrong (causes stranding) |
|--------|-------------------|--------------------------|
| wrongCategory + category provided | `is_active=true, status=annotated` | — |
| wrongCategory + no category | `status=pending` (keep is_active unchanged) | `is_active=false, status=pending` ← strands forever |
| wrongDetails + directly corrected | `is_active=true, status=annotated` | — |
| wrongDetails + needs re-annotation | `status=pending` (keep is_active unchanged) | `is_active=false, status=pending` ← strands forever |
| irrelevant | `is_active=false, status=annotated` | `is_active=false, status=pending` ← strands forever |

**Rule**: The annotator queries `is_active=True AND annotation_status=pending` only. Any path that sets `is_active=false` must NOT also set `annotation_status=pending`, as the event will never be processed and never be re-activated.

## Event detail page (web) — inactive events
- `web/app/[locale]/events/[id]/page.tsx` must include `if (!event.is_active) notFound()` immediately after fetching the event. Without this, deactivated events remain accessible by direct URL.
- Deactivating an event in the DB is NOT sufficient to hide it from public access — the detail page must also guard against it.

## Localized location / address / hours (migration 010)
- `location_name`, `location_address`, and `business_hours` have `_zh` and `_en` variants in the DB (migration 010).
- Annotator GPT schema explicitly requests `location_name_zh`, `location_name_en`, `location_address_zh`, `location_address_en`, `business_hours_zh`, `business_hours_en`.
- `web/lib/types.ts` exposes `getEventLocationName(event, locale)`, `getEventLocationAddress(event, locale)`, `getEventBusinessHours(event, locale)` — all fall back to the Japanese original if the localized variant is null.
- Event detail page (`/events/[id]/page.tsx`) uses these helpers instead of raw field access.
- **Rule**: Any field that a non-Japanese visitor reads on the event page must have locale variants OR use a helper with Japanese fallback. Check the event detail page for raw `event.field` access when adding new DB columns.


## eplus-specific
- **`_BLOCKED_TITLE_RE`**: Title patterns that cause immediate rejection before the event is appended. Add known non-Taiwan series here.
- **神韻 (Shen Yun) is permanently blocked**: It is a US-based Falun Gong performing arts group. It mentions 台湾 in search results but has **no connection to Taiwan culture**. Blocked in both `eplus.py` (`_BLOCKED_TITLE_RE`) and `iwafu.py` (`_BLOCKED_SERIES`).
- **No detail-page load in eplus**: Unlike iwafu, eplus does not visit individual event pages. All filtering must happen at card-parse time using `_BLOCKED_TITLE_RE`.

## jinf-specific
- **Correct page is `/meeting`**: `/event`, `/lecture` return 404. The upcoming events list is at `https://jinf.jp/meeting`.
- **`meetingbox` div not `<li>` or `<article>`**: Upcoming events are `<div class="meetingbox">` elements. Do NOT query for list items.
- **`【場　所】` has full-width space**: The label uses U+3000 between 場 and 所. Use both `場　所` and `場所` in fallback extraction.
- **`source_id` = form ID**: Use the numeric ID from `/meeting/form?id=NNNN` as the stable dedup key. Do NOT hash the title.
- **Filter on full box text**: Taiwan may appear only in speaker affiliations (`台湾元行政院副院長`), not in the title. Filter on full `box_text`, not just the title element.

## jats-specific
- **Two post types in category 6**: Cat 6 (`taikai-tokyo`) contains both announcement posts (`/taikai-tokyo/kantoNNN/`) and structured detail posts (`/taikai/tokyoNNN`). Only scrape detail posts matching `r"/taikai/tokyo\d+$"`.
- **`日時` label has NO colon**: Unlike Waseda where `日時：` uses a colon, JATS uses `日時 DATE` (space only). Use `r"日時\s+(\d{4}年..."`.
- **`場所` label also has no colon**: Same pattern — `場所 VENUE` without colon.
- **Stop labels for special chars**: `■`, `※`, `●`, `http` need the simpler `\s+CHAR` stop pattern (no trailing `[\s：:]`), because the char is immediately followed by Japanese text.
- **ALL events are Taiwan-related**: No keyword filter needed — cat 6 is entirely Taiwan studies research meetings.

## waseda_taiwan-specific
- **Event detection required**: Not all posts are events. Filter by `r'(?:日\s*時|開催日時|開催日)[：:：]'` in content. Working papers and newsletters lack these labels.
- **DOW removal must use space not empty**: `re.sub(r"[（(][月火水木金土日・祝]+[）)]", " ", raw)` — using `""` collapses `YYYY/M/DD（土）HH:MM` into `YYYY/M/DDHH:MM` with no separator.
- **`日 時：` with internal space**: Some posts write `日 時：` (with U+0020 space between 日 and 時). Use `r"日\s*時"` in regex.
- **Address parentheses**: Full address `（東京都...）` may be embedded in the venue string. Extract with `r"(東京都[^\s]{5,60})"` and strip trailing `）` with `.rstrip("）)")`.
- **WP REST API, single category**: All posts are `未分類` — no category filtering possible, must process all posts and filter by event detection.

## Registration
- After creating a new scraper file, always add it to `SCRAPERS = [...]` in `scraper/main.py`.
- Test with `python main.py --dry-run --source <source_name>` before any other step.

## Mandatory Post-Change Checklist

**Every time a scraper is modified or a new scraper is added, you MUST complete ALL of the following before returning. No exceptions.**

### 1. history.md — always update on bug fix or unexpected behaviour
- File: `.github/skills/scraper-expert/history.md`
- Append at the TOP (newest first):
  ```
  ---
  ## YYYY-MM-DD — <short title>
  **Error:** <what went wrong>
  **Fix:** <what was changed>
  **Lesson:** <generalizable rule> → [Added to SKILL.md | Already in SKILL.md]
  ---
  ```
- Skip only if the change is purely additive with zero unexpected behaviour (e.g. adding a new source that worked perfectly on first try with no surprises).

### 2. SKILL.md — update if a new rule is discovered
- File: `.github/skills/scraper-expert/SKILL.md` (this file)
- If the lesson is source-specific: add a `## <source>-specific` subsection or extend the existing one.
- If the lesson is universal (applies to all scrapers): add it under `## BaseScraper Contract` or `## Registration`.
- Never duplicate a rule that already exists.

### 3. Per-source SKILL.md — update if a platform rule changed
| Modified source | Platform SKILL to update |
|-----------------|--------------------------|
| `peatix.py` | `.github/skills/peatix/SKILL.md` |
| `taiwan_cultural_center.py` | `.github/skills/taiwan_cultural_center/SKILL.md` |
| `connpass.py` or `doorkeeper.py` | `.github/skills/community-platforms/SKILL.md` |
| Other sources | No dedicated SKILL yet — add rule here instead |

### 4. dry-run validation — always run before finishing
```bash
cd scraper && python main.py --dry-run --source <source_name> 2>&1 | head -80
```
Confirm: `start_date` populated, no unhandled exceptions, events count is non-zero (or zero for an expected reason).

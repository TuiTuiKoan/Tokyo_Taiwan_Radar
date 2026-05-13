---
applyTo: "supabase/**"
---

# Database — Coding Instructions

## Supabase project

- Project ref: `cjtndektjjpvvjofdvzr`
- Run migrations via **Supabase Dashboard → SQL Editor** (no CLI access configured)
- Number migrations sequentially: `001`, `002`, … Latest is `069_explicit_grants.sql` (number `044` is reserved for future corrections work — skip to `070` for the next new migration)
- If the next sequence number is already taken, append `b` (e.g. `012b_event_reports_suggested_category.sql`) and add a comment at the top of the SQL file explaining the conflict. Do not skip numbers silently.
- Known conflicts: `011_force_rescrape.sql` + `011_secondary_source_urls.sql`; `018_official_url.sql` + `018b_scraped_at.sql`; `020_creators.sql` was the intended 019 but 019 was skipped; `029_aeo_visits.sql` + `029b_realtime_events.sql`; `038_performer.sql` + `038b_field_corrections.sql`

## Explicit GRANT requirement (Supabase policy change — effective October 30, 2026)

**Starting October 30, 2026, Supabase no longer grants implicit Data API access to new tables in the public schema.** Every migration that creates a new table MUST include explicit `GRANT` statements, or PostgREST/supabase-js will return a `42501` error.

### GRANT template for new table migrations

Use the tier that matches the table's access model:

```sql
-- ── Tier A: Public-read table (web app reads via anon key) ──────────────────
ALTER TABLE public.your_table ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.your_table TO anon, authenticated, service_role;
-- (add INSERT/UPDATE/DELETE to authenticated/service_role as needed)

-- ── Tier B: Admin-only table (no anon access) ───────────────────────────────
ALTER TABLE public.your_table ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.your_table
  TO authenticated, service_role;

-- ── Tier C: Service-role only (scraper/internal) ────────────────────────────
ALTER TABLE public.your_table ENABLE ROW LEVEL SECURITY;
-- No RLS policy = deny-all for anon/authenticated; service_role bypasses RLS.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.your_table
  TO service_role;
```

**Rules:**
- Always enable RLS before adding GRANTs — without RLS, any granted role has unrestricted row access
- `service_role` bypasses RLS but still needs an explicit table-level GRANT post-October 30
- GRANTs for `anon` should only be added to tables with a public-read RLS policy (`USING (true)` or `USING (is_active = true)`)
- Migration `069_explicit_grants.sql` covers all tables created before this rule was introduced

## Schema overview

### `events` (core table)

| Column | Type | Notes |
|--------|------|-------|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `source_name` | `text` | Snake-case scraper key |
| `source_id` | `text` | Stable per-source ID — dedup key |
| `source_url` | `text` | |
| `original_language` | `text` | `'ja'` \| `'zh'` \| `'en'` |
| `name_ja/zh/en` | `text` | Trilingual |
| `description_ja/zh/en` | `text` | Trilingual |
| `category` | `text[]` | Values from canonical category list |
| `start_date` / `end_date` | `timestamptz` | |
| `location_name/address` | `text` | |
| `business_hours` | `text` | |
| `is_paid` | `boolean` | |
| `price_info` | `text` | |
| `is_active` | `boolean` | default `true` |
| `parent_event_id` | `uuid` → `events.id` | Set on sub-events only |
| `raw_title` | `text` | Original scrape, never overwritten |
| `raw_description` | `text` | Original scrape, never overwritten |
| `selection_reason` | `text` | JSON: `{"ja":"…","zh":"…","en":"…"}` |
| `annotation_status` | `text` | `'pending'` → `'annotated'` → `'reviewed'` (human-confirmed, fully protected) |
| `annotated_at` | `timestamptz` | |
| `force_rescrape` | `boolean` | When `true`, next scraper run fully overwrites and resets to `pending` |
| `secondary_source_urls` | `text[]` | Secondary source URLs appended by `merger.py` |
| `official_url` | `text` | Authoritative organiser URL; takes display priority over `source_url`; `NULL` = unknown |
| `scraped_at` | `timestamptz` | Last scraper upsert timestamp |
| `record_links` | `jsonb` | Array of `{title, url}` for post-event coverage; admin-managed; default `[]` |
| `organizer` | `text` | Primary organizer name |
| `co_organizers` | `text[]` | Co-organizer names |
| `sponsors` | `text[]` | Sponsor names |
| `organizer_type` | `text` | CHECK: `government`, `npo`, `academic`, `corporate`, `media`, `community`, `individual`, `other` |
| `event_form` | `text` | CHECK: `in_person`, `online`, `hybrid` |
| `primary_language` | `text` | CHECK: `ja`, `zh`, `en`, `multi` |
| `has_japanese_support` | `boolean` | default `false` |
| `has_english_support` | `boolean` | default `false` |
| `organizer_url` | `text` | Authoritative organiser URL for Schema.org JSON-LD |
| `price_amount` | `numeric` | Numeric ticket price for Schema.org Offers |
| `price_currency` | `text` | ISO 4217 currency code; default `'JPY'` |
| `event_status` | `text` | CHECK: `scheduled`, `cancelled`, `postponed`, `rescheduled`; default `'scheduled'` |
| `performer` | `text` | Single primary performer/presenter for Schema.org Person |
| `created_at` / `updated_at` | `timestamptz` | |

Unique constraint: `(source_name, source_id)`

### Other tables

- `saved_events` — `(user_id uuid, event_id uuid)` for user bookmarks
- `user_roles` — `(user_id uuid, role text)` e.g. `'admin'`
- `category_corrections` — admin feedback for AI annotator retraining
- `event_reports` — user-submitted corrections / reports on events
- `scraper_runs` — per-run logs (source, event counts, success, duration_seconds)
- `research_reports` — Researcher agent output per source
- `research_sources` — curated list of candidate sources with `status` (`pending` / `viable` / `not-viable` / `implemented`); `scraper_source_name` (matches `_scraper_key()` in main.py); `scrape_times_per_day` int (1–8, default 1); `scrape_hours_jst` int[] (default `{9}`); `display_type` text (one of the 14 source types — see `sources.type`; admin-editable via PATCH `/api/admin/research-sources/:id`; backfilled in migration 068 from the legacy hardcoded `SOURCE_TYPE_MAP` in `web/components/AdminSourcesTable.tsx`)
- `backup_archives` — snapshot metadata
- `event_views` — click analytics per event+locale (view: `event_view_counts`)
- `admin_users_view` — admin-only view of `auth.users` joined with roles
- `creators` — Taiwan creators/voices in Japan: name, platform, handle, profile_url, category, base_location, nationality, is_active, approx_followers, last_post_at, notes
- `creator_events` — `(creator_id uuid, event_id uuid, relationship text)` links creators to events
- `line_subscribers` — LINE OA subscribers: `line_user_id`, `status` (`active`/`blocked`), `language_preference`, `category_preferences text[]`; service-role-only RLS (migration 022)
- `field_corrections` — admin-corrected field values: `(event_id, field_name)` unique; `original_value`, `corrected_value`, `corrected_by`, `report_id` (FK→event_reports, nullable); annotator reads at startup and never overwrites protected fields
- `selection_reason_corrections` — admin-corrected `selection_reason` records: `event_id` unique; `raw_title`, `raw_description` (for few-shot context); `ai_sr` jsonb, `corrected_sr` jsonb; annotator reads at startup via `selection_reason_feedback.py` for few-shot injection
- `source_exclusions` — admin-defined pattern rules for blocking irrelevant events before upsert: `source_name`, `pattern`, `pattern_type` (substring/regex), `match_field`, `is_active`, `expires_at` (NULL = permanent), `auto_disabled_at`, `auto_disabled_reason` (`expired` | `stale_no_hits`); admin-only RLS. View `source_exclusions_effective` exposes only currently-in-force rules (active, not auto-disabled, not expired); daily CI job `exclusions_maintenance.py` flips `auto_disabled_at` for expired or 90-day-stale rules.
- `source_exclusion_hits` — per-event hit log for exclusion rule matches: `rule_id` FK→source_exclusions, `raw_title`, `source_name`, `matched_at`; 30-day rolling window; service role INSERT (no RLS policy needed); admin-only SELECT
- `announcements` — social/LINE post drafts: `slug` (UNIQUE), `type` (`'manual'` | `'weekly_broadcast'`), `title_*/body_*/image_*` (trilingual), `published_at` (null=draft, future=scheduled, past=published), `social_status` jsonb, `is_featured`; admin-only write RLS
- `announcement_events` — `(announcement_id, event_id)` junction linking announcements to events
- `app_settings` — global key-value config: `key` text PK, `value` jsonb; admin-only RLS; seeded with `weekly_broadcast: {auto_publish: false}`
- `daily_quality_metrics` — daily aggregated KPI: `events_upserted`, `events_active`, `exclusion_hits`, `irrelevant_reports`, `precision_rate`; computed by `scraper/daily_quality.py` (recomputes last 14 days each run to absorb late reports); admin-only RLS
- `sources` — scraper source registry: `id TEXT PK` (= events.source_name), `name`, `type` (one of 14 values: `government` / `academic` / `event_platform` / `cinema` / `tv` / `venue` / `department_store` / `organizer` / `ngo` / `news_media` / `taiwan_shop` / `personal` / `creator` / `other` — see migrations 060 + 067), `frequency` (daily/weekly), `official_url`, `sort_order INT`, `is_active BOOL`; public SELECT RLS; seeded with 104 rows from web/lib/sources.ts; used by `/sources` public page (migration 060). When adding a new source: insert via SQL with the matching `type` value — do NOT touch `web/lib/sources.ts` SOURCE_TYPES; that array is the SourceType union, not data.

## RLS policies

- Public: `SELECT` on `events` where `is_active = true`
- Authenticated: `SELECT` on `saved_events` for own rows; `INSERT`/`DELETE` own rows
- Admin (`is_admin()`): full access on all tables
- Service role (scraper): bypasses RLS via `SUPABASE_SERVICE_ROLE_KEY`

## Query conventions

- Homepage always filters: `.is("parent_event_id", null)` — hides sub-events
- Public pages: only show `annotation_status IN ('annotated', 'reviewed')` events
- Upsert uses `on_conflict="source_name,source_id"` with `ignoreDuplicates=False`

## Migration checklist
7
1. Number the file `NNN_descriptive_name.sql` (next = `061`)
2. Use `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
3. Add RLS with `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + policies
4. Test in Supabase SQL Editor before committing
5. Commit the `.sql` file to `supabase/migrations/`
6. **Update this file in the same commit**: "Latest is …", "next = N", Known conflicts (if b-suffix), schema table (new columns), Other tables (new tables), Query conventions (if changed)

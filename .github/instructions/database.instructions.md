---
applyTo: "supabase/**"
---

# Database — Coding Instructions

## Supabase project

- Project ref: `cjtndektjjpvvjofdvzr`
- Run migrations via **Supabase Dashboard → SQL Editor** (no CLI access configured)
- Number migrations sequentially: `001`, `002`, … Latest is `021_record_links.sql`
- If the next sequence number is already taken, append `b` (e.g. `012b_event_reports_suggested_category.sql`) and add a comment at the top of the SQL file explaining the conflict. Do not skip numbers silently.
- Known conflicts: `011_force_rescrape.sql` + `011_secondary_source_urls.sql`; `018_official_url.sql` + `018b_scraped_at.sql`; `020_creators.sql` was the intended 019 but 019 was skipped

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
| `created_at` / `updated_at` | `timestamptz` | |

Unique constraint: `(source_name, source_id)`

### Other tables

- `saved_events` — `(user_id uuid, event_id uuid)` for user bookmarks
- `user_roles` — `(user_id uuid, role text)` e.g. `'admin'`
- `category_corrections` — admin feedback for AI annotator retraining
- `event_reports` — user-submitted corrections / reports on events
- `scraper_runs` — per-run logs (source, event counts, success, duration_seconds)
- `research_reports` — Researcher agent output per source
- `research_sources` — curated list of candidate sources with `status` (`pending` / `viable` / `not-viable` / `implemented`)
- `backup_archives` — snapshot metadata
- `event_views` — click analytics per event+locale (view: `event_view_counts`)
- `admin_users_view` — admin-only view of `auth.users` joined with roles
- `creators` — Taiwan creators/voices in Japan: name, platform, handle, profile_url, category, base_location, nationality, is_active, approx_followers, last_post_at, notes
- `creator_events` — `(creator_id uuid, event_id uuid, relationship text)` links creators to events

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

1. Number the file `NNN_descriptive_name.sql` (next = `022`)
2. Use `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
3. Add RLS with `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + policies
4. Test in Supabase SQL Editor before committing
5. Commit the `.sql` file to `supabase/migrations/`
6. **Update this file in the same commit**: "Latest is …", "next = N", Known conflicts (if b-suffix), schema table (new columns), Other tables (new tables), Query conventions (if changed)

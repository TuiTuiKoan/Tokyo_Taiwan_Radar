---
applyTo: "supabase/**"
---

# Database — Coding Instructions

## Supabase project

- Project ref: `cjtndektjjpvvjofdvzr`
- Run migrations via **Supabase Dashboard → SQL Editor** (no CLI access configured)
- Number migrations sequentially: `001`, `002`, … Latest is `005_category_corrections.sql`

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
| `annotation_status` | `text` | `'pending'` → `'annotated'` |
| `annotated_at` | `timestamptz` | |
| `created_at` / `updated_at` | `timestamptz` | |

Unique constraint: `(source_name, source_id)`

### Other tables

- `saved_events` — `(user_id uuid, event_id uuid)` for user bookmarks
- `user_roles` — `(user_id uuid, role text)` e.g. `'admin'`
- `category_corrections` — admin feedback for AI annotator retraining

## RLS policies

- Public: `SELECT` on `events` where `is_active = true`
- Authenticated: `SELECT` on `saved_events` for own rows; `INSERT`/`DELETE` own rows
- Admin (`is_admin()`): full access on all tables
- Service role (scraper): bypasses RLS via `SUPABASE_SERVICE_ROLE_KEY`

## Query conventions

- Homepage always filters: `.is("parent_event_id", null)` — hides sub-events
- Public pages: only show `annotation_status = 'annotated'` events
- Upsert uses `on_conflict="source_name,source_id"` with `ignoreDuplicates=False`

## Migration checklist

1. Number the file `NNN_descriptive_name.sql` (next = `006`)
2. Use `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
3. Add RLS with `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + policies
4. Test in Supabase SQL Editor before committing
5. Commit the `.sql` file to `supabase/migrations/`

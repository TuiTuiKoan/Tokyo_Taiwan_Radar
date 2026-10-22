---
applyTo: "supabase/**"
---

# Database — Coding Instructions

## Supabase project

- Project ref: `cjtndektjjpvvjofdvzr`
- Run migrations via **Supabase Dashboard → SQL Editor** (no CLI access configured)
- Number migrations sequentially: `001`, `002`, … Latest is `100_rpc_execute_lockdown.sql` (next = `101`). Previous milestones: `076_venues_authority.sql`, `077_*`, `078_performer_url.sql`, `079` (skipped), `080_fc_metric_fix.sql`, `081_venues_business_hours.sql`, `082_announcements_storage_bucket.sql`, `083_event_views_country_region.sql`, `084_fix_security_invoker_views.sql`, `085_event_views_traffic_source.sql`, `086_account_profiles.sql`, `087_increment_account_usage_rpc.sql`, `088_rls_perf_account.sql`, `089_annotation_retry_count.sql`, `090_event_submission_url.sql`, `091_sources_hankyu_stores.sql` (registers hankyu_hakata/hankyu_kobe as department_store, sets hankyu_umeda frequency=weekly), `092_sources_hanshin.sql` (registers hanshin_umeda as department_store/weekly), `093_sources_hanshin_branches.sql` (registers hanshin_nishinomiya/hanshin_mikage/hanshin_amagasaki as department_store/weekly), `094_admin_reports_maintenance_lock.sql` (decision-16a Admin Reports #204 cleanup lock: fail-closed `admin_reports_maintenance_active()` predicate that treats only exact JSON boolean `false` as inactive + per-command RESTRICTIVE RLS on the six writer tables + lock-key immutability for `authenticated`; **APPLIED in production (confirmed 2026-08-01), after `_oneoff_admin_reports_maintenance.py seed-inactive` seeded the inactive row**), `095_organizer_authority.sql` (organizers authority columns + `events` co-organizer/sponsor cardinality CHECKs + `research_sources` 10-value scalar CHECK; **APPLIED in production, confirmed 2026-08-01**), `096_maintenance_lock_search_path.sql` (Lane A A2 narrow-scope hardening of the decision-16a lock: `CREATE OR REPLACE` — never `DROP`, the RESTRICTIVE policies depend on the function OID — moves `admin_reports_maintenance_active()` from `search_path = public` to the contract value `pg_catalog` and re-declares owner + EXECUTE ACL idempotently; **APPLIED in production, confirmed 2026-08-01**), `097_sources_retire_connpass_doorkeeper.sql` (after the Connpass/Doorkeeper scrapers were deleted: `sources.is_active = FALSE` for both, soft-disables active `doorkeeper` events with `deactivated_reason = 'source_retired_doorkeeper'`, moves their `research_sources` rows to `not-viable`; **not yet applied**), `098_scope_report_transaction.sql` (next = `098`). Previous milestones: `076_venues_authority.sql`, `077_*`, `078_performer_url.sql`, `079` (skipped), `080_fc_metric_fix.sql`, `081_venues_business_hours.sql`, `082_announcements_storage_bucket.sql`, `083_event_views_country_region.sql`, `084_fix_security_invoker_views.sql`, `085_event_views_traffic_source.sql`, `086_account_profiles.sql`, `087_increment_account_usage_rpc.sql`, `088_rls_perf_account.sql`, `089_annotation_retry_count.sql`, `090_event_submission_url.sql`, `091_sources_hankyu_stores.sql` (registers hankyu_hakata/hankyu_kobe as department_store, sets hankyu_umeda frequency=weekly), `092_sources_hanshin.sql` (registers hanshin_umeda as department_store/weekly), `093_sources_hanshin_branches.sql` (registers hanshin_nishinomiya/hanshin_mikage/hanshin_amagasaki as department_store/weekly), `094_admin_reports_maintenance_lock.sql` (decision-16a Admin Reports #204 cleanup lock: fail-closed `admin_reports_maintenance_active()` predicate that treats only exact JSON boolean `false` as inactive + per-command RESTRICTIVE RLS on the six writer tables + lock-key immutability for `authenticated`; **APPLIED in production (confirmed 2026-08-01), after `_oneoff_admin_reports_maintenance.py seed-inactive` seeded the inactive row**), `095_organizer_authority.sql` (organizers authority columns + `events` co-organizer/sponsor cardinality CHECKs + `research_sources` 10-value scalar CHECK; **APPLIED in production, confirmed 2026-08-01**), `096_maintenance_lock_search_path.sql` (Lane A A2 narrow-scope hardening of the decision-16a lock: `CREATE OR REPLACE`, never `DROP`, because the RESTRICTIVE policies depend on the function OID; moves `admin_reports_maintenance_active()` from `search_path = public` to `pg_catalog` and re-declares owner + EXECUTE ACL idempotently; **APPLIED in production, confirmed 2026-08-01**), `098_scope_report_transaction.sql` (adds the `SECURITY INVOKER` `confirm_scope_report` RPC with report/event row locks, canonical evidence-hash validation, atomic event deactivation + report confirmation, and a RESTRICTIVE INSERT policy reserving scope/security machine tokens for service role; **APPLIED in production, confirmed 2026-10-22** (read-back: `prosecdef=false`, owner `postgres`, `search_path=pg_catalog`, EXECUTE only for `authenticated`/`service_role`; RESTRICTIVE INSERT policy on `anon`/`authenticated`; anonymous call raises `42501 Forbidden`)), `099_llm_usage.sql` (llm-cost-reset #363: `llm_usage` one row per OpenAI call, `llm_pricing` the only place prices live, `security_invoker` view `llm_cost_daily` computing cost per JST day/caller/model at read time, `llm_cache` processed markers for enrich steps; admin-read RLS, service-role writes, explicit `REVOKE ALL … FROM anon, authenticated` because default privileges still auto-grant before 2026-10-30; **APPLIED in production, confirmed 2026-10-22** (read-back: four objects present, view `security_invoker=true`, RLS on the three tables, 2 `llm_pricing` rows, anon has no grants, authenticated SELECT only; migration record `20261022135429 099_llm_usage`; the security advisor's only new finding is INFO `rls_enabled_no_policy` on the intentionally service-role-only `llm_cache`)), `100_rpc_execute_lockdown.sql` (revokes EXECUTE from `PUBLIC`/`anon`/`authenticated` on the `SECURITY DEFINER` helpers `archive_event_related_data(uuid[], text)` and `increment_account_usage(uuid, integer, integer)`, leaving `service_role` only, and pins the latter's `search_path` to `pg_catalog`; a trailing `DO` block aborts the transaction if the ACL check fails. Background: `REVOKE ... FROM PUBLIC` alone does not remove Supabase's direct default grants to `anon`/`authenticated`; **APPLIED in production, confirmed 2026-10-22** (read-back: both ACLs are `{postgres=X, service_role=X}`, `increment_account_usage` `search_path=pg_catalog`; security advisor lints 0011/0028/0029 no longer list either function)).
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

### Functions: revoke from `anon` and `authenticated` by name

Supabase's default privileges grant `EXECUTE` on every new `public` function directly to `anon` and `authenticated`, so `REVOKE ... FROM PUBLIC` alone leaves the function callable through `/rest/v1/rpc/` (migration 013 missed this; fixed in 100). For a `SECURITY DEFINER` function that only server code calls:

```sql
REVOKE EXECUTE ON FUNCTION public.fn(args) FROM PUBLIC, anon, authenticated;
GRANT  EXECUTE ON FUNCTION public.fn(args) TO service_role;
```

Grant `authenticated` only when the body checks the caller itself (`auth.uid()` / `is_admin()`), and always pin `SET search_path`.

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
| `annotation_status` | `text` | `'pending'` → `'annotated'` → `'reviewed'` (human-confirmed, fully protected); `'error'` set by annotator on parse failure, recovered by `error_recovery.py` |
| `annotated_at` | `timestamptz` | |
| `annotation_retry_count` | `int` | default `0`; `error_recovery.py` retry counter for stuck `'error'` events (migration 089) |
| `force_rescrape` | `boolean` | When `true`, next scraper run fully overwrites and resets to `pending` |
| `secondary_source_urls` | `text[]` | Secondary source URLs appended by `merger.py` |
| `official_url` | `text` | Authoritative organiser URL; takes display priority over `source_url`; `NULL` = unknown |
| `scraped_at` | `timestamptz` | Last scraper upsert timestamp |
| `record_links` | `jsonb` | Array of `{title, url}` for post-event coverage; admin-managed; default `[]` |
| `organizer` | `text` | Primary organizer name |
| `co_organizers` | `text[]` | Co-organizer names |
| `co_organizer_types` | `text[]` | Parallel to `co_organizers`; same length enforced by `events_co_org_cardinality_check` (migration 095) |
| `sponsors` | `text[]` | Sponsor names |
| `sponsor_types` | `text[]` | Parallel to `sponsors`; same length enforced by `events_sponsor_cardinality_check` (migration 095) |
| `organizer_type` | `text[]` | CHECK: elements from the canonical 10-value set `government`, `semi_official`, `cultural_institution`, `academic`, `commercial_brand`, `independent_venue`, `civic_group`, `media`, `individual`, `unknown` (migration 086). Pass a Python list, never a bare string. The annotator LLM vocabulary stays at 9 values and never emits `individual` |
| `event_form` | `text[]` | CHECK: elements from `exhibition`, `screening`, `lecture`, `performance`, `market`, `workshop`, `conference`, `networking`, `screening_with_talk`, `tour`, `competition`, `tasting`, `broadcast`, `study_abroad`, `publication`, `other` (migration 047 renamed the pre-047 names; writer whitelist is `_VALID_EVENT_FORMS` in `scraper/database.py`) |
| `primary_language` | `text` | CHECK: `ja`, `zh`, `en`, `mixed` |
| `has_japanese_support` | `boolean` | default `false` |
| `has_english_support` | `boolean` | default `false` |
| `organizer_url` | `text` | Authoritative organiser URL for Schema.org JSON-LD |
| `price_amount` | `numeric` | Numeric ticket price for Schema.org Offers |
| `price_currency` | `text` | ISO 4217 currency code; default `'JPY'` |
| `event_status` | `text` | CHECK: `scheduled`, `cancelled`, `postponed`, `rescheduled`; default `'scheduled'` |
| `performer` | `text` | Single primary performer/presenter for Schema.org Person |
| `created_at` / `updated_at` | `timestamptz` | |

Unique constraint: `(source_name, source_id)`

Cardinality constraints (migration 095, ordinary VALIDATED constraints enforced table-wide): `events_co_org_cardinality_check` requires `cardinality(co_organizers) = cardinality(co_organizer_types)`, and `events_sponsor_cardinality_check` requires `cardinality(sponsors) = cardinality(sponsor_types)`. NULL and empty array both count as 0. A writer that fills one side of a pair must fill the other or the write is rejected.

### Other tables

- `saved_events` — `(user_id uuid, event_id uuid)` for user bookmarks
- `user_roles` — `(user_id uuid, role text)` e.g. `'admin'`
- `account_usage` — `(user_id uuid, usage_date date, annotate_count int)` tracks daily quota usages (migration 086/087)
- `category_corrections` — admin feedback for AI annotator retraining
- `event_reports` — user-submitted corrections / reports on events; machine-owned scope/security tokens are service-role-only after migration 098, and scope confirmation uses the atomic `confirm_scope_report` RPC
- `scraper_runs` — per-run logs (source, event counts, success, duration_seconds). Its `cost_usd` is legacy (annotator/researcher only, hard-coded prices); OpenAI cost comes from `llm_cost_daily` (migration 099)
- `llm_usage` — one row per OpenAI API call (migration 099): `caller` (`<group>.<name>`), requested `model`, `endpoint` (`chat`/`responses`), `input_tokens` (includes cached), `cached_input_tokens`, `output_tokens`, `web_search_calls`, `status` (`ok`/`error`), `error_code`, `user_id` (web account APIs), `run_ref`; written by `scraper/llm_client.py` and `web/lib/llm/openai.server.ts` with the service role; admin-only SELECT
- `llm_pricing` — `(model, effective_from)` PK with USD per 1M `input`/`cached_input`/`output` tokens and `per_web_search_call`; change a price by adding a row with a new `effective_from`, never by editing code
- `llm_cost_daily` — `security_invoker` view: calls, errors, tokens and `cost_usd` per JST `day`, `caller`, `model`; `unpriced_calls` counts calls whose model has no price row. The OpenAI dashboard stays the source of truth
- `llm_cache` — `(step, subject_key)` PK, `result jsonb`, `outcome`, `attempted_at`; service-role only; lets enrich steps skip inputs already sent to the LLM
- `research_reports` — Researcher agent output per source
- `research_sources` — curated list of candidate sources with `status` (`pending` / `viable` / `not-viable` / `implemented`); `scraper_source_name` (matches `_scraper_key()` in main.py); `scrape_times_per_day` int (1–8, default 1); `scrape_hours_jst` int[] (default `{9}`); `display_type` text (one of the 14 source types — see `sources.type`; admin-editable via PATCH `/api/admin/research-sources/:id`; backfilled in migration 068 from the legacy hardcoded `SOURCE_TYPE_MAP` in `web/components/AdminSourcesTable.tsx`)
- `backup_archives` — snapshot metadata
- `event_views` — click analytics per event+locale+country (view: `event_view_counts`)
- `admin_users_view` — admin-only view of `auth.users` joined with roles
- `creators` — Taiwan creators/voices in Japan: name, platform, handle, profile_url, category, base_location, nationality, is_active, approx_followers, last_post_at, notes
- `creator_events` — `(creator_id uuid, event_id uuid, relationship text)` links creators to events
- `line_subscribers` — LINE OA subscribers: `line_user_id`, `status` (`active`/`blocked`), `language_preference`, `category_preferences text[]`; service-role-only RLS (migration 022)
- `field_corrections` — admin-corrected field values: `(event_id, field_name)` unique; `original_value`, `corrected_value`, `corrected_by`, `report_id` (FK→event_reports, nullable); `first_override_attempted_at` (write-once, set on first B1 guard hit); `last_override_attempted_at` (updated on every B1 guard hit); `override_attempt_count` (cumulative); annotator reads at startup and never overwrites protected fields
- `field_corrections_audit` — audit trail for `qa_heartbeat.py` automatic FC unlock/override (migration 075): `event_id`, `field_name`, `report_id`, `event_before_value_json`/`event_after_value_json` (JSONB so text[] roundtrips), `fc_before_*` columns, `unlock_reason`, `r_class`, `model_used`, `confidence`, `operation_status` (`started`|`applied`|`verify_failed`|`rolled_back`), `verified_at`, `rolled_back_at`, `rolled_back_reason`; service-role-only RLS
- `selection_reason_corrections` — admin-corrected `selection_reason` records: `event_id` unique; `raw_title`, `raw_description` (for few-shot context); `ai_sr` jsonb, `corrected_sr` jsonb; annotator reads at startup via `selection_reason_feedback.py` for few-shot injection
- `source_exclusions` — admin-defined pattern rules for blocking irrelevant events before upsert: `source_name`, `pattern`, `pattern_type` (substring/regex), `match_field`, `is_active`, `expires_at` (NULL = permanent), `auto_disabled_at`, `auto_disabled_reason` (`expired` | `stale_no_hits`); admin-only RLS. View `source_exclusions_effective` exposes only currently-in-force rules (active, not auto-disabled, not expired); daily CI job `exclusions_maintenance.py` flips `auto_disabled_at` for expired or 90-day-stale rules.
- `source_exclusion_hits` — per-event hit log for exclusion rule matches: `rule_id` FK→source_exclusions, `raw_title`, `source_name`, `matched_at`; 30-day rolling window; service role INSERT (no RLS policy needed); admin-only SELECT
- `announcements` — social/LINE post drafts: `slug` (UNIQUE), `type` (`'manual'` | `'weekly_broadcast'`), `title_*/body_*/image_*` (trilingual), `published_at` (null=draft, future=scheduled, past=published), `social_status` jsonb, `is_featured`; admin-only write RLS
- `announcement_events` — `(announcement_id, event_id)` junction linking announcements to events
- `app_settings` — global key-value config: `key` text PK, `value` jsonb; admin-only RLS; seeded with `weekly_broadcast: {auto_publish: false}`. Reserved key `admin_reports_cleanup_maintenance` `{active: bool, window_id, reason, opened_at, actor}` is the decision-16a Admin Reports #204 maintenance lock — **service-role-only** (RESTRICTIVE `app_settings_lock_key_immutable` from migration 094 blocks all `authenticated` writes to this key; the browser cannot flip it). Operated solely by `scraper/_oneoff_admin_reports_maintenance.py` (status / seed-inactive / acquire / release) via atomic token+`value->>active` compare-and-set.
- `daily_quality_metrics` — daily aggregated KPI: `events_upserted`, `events_active`, `exclusion_hits`, `irrelevant_reports`, `precision_rate`, `fc_override_attempts` (first-occurrence count via `first_override_attempted_at`), `annotator_stage1_pass`, `annotator_stage2_pass` (combined), `annotator_stage2_nz_pass`, `annotator_stage2_ne_pass` (split), `annotator_eval_run_at`; computed by `scraper/daily_quality.py` (recomputes last 14 days each run to absorb late reports); admin-only RLS
- `organizers` — organizer entity registry (migration 050): `id UUID PK`, `name`, `organizer_type TEXT` scalar with the same canonical 10-value CHECK as `events.organizer_type` (migration 095 normalized the legacy JSON-text form `'["commercial_brand"]'` to the bare scalar), `is_authoritative BOOL NOT NULL DEFAULT false` (migration 095; when true the registry resolver treats this row as the canonical entity type unless a `field_corrections` lock exists — LLM output must never flip this flag), partial index `idx_organizers_is_authoritative` on `is_authoritative = true`
- `venues` — venue registry: `id UUID PK`, `name TEXT`, `address TEXT`, `prefecture TEXT`, `lat/lng NUMERIC`, `is_authoritative BOOL`, `location_name_zh/en TEXT`, `location_url TEXT`, `business_hours TEXT` (standard operating hours; used by `enrich_location.py` to auto-populate `events.business_hours` when `is_authoritative=true` and no FC lock exists)
- `sources` — scraper source registry: `id TEXT PK` (= events.source_name), `name`, `type` (one of 14 values: `government` / `academic` / `event_platform` / `cinema` / `tv` / `venue` / `department_store` / `organizer` / `ngo` / `news_media` / `taiwan_shop` / `personal` / `creator` / `other` — see migrations 060 + 067), `frequency` (daily/weekly), `official_url`, `sort_order INT`, `is_active BOOL`; public SELECT RLS; seeded with 104 rows from web/lib/sources.ts; used by `/sources` public page (migration 060). When adding a new source: insert via SQL with the matching `type` value — do NOT touch `web/lib/sources.ts` SOURCE_TYPES; that array is the SourceType union, not data.

## RLS policies

- Public: `SELECT` on `events` where `is_active = true`
- Authenticated: `SELECT` on `saved_events` for own rows; `INSERT`/`DELETE` own rows
- Admin (`is_admin()`): full access on all tables
- Service role (scraper): bypasses RLS via `SUPABASE_SERVICE_ROLE_KEY`
- **Maintenance lock (migration 094, decision-16a)**: fail-closed `public.admin_reports_maintenance_active()` (`SECURITY DEFINER STABLE`; live `search_path = pg_catalog`, matching the approved contract since migration 096 was applied on 2026-08-01; returns `true`/DENY unless the `admin_reports_cleanup_maintenance` row exists with the exact JSON boolean predicate `value->'active' = 'false'::jsonb`). Missing keys, JSON null, string `"false"`, other malformed values, and a missing row all deny. Per-command RESTRICTIVE policies `<t>_maint_block_{insert,update,delete}` on `events`, `event_reports`, `field_corrections`, `category_corrections`, `selection_reason_corrections`, `works` AND with the permissive policies to block anon/authenticated writes while the lock is active — SELECT untouched, service_role unaffected (bypasses RLS). Migrations 094 and 096 are both APPLIED in production (confirmed 2026-08-01); the lock row is currently inactive.
- **Machine report provenance (migration 098, applied in production 2026-10-22)**: `event_reports_machine_tokens_block_insert` is RESTRICTIVE for `anon` and `authenticated`, rejecting scope/security base tokens and their metadata prefixes. Service role bypasses RLS and remains the only producer. `confirm_scope_report` is `SECURITY INVOKER`, requires an authenticated admin, locks both pending report and event rows, validates the exact five-token scope payload plus expected hash, and atomically deactivates the event and confirms the report.

## Query conventions

- Homepage always filters: `.is("parent_event_id", null)` — hides sub-events
- Public pages: only show `annotation_status IN ('annotated', 'reviewed')` events
- Upsert uses `on_conflict="source_name,source_id"` with `ignoreDuplicates=False`

## Migration checklist

1. Number the file `NNN_descriptive_name.sql` (next = `101`)
2. Use `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
3. Add RLS with `ALTER TABLE … ENABLE ROW LEVEL SECURITY` + policies
4. Test in Supabase SQL Editor before committing
5. Commit the `.sql` file to `supabase/migrations/`
6. **Update this file in the same commit**: "Latest is …", "next = N", Known conflicts (if b-suffix), schema table (new columns), Other tables (new tables), Query conventions (if changed)

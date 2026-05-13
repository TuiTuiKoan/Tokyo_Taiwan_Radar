-- 069_explicit_grants.sql
-- Adds explicit GRANT statements to all existing public-schema tables.
--
-- WHY: Starting October 30, 2026 (existing projects), Supabase will no longer
-- grant implicit access to new tables in the public schema. Existing tables keep
-- their current implicit grants until that date; this migration makes them
-- explicit so the project is compliant before the deadline.
--
-- Ref: Supabase announcement — "Explicit grants for Data API" (2026-05)
-- Project: cjtndektjjpvvjofdvzr (Tokyo Taiwan Radar)
-- Run via: Supabase Dashboard → SQL Editor

-- ─── PART 1: ALTER DEFAULT PRIVILEGES ────────────────────────────────────────
-- Future tables created by the postgres role will automatically receive these
-- grants, so new migrations don't need per-table GRANT statements (though it is
-- still good practice to include them for clarity).

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO anon;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO service_role;

-- ─── PART 2: Per-table GRANTs for all existing tables ─────────────────────────
-- Organised by access tier (mirrors RLS policies defined in earlier migrations).

-- ── Tier A: Public-read tables (anon SELECT allowed) ─────────────────────────
-- Web app queries these via the anon key; RLS policies further restrict rows.

GRANT SELECT ON public.events
  TO anon, authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.announcements
  TO authenticated, service_role;
GRANT SELECT ON public.announcements
  TO anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.announcement_events
  TO authenticated, service_role;
GRANT SELECT ON public.announcement_events
  TO anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.works
  TO authenticated, service_role;
GRANT SELECT ON public.works
  TO anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.organizers
  TO authenticated, service_role;
GRANT SELECT ON public.organizers
  TO anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.venues
  TO authenticated, service_role;
GRANT SELECT ON public.venues
  TO anon;

-- sources: already has GRANT SELECT in 060, re-declare for consistency
GRANT SELECT, INSERT, UPDATE, DELETE ON public.sources
  TO authenticated, service_role;
GRANT SELECT ON public.sources
  TO anon;

GRANT SELECT ON public.external_stats_taiwan_visitors
  TO anon, authenticated, service_role;

GRANT SELECT ON public.external_stats_resident_taiwanese
  TO anon, authenticated, service_role;

GRANT SELECT ON public.external_stats_population
  TO anon, authenticated, service_role;

-- ── Tier B: Anonymous write tables ───────────────────────────────────────────
-- anon can INSERT; RLS policies (defined in original migrations) control what rows
-- are visible per role.

GRANT INSERT ON public.event_reports
  TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.event_reports
  TO authenticated, service_role;

GRANT INSERT ON public.event_views
  TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.event_views
  TO authenticated, service_role;

GRANT INSERT ON public.aeo_visits
  TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.aeo_visits
  TO authenticated, service_role;

-- ── Tier C: Authenticated-user tables ────────────────────────────────────────
-- No anon access; RLS restricts rows to the owning user or admin.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.saved_events
  TO authenticated, service_role;

GRANT SELECT ON public.user_roles
  TO authenticated, service_role;

-- ── Tier D: Admin-managed tables ─────────────────────────────────────────────
-- Authenticated admins + service_role (scraper/annotator) only.
-- RLS policies in each original migration enforce admin-only access.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.category_corrections
  TO authenticated, service_role;

GRANT SELECT ON public.category_corrections_archive
  TO authenticated, service_role;

GRANT SELECT ON public.event_reports_archive
  TO authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.creators
  TO authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.creator_events
  TO authenticated, service_role;

-- scraper_runs: scraper (service_role) INSERTs after every run; admins read
GRANT SELECT, INSERT ON public.scraper_runs
  TO service_role;
GRANT SELECT ON public.scraper_runs
  TO authenticated;

-- research_reports: researcher agent (service_role) INSERTs; admins read
GRANT SELECT, INSERT ON public.research_reports
  TO service_role;
GRANT SELECT ON public.research_reports
  TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.research_sources
  TO authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.field_corrections
  TO authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.selection_reason_corrections
  TO authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.source_exclusions
  TO authenticated, service_role;

GRANT SELECT ON public.source_exclusion_hits
  TO authenticated, service_role;

-- quota_snapshots: 042 already granted to service_role and authenticated;
-- re-declare for completeness.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.quota_snapshots
  TO authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.daily_quality_metrics
  TO authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.app_settings
  TO authenticated, service_role;

-- ── Tier E: Service-role only ─────────────────────────────────────────────────
-- line_subscribers: RLS enabled with no policies (deny-all for all roles except
-- service_role which bypasses RLS). No authenticated GRANT intentional.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.line_subscribers
  TO service_role;

-- 105: drop the three external_stats_* tables (created in 055)
--
-- The JNTO / MOJ / e-Stat monthly pull (scraper/external_stats/, external-stats-pull.yml)
-- fed only the benchmark section of the manually run monthly report. The report was never
-- taken further, neither the website nor the admin reads these tables, and the pull failed
-- every month from 2026-05 (#540). The user decided on 2026-11-08 to remove the feature;
-- the code, workflow and report section are removed in the same PR.
--
-- The data is public government statistics and can be fetched again; nothing else
-- references these tables (no views, foreign keys or functions). Dropping a table also
-- drops its indexes, RLS policies and grants (055, 069).
--
-- Irreversible. Apply manually in Supabase Dashboard → SQL Editor after the PR is merged.
-- Optional dry-run first: run the block with ROLLBACK instead of COMMIT.

BEGIN;

DROP TABLE IF EXISTS public.external_stats_taiwan_visitors;
DROP TABLE IF EXISTS public.external_stats_resident_taiwanese;
DROP TABLE IF EXISTS public.external_stats_population;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name LIKE 'external\_stats\_%'
  ) THEN
    RAISE EXCEPTION 'external_stats_* tables still present';
  END IF;
END $$;

COMMIT;

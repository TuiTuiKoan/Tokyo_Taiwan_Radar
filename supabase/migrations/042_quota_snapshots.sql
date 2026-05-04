-- ============================================================
-- 042: quota_snapshots
-- 每日配額快照 — Supabase DB size, GH Actions minutes 趨勢分析
-- Admin must run in Supabase Dashboard → SQL Editor
-- ============================================================

-- Table: 每日快照
CREATE TABLE IF NOT EXISTS quota_snapshots (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  taken_at     timestamptz NOT NULL DEFAULT now(),
  resource     text NOT NULL,        -- 'supabase_db' | 'gh_actions_minutes'
  metric       text NOT NULL,        -- 'total_bytes' | 'minutes_30d' | 'pct_used'
  value        numeric NOT NULL,
  limit_value  numeric,              -- 配額上限（NULL = 無上限或不適用）
  details      jsonb                 -- 額外資訊（各表大小、各 workflow 用量）
);

CREATE INDEX IF NOT EXISTS idx_quota_snapshots_taken_at
  ON quota_snapshots(taken_at DESC);
CREATE INDEX IF NOT EXISTS idx_quota_snapshots_resource
  ON quota_snapshots(resource, taken_at DESC);

-- RLS
ALTER TABLE quota_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view quota_snapshots"
  ON quota_snapshots FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );
-- service role INSERT 不受 RLS 限制，無需額外 policy

-- RPC：DB 大小摘要
-- SECURITY DEFINER + explicit search_path to prevent search_path injection
CREATE OR REPLACE FUNCTION public.db_size_summary()
RETURNS jsonb
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_catalog
AS $$
  SELECT jsonb_build_object(
    'total_bytes', pg_database_size(current_database()),
    'tables', (
      SELECT jsonb_agg(
        jsonb_build_object(
          'table', tablename,
          'bytes', pg_total_relation_size(quote_ident(tablename))
        )
        ORDER BY pg_total_relation_size(quote_ident(tablename)) DESC
      )
      FROM pg_tables
      WHERE schemaname = 'public'
      LIMIT 20
    )
  );
$$;

REVOKE ALL ON FUNCTION public.db_size_summary() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.db_size_summary() FROM anon;
GRANT EXECUTE ON FUNCTION public.db_size_summary() TO service_role;
GRANT EXECUTE ON FUNCTION public.db_size_summary() TO authenticated;

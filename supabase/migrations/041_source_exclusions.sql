-- ============================================================
-- 041: source_exclusions + source_exclusion_hits
-- ============================================================

-- Table 1: 封鎖規則
CREATE TABLE IF NOT EXISTS source_exclusions (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  source_name     text        NOT NULL,
  pattern         text        NOT NULL,
  pattern_type    text        NOT NULL DEFAULT 'substring'
                    CHECK (pattern_type IN ('substring','regex')),
  match_field     text        NOT NULL DEFAULT 'raw_title'
                    CHECK (match_field IN ('raw_title','raw_description','raw_title_or_description')),
  reason          text,
  is_active       boolean     NOT NULL DEFAULT true,
  created_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  last_matched_at timestamptz,
  match_count     int         NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS source_exclusions_source_active_idx
  ON source_exclusions (source_name) WHERE is_active = true;

ALTER TABLE source_exclusions ENABLE ROW LEVEL SECURITY;

CREATE POLICY source_exclusions_admin_select
  ON source_exclusions FOR SELECT TO authenticated
  USING (public.is_admin());

CREATE POLICY source_exclusions_admin_all
  ON source_exclusions FOR ALL TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

-- Table 2: 命中記錄（30 天 rolling window）
CREATE TABLE IF NOT EXISTS source_exclusion_hits (
  id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id     uuid        NOT NULL REFERENCES source_exclusions(id) ON DELETE CASCADE,
  raw_title   text,
  source_name text        NOT NULL,
  matched_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_exclusion_hits_matched_at_idx
  ON source_exclusion_hits (matched_at DESC);

CREATE INDEX IF NOT EXISTS source_exclusion_hits_rule_matched_idx
  ON source_exclusion_hits (rule_id, matched_at DESC);

ALTER TABLE source_exclusion_hits ENABLE ROW LEVEL SECURITY;

CREATE POLICY source_exclusion_hits_admin_select
  ON source_exclusion_hits FOR SELECT TO authenticated
  USING (public.is_admin());

-- service role 的 INSERT 不受 RLS 限制，無需額外 policy

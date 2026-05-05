-- ============================================================
-- 045: source_exclusions TTL + auto-disable
-- Admin must run in Supabase Dashboard → SQL Editor
-- ============================================================

ALTER TABLE source_exclusions
  ADD COLUMN IF NOT EXISTS expires_at           timestamptz,
  ADD COLUMN IF NOT EXISTS auto_disabled_at     timestamptz,
  ADD COLUMN IF NOT EXISTS auto_disabled_reason text
    CHECK (auto_disabled_reason IS NULL
           OR auto_disabled_reason IN ('expired','stale_no_hits'));

COMMENT ON COLUMN source_exclusions.expires_at IS
  'NULL = permanent. If set and <= now(), the rule is no longer applied by the scraper filter.';
COMMENT ON COLUMN source_exclusions.auto_disabled_at IS
  'When the daily maintenance script disabled this rule. Admin can clear to re-enable.';

-- View: rules currently in force
CREATE OR REPLACE VIEW source_exclusions_effective AS
SELECT *
FROM source_exclusions
WHERE is_active = true
  AND auto_disabled_at IS NULL
  AND (expires_at IS NULL OR expires_at > now());

GRANT SELECT ON source_exclusions_effective TO authenticated;

-- Index to speed maintenance scans
CREATE INDEX IF NOT EXISTS source_exclusions_expires_at_idx
  ON source_exclusions(expires_at) WHERE expires_at IS NOT NULL AND auto_disabled_at IS NULL;

CREATE INDEX IF NOT EXISTS source_exclusions_last_matched_idx
  ON source_exclusions(last_matched_at) WHERE auto_disabled_at IS NULL;

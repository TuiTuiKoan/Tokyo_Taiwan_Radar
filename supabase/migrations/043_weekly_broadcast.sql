-- ============================================================
-- 043: weekly_broadcast
-- 週報草稿 + 自動發送設定
-- Admin must run in Supabase Dashboard → SQL Editor
-- ============================================================

-- 1. Add type column to announcements
ALTER TABLE announcements
  ADD COLUMN IF NOT EXISTS type text NOT NULL DEFAULT 'manual';

-- Valid values: 'manual' | 'weekly_broadcast'
-- Index for querying drafts by type
CREATE INDEX IF NOT EXISTS idx_announcements_type
  ON announcements(type, created_at DESC);

-- 2. app_settings table (global key-value config store)
CREATE TABLE IF NOT EXISTS app_settings (
  key         text PRIMARY KEY,
  value       jsonb NOT NULL,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  updated_by  uuid REFERENCES auth.users(id)
);

-- RLS: only admins can read/write
ALTER TABLE app_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admin full access on app_settings"
  ON app_settings FOR ALL TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM user_roles
      WHERE user_id = auth.uid() AND role = 'admin'
    )
  );

-- Service role has unrestricted access (no policy needed for service_role)

-- Seed the weekly broadcast setting
INSERT INTO app_settings (key, value)
VALUES ('weekly_broadcast', '{"auto_publish": false}'::jsonb)
ON CONFLICT (key) DO NOTHING;

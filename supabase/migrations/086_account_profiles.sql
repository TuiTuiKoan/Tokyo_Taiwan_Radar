-- 086_account_profiles.sql
-- Batch A account/profile foundation for self-registered organizers.
-- Run in Supabase Dashboard -> SQL Editor.

ALTER TABLE public.creators
  ADD COLUMN IF NOT EXISTS user_id uuid references auth.users(id) on delete set null,
  ADD COLUMN IF NOT EXISTS user_handle text,
  ADD COLUMN IF NOT EXISTS organizer_name_zh text,
  ADD COLUMN IF NOT EXISTS organizer_name_ja text,
  ADD COLUMN IF NOT EXISTS organizer_name_en text,
  ADD COLUMN IF NOT EXISTS website_url text,
  ADD COLUMN IF NOT EXISTS social_x text,
  ADD COLUMN IF NOT EXISTS social_instagram text,
  ADD COLUMN IF NOT EXISTS social_note text,
  ADD COLUMN IF NOT EXISTS social_facebook text,
  ADD COLUMN IF NOT EXISTS social_threads text,
  ADD COLUMN IF NOT EXISTS social_youtube text,
  ADD COLUMN IF NOT EXISTS avatar_url text,
  ADD COLUMN IF NOT EXISTS region text,
  ADD COLUMN IF NOT EXISTS is_self_registered boolean not null default false;

ALTER TABLE public.creators
  ALTER COLUMN name DROP NOT NULL,
  ALTER COLUMN platform DROP NOT NULL,
  ALTER COLUMN profile_url DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS creators_user_id_unique_idx
  ON public.creators (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS creators_user_handle_unique_idx
  ON public.creators (user_handle);

ALTER TABLE public.creators
  DROP CONSTRAINT IF EXISTS creators_user_handle_check;

ALTER TABLE public.creators
  ADD CONSTRAINT creators_user_handle_check
  CHECK (user_handle IS NULL OR user_handle ~ '^[a-z0-9]+$');

ALTER TABLE public.events
  ADD COLUMN IF NOT EXISTS owner_user_id uuid references auth.users(id) on delete set null,
  ADD COLUMN IF NOT EXISTS closed_by_owner boolean not null default false,
  ADD COLUMN IF NOT EXISTS is_user_submitted boolean not null default false;

CREATE INDEX IF NOT EXISTS events_owner_user_id_idx
  ON public.events (owner_user_id)
  WHERE owner_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS events_is_user_submitted_idx
  ON public.events (is_user_submitted)
  WHERE is_user_submitted = true;

CREATE INDEX IF NOT EXISTS events_closed_by_owner_idx
  ON public.events (closed_by_owner)
  WHERE closed_by_owner = true;

ALTER TABLE public.user_roles
  ADD COLUMN IF NOT EXISTS publish_banned_until timestamptz;

CREATE TABLE IF NOT EXISTS public.account_usage (
  user_id uuid not null references auth.users(id) on delete cascade,
  usage_date date not null,
  annotate_count integer not null default 0,
  primary key (user_id, usage_date)
);

ALTER TABLE public.account_usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users read own account usage" ON public.account_usage;
CREATE POLICY "Users read own account usage"
  ON public.account_usage FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

ALTER TABLE public.events
  DROP CONSTRAINT IF EXISTS events_organizer_type_check;

ALTER TABLE public.events
  ADD CONSTRAINT events_organizer_type_check
  CHECK (
    organizer_type <@ ARRAY[
      'government','semi_official','cultural_institution','academic',
      'commercial_brand','independent_venue','civic_group','media',
      'unknown','individual'
    ]::text[]
  );

CREATE OR REPLACE VIEW public.public_creator_profiles
WITH (security_invoker = on) AS
SELECT
  user_handle,
  organizer_name_zh,
  organizer_name_ja,
  organizer_name_en,
  avatar_url,
  website_url,
  social_x,
  social_instagram,
  social_note,
  social_facebook,
  social_threads,
  social_youtube,
  category,
  region
FROM public.creators
WHERE is_active = true
  AND is_self_registered = true
  AND user_handle IS NOT NULL;

ALTER TABLE public.creators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Admins manage creators" ON public.creators;
CREATE POLICY "Admins manage creators"
  ON public.creators FOR ALL
  TO authenticated
  USING (public.is_admin())
  WITH CHECK (public.is_admin());

DROP POLICY IF EXISTS "Creators select own profile" ON public.creators;
CREATE POLICY "Creators select own profile"
  ON public.creators FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "Public read self registered creator profiles" ON public.creators;
CREATE POLICY "Public read self registered creator profiles"
  ON public.creators FOR SELECT
  TO anon
  USING (
    is_active = true
    AND is_self_registered = true
    AND user_handle IS NOT NULL
  );

DROP POLICY IF EXISTS "Users read own submitted events" ON public.events;
CREATE POLICY "Users read own submitted events"
  ON public.events FOR SELECT
  TO authenticated
  USING (owner_user_id = auth.uid());

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'avatars',
  'avatars',
  true,
  2097152,
  ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS "Public read avatars" ON storage.objects;
CREATE POLICY "Public read avatars"
  ON storage.objects FOR SELECT
  TO public
  USING (bucket_id = 'avatars');

DROP POLICY IF EXISTS "Users upload own avatar files" ON storage.objects;
CREATE POLICY "Users upload own avatar files"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'avatars'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users update own avatar files" ON storage.objects;
CREATE POLICY "Users update own avatar files"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (
    bucket_id = 'avatars'
    AND (storage.foldername(name))[1] = auth.uid()::text
  )
  WITH CHECK (
    bucket_id = 'avatars'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

DROP POLICY IF EXISTS "Users delete own avatar files" ON storage.objects;
CREATE POLICY "Users delete own avatar files"
  ON storage.objects FOR DELETE
  TO authenticated
  USING (
    bucket_id = 'avatars'
    AND (storage.foldername(name))[1] = auth.uid()::text
  );

REVOKE ALL ON public.creators FROM anon;
GRANT SELECT (
  user_handle,
  organizer_name_zh,
  organizer_name_ja,
  organizer_name_en,
  avatar_url,
  website_url,
  social_x,
  social_instagram,
  social_note,
  social_facebook,
  social_threads,
  social_youtube,
  category,
  region,
  is_active,
  is_self_registered
) ON public.creators TO anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.creators TO authenticated, service_role;

GRANT SELECT ON public.public_creator_profiles TO anon, authenticated, service_role;

REVOKE INSERT, UPDATE, DELETE ON public.events FROM authenticated;
GRANT SELECT ON public.events TO anon, authenticated, service_role;
GRANT INSERT, UPDATE, DELETE ON public.events TO service_role;

REVOKE ALL ON public.account_usage FROM anon, authenticated;
GRANT SELECT ON public.account_usage TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.account_usage TO service_role;

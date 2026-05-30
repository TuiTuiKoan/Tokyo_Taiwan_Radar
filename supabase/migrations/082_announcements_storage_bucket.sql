-- 082_announcements_storage_bucket.sql
-- Create public storage bucket for announcement cover images.
-- Files are uploaded via service role (bypasses RLS) and served via public URL.

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'announcements',
  'announcements',
  true,           -- public: cover images are accessible via getPublicUrl()
  5242880,        -- 5 MB
  ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif']
)
ON CONFLICT (id) DO NOTHING;

-- Public read: anyone can view cover images
CREATE POLICY "Public read announcement covers"
  ON storage.objects FOR SELECT
  TO public
  USING (bucket_id = 'announcements');

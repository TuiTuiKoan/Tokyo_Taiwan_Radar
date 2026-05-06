-- 051: works_tv_drama
-- Expand work_type check constraint to include TV drama and variety types.
-- Admin must run in Supabase Dashboard → SQL Editor.

ALTER TABLE works DROP CONSTRAINT IF EXISTS works_work_type_check;
ALTER TABLE works ADD CONSTRAINT works_work_type_check
  CHECK (work_type IN ('film','stage','exhibition','concert_tour','tv_drama','tv_variety','other'));

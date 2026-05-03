-- 036_has_chinese_support.sql
-- Tier 1 follow-up: add has_chinese_support flag for symmetry with
-- has_japanese_support / has_english_support introduced in 035.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS has_chinese_support boolean;

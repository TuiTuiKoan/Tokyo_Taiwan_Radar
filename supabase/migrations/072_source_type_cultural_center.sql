-- 072: replace 'creator' with 'cultural_center' in research_sources.display_type
-- Merges 'creator' → 'personal' for general creators,
-- adds 'cultural_center' for language schools / cultural institutes.

-- Step A: reclassify known rows BEFORE dropping the constraint
UPDATE research_sources SET display_type = 'ngo'             WHERE id = 155;  -- NPO法人埼玉県日台親善協会
UPDATE research_sources SET display_type = 'cultural_center' WHERE id = 194;  -- 台湾華語文学習センター（大阪弁天町）
UPDATE research_sources SET display_type = 'cultural_center' WHERE id = 101;  -- 台湾留学サポートセンター
UPDATE research_sources SET display_type = 'personal'        WHERE display_type = 'creator';  -- 残り (id=156 ベクトル台湾, id=78 note meta row)

-- Step B: drop old CHECK constraint and add new one with cultural_center
ALTER TABLE research_sources
  DROP CONSTRAINT IF EXISTS research_sources_display_type_check;

ALTER TABLE research_sources
  ADD CONSTRAINT research_sources_display_type_check
  CHECK (display_type IN (
    'government',
    'academic',
    'event_platform',
    'cinema',
    'tv',
    'venue',
    'department_store',
    'organizer',
    'ngo',
    'news_media',
    'taiwan_shop',
    'personal',
    'cultural_center',
    'other'
  ));

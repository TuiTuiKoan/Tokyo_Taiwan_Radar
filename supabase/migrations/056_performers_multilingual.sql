-- performers multilingual arrays
ALTER TABLE events ADD COLUMN IF NOT EXISTS performers_zh TEXT[];
ALTER TABLE events ADD COLUMN IF NOT EXISTS performers_en TEXT[];

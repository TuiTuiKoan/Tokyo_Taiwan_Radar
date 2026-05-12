-- ============================================================
-- 067: expand sources.type CHECK constraint to 14 values
-- ------------------------------------------------------------
-- Splits 'official' (31 rows) into venue / department_store / organizer.
-- Renames 'news' → 'news_media' (18 rows).
-- Renames 'ticketing' → 'event_platform' (6 rows).
-- Adds new values: tv, venue, department_store, organizer, ngo,
--                  news_media, event_platform, taiwan_shop, personal.
-- Pre-existing values kept: government, academic, cinema, creator, other.
-- ------------------------------------------------------------
-- DO NOT RUN until user has reviewed the official-split list (see commit
-- message). After review, run via Supabase Dashboard → SQL Editor.
-- ============================================================

-- ── Step 1: drop old constraint so we can rename/split values ──
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_type_check;

-- ── Step 2: bulk rename ───────────────────────────────────
UPDATE sources SET type = 'news_media'     WHERE type = 'news';
UPDATE sources SET type = 'event_platform' WHERE type = 'ticketing';

-- ── Step 3: split 'official' into venue / department_store / organizer ──
-- VENUE (10): museums, galleries, live houses, performance/event spaces
UPDATE sources SET type = 'venue' WHERE id IN (
  'mot',                  -- 東京都現代美術館 (MOT)
  'faam_fukuoka',         -- 福岡アジア美術館
  'whitestone_gallery',   -- Whitestone Gallery
  'acros_fukuoka',        -- ACROS 福岡（multi-purpose hall）
  'moonromantic',         -- 月見ル君想フ（live house）
  'morc_asagaya',         -- MORC 阿佐ヶ谷（live house）
  'artistcafe',           -- Artist Cafe
  'otto',                 -- OTTO Gallery
  'johakyu',              -- Johakyu（gallery）
  'ginsee'                -- 銀座シャラララ（event space）
);

-- DEPARTMENT_STORE (4)
UPDATE sources SET type = 'department_store' WHERE id IN (
  'hankyu_umeda',           -- 阪急うめだ本店
  'daimaru_matsuzakaya',    -- 大丸松坂屋
  'eslite_spectrum',        -- 誠品生活日本橋
  'maruhiro'                -- マルヒロ
);

-- ORGANIZER (16): festivals, film festivals, publishers, communities, book cafes that organize events
UPDATE sources SET type = 'organizer' WHERE id IN (
  'taiwan_festa',           -- Taiwan Festa
  'taiwan_festival_tokyo',  -- 東京台湾祭
  'taiwan_matsuri',         -- 台湾祭
  'taiwan_faasai',          -- Taiwan FAASAI
  'taiwan_prism',           -- Taiwan Prism
  'taiwanbunkasai',         -- 台湾文化祭
  'tiff',                   -- 東京国際映画祭
  'tokyo_filmex',           -- Tokyo FILMeX
  'ssff',                   -- Short Shorts Film Festival & Asia
  'oaff',                   -- 大阪アジアン映画祭
  'yebizo',                 -- 恵比寿映像祭
  'kgplus_kyotographie',    -- KYOTOGRAPHIE
  'bigromanticrecords',     -- Big Romantic Records（label/organizer）
  'hakusuisha',             -- 白水社（publisher）
  'tsudoi_osaka',           -- 大阪集い
  'bookandbeer'             -- 本屋ビール（event-organizing book cafe）
);

-- GOVERNMENT (1 reclassified from official):
-- startup_terrace = 台灣經濟部中小及新創企業署 新創基地
UPDATE sources SET type = 'government' WHERE id = 'startup_terrace';

-- ── Sanity check ───────────────────────────────────────────
DO $$
DECLARE remaining INT;
BEGIN
  SELECT COUNT(*) INTO remaining FROM sources WHERE type IN ('official','news','ticketing');
  IF remaining > 0 THEN
    RAISE EXCEPTION 'Migration 067: % source(s) still use deprecated type values', remaining;
  END IF;
END $$;

-- ── Step 4: add new CHECK constraint (only after all rows updated) ──
ALTER TABLE sources ADD CONSTRAINT sources_type_check CHECK (type IN (
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
  'creator',
  'other'
));

-- ── Step 5: post-review adjustments (2026-05-12) ───────────
-- bookandbeer: book cafe that organizes Taiwan-related events → organizer
-- startup_terrace: 台湾経済部 中小及新創企業署 新創基地 → government
UPDATE sources SET type = 'organizer'  WHERE id = 'bookandbeer';
UPDATE sources SET type = 'government' WHERE id = 'startup_terrace';

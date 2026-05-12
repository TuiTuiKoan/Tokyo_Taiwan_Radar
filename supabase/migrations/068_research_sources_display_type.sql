-- ============================================================
-- 068: add research_sources.display_type for unified UI classification
-- ------------------------------------------------------------
-- The admin AdminSourcesTable previously hardcoded a SOURCE_TYPE_MAP
-- (research_sources.id → category). This migration moves that mapping
-- into the DB so the same value can be edited inline (PATCH endpoint).
-- ------------------------------------------------------------
-- Run AFTER 067 (which expands the value set used by the CHECK below).
-- ============================================================

ALTER TABLE research_sources
  ADD COLUMN IF NOT EXISTS display_type TEXT
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
    'creator',
    'other'
  ));

CREATE INDEX IF NOT EXISTS idx_research_sources_display_type
  ON research_sources(display_type);

-- ── Backfill 1: rows linked to a registered scraper source ────
UPDATE research_sources rs
SET display_type = s.type
FROM sources s
WHERE rs.scraper_source_name = s.id
  AND rs.display_type IS NULL;

-- ── Backfill 2: unmatched rows, using the legacy hardcoded SOURCE_TYPE_MAP
-- (formerly in web/components/AdminSourcesTable.tsx).
-- research_sources.id → display_type
-- ────────────────────────────────────────────────────────────

-- event_platform (13)
UPDATE research_sources SET display_type = 'event_platform'
WHERE id IN (14, 47, 20, 19, 17, 32, 45, 15, 77, 23, 79, 83, 106)
  AND display_type IS NULL;

-- news_media (16)
UPDATE research_sources SET display_type = 'news_media'
WHERE id IN (4, 6, 96, 128, 132, 133, 135, 166, 167, 168, 229, 230, 237, 238, 318, 391)
  AND display_type IS NULL;

-- academic (26)
UPDATE research_sources SET display_type = 'academic'
WHERE id IN (28, 29, 24, 25, 10, 26, 31, 27, 30, 54, 55, 61, 62, 63, 64, 65,
             84, 92, 93, 1, 2, 3, 12, 52, 74, 380)
  AND display_type IS NULL;

-- venue (9)
UPDATE research_sources SET display_type = 'venue'
WHERE id IN (81, 76, 48, 49, 75, 85, 53, 82, 5)
  AND display_type IS NULL;

-- cinema (18)
UPDATE research_sources SET display_type = 'cinema'
WHERE id IN (35, 56, 38, 41, 33, 34, 50, 51, 36, 59, 58, 86, 70, 67, 37, 39, 40, 207)
  AND display_type IS NULL;

-- tv (5)
UPDATE research_sources SET display_type = 'tv'
WHERE id IN (95, 71, 72, 73, 94)
  AND display_type IS NULL;

-- government (11)
UPDATE research_sources SET display_type = 'government'
WHERE id IN (8, 13, 80, 87, 16, 60, 66, 68, 89, 90, 88)
  AND display_type IS NULL;

-- department_store (4)
UPDATE research_sources SET display_type = 'department_store'
WHERE id IN (46, 129, 130, 131)
  AND display_type IS NULL;

-- organizer (6)
UPDATE research_sources SET display_type = 'organizer'
WHERE id IN (57, 21, 69, 91, 9, 22)
  AND display_type IS NULL;

-- ngo (5)
UPDATE research_sources SET display_type = 'ngo'
WHERE id IN (7, 18, 101, 155, 194)
  AND display_type IS NULL;

-- personal (1)
UPDATE research_sources SET display_type = 'personal'
WHERE id IN (78)
  AND display_type IS NULL;

-- taiwan_shop (3)
UPDATE research_sources SET display_type = 'taiwan_shop'
WHERE id IN (127, 141, 164)
  AND display_type IS NULL;

-- Rows still NULL after backfill = auto-discovered candidates not yet
-- manually classified. The admin UI defaults them to 'other'.

-- ── RLS: allow admins to UPDATE display_type (PATCH endpoint) ──
-- (existing 012_research_admin_update.sql already grants admin UPDATE)

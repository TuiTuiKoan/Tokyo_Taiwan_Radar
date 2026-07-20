-- ============================================================
-- 095: organizer_authority
-- Wave 2 Phase B0a (storage enum reconciliation) + Phase B
-- (organizers authority columns + events co/sponsor cardinality guards),
-- merged into one transaction-wrapped, rollback-safe migration.
--
-- ⛔ APPLY PREREQUISITE (READ BEFORE RUNNING) — fail-closed by design:
--   The two events cardinality CHECK constraints in section 3 are ordinary
--   VALIDATED constraints (NOT "NOT VALID"). At authoring time the live DB
--   has 70 parallel-array mismatches (66 distinct events; co=63 / sponsor=7;
--   17 active / 53 inactive) across the WHOLE table. Applying this migration
--   before Phase A.5 remediation has driven that count to 0 will make the
--   `ALTER TABLE events ADD CONSTRAINT ...` step ERROR and abort the entire
--   transaction, leaving nothing half-applied. This is intentional:
--       gate 2A  = Phase A.5 apply  -> table-wide co/sponsor mismatch = 0
--       gate 2B  = THIS migration
--   Do NOT paste this into the SQL Editor until the gate-2A read-back shows a
--   table-wide (active + inactive) mismatch of 0.
--
-- SCOPE / NON-SCOPE:
--   * Touches: research_sources (CHECK swap), organizers (normalize + new
--     column + CHECK + partial index), events (two cardinality CHECKs).
--   * Does NOT touch events.organizer_type (already the 10-value text[] set
--     established by migration 086).
--   * Contains NO GRANT / REVOKE / ALTER VIEW: no new table and no permission
--     change, so no Data-API GRANT block (October-30 policy) is required.
--   * Does NOT modify the already-applied historical migrations 039 / 058 /
--     086; it only re-shapes the constraints they created.
--
-- CANONICAL STORAGE VOCABULARY (10 values) — authoritative source is the live
-- events_organizer_type_check (migration 086):
--     government, semi_official, cultural_institution, academic,
--     commercial_brand, independent_venue, civic_group, media,
--     individual, unknown
--   (The annotator LLM vocabulary deliberately stays at 9 values and never
--    emits 'individual'; 'individual' is a storage/registry-only value.)
--
-- ROLLBACK (manual, only if ever needed after a successful apply):
--     BEGIN;
--     ALTER TABLE events DROP CONSTRAINT IF EXISTS events_sponsor_cardinality_check;
--     ALTER TABLE events DROP CONSTRAINT IF EXISTS events_co_org_cardinality_check;
--     DROP INDEX IF EXISTS idx_organizers_is_authoritative;
--     ALTER TABLE organizers DROP CONSTRAINT IF EXISTS organizers_organizer_type_check;
--     ALTER TABLE organizers DROP COLUMN IF EXISTS is_authoritative;
--     ALTER TABLE research_sources DROP CONSTRAINT IF EXISTS research_sources_default_organizer_type_check;
--     ALTER TABLE research_sources ADD CONSTRAINT research_sources_default_organizer_type_check
--       CHECK (default_organizer_type IS NULL OR default_organizer_type IN (
--         'government','semi_official','cultural_institution','academic',
--         'commercial_brand','independent_venue','civic_group','media','unknown'));
--     COMMIT;
--   NOTE: the legacy organizers.organizer_type JSON-text form
--   ('["commercial_brand"]') is NOT auto-restored on rollback (the scalar
--   form is intentionally lossy); re-seed from the audit manifest if required.
--
-- Admin must run in Supabase Dashboard -> SQL Editor.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. research_sources.default_organizer_type — B0a scalar CHECK swap.
--    Migration 039 seeded a 9-value CHECK. Extend it to the canonical 10
--    (adds 'individual'). This is a SCALAR text column, so keep the
--    "IS NULL OR ... IN (...)" form; do NOT copy the events "<@ ARRAY[...]"
--    array-column syntax.
--
--    Live DISTINCT non-null values at authoring time (31 rows, every value
--    already inside the old 9-value set, so the 10-value superset rejects
--    nothing):
--        academic, commercial_brand, cultural_institution, government,
--        independent_venue, media, semi_official
-- ------------------------------------------------------------
ALTER TABLE research_sources
  DROP CONSTRAINT IF EXISTS research_sources_default_organizer_type_check;

ALTER TABLE research_sources
  ADD CONSTRAINT research_sources_default_organizer_type_check
  CHECK (
    default_organizer_type IS NULL OR
    default_organizer_type IN (
      'government','semi_official','cultural_institution','academic',
      'commercial_brand','independent_venue','civic_group','media',
      'individual','unknown'
    )
  );

-- ------------------------------------------------------------
-- 2. organizers — B: normalize legacy JSON-text organizer_type to scalar,
--    add is_authoritative, add the canonical 10-value scalar CHECK, and a
--    partial index for authoritative lookups.
--
--    Live DISTINCT non-null organizer_type at authoring time (2 of 204 rows):
--        '["commercial_brand"]'   -> normalizes to scalar 'commercial_brand'
--    No multi-value or illegal values are present. The two-step normalize
--    below is defensive and lossless for legal single values:
--      2a. promote UNAMBIGUOUS single-element bracketed arrays of a legal
--          value to their scalar form using PURE TEXT ops -> it never casts
--          to jsonb, so it cannot throw on malformed data;
--      2b. NULL out any remaining non-null value that is not already a legal
--          scalar (multi-value arrays / illegal / unparseable) and leave it
--          for manual review. No legal information is silently dropped,
--          because step 2a has already rescued every unambiguous legal value.
-- ------------------------------------------------------------

-- 2a. Unambiguous single-element legal array -> scalar.
--     btrim(btrim(btrim(x), '[]'), ' ''"') strips outer spaces, then the
--     surrounding brackets, then any spaces / single-quotes / double-quotes,
--     yielding the bare value. The single-element guard rejects any value
--     containing a comma (i.e. multi-element arrays).
UPDATE organizers AS o
SET organizer_type = btrim(btrim(btrim(o.organizer_type), '[]'), ' ''"')
WHERE o.organizer_type IS NOT NULL
  AND btrim(o.organizer_type) LIKE '[%]'
  AND position(',' IN o.organizer_type) = 0
  AND btrim(btrim(btrim(o.organizer_type), '[]'), ' ''"') IN (
    'government','semi_official','cultural_institution','academic',
    'commercial_brand','independent_venue','civic_group','media',
    'individual','unknown'
  );

-- 2b. Anything still non-null and not a legal scalar -> NULL (manual review).
--     Expected to affect 0 rows given the authoring-time data.
UPDATE organizers
SET organizer_type = NULL
WHERE organizer_type IS NOT NULL
  AND organizer_type NOT IN (
    'government','semi_official','cultural_institution','academic',
    'commercial_brand','independent_venue','civic_group','media',
    'individual','unknown'
  );

ALTER TABLE organizers
  ADD COLUMN IF NOT EXISTS is_authoritative BOOL NOT NULL DEFAULT false;

ALTER TABLE organizers
  DROP CONSTRAINT IF EXISTS organizers_organizer_type_check;

ALTER TABLE organizers
  ADD CONSTRAINT organizers_organizer_type_check
  CHECK (
    organizer_type IS NULL OR
    organizer_type IN (
      'government','semi_official','cultural_institution','academic',
      'commercial_brand','independent_venue','civic_group','media',
      'individual','unknown'
    )
  );

CREATE INDEX IF NOT EXISTS idx_organizers_is_authoritative
  ON organizers(is_authoritative) WHERE is_authoritative = true;

COMMENT ON COLUMN organizers.is_authoritative IS
  'When true, the organizer registry resolver treats this row as the canonical entity type (unless a field_corrections lock exists). LLM output must never flip this flag.';

-- ------------------------------------------------------------
-- 3. events — B: durable co/sponsor parallel-array cardinality guards.
--    ⚠️ VALIDATED constraints (no NOT VALID): PostgreSQL scans the whole
--    table when adding them, so they FAIL CLOSED if ANY table-wide mismatch
--    remains (70 pairs at authoring time). Apply only after gate 2A = 0.
--    COALESCE collapses both NULL and empty-array to 0, so "no entries" on
--    either side is treated as equal (0 = 0).
--    DROP IF EXISTS makes re-runs idempotent.
-- ------------------------------------------------------------
ALTER TABLE events
  DROP CONSTRAINT IF EXISTS events_co_org_cardinality_check;

ALTER TABLE events
  ADD CONSTRAINT events_co_org_cardinality_check
  CHECK (
    COALESCE(cardinality(co_organizers), 0) = COALESCE(cardinality(co_organizer_types), 0)
  );

ALTER TABLE events
  DROP CONSTRAINT IF EXISTS events_sponsor_cardinality_check;

ALTER TABLE events
  ADD CONSTRAINT events_sponsor_cardinality_check
  CHECK (
    COALESCE(cardinality(sponsors), 0) = COALESCE(cardinality(sponsor_types), 0)
  );

COMMIT;

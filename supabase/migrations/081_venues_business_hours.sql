-- Migration 080: venues.business_hours column
-- Purpose: Store venue-level standard operating hours so enrich_location.py
--          can auto-propagate to events.business_hours without manual FC correction.
--
-- Design intent:
--   1. Seed known authoritative venues with their actual hours (see INSERT below).
--   2. enrich_location.py: when event.location_name matches venues.name and
--      venues.is_authoritative = true and event.business_hours IS NULL and no
--      field_corrections lock exists → copy venue.business_hours to event.
--   3. This removes the human error path of guessing/assuming hours.
--
-- Related: venues.is_authoritative (migration 076)
-- Next step: update enrich_location.py or add backfill_venue_business_hours.py

ALTER TABLE venues
  ADD COLUMN IF NOT EXISTS business_hours TEXT;

COMMENT ON COLUMN venues.business_hours IS
  'Standard operating hours for the venue. '
  'Format: 平日 HH:MM〜HH:MM / 土日祝 HH:MM〜HH:MM or similar. '
  'Used by enrich_location.py to auto-populate events.business_hours when '
  'venues.is_authoritative = true and no field_corrections lock exists.';

-- Seed: Lumine Est Shinjuku (confirmed hours 2026-05)
-- Shopping floors: 平日 11:00〜21:00 / 土日祝 10:30〜21:00
-- Restaurant floor: 11:00〜22:00 (not seeded — event type dependent)
-- UPDATE venues
--   SET business_hours = '平日 11:00〜21:00 / 土日祝 10:30〜21:00'
-- WHERE name ILIKE '%ルミネエスト%' AND is_authoritative = true;
--
-- ↑ Uncomment and run after seeding the venue with is_authoritative = true.

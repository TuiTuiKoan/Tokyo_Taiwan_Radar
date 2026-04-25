-- Migration 010: localized location / address / hours fields
-- location_name, location_address, and business_hours were stored in
-- Japanese only. Add zh/en variants so the event detail page can display
-- them in the visitor's locale. Annotator fills these during annotation.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS location_name_zh    TEXT,
  ADD COLUMN IF NOT EXISTS location_name_en    TEXT,
  ADD COLUMN IF NOT EXISTS location_address_zh TEXT,
  ADD COLUMN IF NOT EXISTS location_address_en TEXT,
  ADD COLUMN IF NOT EXISTS business_hours_zh   TEXT,
  ADD COLUMN IF NOT EXISTS business_hours_en   TEXT;

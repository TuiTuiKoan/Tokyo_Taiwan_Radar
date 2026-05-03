-- 037_event_status_and_offers.sql
-- Schema.org Event JSON-LD compliance (Tier 1.5):
-- organizer_url, price_amount, price_currency, event_status.

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS organizer_url text,
  ADD COLUMN IF NOT EXISTS price_amount numeric,
  ADD COLUMN IF NOT EXISTS price_currency text DEFAULT 'JPY',
  ADD COLUMN IF NOT EXISTS event_status text DEFAULT 'scheduled';

ALTER TABLE events
  ADD CONSTRAINT events_event_status_check
  CHECK (event_status IN ('scheduled','cancelled','postponed','rescheduled'));

ALTER TABLE events
  ADD CONSTRAINT events_price_currency_check
  CHECK (price_currency IS NULL OR price_currency ~ '^[A-Z]{3}$');

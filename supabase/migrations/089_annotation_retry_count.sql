-- Migration 089: annotation retry counter for error_recovery.py
--
-- Spec originally referenced 082, but 082–088 are already in use
-- (082_announcements_storage_bucket … 088_rls_perf_account). 089 is the next
-- free sequential number per database.instructions.md (no b-suffix needed).
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS annotation_retry_count INT NOT NULL DEFAULT 0;

COMMENT ON COLUMN events.annotation_retry_count IS
  'error_recovery.py retry counter. Incremented each time an error event is reset to pending. Reset to 0 by error_recovery when the event reaches annotated. Escalated to human when >= MAX_RETRY.';

-- Migration 052b: event_media_coverage view
-- Spec: docs/specs/active/report-prototype-gap-fix/proposal.md § Phase 3
-- NOTE: 052_events_director.sql was applied first; this migration is 052b per
-- project convention (b-suffix on conflict).
-- secondary_source_urls is a TEXT[] column on events (not a join table).
-- We parse domain shortnames from URL strings for display.

CREATE OR REPLACE VIEW event_media_coverage AS
SELECT
  e.id                        AS event_id,
  e.name_ja,
  e.start_date,
  e.category,
  e.location_prefectures,
  COALESCE(array_length(e.secondary_source_urls, 1), 0)  AS media_count,
  e.secondary_source_urls                                AS media_urls,
  (
    SELECT ARRAY_AGG(DISTINCT
      CASE
        WHEN u LIKE '%prtimes.jp%'       THEN 'prtimes'
        WHEN u LIKE '%news.google.com%'  THEN 'gnews'
        WHEN u LIKE '%nhk.or.jp%'        THEN 'nhk'
        WHEN u LIKE '%walkerplus.com%'   THEN 'walkerplus'
        WHEN u LIKE '%arukikata.co.jp%'  THEN 'arukikata'
        ELSE regexp_replace(
               regexp_replace(u, '^https?://(?:www\.)?', ''),
               '/.*$', '')
      END
    )
    FROM unnest(e.secondary_source_urls) AS u
  )                                                       AS media_source_names
FROM events e
WHERE e.is_active = true
  AND e.annotation_status IN ('annotated', 'reviewed')
  AND e.secondary_source_urls IS NOT NULL
  AND array_length(e.secondary_source_urls, 1) > 0;

GRANT SELECT ON event_media_coverage TO anon, authenticated;

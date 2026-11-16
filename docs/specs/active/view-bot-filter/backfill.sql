-- view-bot-filter: re-runnable backfill (production write — human gate).
-- Run once AFTER the PR is deployed, to label rows that the old record-view.ts
-- wrote between applying migration 109 and the deploy (they got the default
-- 'unclassified'). Identical to the UPDATE inside 109; idempotent.
-- Run in the Supabase SQL Editor.

begin;
set local lock_timeout = '5s';

update public.event_views v
set visitor_class = 'known_bot',
    bot_name      = m.bot_name
from public.event_views ev
cross join lateral (
  select a.bot_name
    from public.aeo_visits a
   where a.visit_type = 'bot'
     and a.visited_at between ev.viewed_at - interval '30 seconds'
                          and ev.viewed_at + interval '5 seconds'
     and a.path = '/' || ev.locale || '/events/' || ev.event_id::text
   order by abs(extract(epoch from a.visited_at - ev.viewed_at))
   limit 1
) m
where v.id = ev.id
  and ev.visitor_class = 'unclassified'
  and m.bot_name is not null;

commit;

-- Read-back:
-- select visitor_class, count(*) from public.event_views
--  where viewed_at >= '<deploy time>' group by 1;   -- expect no 'unclassified'

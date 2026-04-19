-- Store admin category corrections as training data for the AI annotator.
-- When an admin manually changes an event's category in the admin UI,
-- a correction record is created.
create table if not exists public.category_corrections (
  id          uuid primary key default gen_random_uuid(),
  event_id    uuid not null references public.events(id) on delete cascade,
  raw_title   text,
  raw_description text,
  ai_category text[] not null default '{}',
  corrected_category text[] not null default '{}',
  corrected_by uuid references auth.users(id),
  created_at  timestamptz not null default now(),
  unique(event_id)
);

-- RLS: admins can read/write, service role bypasses
alter table public.category_corrections enable row level security;

create policy "Admins manage corrections"
  on public.category_corrections for all
  using (public.is_admin());

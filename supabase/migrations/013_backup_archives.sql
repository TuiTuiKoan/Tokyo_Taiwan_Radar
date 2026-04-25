-- 013_backup_archives.sql
-- Archive tables and helper function for backing up event-related records before deletion.

create table if not exists public.category_corrections_archive (
  id uuid primary key default gen_random_uuid(),
  source_event_id uuid not null,
  archive_reason text not null,
  archived_at timestamptz not null default now(),
  original_id uuid not null,
  event_id uuid not null,
  raw_title text,
  raw_description text,
  ai_category text[] not null default '{}',
  corrected_category text[] not null default '{}',
  corrected_by uuid,
  created_at timestamptz
);

create index if not exists category_corrections_archive_source_event_id_idx
  on public.category_corrections_archive(source_event_id);

create index if not exists category_corrections_archive_archived_at_idx
  on public.category_corrections_archive(archived_at);

alter table public.category_corrections_archive enable row level security;

create policy "Admins can view category_corrections_archive"
  on public.category_corrections_archive for select
  using (public.is_admin());

create table if not exists public.event_reports_archive (
  id uuid primary key default gen_random_uuid(),
  source_event_id uuid not null,
  archive_reason text not null,
  archived_at timestamptz not null default now(),
  original_id uuid not null,
  event_id uuid not null,
  report_types text[] not null,
  locale text,
  status text,
  admin_notes text,
  confirmed_at timestamptz,
  created_at timestamptz
);

create index if not exists event_reports_archive_source_event_id_idx
  on public.event_reports_archive(source_event_id);

create index if not exists event_reports_archive_archived_at_idx
  on public.event_reports_archive(archived_at);

alter table public.event_reports_archive enable row level security;

create policy "Admins can view event_reports_archive"
  on public.event_reports_archive for select
  using (public.is_admin());

create or replace function public.archive_event_related_data(
  p_event_ids uuid[],
  p_reason text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_event_ids is null or array_length(p_event_ids, 1) is null then
    raise exception 'p_event_ids must not be empty';
  end if;

  if p_reason is null or btrim(p_reason) = '' then
    raise exception 'p_reason must not be empty';
  end if;

  insert into public.category_corrections_archive (
    source_event_id,
    archive_reason,
    archived_at,
    original_id,
    event_id,
    raw_title,
    raw_description,
    ai_category,
    corrected_category,
    corrected_by,
    created_at
  )
  select
    c.event_id as source_event_id,
    p_reason,
    now(),
    c.id as original_id,
    c.event_id,
    c.raw_title,
    c.raw_description,
    c.ai_category,
    c.corrected_category,
    c.corrected_by,
    c.created_at
  from public.category_corrections c
  where c.event_id = any (p_event_ids);

  insert into public.event_reports_archive (
    source_event_id,
    archive_reason,
    archived_at,
    original_id,
    event_id,
    report_types,
    locale,
    status,
    admin_notes,
    confirmed_at,
    created_at
  )
  select
    r.event_id as source_event_id,
    p_reason,
    now(),
    r.id as original_id,
    r.event_id,
    r.report_types,
    r.locale,
    r.status,
    r.admin_notes,
    r.confirmed_at,
    r.created_at
  from public.event_reports r
  where r.event_id = any (p_event_ids);
end;
$$;

revoke all on function public.archive_event_related_data(uuid[], text) from public;
grant execute on function public.archive_event_related_data(uuid[], text) to service_role;
"""Migrations 106 and 107 (Supabase advisor hardening) against a throwaway PostgreSQL.

Starts its own cluster from a local PostgreSQL install (pg_ctl on PATH,
Homebrew, or /usr/lib/postgresql) and skips when there is none. Nothing here
touches Supabase. Run: cd scraper && python -m pytest tests/test_advisor_hardening.py -q

The fixture rebuilds the 17 affected tables with the verbatim production
policies (BEFORE_POLICIES), production table grants, Supabase's real
auth.uid()/auth.role(), and the ensure_rls event trigger. Migrations run as a
non-superuser owner role (postgres_owner, BYPASSRLS) like Supabase's postgres;
the event trigger and the auth schema belong to the superuser. Spec:
docs/specs/active/supabase-advisor-hardening/proposal.md
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")
from psycopg2 import errors  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MIG_106 = ROOT / "supabase" / "migrations" / "106_advisor_security_hardening.sql"
MIG_107 = ROOT / "supabase" / "migrations" / "107_rls_initplan_policy_cleanup.sql"
DRY_DIR = ROOT / "docs" / "specs" / "active" / "supabase-advisor-hardening" / "dryrun"
DRY_106 = DRY_DIR / "106_advisor_security_hardening.dryrun.sql"
DRY_107 = DRY_DIR / "107_rls_initplan_policy_cleanup.dryrun.sql"
EXPLAIN_OUT = Path(os.environ.get("ADVISOR_EXPLAIN_OUT", tempfile.gettempdir())) / "advisor_hardening_explain.txt"

# --- verbatim production policies (pg_policies, 2026-11-10) -----------------
# (table, policy, permissive, cmd, roles::text, qual, with_check)
BEFORE_POLICIES = [
    ('account_usage', 'Users read own account usage', 'PERMISSIVE', 'SELECT', '{authenticated}', '(auth.uid() = user_id)', None),
    ('aeo_visits', 'Admins read aeo_visits', 'PERMISSIVE', 'SELECT', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('aeo_visits', 'Anyone can insert aeo_visit', 'PERMISSIVE', 'INSERT', '{public}', None, 'true'),
    ('announcement_events', 'announcement_events_admin_all', 'PERMISSIVE', 'ALL', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))"),
    ('announcement_events', 'announcement_events_public_read', 'PERMISSIVE', 'SELECT', '{public}', '(EXISTS ( SELECT 1\n   FROM announcements a\n  WHERE ((a.id = announcement_events.announcement_id) AND (a.published_at IS NOT NULL) AND (a.published_at <= now()))))', None),
    ('announcements', 'announcements_admin_all', 'PERMISSIVE', 'ALL', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))"),
    ('announcements', 'announcements_public_read', 'PERMISSIVE', 'SELECT', '{public}', '((published_at IS NOT NULL) AND (published_at <= now()))', None),
    ('app_settings', 'Admin full access on app_settings', 'PERMISSIVE', 'ALL', '{authenticated}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))"),
    ('app_settings', 'app_settings_lock_key_immutable', 'RESTRICTIVE', 'ALL', '{authenticated}', "(key <> 'admin_reports_cleanup_maintenance'::text)", "(key <> 'admin_reports_cleanup_maintenance'::text)"),
    ('creator_events', 'Admins manage creator_events', 'PERMISSIVE', 'ALL', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('event_reports', 'Admins can update reports', 'PERMISSIVE', 'UPDATE', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('event_reports', 'Admins can view reports', 'PERMISSIVE', 'SELECT', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('event_reports', 'Anyone can submit reports', 'PERMISSIVE', 'INSERT', '{public}', None, 'true'),
    ('event_reports', 'event_reports_machine_tokens_block_insert', 'RESTRICTIVE', 'INSERT', '{anon,authenticated}', None, "(NOT (EXISTS ( SELECT 1\n   FROM unnest(event_reports.report_types) token(value)\n  WHERE ((token.value = ANY (ARRAY['scopeReviewNonJapan'::text, 'auto_security_prompt_injection'::text])) OR (token.value ~~ 'scopeDecision:%'::text) OR (token.value ~~ 'scopeRegion:%'::text) OR (token.value ~~ 'scopeHash:%'::text) OR (token.value ~~ 'securityHash:%'::text) OR (token.value ~~ 'securitySeverity:%'::text)))))"),
    ('event_reports', 'event_reports_maint_block_delete', 'RESTRICTIVE', 'DELETE', '{public}', '(NOT admin_reports_maintenance_active())', None),
    ('event_reports', 'event_reports_maint_block_insert', 'RESTRICTIVE', 'INSERT', '{public}', None, '(NOT admin_reports_maintenance_active())'),
    ('event_reports', 'event_reports_maint_block_update', 'RESTRICTIVE', 'UPDATE', '{public}', '(NOT admin_reports_maintenance_active())', '(NOT admin_reports_maintenance_active())'),
    ('event_views', 'Admins read event_views', 'PERMISSIVE', 'SELECT', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('event_views', 'Anyone can insert event_view', 'PERMISSIVE', 'INSERT', '{public}', None, 'true'),
    ('field_corrections', 'Admin full access on field_corrections', 'PERMISSIVE', 'ALL', '{authenticated}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))"),
    ('field_corrections', 'field_corrections_maint_block_delete', 'RESTRICTIVE', 'DELETE', '{public}', '(NOT admin_reports_maintenance_active())', None),
    ('field_corrections', 'field_corrections_maint_block_insert', 'RESTRICTIVE', 'INSERT', '{public}', None, '(NOT admin_reports_maintenance_active())'),
    ('field_corrections', 'field_corrections_maint_block_update', 'RESTRICTIVE', 'UPDATE', '{public}', '(NOT admin_reports_maintenance_active())', '(NOT admin_reports_maintenance_active())'),
    ('quota_snapshots', 'Admins can view quota_snapshots', 'PERMISSIVE', 'SELECT', '{authenticated}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('research_reports', 'Admins can update research_reports', 'PERMISSIVE', 'UPDATE', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('research_reports', 'Admins read research_reports', 'PERMISSIVE', 'SELECT', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('research_reports', 'Admins update research_reports', 'PERMISSIVE', 'UPDATE', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('research_sources', 'Admins can read research_sources', 'PERMISSIVE', 'SELECT', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('research_sources', 'Admins can update research_sources', 'PERMISSIVE', 'UPDATE', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('research_sources', 'Service role can write research_sources', 'PERMISSIVE', 'ALL', '{public}', "(auth.role() = 'service_role'::text)", None),
    ('scraper_runs', 'Admins read scraper_runs', 'PERMISSIVE', 'SELECT', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", None),
    ('selection_reason_corrections', 'admin_full_src', 'PERMISSIVE', 'ALL', '{authenticated}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))"),
    ('selection_reason_corrections', 'selection_reason_corrections_maint_block_delete', 'RESTRICTIVE', 'DELETE', '{public}', '(NOT admin_reports_maintenance_active())', None),
    ('selection_reason_corrections', 'selection_reason_corrections_maint_block_insert', 'RESTRICTIVE', 'INSERT', '{public}', None, '(NOT admin_reports_maintenance_active())'),
    ('selection_reason_corrections', 'selection_reason_corrections_maint_block_update', 'RESTRICTIVE', 'UPDATE', '{public}', '(NOT admin_reports_maintenance_active())', '(NOT admin_reports_maintenance_active())'),
    ('source_exclusions', 'source_exclusions_admin_all', 'PERMISSIVE', 'ALL', '{authenticated}', 'is_admin()', 'is_admin()'),
    ('source_exclusions', 'source_exclusions_admin_select', 'PERMISSIVE', 'SELECT', '{authenticated}', 'is_admin()', None),
    ('user_roles', 'Users read own role', 'PERMISSIVE', 'SELECT', '{public}', '(auth.uid() = user_id)', None),
    ('works', 'Admins can manage works', 'PERMISSIVE', 'ALL', '{public}', "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))", "(EXISTS ( SELECT 1\n   FROM user_roles\n  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))"),
    ('works', 'Anyone can read works', 'PERMISSIVE', 'SELECT', '{public}', 'true', None),
    ('works', 'works_maint_block_delete', 'RESTRICTIVE', 'DELETE', '{public}', '(NOT admin_reports_maintenance_active())', None),
    ('works', 'works_maint_block_insert', 'RESTRICTIVE', 'INSERT', '{public}', None, '(NOT admin_reports_maintenance_active())'),
    ('works', 'works_maint_block_update', 'RESTRICTIVE', 'UPDATE', '{public}', '(NOT admin_reports_maintenance_active())', '(NOT admin_reports_maintenance_active())'),
]
DROPPED_POLICIES = [('research_reports', 'Admins update research_reports'), ('research_sources', 'Service role can write research_sources'), ('source_exclusions', 'source_exclusions_admin_select')]
FK_COLUMNS = [('announcements', 'author_id'), ('app_settings', 'updated_by'), ('category_corrections', 'corrected_by'), ('field_corrections', 'corrected_by'), ('field_corrections_audit', 'report_id'), ('selection_reason_corrections', 'corrected_by'), ('source_exclusions', 'created_by')]

ADMIN_B = BEFORE_POLICIES[1][5]
TABLES = sorted({r[0] for r in BEFORE_POLICIES})
assert len(TABLES) == 17

ADMIN_ID = "00000000-0000-0000-0000-0000000000a1"
USER_ID = "00000000-0000-0000-0000-0000000000b2"
NOROLE_ID = "00000000-0000-0000-0000-0000000000c3"
OTHER_ID = "00000000-0000-0000-0000-0000000000d4"
LOCK_KEY = "admin_reports_cleanup_maintenance"

IDENTITIES = {
    "anon": ("anon", {"role": "anon"}),
    "user": ("authenticated", {"sub": USER_ID, "role": "authenticated"}),
    "admin": ("authenticated", {"sub": ADMIN_ID, "role": "authenticated"}),
    "norole": ("authenticated", {"sub": NOROLE_ID, "role": "authenticated"}),
    "service": ("service_role", {"role": "service_role"}),
}

# --- schema fixture ----------------------------------------------------------
ROLES_SQL = """
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
  if not exists (select 1 from pg_roles where rolname = 'postgres_owner') then create role postgres_owner login bypassrls; end if;
  if not exists (select 1 from pg_roles where rolname = 'ddl_tester') then create role ddl_tester login; end if;
end $$;
"""

# Superuser part: auth schema (Supabase's real auth.uid()/auth.role()) and grants.
SUPER_SQL = """
create schema auth;
create table auth.users (
  id uuid primary key,
  email text,
  created_at timestamptz not null default now(),
  last_sign_in_at timestamptz
);
create function auth.uid() returns uuid language sql stable as $f$
  select
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$f$;
create function auth.role() returns text language sql stable as $f$
  select
  coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$f$;
grant usage on schema auth to anon, authenticated, service_role, postgres_owner;
grant select, references on auth.users to postgres_owner;
grant usage on schema public to anon, authenticated, service_role, postgres_owner;
grant create on schema public to postgres_owner, ddl_tester;
grant ddl_tester to postgres_owner;
-- Supabase grants every new public object to the API roles.
alter default privileges for role postgres_owner in schema public grant all on tables to anon, authenticated, service_role;
alter default privileges for role postgres_owner in schema public grant all on sequences to anon, authenticated, service_role;
alter default privileges for role postgres_owner in schema public grant execute on functions to anon, authenticated, service_role;
insert into auth.users (id, email, last_sign_in_at) values
  ('%(admin)s', 'admin@example.test', now()),
  ('%(user)s', 'user@example.test', now()),
  ('%(norole)s', 'norole@example.test', null);
""" % {"admin": ADMIN_ID, "user": USER_ID, "norole": NOROLE_ID}

# Owner part (runs as postgres_owner): public tables, functions, triggers.
OWNER_SQL = """
create function public.set_updated_at() returns trigger language plpgsql as $f$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$f$;
create function public.set_creators_updated_at() returns trigger language plpgsql as $f$
begin
  new.updated_at = now();
  return new;
end;
$f$;
create function public.update_announcements_updated_at() returns trigger language plpgsql as $f$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$f$;
create function public.works_set_updated_at() returns trigger language plpgsql as $f$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$f$;

create table public.user_roles (
  user_id uuid primary key, role text not null default 'user', publish_banned_until timestamptz);
create function public.is_admin() returns boolean language sql stable security definer as $f$
  select exists (
    select 1 from public.user_roles
    where user_id = (select auth.uid()) and role = 'admin'
  );
$f$;
create table public.app_settings (
  key text primary key, value jsonb not null, updated_at timestamptz not null default now(),
  updated_by uuid references auth.users(id));
create function public.admin_reports_maintenance_active() returns boolean language sql stable security definer
  set search_path to 'pg_catalog' as $f$
  SELECT NOT EXISTS (
    SELECT 1 FROM public.app_settings
    WHERE key = 'admin_reports_cleanup_maintenance'
      AND value->'active' = 'false'::jsonb
  );
$f$;
create function public.admin_list_users()
 returns table(id uuid, email text, created_at timestamptz, last_sign_in_at timestamptz, role text)
 language plpgsql security definer set search_path to 'pg_catalog' as $f$
declare
  v_sub text;
  v_user_id uuid;
begin
  v_sub := nullif(current_setting('request.jwt.claim.sub', true), '');
  v_user_id := coalesce(auth.uid(), v_sub::uuid);
  if v_user_id is null then
    raise exception 'admin privileges required' using errcode = '42501';
  end if;
  if not exists (select 1 from public.user_roles r where r.user_id = v_user_id and r.role = 'admin') then
    raise exception 'admin privileges required' using errcode = '42501';
  end if;
  return query
  select u.id::uuid, u.email::text, u.created_at::timestamptz, u.last_sign_in_at::timestamptz, r.role::text
  from auth.users u left join public.user_roles r on r.user_id = u.id
  order by u.created_at desc;
end;
$f$;
comment on function public.admin_list_users() is
  'Admin-only RPC; uses auth.uid() first, then request.jwt.claim.sub fallback for SQL Editor testing.';
create function public.rls_auto_enable() returns event_trigger language plpgsql security definer
  set search_path to 'pg_catalog' as $f$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN
    SELECT *
    FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
      AND object_type IN ('table','partitioned table')
  LOOP
     IF cmd.schema_name IS NOT NULL AND cmd.schema_name IN ('public') AND cmd.schema_name NOT IN ('pg_catalog','information_schema') AND cmd.schema_name NOT LIKE 'pg_toast%%' AND cmd.schema_name NOT LIKE 'pg_temp%%' THEN
      BEGIN
        EXECUTE format('alter table if exists %%s enable row level security', cmd.object_identity);
        RAISE LOG 'rls_auto_enable: enabled RLS on %%', cmd.object_identity;
      EXCEPTION
        WHEN OTHERS THEN
          RAISE LOG 'rls_auto_enable: failed to enable RLS on %%', cmd.object_identity;
      END;
     ELSE
        RAISE LOG 'rls_auto_enable: skip %% (either system schema or not in enforced list: %%.)', cmd.object_identity, cmd.schema_name;
     END IF;
  END LOOP;
END;
$f$;
-- Production ACLs: no PUBLIC entry on these two, PUBLIC on the rest.
revoke execute on function public.admin_list_users() from public;
revoke execute on function public.admin_reports_maintenance_active() from public;

create table public.account_usage (
  user_id uuid not null, usage_date date not null,
  annotate_count int not null default 0, extract_count int not null default 0,
  primary key (user_id, usage_date));
create table public.aeo_visits (
  id bigint generated by default as identity primary key, visited_at timestamptz not null default now(),
  visit_type text not null, bot_name text, path text not null, country text);
create table public.announcements (
  id uuid primary key default gen_random_uuid(), slug text not null unique, title_ja text,
  is_featured boolean not null default false, published_at timestamptz,
  author_id uuid references auth.users(id), created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(), type text not null default 'manual');
create table public.announcement_events (announcement_id uuid not null, event_id uuid not null);
create table public.creator_events (creator_id uuid not null, event_id uuid not null, relationship text not null);
create table public.event_reports (
  id uuid primary key default gen_random_uuid(), event_id uuid not null, report_types text[] not null,
  locale text, status text not null default 'pending', admin_notes text, confirmed_at timestamptz,
  created_at timestamptz not null default now(), suggested_category text[]);
create table public.event_views (
  id bigint generated by default as identity primary key, event_id uuid not null,
  viewed_at timestamptz not null default now(), locale text not null default 'zh');
create table public.field_corrections (
  id uuid primary key default gen_random_uuid(), event_id uuid not null, field_name text not null,
  original_value text, corrected_value text not null, corrected_by uuid references auth.users(id),
  created_at timestamptz default now(), report_id uuid);
create index field_corrections_event_id_idx on public.field_corrections (event_id);
create table public.field_corrections_audit (
  id uuid primary key default gen_random_uuid(), event_id uuid not null, field_name text not null,
  report_id uuid references public.event_reports(id) on delete set null, unlock_reason text not null);
create table public.category_corrections (
  id uuid primary key default gen_random_uuid(), event_id uuid not null unique,
  corrected_by uuid references auth.users(id));
create table public.quota_snapshots (
  id uuid primary key default gen_random_uuid(), taken_at timestamptz not null default now(),
  resource text not null, metric text not null, value numeric not null);
create table public.research_reports (
  id bigint generated by default as identity primary key, created_at timestamptz not null default now(),
  report_type text not null, content jsonb not null, status text not null default 'pending');
create table public.research_sources (
  id serial primary key, name text not null, url text not null, status text not null default 'candidate');
create table public.scraper_runs (
  id bigint generated by default as identity primary key, ran_at timestamptz not null default now(),
  source text not null, success boolean not null default true);
create table public.selection_reason_corrections (
  id uuid primary key default gen_random_uuid(), event_id uuid not null, corrected_sr jsonb not null,
  corrected_by uuid references auth.users(id), created_at timestamptz not null default now());
create table public.source_exclusions (
  id uuid primary key default gen_random_uuid(), source_name text not null, pattern text not null,
  created_by uuid references auth.users(id) on delete set null);
create table public.works (
  id uuid primary key default gen_random_uuid(), work_type text not null, original_title text not null,
  updated_at timestamptz default now());
create table public.events (
  id uuid primary key default gen_random_uuid(), name_ja text, is_active boolean not null default true,
  updated_at timestamptz not null default now());
create table public.creators (
  id uuid primary key default gen_random_uuid(), name text, updated_at timestamptz not null default now());

create trigger events_updated_at before update on public.events for each row execute function set_updated_at();
create trigger creators_updated_at before update on public.creators for each row execute function set_creators_updated_at();
create trigger announcements_updated_at before update on public.announcements for each row execute function update_announcements_updated_at();
create trigger works_updated_at before update on public.works for each row execute function works_set_updated_at();

alter table public.events enable row level security;
alter table public.creators enable row level security;
alter table public.field_corrections_audit enable row level security;
alter table public.category_corrections enable row level security;
%(enable_rls)s
create policy "Public read active events" on public.events for select to public using (is_active);
create policy "Admins read all events" on public.events for select to public using (public.is_admin());
create policy "Admins manage creators" on public.creators for all to authenticated using (public.is_admin()) with check (public.is_admin());

-- Production table grants differ from "everything" in two places.
revoke all on public.account_usage from anon;
revoke insert, update, delete, truncate, references, trigger on public.account_usage from authenticated;
revoke all on public.creators from anon;

%(policies)s

insert into public.user_roles (user_id, role) values ('%(admin)s', 'admin'), ('%(user)s', 'user');
insert into public.app_settings (key, value) values ('%(lock)s', '{"active": false}'), ('other_key', '{"v": 1}');
insert into public.account_usage (user_id, usage_date) values ('%(user)s', '2026-01-01'), ('%(other)s', '2026-01-01');
insert into public.events (name_ja, is_active) values ('active', true), ('inactive', false);
insert into public.creators (name) values ('c1');
insert into public.announcements (slug, title_ja, published_at, author_id) values
  ('pub', 'p', now() - interval '1 day', '%(admin)s'), ('draft', 'd', null, null);
insert into public.announcement_events (announcement_id, event_id)
  select id, gen_random_uuid() from public.announcements;
insert into public.creator_events values (gen_random_uuid(), gen_random_uuid(), 'organizer');
insert into public.event_reports (id, event_id, report_types) values
  ('00000000-0000-0000-0000-00000000e001', gen_random_uuid(), '{wrong_date}'), (gen_random_uuid(), gen_random_uuid(), '{other}');
insert into public.event_views (event_id) values (gen_random_uuid());
insert into public.field_corrections (event_id, field_name, corrected_value, corrected_by)
  values (gen_random_uuid(), 'name_ja', 'v', '%(admin)s');
insert into public.field_corrections_audit (event_id, field_name, report_id, unlock_reason)
  values (gen_random_uuid(), 'name_ja', '00000000-0000-0000-0000-00000000e001', 'x');
insert into public.category_corrections (event_id, corrected_by) values (gen_random_uuid(), '%(admin)s');
insert into public.quota_snapshots (resource, metric, value) values ('r', 'm', 1);
insert into public.research_reports (report_type, content) values ('t', '{}'), ('t2', '{}');
insert into public.research_sources (name, url) values ('n', 'u');
insert into public.scraper_runs (source) values ('s');
insert into public.selection_reason_corrections (event_id, corrected_sr) values (gen_random_uuid(), '{}');
insert into public.source_exclusions (source_name, pattern, created_by) values ('s', 'p', '%(admin)s');
insert into public.works (work_type, original_title) values ('movie', 'w');
insert into public.aeo_visits (visit_type, path) select 'bot', '/p' || g from generate_series(1, 30000) g;
analyze;
"""

# Superuser part 2: the Dashboard-created event trigger.
EVENT_TRIGGER_SQL = """
create event trigger ensure_rls on ddl_command_end
  when tag in ('CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO')
  execute function public.rls_auto_enable();
"""

OPS = {
    "user_roles": ("role", "user_id, role", "gen_random_uuid(), 'user'"),
    "account_usage": ("annotate_count", "user_id, usage_date", "gen_random_uuid(), '2099-01-01'"),
    "event_reports": ("status", "event_id, report_types", "gen_random_uuid(), '{x}'"),
    "scraper_runs": ("source", "source", "'x'"),
    "research_reports": ("status", "report_type, content", "'x', '{}'"),
    "research_sources": ("name", "name, url", "'n2', 'u2'"),
    "event_views": ("locale", "event_id", "gen_random_uuid()"),
    "creator_events": ("relationship", "creator_id, event_id, relationship", "gen_random_uuid(), gen_random_uuid(), 'r'"),
    "aeo_visits": ("path", "visit_type, path", "'bot', '/new'"),
    "announcements": ("title_ja", "slug", "'new-' || gen_random_uuid()"),
    "announcement_events": ("announcement_id", "announcement_id, event_id", "gen_random_uuid(), gen_random_uuid()"),
    "field_corrections": ("field_name", "event_id, field_name, corrected_value", "gen_random_uuid(), 'f', 'v'"),
    "selection_reason_corrections": ("corrected_sr", "event_id, corrected_sr", "gen_random_uuid(), '{}'"),
    "quota_snapshots": ("resource", "resource, metric, value", "'r', 'm', 1"),
    "works": ("original_title", "work_type, original_title", "'movie', 'w2'"),
    "app_settings": ("value", "key, value", "'k_new', '{}'"),
    "source_exclusions": ("pattern", "source_name, pattern", "'s2', 'p2'"),
}
assert sorted(OPS) == TABLES


def _pg_bin() -> Path | None:
    found = shutil.which("pg_ctl")
    candidates = [Path(found).parent] if found else []
    candidates += [Path(p) for p in sorted(glob.glob("/opt/homebrew/opt/postgresql@*/bin"), reverse=True)]
    candidates += [Path(p) for p in sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)]
    for c in candidates:
        if (c / "pg_ctl").exists() and (c / "initdb").exists():
            return c
    return None


def _policy_ddl() -> str:
    out = []
    for table, name, permissive, cmd, roles, qual, check in BEFORE_POLICIES:
        sql = f'create policy "{name}" on public.{table} as {permissive.lower()} for {cmd.lower()}'
        sql += " to " + roles.strip("{}").replace(",", ", ")
        if qual is not None:
            sql += f" using ({qual})"
        if check is not None:
            sql += f" with check ({check})"
        out.append(sql + ";")
    return "\n".join(out)


def _connect(info, user=None, dbname=None, autocommit=True):
    kw = dict(info)
    if user:
        kw["user"] = user
    if dbname:
        kw["dbname"] = dbname
    conn = psycopg2.connect(**kw)
    conn.autocommit = autocommit
    return conn


def _build_db(info, name):
    """Create database `name` with the production-like fixture; returns its connection info."""
    root = _connect(info, dbname="postgres")
    with root.cursor() as cur:
        cur.execute(f"create database {name}")
    root.close()
    dbi = dict(info, dbname=name)
    sup = _connect(dbi)
    with sup.cursor() as cur:
        cur.execute(SUPER_SQL)
    own = _connect(dbi, user="postgres_owner")
    enable_rls = "\n".join(f"alter table public.{t} enable row level security;" for t in TABLES)
    with own.cursor() as cur:
        cur.execute(OWNER_SQL % {
            "enable_rls": enable_rls, "policies": _policy_ddl(),
            "admin": ADMIN_ID, "user": USER_ID, "other": OTHER_ID, "lock": LOCK_KEY,
        })
    own.close()
    with sup.cursor() as cur:
        cur.execute(EVENT_TRIGGER_SQL)
    sup.close()
    return dbi


@pytest.fixture(scope="module")
def cluster():
    bin_dir = _pg_bin()
    if bin_dir is None:
        pytest.skip("no local PostgreSQL install (pg_ctl/initdb) found")
    root = Path(tempfile.mkdtemp(prefix="ttrpg", dir="/tmp"))
    data = root / "data"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    subprocess.run([bin_dir / "initdb", "-D", data, "-U", "postgres", "-A", "trust", "-E", "UTF8", "--locale=C"],
                   check=True, capture_output=True)
    subprocess.run([bin_dir / "pg_ctl", "-D", data, "-w", "-l", root / "server.log", "-o",
                    f"-p {port} -c listen_addresses='' -c unix_socket_directories={root} -c fsync=off", "start"],
                   check=True, capture_output=True)
    info = {"host": str(root), "port": port, "dbname": "postgres", "user": "postgres"}
    admin = _connect(info)
    with admin.cursor() as cur:
        cur.execute(ROLES_SQL)
    admin.close()
    yield info
    subprocess.run([bin_dir / "pg_ctl", "-D", data, "-m", "immediate", "stop"], capture_output=True)
    shutil.rmtree(root, ignore_errors=True)


def run_migration(info, path: Path):
    conn = _connect(info, user="postgres_owner")
    try:
        with conn.cursor() as cur:
            cur.execute(path.read_text())
    finally:
        conn.close()


def as_identity(info, who):
    """Superuser connection that SET ROLEs into one of the five identities, JWT claims set."""
    role, claims = IDENTITIES[who]
    conn = _connect(info, autocommit=False)
    with conn.cursor() as cur:
        cur.execute(f"set role {role}")
        cur.execute("select set_config('request.jwt.claims', %s, false)", (json.dumps(claims),))
    return conn


def attempt(conn, sql):
    """Run sql inside a savepoint, roll it back; return rowcount / scalar or the SQLSTATE."""
    with conn.cursor() as cur:
        cur.execute("savepoint s")
        try:
            cur.execute(sql)
            if sql.lstrip().lower().startswith("select"):
                result = cur.fetchone()[0]
            elif sql.lstrip().lower().startswith("insert"):
                result = "ok" if cur.rowcount >= 0 else "?"
            else:
                result = cur.rowcount
        except psycopg2.Error as exc:
            result = exc.pgcode
        cur.execute("rollback to savepoint s")
    return result


def behaviour_matrix(info):
    matrix = {}
    for who in IDENTITIES:
        conn = as_identity(info, who)
        for table in TABLES:
            col, ins_cols, ins_vals = OPS[table]
            matrix[(who, table, "select")] = attempt(conn, f"select count(*) from public.{table}")
            matrix[(who, table, "update")] = attempt(conn, f"update public.{table} set {col} = {col}")
            matrix[(who, table, "delete")] = attempt(conn, f"delete from public.{table}")
            matrix[(who, table, "insert")] = attempt(
                conn, f"insert into public.{table} ({ins_cols}) values ({ins_vals})")
        conn.rollback()
        conn.close()
    return matrix


def policies(info, tables=None):
    conn = _connect(info)
    with conn.cursor() as cur:
        cur.execute(
            "select tablename::text, policyname::text, permissive::text, cmd::text, roles::text, qual, with_check"
            " from pg_policies where schemaname = 'public' order by 1, 2")
        rows = cur.fetchall()
    conn.close()
    if tables is not None:
        rows = [r for r in rows if r[0] in tables]
    return rows


def scalar(info, sql, params=None, user=None):
    conn = _connect(info, user=user)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        value = cur.fetchone()[0]
    conn.close()
    return value


def explain(info, who, sql):
    conn = as_identity(info, who)
    with conn.cursor() as cur:
        cur.execute("explain (costs off) " + sql)
        plan = "\n".join(r[0] for r in cur.fetchall())
    conn.rollback()
    conn.close()
    return plan


FUNCS = ["is_admin", "admin_reports_maintenance_active", "admin_list_users", "rls_auto_enable",
         "set_creators_updated_at", "set_updated_at", "update_announcements_updated_at", "works_set_updated_at"]


def acl_matrix(info):
    conn = _connect(info)
    out = {}
    with conn.cursor() as cur:
        for f in FUNCS:
            for role in ("anon", "authenticated", "service_role"):
                cur.execute("select has_function_privilege(%s, %s::regprocedure, 'EXECUTE')",
                            (role, f"public.{f}()"))
                out[(f, role)] = cur.fetchone()[0]
    conn.close()
    return out


def proconfig(info):
    conn = _connect(info)
    with conn.cursor() as cur:
        cur.execute("select proname, proconfig from pg_proc where pronamespace = 'public'::regnamespace"
                    " and proname = any(%s)", (FUNCS,))
        out = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()
    return out


def is_admin_oid_and_deps(info):
    conn = _connect(info)
    with conn.cursor() as cur:
        cur.execute("select oid from pg_proc where proname = 'is_admin' and pronamespace = 'public'::regnamespace")
        oid = cur.fetchone()[0]
        cur.execute(
            "select count(*) from pg_depend d where d.refclassid = 'pg_proc'::regclass and d.refobjid = %s"
            " and d.classid = 'pg_policy'::regclass", (oid,))
        deps = cur.fetchone()[0]
    conn.close()
    return oid, deps


def index_leads_with(info, table, column):
    return scalar(info, """
        select exists (select 1 from pg_index i
          join pg_attribute a on a.attrelid = i.indrelid and a.attnum = i.indkey[0]
         where i.indrelid = %s::regclass and a.attname = %s and i.indisvalid and i.indpred is null)""",
                  (f"public.{table}", column))


def norm(s):
    if s is None:
        return None
    s = re.sub(r"\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)", "@UID@", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def expected_after():
    dropped = set(DROPPED_POLICIES)
    out = []
    for table, name, permissive, cmd, roles, qual, check in BEFORE_POLICIES:
        if (table, name) in dropped:
            continue
        new_roles = "{authenticated}" if (qual == ADMIN_B and roles == "{public}") else roles
        sub = (lambda s: None if s is None else s.replace("auth.uid()", "@UID@"))
        out.append((table, name, permissive, cmd, new_roles, norm(sub(qual)), norm(sub(check))))
    return sorted(out)


def normalised(rows):
    return sorted((t, p, pm, c, r, norm(q), norm(w)) for t, p, pm, c, r, q, w in rows)


class Stages:
    pass


@pytest.fixture(scope="module")
def stages(cluster):
    """One database taken through: production-like -> 106 -> 107, with snapshots between."""
    info = _build_db(cluster, "adv_main")
    s = Stages()
    s.info = info
    s.cluster = cluster
    s.matrix0 = behaviour_matrix(info)
    s.policies0 = policies(info)
    s.acl0 = acl_matrix(info)
    s.config0 = proconfig(info)
    s.oid0, s.deps0 = is_admin_oid_and_deps(info)
    s.fk_before = {(t, c): index_leads_with(info, t, c) for t, c in FK_COLUMNS}
    s.explain_before = {
        "aeo_visits (admin)": explain(info, "admin", "select * from public.aeo_visits where path = '/p5'"),
        "aeo_visits (anon)": explain(info, "anon", "select * from public.aeo_visits where path = '/p5'"),
        "user_roles (user)": explain(info, "user", "select * from public.user_roles"),
        "account_usage (user)": explain(info, "user", "select * from public.account_usage"),
    }
    run_migration(info, MIG_106)
    s.matrix1 = behaviour_matrix(info)
    s.policies1 = policies(info)
    s.acl1 = acl_matrix(info)
    s.config1 = proconfig(info)
    s.oid1, s.deps1 = is_admin_oid_and_deps(info)
    run_migration(info, MIG_107)
    s.matrix2 = behaviour_matrix(info)
    s.policies2 = policies(info)
    s.acl2 = acl_matrix(info)
    s.fk_after = {(t, c): index_leads_with(info, t, c) for t, c in FK_COLUMNS}
    s.explain_after = {
        "aeo_visits (admin)": explain(info, "admin", "select * from public.aeo_visits where path = '/p5'"),
        "aeo_visits (anon)": explain(info, "anon", "select * from public.aeo_visits where path = '/p5'"),
        "user_roles (user)": explain(info, "user", "select * from public.user_roles"),
        "account_usage (user)": explain(info, "user", "select * from public.account_usage"),
    }
    return s


# --- fixture sanity ------------------------------------------------------------
def test_fixture_matches_production_before_image(stages):
    got = [r for r in stages.policies0 if r[0] in TABLES]
    assert normalised(got) == normalised(BEFORE_POLICIES)
    assert len(got) == 43


def test_fixture_is_not_superuser_migration_context(stages):
    conn = _connect(stages.info, user="postgres_owner")
    with conn.cursor() as cur:
        cur.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
        assert cur.fetchone() == (False, True)
    conn.close()


# --- 107 behaviour ------------------------------------------------------------
def test_behaviour_matrix_identical_before_and_after_107(stages):
    assert len(stages.matrix0) == 5 * 17 * 4
    diffs = {k: (stages.matrix0[k], stages.matrix2[k]) for k in stages.matrix0 if stages.matrix0[k] != stages.matrix2[k]}
    assert diffs == {}


def test_behaviour_matrix_unchanged_by_106(stages):
    diffs = {k: (stages.matrix0[k], stages.matrix1[k]) for k in stages.matrix0 if stages.matrix0[k] != stages.matrix1[k]}
    assert diffs == {}


def test_behaviour_matrix_is_not_trivial(stages):
    m = stages.matrix2
    assert m[("admin", "event_reports", "select")] == 2
    assert m[("user", "event_reports", "select")] == 0
    assert m[("anon", "event_reports", "insert")] == "ok"
    assert m[("anon", "user_roles", "select")] == 0
    assert m[("user", "user_roles", "select")] == 1
    assert m[("admin", "user_roles", "select")] == 1
    assert m[("user", "account_usage", "select")] == 1
    assert m[("norole", "account_usage", "select")] == 0
    assert m[("anon", "account_usage", "select")] == "42501"
    assert m[("service", "works", "select")] == 1
    assert m[("admin", "works", "insert")] == "ok"
    assert m[("user", "works", "insert")] == "42501"
    assert m[("anon", "research_sources", "select")] == 0
    assert m[("admin", "research_sources", "select")] == 1
    assert m[("admin", "source_exclusions", "select")] == 1
    assert m[("user", "source_exclusions", "select")] == 0
    assert m[("admin", "aeo_visits", "select")] == 30000
    assert m[("anon", "aeo_visits", "insert")] == "ok"


def test_maintenance_lock_still_blocks_and_releases(stages):
    info = stages.info

    def set_lock(active):
        conn = _connect(info)
        with conn.cursor() as cur:
            cur.execute("update public.app_settings set value = %s::jsonb where key = %s",
                        (json.dumps({"active": active}), LOCK_KEY))
        conn.close()

    insert_work = "insert into public.works (work_type, original_title) values ('m', 'locked')"
    insert_fc = "insert into public.field_corrections (event_id, field_name, corrected_value) values (gen_random_uuid(), 'f', 'v')"
    update_report = "update public.event_reports set status = status"
    insert_report = "insert into public.event_reports (event_id, report_types) values (gen_random_uuid(), '{x}')"
    try:
        set_lock(True)
        admin = as_identity(info, "admin")
        assert attempt(admin, insert_work) == "42501"
        assert attempt(admin, insert_fc) == "42501"
        assert attempt(admin, update_report) == 0
        admin.close()
        anon = as_identity(info, "anon")
        assert attempt(anon, insert_report) == "42501"
        anon.close()
        set_lock(False)
        admin = as_identity(info, "admin")
        assert attempt(admin, insert_work) == "ok"
        assert attempt(admin, insert_fc) == "ok"
        assert attempt(admin, update_report) == 2
        admin.close()
        anon = as_identity(info, "anon")
        assert attempt(anon, insert_report) == "ok"
        anon.close()
    finally:
        set_lock(False)


def test_policy_structure_after_107(stages):
    got = normalised([r for r in stages.policies2 if r[0] in TABLES])
    assert got == expected_after()
    assert len(got) == 40


def test_policy_cmd_and_permissive_unchanged(stages):
    before = {(r[0], r[1]): (r[2], r[3]) for r in stages.policies0}
    after = {(r[0], r[1]): (r[2], r[3]) for r in stages.policies2}
    assert {k: v for k, v in before.items() if k in after} == after
    removed = set(before) - set(after)
    assert removed == set(DROPPED_POLICIES)


def test_roles_change_only_as_planned(stages):
    before = {(r[0], r[1]): r[4] for r in stages.policies0}
    changed = {(r[0], r[1]): (before[(r[0], r[1])], r[4]) for r in stages.policies2
               if before[(r[0], r[1])] != r[4]}
    assert changed and all(old == "{public}" and new == "{authenticated}" for old, new in changed.values())
    assert ("user_roles", "Users read own role") not in changed
    assert len(changed) == 13
    # events and every policy outside the 17 tables are not touched at all.
    outside_before = [r for r in stages.policies0 if r[0] not in TABLES]
    outside_after = [r for r in stages.policies2 if r[0] not in TABLES]
    assert outside_before == outside_after and len(outside_before) == 3


def test_no_unwrapped_auth_calls_remain(stages):
    for table, name, _pm, _cmd, _roles, qual, check in stages.policies2:
        for text in (qual, check):
            stripped = re.sub(r"\(\s*SELECT\s+auth\.(uid|role)\(\)\s+AS\s+\w+\s*\)", "", text or "", flags=re.I)
            assert not re.search(r"auth\.(uid|role)\(\)", stripped), (table, name, text)
    wrapped = [r for r in stages.policies2 if "SELECT auth.uid()" in (r[5] or "") + (r[6] or "")]
    assert len(wrapped) == 19


def test_with_check_only_where_it_existed(stages):
    before = {(r[0], r[1]): r[6] is not None for r in stages.policies0}
    after = {(r[0], r[1]): r[6] is not None for r in stages.policies2}
    assert {k: v for k, v in before.items() if k in after} == after


# --- 106 ----------------------------------------------------------------------
def test_acl_matrix_after_106(stages):
    a = stages.acl1
    for role in ("anon", "authenticated", "service_role"):
        # untouched helpers keep every role (anon needs them inside policies)
        assert a[("is_admin", role)] is True
        assert a[("admin_reports_maintenance_active", role)] is True
    assert a[("admin_list_users", "anon")] is False
    assert a[("admin_list_users", "authenticated")] is True
    assert a[("admin_list_users", "service_role")] is True
    assert a[("rls_auto_enable", "anon")] is False
    assert a[("rls_auto_enable", "authenticated")] is False
    assert a[("rls_auto_enable", "service_role")] is True
    # trigger functions keep their grants
    for f in ("set_creators_updated_at", "set_updated_at", "update_announcements_updated_at", "works_set_updated_at"):
        for role in ("anon", "authenticated", "service_role"):
            assert a[(f, role)] is True
    # before: everything was executable
    assert stages.acl0[("admin_list_users", "anon")] is True
    assert stages.acl0[("rls_auto_enable", "authenticated")] is True
    assert stages.acl2 == stages.acl1


def test_no_public_execute_left_on_revoked_functions(stages):
    conn = _connect(stages.info)
    with conn.cursor() as cur:
        cur.execute("select proname, proacl::text from pg_proc where pronamespace = 'public'::regnamespace"
                    " and proname in ('admin_list_users', 'rls_auto_enable')")
        acls = dict(cur.fetchall())
    conn.close()
    for name, acl in acls.items():
        assert not acl.startswith("{=") and ",=" not in acl, (name, acl)


def test_admin_list_users_behaviour(stages):
    anon = as_identity(stages.info, "anon")
    assert attempt(anon, "select count(*) from public.admin_list_users()") == "42501"
    anon.close()
    user = as_identity(stages.info, "user")
    assert attempt(user, "select count(*) from public.admin_list_users()") == "42501"
    user.close()
    norole = as_identity(stages.info, "norole")
    assert attempt(norole, "select count(*) from public.admin_list_users()") == "42501"
    norole.close()
    admin = as_identity(stages.info, "admin")
    assert attempt(admin, "select count(*) from public.admin_list_users()") == 3
    admin.close()
    service = as_identity(stages.info, "service")
    # service_role keeps EXECUTE; the body still demands an admin sub (unchanged behaviour)
    assert attempt(service, "select count(*) from public.admin_list_users()") == "42501"
    service.close()
    # anon error comes from the ACL layer now: permission denied for function
    anon = as_identity(stages.info, "anon")
    with anon.cursor() as cur:
        with pytest.raises(errors.InsufficientPrivilege, match="permission denied for function admin_list_users"):
            cur.execute("select * from public.admin_list_users()")
    anon.close()


def test_is_admin_oid_dependents_and_search_path(stages):
    assert stages.oid0 == stages.oid1
    assert stages.deps0 == stages.deps1 and stages.deps0 >= 3
    assert stages.config0["is_admin"] is None
    for f in ("is_admin", "set_creators_updated_at", "set_updated_at",
              "update_announcements_updated_at", "works_set_updated_at"):
        assert stages.config1[f] == ["search_path=pg_catalog"], f
    assert stages.config1["admin_list_users"] == ["search_path=pg_catalog"]
    assert stages.config1["admin_reports_maintenance_active"] == ["search_path=pg_catalog"]
    assert stages.config1["rls_auto_enable"] == ["search_path=pg_catalog"]
    conn = _connect(stages.info)
    with conn.cursor() as cur:
        cur.execute("select prosecdef, pg_get_userbyid(proowner) from pg_proc where proname = 'is_admin'")
        assert cur.fetchone() == (True, "postgres_owner")
    conn.close()


def test_anon_events_read_still_works(stages):
    anon = as_identity(stages.info, "anon")
    assert attempt(anon, "select count(*) from public.events") == 1
    anon.close()
    admin = as_identity(stages.info, "admin")
    assert attempt(admin, "select count(*) from public.events") == 2
    admin.close()


def test_function_comments(stages):
    conn = _connect(stages.info)
    with conn.cursor() as cur:
        cur.execute("select p.proname, obj_description(p.oid, 'pg_proc') from pg_proc p"
                    " where pronamespace = 'public'::regnamespace and proname in"
                    " ('admin_list_users', 'is_admin', 'admin_reports_maintenance_active', 'rls_auto_enable')")
        comments = dict(cur.fetchall())
    conn.close()
    assert comments["admin_list_users"].startswith(
        "Admin-only RPC; uses auth.uid() first, then request.jwt.claim.sub fallback for SQL Editor testing.")
    assert "authenticated and service_role only" in comments["admin_list_users"]
    assert "SET search_path = pg_catalog" in comments["is_admin"] and "anon" in comments["is_admin"]
    assert "anon" in comments["admin_reports_maintenance_active"]
    assert "Dashboard" in comments["rls_auto_enable"] and "rerun migration 106" in comments["rls_auto_enable"]


def test_event_trigger_still_enables_rls_without_execute(stages):
    info = stages.info
    assert scalar(info, "select has_function_privilege('ddl_tester', 'public.rls_auto_enable()', 'EXECUTE')") is False
    conn = _connect(info, user="ddl_tester")
    with conn.cursor() as cur:
        cur.execute("create table public.zz_new_table (id int)")
        cur.execute("select relrowsecurity from pg_class where oid = 'public.zz_new_table'::regclass")
        assert cur.fetchone()[0] is True
        cur.execute("drop table public.zz_new_table")
    conn.close()


@pytest.mark.parametrize("table,column,sql", [
    ("events", "name_ja", "update public.events set name_ja = 'x' where name_ja = 'active'"),
    ("creators", "name", "update public.creators set name = 'x'"),
    ("announcements", "title_ja", "update public.announcements set title_ja = 'x'"),
    ("works", "original_title", "update public.works set original_title = original_title || 'x'"),
])
def test_updated_at_triggers_still_fire(stages, table, column, sql):
    conn = _connect(stages.info)
    with conn.cursor() as cur:
        cur.execute(f"update public.{table} set updated_at = '2000-01-01'")
        cur.execute(sql)
        cur.execute(f"select min(updated_at) > now() - interval '1 minute' from public.{table}")
        assert cur.fetchone()[0] is True
    conn.close()


def test_foreign_key_indexes(stages):
    assert not any(stages.fk_before.values())
    assert all(stages.fk_after.values()) and len(stages.fk_after) == 7
    conn = _connect(stages.info)
    with conn.cursor() as cur:
        for table, column in FK_COLUMNS:
            cur.execute("select count(*) from pg_indexes where schemaname = 'public' and indexname = %s",
                        (f"{table}_{column}_idx",))
            assert cur.fetchone()[0] == 1
    conn.close()


def test_explain_before_after(stages):
    lines = []
    for key in stages.explain_before:
        lines.append(f"=== {key} :: before 107 ===\n{stages.explain_before[key]}\n")
        lines.append(f"=== {key} :: after 107 ===\n{stages.explain_after[key]}\n")
    text = "\n".join(lines)
    EXPLAIN_OUT.write_text(text)
    print("\n" + text)
    # Admin-type policies were already InitPlans; the wrap only removes per-row evaluation elsewhere.
    assert "InitPlan" in stages.explain_before["aeo_visits (admin)"]
    assert "InitPlan" in stages.explain_after["aeo_visits (admin)"]
    assert "InitPlan" not in stages.explain_before["user_roles (user)"]
    assert "InitPlan" in stages.explain_after["user_roles (user)"]
    assert "InitPlan" not in stages.explain_before["account_usage (user)"]
    assert "InitPlan" in stages.explain_after["account_usage (user)"]


# --- idempotence, dry-run files, negative cases ---------------------------------
def test_migrations_are_idempotent(stages):
    info = stages.info
    pol, acl, cfg = policies(info), acl_matrix(info), proconfig(info)
    run_migration(info, MIG_106)
    run_migration(info, MIG_107)
    assert policies(info) == pol and acl_matrix(info) == acl and proconfig(info) == cfg
    assert behaviour_matrix(info) == stages.matrix2


def _split_dryrun(path: Path):
    return path.read_text().rstrip("\n").split("\n")


@pytest.mark.parametrize("mig,dry,first_comment", [(MIG_106, DRY_106, "106"), (MIG_107, DRY_107, "107")])
def test_dryrun_files_match_migrations(mig, dry, first_comment):
    m = mig.read_text().rstrip("\n").split("\n")
    d = _split_dryrun(dry)
    assert m.count("commit;") == 1 and m[-1] == "commit;"
    assert d[0].startswith("-- DRY RUN") and first_comment in d[0]
    assert d[-1] == "rollback;" and "commit;" not in d
    assert d[1:-1] == m[:-1]


def test_dryrun_files_change_nothing(cluster):
    info = _build_db(cluster, "adv_dry")
    before = (policies(info), acl_matrix(info), proconfig(info),
              {(t, c): index_leads_with(info, t, c) for t, c in FK_COLUMNS})
    run_migration(info, DRY_106)
    run_migration(info, DRY_107)
    after = (policies(info), acl_matrix(info), proconfig(info),
             {(t, c): index_leads_with(info, t, c) for t, c in FK_COLUMNS})
    assert before == after


def _tamper_text(conn):
    with conn.cursor() as cur:
        cur.execute('alter policy "Admins read research_reports" on public.research_reports using (true)')


def _tamper_extra(conn):
    with conn.cursor() as cur:
        cur.execute('create policy "extra" on public.works for select to anon using (true)')


def _tamper_missing(conn):
    with conn.cursor() as cur:
        cur.execute('drop policy "Anyone can read works" on public.works')


def _tamper_roles(conn):
    with conn.cursor() as cur:
        cur.execute('alter policy "Users read own role" on public.user_roles to authenticated')


@pytest.mark.parametrize("name,tamper", [
    ("text", _tamper_text), ("extra", _tamper_extra), ("missing", _tamper_missing), ("roles", _tamper_roles)])
def test_107_refuses_drifted_policies_and_changes_nothing(cluster, name, tamper):
    info = _build_db(cluster, f"adv_neg_{name}")
    owner = _connect(info, user="postgres_owner")
    tamper(owner)
    owner.close()
    before = policies(info)
    fk_before = {(t, c): index_leads_with(info, t, c) for t, c in FK_COLUMNS}
    with pytest.raises(errors.RaiseException, match=r"^107: live policies"):
        run_migration(info, MIG_107)
    assert policies(info) == before
    assert {(t, c): index_leads_with(info, t, c) for t, c in FK_COLUMNS} == fk_before


def test_107_lock_timeout_rolls_everything_back(cluster):
    info = _build_db(cluster, "adv_lock")
    before = policies(info)
    blocker = _connect(info, autocommit=False)
    with blocker.cursor() as cur:
        cur.execute("lock table public.user_roles in access share mode")
    try:
        start = time.monotonic()
        with pytest.raises(errors.LockNotAvailable):
            run_migration(info, MIG_107)
        elapsed = time.monotonic() - start
    finally:
        blocker.rollback()
        blocker.close()
    assert 4 <= elapsed < 20
    assert policies(info) == before
    assert not any(index_leads_with(info, t, c) for t, c in FK_COLUMNS)
    run_migration(info, MIG_107)  # a plain rerun succeeds once the lock is gone
    assert len([r for r in policies(info) if r[0] in TABLES]) == 40


def test_106_post_check_fails_when_acl_is_wrong(cluster):
    info = _build_db(cluster, "adv_post106")
    sup = _connect(info)
    with sup.cursor() as cur:
        # Drift: authenticated loses is_admin(), which 106 must leave executable, so its post-check trips.
        cur.execute("revoke execute on function public.is_admin() from public, authenticated")
    sup.close()
    with pytest.raises(errors.RaiseException, match=r"^106:"):
        run_migration(info, MIG_106)
    assert scalar(info, "select has_function_privilege('anon', 'public.admin_list_users()', 'EXECUTE')") is True

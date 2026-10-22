-- 099_llm_usage.sql
-- Shared OpenAI usage ledger (llm-cost-reset spec, #363).
--
-- scraper_runs.cost_usd only covered annotator and researcher, priced with
-- hard-coded rates and no cached tokens, so the weekly report under-counted
-- OpenAI spend about 4x against the dashboard. From here on every OpenAI call
-- (scraper/llm_client.py, web/lib/llm/openai.server.ts) writes one llm_usage
-- row; prices live only in llm_pricing; cost is computed at read time by the
-- llm_cost_daily view, so a wrong price is fixed by editing llm_pricing, not
-- by backfilling rows.
--
-- llm_cache holds "already tried / already processed" markers and cached
-- results for the enrich steps (#317 poster hash, #321 cinemaclair image and
-- qa_heartbeat report id, #360 enrich_location event id).
--
-- 098 is taken by 098_scope_report_transaction.sql (japan-scope-gate).
-- Run in Supabase Dashboard → SQL Editor. Idempotent.

-- ── llm_usage: one row per API call ─────────────────────────────────────────
create table if not exists public.llm_usage (
  id                   bigint generated always as identity primary key,
  created_at           timestamptz not null default now(),
  caller               text        not null,  -- "<group>.<name>", e.g. annotator.annotate, web.account.extract-from-image
  model                text        not null,  -- the requested model name, joined to llm_pricing.model
  endpoint             text        not null check (endpoint in ('chat', 'responses')),
  input_tokens         integer     not null default 0,  -- includes cached_input_tokens
  cached_input_tokens  integer     not null default 0,
  output_tokens        integer     not null default 0,
  web_search_calls     integer     not null default 0,
  status               text        not null check (status in ('ok', 'error')),
  error_code           text,
  user_id              uuid        references auth.users (id) on delete set null,  -- web account APIs only
  run_ref              text        -- GitHub Actions "<workflow>#<run_id>"; null on the web
);

comment on table public.llm_usage is
  'One row per OpenAI API call from the scraper and the web app. Cost is computed by llm_cost_daily from llm_pricing.';

create index if not exists llm_usage_created_at_idx on public.llm_usage (created_at);
-- Per-user daily quota checks on the account APIs (#322).
create index if not exists llm_usage_user_caller_idx
  on public.llm_usage (user_id, caller, created_at)
  where user_id is not null;

-- ── llm_pricing: the only place prices live ─────────────────────────────────
create table if not exists public.llm_pricing (
  model                  text    not null,
  effective_from         date    not null,
  input_per_mtok         numeric(12, 6) not null,  -- USD per 1M uncached input tokens
  cached_input_per_mtok  numeric(12, 6) not null,  -- USD per 1M cached input tokens
  output_per_mtok        numeric(12, 6) not null,  -- USD per 1M output tokens
  per_web_search_call    numeric(12, 6) not null default 0,  -- USD per web_search tool call
  notes                  text,
  primary key (model, effective_from)
);

comment on table public.llm_pricing is
  'OpenAI prices by model and effective date (JST). Add a row with a new effective_from to change a price.';

-- Standard-tier prices from the OpenAI model pages, checked 2026-10-22.
insert into public.llm_pricing
  (model, effective_from, input_per_mtok, cached_input_per_mtok, output_per_mtok, per_web_search_call, notes)
values
  ('gpt-4o',      date '2026-01-01', 2.50, 1.25,  10.00, 0, 'OpenAI model page, checked 2026-10-22'),
  ('gpt-4o-mini', date '2026-01-01', 0.15, 0.075, 0.60,  0, 'OpenAI model page, checked 2026-10-22')
on conflict (model, effective_from) do nothing;

-- ── llm_cost_daily: tokens and cost per JST day, caller and model ───────────
create or replace view public.llm_cost_daily
with (security_invoker = true) as
select
  (u.created_at at time zone 'Asia/Tokyo')::date                    as day,
  u.caller,
  u.model,
  count(*)                                                           as calls,
  count(*) filter (where u.status = 'error')                         as errors,
  sum(u.input_tokens)                                                as input_tokens,
  sum(u.cached_input_tokens)                                         as cached_input_tokens,
  sum(u.output_tokens)                                               as output_tokens,
  sum(u.web_search_calls)                                            as web_search_calls,
  coalesce(sum(
      (greatest(u.input_tokens - u.cached_input_tokens, 0) * p.input_per_mtok
       + u.cached_input_tokens * p.cached_input_per_mtok
       + u.output_tokens * p.output_per_mtok) / 1000000.0
      + u.web_search_calls * p.per_web_search_call
  ), 0)::numeric(12, 6)                                              as cost_usd,
  -- Calls whose model has no llm_pricing row: their cost is missing from cost_usd.
  count(*) filter (where p.model is null)                            as unpriced_calls
from public.llm_usage u
left join lateral (
  select lp.*
  from public.llm_pricing lp
  where lp.model = u.model
    and lp.effective_from <= (u.created_at at time zone 'Asia/Tokyo')::date
  order by lp.effective_from desc
  limit 1
) p on true
group by 1, 2, 3;

comment on view public.llm_cost_daily is
  'OpenAI tokens and estimated cost per JST day, caller and model. The OpenAI dashboard stays the source of truth.';

-- ── llm_cache: processed markers and cached results for enrich steps ────────
create table if not exists public.llm_cache (
  step          text        not null,  -- e.g. poster_ocr, location_extract, cinemaclair_ocr, qa_classify
  subject_key   text        not null,  -- e.g. image sha256, event id, image URL, report id
  result        jsonb,
  outcome       text,                  -- e.g. applied, empty, low_confidence, error
  attempted_at  timestamptz not null default now(),
  primary key (step, subject_key)
);

comment on table public.llm_cache is
  'Markers and cached results so enrich steps do not resend the same input to the LLM.';

-- ── RLS and grants ──────────────────────────────────────────────────────────
alter table public.llm_usage   enable row level security;
alter table public.llm_pricing enable row level security;
alter table public.llm_cache   enable row level security;

drop policy if exists "Admins read llm_usage" on public.llm_usage;
create policy "Admins read llm_usage"
  on public.llm_usage for select
  using ((select public.is_admin()));

drop policy if exists "Admins read llm_pricing" on public.llm_pricing;
create policy "Admins read llm_pricing"
  on public.llm_pricing for select
  using ((select public.is_admin()));

-- llm_cache: service_role only (no policy = deny for anon/authenticated).

-- The scraper and web server write with the service role, which bypasses RLS
-- but needs table grants. Admins read through RLS. No anon access.
grant select, insert on public.llm_usage to service_role;
grant select on public.llm_usage to authenticated;
grant select, insert, update on public.llm_pricing to service_role;
grant select on public.llm_pricing to authenticated;
grant select on public.llm_cost_daily to authenticated, service_role;
grant select, insert, update, delete on public.llm_cache to service_role;

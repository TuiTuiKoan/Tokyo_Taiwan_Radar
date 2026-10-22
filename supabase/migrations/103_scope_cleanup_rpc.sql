-- ============================================================
-- 103: scope_cleanup_rpc
-- Transactional, service-role-only batch deactivation for the reviewed
-- non-Japan-scope events (japan-scope-gate Phase 6b; see
-- docs/specs/active/japan-scope-gate/plan.md).
--
--   public.apply_scope_cleanup(p_mode text, p_manifest jsonb) RETURNS jsonb
--
--   p_mode = 'validate'  read-only pre-check. Takes NO table lock, so it has
--                        no atomicity guarantee: use it for the approval
--                        package only. Returns {ok, problems, ...}.
--   p_mode = 'apply'     takes LOCK TABLE public.events IN SHARE ROW
--                        EXCLUSIVE MODE, repeats every check, then
--                        deactivates the whole set in ONE UPDATE. Any
--                        mismatch raises 40001 and writes nothing.
--
-- The lock blocks every INSERT/UPDATE/DELETE on events for the duration of
-- the call. A foreign-key check from another table (saved_events, ...) takes
-- only ROW SHARE, which does not conflict, so it proceeds unless it references
-- one of the target rows, which this call holds FOR UPDATE (tested on
-- PostgreSQL 17). lock_timeout is 5s: a busy table fails the call with zero
-- writes.
--
-- The database does not recompute manifest_digest (it cannot reproduce the
-- CLI's canonical JSON). The digest is an opaque audit string whose first 12
-- characters go into deactivated_reason; binding the digest to the user's
-- approval is the CLI's job. What the database verifies is that the live rows
-- equal the approved before-image field by field (updated_at included).
--
-- SECURITY INVOKER on purpose: service_role can already UPDATE events, so a
-- DEFINER function would only become a privilege escalation if its ACL drifted.
-- This migration only creates the function; it does not touch any RLS policy
-- or table grant.
--
-- APPLY STATUS: APPLIED in production 2026-10-23 through Supabase Dashboard ->
-- SQL Editor as postgres, after a rollback-only dry-run. Read-back:
-- prosecdef=false, owner postgres, proconfig search_path=pg_catalog and
-- lock_timeout=5s, ACL {postgres=X/postgres,service_role=X/postgres}. The
-- trailing DO block fails the transaction if the function is not exactly as
-- described above.
-- ============================================================

begin;

create or replace function public.apply_scope_cleanup(
  p_mode text,
  p_manifest jsonb
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog
set lock_timeout = '5s'
as $function$
declare
  c_top_keys constant text[] := array[
    'schema_version', 'manifest_digest', 'target_count', 'targets', 'external_children'
  ];
  c_target_keys constant text[] := array['id', 'category', 'before'];
  c_before_keys constant text[] := array[
    'source_name', 'raw_title', 'location_address', 'location_prefectures',
    'annotation_status', 'parent_event_id', 'is_active', 'deactivated_at',
    'deactivated_reason', 'deactivated_by_pass', 'updated_at', 'raw_description_sha256'
  ];
  v_digest text;
  v_digest12 text;
  v_count int;
  v_ids uuid[];
  v_problems jsonb := '[]'::jsonb;
  v_part jsonb;
  v_external_live jsonb;
  v_external_manifest jsonb;
  v_already int;
  v_active_before bigint;
  v_active_after bigint;
  v_rows bigint;
  v_now timestamptz;
  v_after jsonb;
begin
  if current_user not in ('service_role', 'postgres') then
    raise exception 'Forbidden' using errcode = '42501';
  end if;

  if p_mode is null or p_mode not in ('validate', 'apply') then
    raise exception 'p_mode must be validate or apply' using errcode = '22023';
  end if;

  -- ---- shape: strict, extra or missing keys are rejected -------------------
  if p_manifest is null or pg_catalog.jsonb_typeof(p_manifest) <> 'object'
     or exists (
       select 1 from pg_catalog.jsonb_object_keys(p_manifest) as k(key)
       where k.key <> all (c_top_keys)
     )
     or exists (
       select 1 from pg_catalog.unnest(c_top_keys) as k(key)
       where not (p_manifest ? k.key)
     ) then
    raise exception 'Invalid manifest keys' using errcode = '22023';
  end if;

  if p_manifest -> 'schema_version' is distinct from '2'::jsonb then
    raise exception 'Unsupported schema_version' using errcode = '22023';
  end if;

  v_digest := p_manifest ->> 'manifest_digest';
  if v_digest is null or v_digest !~ '^[0-9a-f]{64}$' then
    raise exception 'Invalid manifest_digest' using errcode = '22023';
  end if;
  v_digest12 := pg_catalog.substr(v_digest, 1, 12);

  if pg_catalog.jsonb_typeof(p_manifest -> 'targets') <> 'array'
     or pg_catalog.jsonb_typeof(p_manifest -> 'external_children') <> 'array'
     or pg_catalog.jsonb_typeof(p_manifest -> 'target_count') <> 'number' then
    raise exception 'Invalid manifest types' using errcode = '22023';
  end if;

  v_count := (p_manifest ->> 'target_count')::int;
  if v_count < 1 or v_count > 50
     or pg_catalog.jsonb_array_length(p_manifest -> 'targets') <> v_count then
    raise exception 'target_count mismatch or out of range' using errcode = '22023';
  end if;

  if exists (
       select 1
       from pg_catalog.jsonb_array_elements(p_manifest -> 'targets') as t(value)
       where pg_catalog.jsonb_typeof(t.value) <> 'object'
          or exists (
               select 1 from pg_catalog.jsonb_object_keys(t.value) as k(key)
               where k.key <> all (c_target_keys))
          or exists (
               select 1 from pg_catalog.unnest(c_target_keys) as k(key)
               where not (t.value ? k.key))
          or pg_catalog.jsonb_typeof(t.value -> 'before') <> 'object'
          or exists (
               select 1 from pg_catalog.jsonb_object_keys(t.value -> 'before') as k(key)
               where k.key <> all (c_before_keys))
          or exists (
               select 1 from pg_catalog.unnest(c_before_keys) as k(key)
               where not ((t.value -> 'before') ? k.key))
          or coalesce(t.value ->> 'category', '') !~ '^[A-Za-z0-9_]{1,64}$'
     )
     or exists (
       select 1
       from pg_catalog.jsonb_array_elements(p_manifest -> 'external_children') as e(value)
       where pg_catalog.jsonb_typeof(e.value) <> 'object'
          or exists (
               select 1 from pg_catalog.jsonb_object_keys(e.value) as k(key)
               where k.key <> all (array['id', 'parent_event_id']))
          or not (e.value ? 'id') or not (e.value ? 'parent_event_id')
     ) then
    raise exception 'Invalid manifest entries' using errcode = '22023';
  end if;

  -- uuid casts raise 22P02 on malformed ids, which also writes nothing.
  select pg_catalog.array_agg((t.value ->> 'id')::uuid order by (t.value ->> 'id')::uuid)
    into v_ids
    from pg_catalog.jsonb_array_elements(p_manifest -> 'targets') as t(value);

  if (select pg_catalog.count(distinct i) from pg_catalog.unnest(v_ids) as i) <> v_count then
    raise exception 'Duplicate target ids' using errcode = '22023';
  end if;

  -- ---- apply: serialize against every other writer of events ---------------
  if p_mode = 'apply' then
    lock table public.events in share row exclusive mode;

    perform 1
      from public.events as e
     where e.id = any (v_ids)
     order by e.id
       for update;

    -- Idempotent retry: every target already carries this manifest's marker.
    select pg_catalog.count(*)
      into v_already
      from public.events as e
     where e.id = any (v_ids)
       and e.is_active is false
       and e.deactivated_reason like '%scope cleanup ' || v_digest12;
    if v_already = v_count then
      return pg_catalog.jsonb_build_object(
        'status', 'noop',
        'applied_count', 0,
        'target_count', v_count,
        'manifest_digest', v_digest
      );
    end if;
  end if;

  -- ---- before-image: live rows must equal the approved rows ----------------
  select coalesce(pg_catalog.jsonb_agg(
           pg_catalog.jsonb_build_object(
             'id', m.id,
             'problem', case when e.id is null then 'missing' else 'drift' end,
             'fields', f.fields)
           order by m.id), '[]'::jsonb)
    into v_part
    from (
      select (t.value ->> 'id')::uuid as id, t.value -> 'before' as b
      from pg_catalog.jsonb_array_elements(p_manifest -> 'targets') as t(value)
    ) as m
    left join public.events as e on e.id = m.id
    cross join lateral (
      select coalesce(pg_catalog.jsonb_agg(c.k order by c.k) filter (where not c.same),
                      '[]'::jsonb) as fields
      from (values
        ('source_name', (m.b ->> 'source_name') is not distinct from e.source_name),
        ('raw_title', (m.b ->> 'raw_title') is not distinct from e.raw_title),
        ('location_address', (m.b ->> 'location_address') is not distinct from e.location_address),
        ('location_prefectures',
           coalesce(pg_catalog.to_jsonb(e.location_prefectures), 'null'::jsonb)
           = coalesce(m.b -> 'location_prefectures', 'null'::jsonb)),
        ('annotation_status', (m.b ->> 'annotation_status') is not distinct from e.annotation_status),
        ('parent_event_id', (m.b ->> 'parent_event_id')::uuid is not distinct from e.parent_event_id),
        ('is_active', (m.b ->> 'is_active')::boolean is not distinct from e.is_active),
        ('deactivated_at', (m.b ->> 'deactivated_at')::timestamptz is not distinct from e.deactivated_at),
        ('deactivated_reason', (m.b ->> 'deactivated_reason') is not distinct from e.deactivated_reason),
        ('deactivated_by_pass', (m.b ->> 'deactivated_by_pass') is not distinct from e.deactivated_by_pass),
        ('updated_at', (m.b ->> 'updated_at')::timestamptz is not distinct from e.updated_at),
        ('raw_description_sha256',
           (m.b ->> 'raw_description_sha256') is not distinct from
           case when e.raw_description is null then null
                else pg_catalog.encode(
                       pg_catalog.sha256(pg_catalog.convert_to(e.raw_description, 'UTF8')),
                       'hex') end)
      ) as c(k, same)
    ) as f
   where e.id is null or f.fields <> '[]'::jsonb;
  v_problems := v_problems || v_part;

  -- ---- closed family: parents inside the set, children listed or inactive --
  select coalesce(pg_catalog.jsonb_agg(
           pg_catalog.jsonb_build_object(
             'id', e.id, 'problem', 'parent_outside_set', 'parent_event_id', e.parent_event_id)
           order by e.id), '[]'::jsonb)
    into v_part
    from public.events as e
   where e.id = any (v_ids)
     and e.parent_event_id is not null
     and e.parent_event_id <> all (v_ids);
  v_problems := v_problems || v_part;

  select coalesce(pg_catalog.jsonb_agg(
           pg_catalog.jsonb_build_object('id', c.id, 'parent_event_id', c.parent_event_id)
           order by c.id), '[]'::jsonb)
    into v_external_live
    from public.events as c
   where c.parent_event_id = any (v_ids)
     and c.id <> all (v_ids);

  select coalesce(pg_catalog.jsonb_agg(
           pg_catalog.jsonb_build_object(
             'id', (x.value ->> 'id')::uuid,
             'parent_event_id', (x.value ->> 'parent_event_id')::uuid)
           order by (x.value ->> 'id')::uuid), '[]'::jsonb)
    into v_external_manifest
    from pg_catalog.jsonb_array_elements(p_manifest -> 'external_children') as x(value);

  if v_external_live is distinct from v_external_manifest then
    v_problems := v_problems || pg_catalog.jsonb_build_array(
      pg_catalog.jsonb_build_object(
        'problem', 'external_children_mismatch',
        'live', v_external_live,
        'manifest', v_external_manifest));
  end if;

  select coalesce(pg_catalog.jsonb_agg(
           pg_catalog.jsonb_build_object('id', c.id, 'problem', 'active_external_child')
           order by c.id), '[]'::jsonb)
    into v_part
    from public.events as c
   where c.parent_event_id = any (v_ids)
     and c.id <> all (v_ids)
     and c.is_active is true;
  v_problems := v_problems || v_part;

  if pg_catalog.jsonb_array_length(v_problems) > 0 then
    if p_mode = 'apply' then
      raise exception 'scope cleanup preconditions failed'
        using errcode = '40001', detail = v_problems::text;
    end if;
    return pg_catalog.jsonb_build_object(
      'status', 'invalid', 'ok', false, 'target_count', v_count, 'problems', v_problems);
  end if;

  if p_mode = 'validate' then
    return pg_catalog.jsonb_build_object(
      'status', 'valid', 'ok', true, 'target_count', v_count, 'problems', v_problems,
      'manifest_digest', v_digest);
  end if;

  -- ---- apply: one UPDATE, row count must equal the target count ------------
  select pg_catalog.count(*) into v_active_before
    from public.events as e where e.is_active is true;

  v_now := pg_catalog.clock_timestamp();

  update public.events as e
     set is_active = false,
         deactivated_at = v_now,
         deactivated_reason = 'out_of_scope: ' || m.category
           || ' - scope cleanup ' || v_digest12,
         deactivated_by_pass = 'admin_manual'
    from (
      select (t.value ->> 'id')::uuid as id, t.value ->> 'category' as category
      from pg_catalog.jsonb_array_elements(p_manifest -> 'targets') as t(value)
    ) as m
   where e.id = m.id
     and e.is_active is true;
  get diagnostics v_rows = row_count;

  if v_rows <> v_count then
    raise exception 'scope cleanup updated % rows, expected %', v_rows, v_count
      using errcode = '40001';
  end if;

  select pg_catalog.count(*) into v_active_after
    from public.events as e where e.is_active is true;

  if v_active_before - v_active_after <> v_count then
    raise exception 'active count changed by %, expected %',
      v_active_before - v_active_after, v_count using errcode = '40001';
  end if;

  select pg_catalog.jsonb_agg(
           pg_catalog.jsonb_build_object(
             'id', e.id,
             'is_active', e.is_active,
             'deactivated_at', e.deactivated_at,
             'deactivated_reason', e.deactivated_reason,
             'deactivated_by_pass', e.deactivated_by_pass,
             'updated_at', e.updated_at)
           order by e.id)
    into v_after
    from public.events as e
   where e.id = any (v_ids);

  return pg_catalog.jsonb_build_object(
    'status', 'applied',
    'applied_count', v_rows,
    'target_count', v_count,
    'manifest_digest', v_digest,
    'deactivated_at', v_now,
    'active_before', v_active_before,
    'active_after', v_active_after,
    'targets', v_after);
end;
$function$;

alter function public.apply_scope_cleanup(text, jsonb) owner to postgres;
revoke all on function public.apply_scope_cleanup(text, jsonb)
  from public, anon, authenticated;
grant execute on function public.apply_scope_cleanup(text, jsonb)
  to service_role;

comment on function public.apply_scope_cleanup(text, jsonb) is
  'Service-role-only batch deactivation of reviewed out-of-scope events. validate = unlocked pre-check; apply = SHARE ROW EXCLUSIVE lock, field-by-field before-image check, closed-family check, one UPDATE.';

do $$
declare
  fn regprocedure := 'public.apply_scope_cleanup(text, jsonb)'::regprocedure;
  v_secdef boolean;
  v_owner text;
  v_config text[];
begin
  select p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig
    into v_secdef, v_owner, v_config
    from pg_proc p where p.oid = fn;
  if v_secdef then
    raise exception '103_scope_cleanup_rpc: % must be SECURITY INVOKER', fn;
  end if;
  if v_owner <> 'postgres' then
    raise exception '103_scope_cleanup_rpc: % owner is %', fn, v_owner;
  end if;
  if not (v_config @> array['search_path=pg_catalog', 'lock_timeout=5s']) then
    raise exception '103_scope_cleanup_rpc: % proconfig is %', fn, v_config;
  end if;
  if has_function_privilege('anon', fn, 'EXECUTE')
     or has_function_privilege('authenticated', fn, 'EXECUTE')
     or has_function_privilege('public', fn, 'EXECUTE') then
    raise exception '103_scope_cleanup_rpc: % still executable by public/anon/authenticated', fn;
  end if;
  if not has_function_privilege('service_role', fn, 'EXECUTE') then
    raise exception '103_scope_cleanup_rpc: % lost service_role EXECUTE', fn;
  end if;
end;
$$;

commit;

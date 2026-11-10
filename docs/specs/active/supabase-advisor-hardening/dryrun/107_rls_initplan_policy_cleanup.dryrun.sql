-- DRY RUN of migration 107: identical to supabase/migrations/107_rls_initplan_policy_cleanup.sql except the last line is rollback;. Nothing is kept.
-- ============================================================
-- 107: rls_initplan_policy_cleanup
-- Lint cleanup from the 2026-11-10 Supabase performance advisor (tracked in
-- #627; spec: docs/specs/active/supabase-advisor-hardening/proposal.md).
--
--   * advisor 0003 (auth_rls_initplan): ALTER POLICY wraps auth.uid() in
--     (select auth.uid()) on 19 policies. 17 admin-type policies were already
--     InitPlans (an uncorrelated EXISTS), so the gain there is lint-only; the
--     per-row savings are on user_roles and account_usage.
--   * admin-only policies that were TO public become TO authenticated.
--   * advisor 0006: drops three redundant policies.
--   * advisor 0001: adds 7 foreign-key indexes.
--
-- Behaviour must not change: scraper/tests/test_advisor_hardening.py compares
-- visible rows and write outcomes for five identities on every table before
-- and after.
--
-- SAFETY:
--   * SET LOCAL lock_timeout = '5s'. ALTER/DROP POLICY take ACCESS EXCLUSIVE.
--     If a lock cannot be had in 5 s the whole transaction rolls back; rerun.
--   * The first DO block compares ALL policies of the 17 tables with the
--     verbatim production before-image and raises on any difference (same idea
--     as 103). It also accepts the after-image, so the migration is rerunnable.
--   * user_roles is altered last, to hold its lock for the shortest time.
--   * The trailing DO block verifies the policy set, that no bare auth.uid()
--     or auth.role() remains, and that all 7 foreign-key columns have a
--     leading-column index.
--
-- APPLY: Supabase Dashboard -> SQL Editor as postgres. The file contains its
-- own begin; ... commit;, so wrapping it in another BEGIN/ROLLBACK does NOT
-- make it a dry run. Use the dry-run copy in docs/specs/active/
-- supabase-advisor-hardening/dryrun/ (same text, trailing rollback;).
-- APPLY STATUS: NOT YET APPLIED.
-- ============================================================

begin;

set local lock_timeout = '5s';
-- Expected policy sets for the 17 tables. 'before' is the verbatim production
-- state captured on 2026-11-10 (notes.md, "逐字 policy"); 'after' is the target.
-- Whitespace is collapsed and `( SELECT auth.uid() AS uid)` is shown as @UID@
-- on both sides so the comparison does not depend on how a client wrapped lines.
create temp table _107_expected (
  which text, t text, p text, pm text, c text, r text, q text, w text
) on commit drop;

insert into _107_expected (which, t, p, pm, c, r, q, w) values
    ('before', $q$account_usage$q$, $q$Users read own account usage$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(auth.uid() = user_id)$q$, null::text),
    ('before', $q$aeo_visits$q$, $q$Admins read aeo_visits$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$aeo_visits$q$, $q$Anyone can insert aeo_visit$q$, $q$PERMISSIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$true$q$),
    ('before', $q$announcement_events$q$, $q$announcement_events_admin_all$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$),
    ('before', $q$announcement_events$q$, $q$announcement_events_public_read$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM announcements a
  WHERE ((a.id = announcement_events.announcement_id) AND (a.published_at IS NOT NULL) AND (a.published_at <= now()))))$q$, null::text),
    ('before', $q$announcements$q$, $q$announcements_admin_all$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$),
    ('before', $q$announcements$q$, $q$announcements_public_read$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$((published_at IS NOT NULL) AND (published_at <= now()))$q$, null::text),
    ('before', $q$app_settings$q$, $q$Admin full access on app_settings$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$),
    ('before', $q$app_settings$q$, $q$app_settings_lock_key_immutable$q$, $q$RESTRICTIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(key <> 'admin_reports_cleanup_maintenance'::text)$q$, $q$(key <> 'admin_reports_cleanup_maintenance'::text)$q$),
    ('before', $q$creator_events$q$, $q$Admins manage creator_events$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$event_reports$q$, $q$Admins can update reports$q$, $q$PERMISSIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$event_reports$q$, $q$Admins can view reports$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$event_reports$q$, $q$Anyone can submit reports$q$, $q$PERMISSIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$true$q$),
    ('before', $q$event_reports$q$, $q$event_reports_machine_tokens_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${anon,authenticated}$q$, null::text, $q$(NOT (EXISTS ( SELECT 1
   FROM unnest(event_reports.report_types) token(value)
  WHERE ((token.value = ANY (ARRAY['scopeReviewNonJapan'::text, 'auto_security_prompt_injection'::text])) OR (token.value ~~ 'scopeDecision:%'::text) OR (token.value ~~ 'scopeRegion:%'::text) OR (token.value ~~ 'scopeHash:%'::text) OR (token.value ~~ 'securityHash:%'::text) OR (token.value ~~ 'securitySeverity:%'::text)))))$q$),
    ('before', $q$event_reports$q$, $q$event_reports_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('before', $q$event_reports$q$, $q$event_reports_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('before', $q$event_reports$q$, $q$event_reports_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$),
    ('before', $q$event_views$q$, $q$Admins read event_views$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$event_views$q$, $q$Anyone can insert event_view$q$, $q$PERMISSIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$true$q$),
    ('before', $q$field_corrections$q$, $q$Admin full access on field_corrections$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$),
    ('before', $q$field_corrections$q$, $q$field_corrections_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('before', $q$field_corrections$q$, $q$field_corrections_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('before', $q$field_corrections$q$, $q$field_corrections_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$),
    ('before', $q$quota_snapshots$q$, $q$Admins can view quota_snapshots$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$research_reports$q$, $q$Admins can update research_reports$q$, $q$PERMISSIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$research_reports$q$, $q$Admins read research_reports$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$research_reports$q$, $q$Admins update research_reports$q$, $q$PERMISSIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$research_sources$q$, $q$Admins can read research_sources$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$research_sources$q$, $q$Admins can update research_sources$q$, $q$PERMISSIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$research_sources$q$, $q$Service role can write research_sources$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${public}$q$, $q$(auth.role() = 'service_role'::text)$q$, null::text),
    ('before', $q$scraper_runs$q$, $q$Admins read scraper_runs$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('before', $q$selection_reason_corrections$q$, $q$admin_full_src$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$),
    ('before', $q$selection_reason_corrections$q$, $q$selection_reason_corrections_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('before', $q$selection_reason_corrections$q$, $q$selection_reason_corrections_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('before', $q$selection_reason_corrections$q$, $q$selection_reason_corrections_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$),
    ('before', $q$source_exclusions$q$, $q$source_exclusions_admin_all$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$is_admin()$q$, $q$is_admin()$q$),
    ('before', $q$source_exclusions$q$, $q$source_exclusions_admin_select$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$is_admin()$q$, null::text),
    ('before', $q$user_roles$q$, $q$Users read own role$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(auth.uid() = user_id)$q$, null::text),
    ('before', $q$works$q$, $q$Admins can manage works$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = auth.uid()) AND (user_roles.role = 'admin'::text))))$q$),
    ('before', $q$works$q$, $q$Anyone can read works$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$true$q$, null::text),
    ('before', $q$works$q$, $q$works_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('before', $q$works$q$, $q$works_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('before', $q$works$q$, $q$works_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$account_usage$q$, $q$Users read own account usage$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(@UID@ = user_id)$q$, null::text),
    ('after', $q$aeo_visits$q$, $q$Admins read aeo_visits$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$aeo_visits$q$, $q$Anyone can insert aeo_visit$q$, $q$PERMISSIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$true$q$),
    ('after', $q$announcement_events$q$, $q$announcement_events_admin_all$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$),
    ('after', $q$announcement_events$q$, $q$announcement_events_public_read$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(EXISTS ( SELECT 1
   FROM announcements a
  WHERE ((a.id = announcement_events.announcement_id) AND (a.published_at IS NOT NULL) AND (a.published_at <= now()))))$q$, null::text),
    ('after', $q$announcements$q$, $q$announcements_admin_all$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$),
    ('after', $q$announcements$q$, $q$announcements_public_read$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$((published_at IS NOT NULL) AND (published_at <= now()))$q$, null::text),
    ('after', $q$app_settings$q$, $q$Admin full access on app_settings$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$),
    ('after', $q$app_settings$q$, $q$app_settings_lock_key_immutable$q$, $q$RESTRICTIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(key <> 'admin_reports_cleanup_maintenance'::text)$q$, $q$(key <> 'admin_reports_cleanup_maintenance'::text)$q$),
    ('after', $q$creator_events$q$, $q$Admins manage creator_events$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$event_reports$q$, $q$Admins can update reports$q$, $q$PERMISSIVE$q$, $q$UPDATE$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$event_reports$q$, $q$Admins can view reports$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$event_reports$q$, $q$Anyone can submit reports$q$, $q$PERMISSIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$true$q$),
    ('after', $q$event_reports$q$, $q$event_reports_machine_tokens_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${anon,authenticated}$q$, null::text, $q$(NOT (EXISTS ( SELECT 1
   FROM unnest(event_reports.report_types) token(value)
  WHERE ((token.value = ANY (ARRAY['scopeReviewNonJapan'::text, 'auto_security_prompt_injection'::text])) OR (token.value ~~ 'scopeDecision:%'::text) OR (token.value ~~ 'scopeRegion:%'::text) OR (token.value ~~ 'scopeHash:%'::text) OR (token.value ~~ 'securityHash:%'::text) OR (token.value ~~ 'securitySeverity:%'::text)))))$q$),
    ('after', $q$event_reports$q$, $q$event_reports_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('after', $q$event_reports$q$, $q$event_reports_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$event_reports$q$, $q$event_reports_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$event_views$q$, $q$Admins read event_views$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$event_views$q$, $q$Anyone can insert event_view$q$, $q$PERMISSIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$true$q$),
    ('after', $q$field_corrections$q$, $q$Admin full access on field_corrections$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$),
    ('after', $q$field_corrections$q$, $q$field_corrections_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('after', $q$field_corrections$q$, $q$field_corrections_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$field_corrections$q$, $q$field_corrections_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$quota_snapshots$q$, $q$Admins can view quota_snapshots$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$research_reports$q$, $q$Admins can update research_reports$q$, $q$PERMISSIVE$q$, $q$UPDATE$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$research_reports$q$, $q$Admins read research_reports$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$research_sources$q$, $q$Admins can read research_sources$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$research_sources$q$, $q$Admins can update research_sources$q$, $q$PERMISSIVE$q$, $q$UPDATE$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$scraper_runs$q$, $q$Admins read scraper_runs$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, null::text),
    ('after', $q$selection_reason_corrections$q$, $q$admin_full_src$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$),
    ('after', $q$selection_reason_corrections$q$, $q$selection_reason_corrections_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('after', $q$selection_reason_corrections$q$, $q$selection_reason_corrections_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$selection_reason_corrections$q$, $q$selection_reason_corrections_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$source_exclusions$q$, $q$source_exclusions_admin_all$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$is_admin()$q$, $q$is_admin()$q$),
    ('after', $q$user_roles$q$, $q$Users read own role$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$(@UID@ = user_id)$q$, null::text),
    ('after', $q$works$q$, $q$Admins can manage works$q$, $q$PERMISSIVE$q$, $q$ALL$q$, $q${authenticated}$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$, $q$(EXISTS ( SELECT 1
   FROM user_roles
  WHERE ((user_roles.user_id = @UID@) AND (user_roles.role = 'admin'::text))))$q$),
    ('after', $q$works$q$, $q$Anyone can read works$q$, $q$PERMISSIVE$q$, $q$SELECT$q$, $q${public}$q$, $q$true$q$, null::text),
    ('after', $q$works$q$, $q$works_maint_block_delete$q$, $q$RESTRICTIVE$q$, $q$DELETE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, null::text),
    ('after', $q$works$q$, $q$works_maint_block_insert$q$, $q$RESTRICTIVE$q$, $q$INSERT$q$, $q${public}$q$, null::text, $q$(NOT admin_reports_maintenance_active())$q$),
    ('after', $q$works$q$, $q$works_maint_block_update$q$, $q$RESTRICTIVE$q$, $q$UPDATE$q$, $q${public}$q$, $q$(NOT admin_reports_maintenance_active())$q$, $q$(NOT admin_reports_maintenance_active())$q$);

-- Before-image check (fail closed). Accepts the full before set (first run) or
-- the full after set (rerun after a successful apply); anything else means the
-- live policies drifted from what this migration was written against.
do $$
declare
  v_before boolean;
  v_after boolean;
begin
  create temp table _107_actual on commit drop as
    select policyname::text p, tablename::text t, permissive::text pm, cmd::text c, roles::text r,
           nullif(btrim(regexp_replace(regexp_replace(qual, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') q, nullif(btrim(regexp_replace(regexp_replace(with_check, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') w
      from pg_policies
     where schemaname = 'public'
       and tablename = any (array['account_usage', 'aeo_visits', 'announcement_events', 'announcements', 'app_settings', 'creator_events', 'event_reports', 'event_views', 'field_corrections', 'quota_snapshots', 'research_reports', 'research_sources', 'scraper_runs', 'selection_reason_corrections', 'source_exclusions', 'user_roles', 'works']);

  select not exists (select t, p, pm, c, r, q, w from _107_actual
                     except select t, p, pm, c, r, nullif(btrim(regexp_replace(regexp_replace(q, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), ''), nullif(btrim(regexp_replace(regexp_replace(w, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') from _107_expected where which = 'before')
     and not exists (select t, p, pm, c, r, nullif(btrim(regexp_replace(regexp_replace(q, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), ''), nullif(btrim(regexp_replace(regexp_replace(w, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') from _107_expected where which = 'before'
                     except select t, p, pm, c, r, q, w from _107_actual),
         not exists (select t, p, pm, c, r, q, w from _107_actual
                     except select t, p, pm, c, r, nullif(btrim(regexp_replace(regexp_replace(q, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), ''), nullif(btrim(regexp_replace(regexp_replace(w, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') from _107_expected where which = 'after')
     and not exists (select t, p, pm, c, r, nullif(btrim(regexp_replace(regexp_replace(q, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), ''), nullif(btrim(regexp_replace(regexp_replace(w, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') from _107_expected where which = 'after'
                     except select t, p, pm, c, r, q, w from _107_actual)
    into v_before, v_after;

  if not (v_before or v_after) then
    raise exception '107: live policies on the 17 tables match neither the expected before-image nor the after-image; nothing was changed. Compare pg_policies with notes.md.';
  end if;
end;
$$;

-- 1. Foreign-key indexes (advisor 0001). Ordinary CREATE INDEX: the tables are
--    small (largest: field_corrections, about 13k rows) and SQL Editor runs a
--    transaction, so CONCURRENTLY is not available.
create index if not exists announcements_author_id_idx on public.announcements (author_id);
create index if not exists app_settings_updated_by_idx on public.app_settings (updated_by);
create index if not exists category_corrections_corrected_by_idx on public.category_corrections (corrected_by);
create index if not exists field_corrections_corrected_by_idx on public.field_corrections (corrected_by);
create index if not exists field_corrections_audit_report_id_idx on public.field_corrections_audit (report_id);
create index if not exists selection_reason_corrections_corrected_by_idx on public.selection_reason_corrections (corrected_by);
create index if not exists source_exclusions_created_by_idx on public.source_exclusions (created_by);

-- 2. Redundant policies.
--    research_reports: duplicate of "Admins can update research_reports".
--    research_sources: service_role has BYPASSRLS, the policy never applies.
--    source_exclusions: covered by source_exclusions_admin_all (ALL).
drop policy if exists "Admins update research_reports" on public.research_reports;
drop policy if exists "Service role can write research_sources" on public.research_sources;
drop policy if exists "source_exclusions_admin_select" on public.source_exclusions;

-- 3. auth.uid() -> (select auth.uid()) (advisor 0003). ALTER POLICY cannot
--    change cmd or PERMISSIVE and keeps the name. Admin-only policies that were
--    TO public become TO authenticated (anon can never pass the admin check).
--    WITH CHECK is only rewritten where the policy already had one.
--    user_roles is last: every admin check reads it, so it is locked for the
--    shortest time.
alter policy "Users read own account usage" on public.account_usage
  using ((select auth.uid()) = user_id);

alter policy "Admins can view reports" on public.event_reports
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins can update reports" on public.event_reports
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins read scraper_runs" on public.scraper_runs
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins read research_reports" on public.research_reports
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins can update research_reports" on public.research_reports
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins can read research_sources" on public.research_sources
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins can update research_sources" on public.research_sources
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins read event_views" on public.event_views
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins manage creator_events" on public.creator_events
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins read aeo_visits" on public.aeo_visits
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "announcements_admin_all" on public.announcements
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ))
  with check (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "announcement_events_admin_all" on public.announcement_events
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ))
  with check (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admin full access on field_corrections" on public.field_corrections
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ))
  with check (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "admin_full_src" on public.selection_reason_corrections
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ))
  with check (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins can view quota_snapshots" on public.quota_snapshots
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admins can manage works" on public.works
  to authenticated
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ))
  with check (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Admin full access on app_settings" on public.app_settings
  using (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ))
  with check (exists (
    select 1 from public.user_roles
    where user_roles.user_id = (select auth.uid())
      and user_roles.role = 'admin'
  ));

alter policy "Users read own role" on public.user_roles
  using ((select auth.uid()) = user_id);

-- Post-check.
do $$
declare
  rec record;
  v_count int;
begin
  -- exact policy set
  drop table _107_actual;
  create temp table _107_actual on commit drop as
    select policyname::text p, tablename::text t, permissive::text pm, cmd::text c, roles::text r,
           nullif(btrim(regexp_replace(regexp_replace(qual, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') q, nullif(btrim(regexp_replace(regexp_replace(with_check, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') w
      from pg_policies
     where schemaname = 'public'
       and tablename = any (array['account_usage', 'aeo_visits', 'announcement_events', 'announcements', 'app_settings', 'creator_events', 'event_reports', 'event_views', 'field_corrections', 'quota_snapshots', 'research_reports', 'research_sources', 'scraper_runs', 'selection_reason_corrections', 'source_exclusions', 'user_roles', 'works']);

  if exists (select t, p, pm, c, r, q, w from _107_actual
             except select t, p, pm, c, r, nullif(btrim(regexp_replace(regexp_replace(q, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), ''), nullif(btrim(regexp_replace(regexp_replace(w, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') from _107_expected where which = 'after')
     or exists (select t, p, pm, c, r, nullif(btrim(regexp_replace(regexp_replace(q, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), ''), nullif(btrim(regexp_replace(regexp_replace(w, '\(\s*SELECT\s+auth\.uid\(\)\s+AS\s+uid\s*\)', '@UID@', 'gi'), '\s+', ' ', 'g')), '') from _107_expected where which = 'after'
                except select t, p, pm, c, r, q, w from _107_actual) then
    raise exception '107: policies after the change differ from the expected after-image';
  end if;

  -- no bare auth.uid() / auth.role() left
  select count(*) into v_count from _107_actual
   where coalesce(q, '') ~ 'auth\.(uid|role)\(\)' or coalesce(w, '') ~ 'auth\.(uid|role)\(\)';
  if v_count <> 0 then
    raise exception '107: % policies still call auth.uid()/auth.role() unwrapped', v_count;
  end if;

  -- every foreign key column in scope has an index that leads with it
  for rec in
    select * from (values
      ('announcements', 'author_id'),
      ('app_settings', 'updated_by'),
      ('category_corrections', 'corrected_by'),
      ('field_corrections', 'corrected_by'),
      ('field_corrections_audit', 'report_id'),
      ('selection_reason_corrections', 'corrected_by'),
      ('source_exclusions', 'created_by')
    ) f(tbl, col)
  loop
    if not exists (
      select 1
        from pg_index i
        join pg_attribute a on a.attrelid = i.indrelid and a.attnum = i.indkey[0]
       where i.indrelid = ('public.' || rec.tbl)::regclass
         and a.attname = rec.col
         and i.indisvalid
         and i.indpred is null
    ) then
      raise exception '107: no index leading with %.%', rec.tbl, rec.col;
    end if;
  end loop;
end;
$$;

rollback;

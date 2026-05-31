-- Migration 084: Fix Security Definer vulnerabilities on views
-- Ensure views strictly respect the invoker's row-level security (RLS) policies
-- and prevent unprivileged authenticated users from bypassing exclusions.

ALTER VIEW public.source_exclusions_effective SET (security_invoker = true);
ALTER VIEW public.event_media_coverage SET (security_invoker = true);

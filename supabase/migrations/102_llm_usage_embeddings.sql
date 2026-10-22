-- 102_llm_usage_embeddings.sql
-- Let llm_usage record embeddings calls (llm-cost-reset spec, #363).
-- Applied to production as 101_llm_usage_embeddings (record 20261022165956);
-- renumbered 102 because 101_rpc_lockdown_followup.sql took 101 on main.
--
-- 099 allowed endpoint in ('chat', 'responses'). eval_annotator.py scores the
-- annotator golden set by meaning with text-embedding-3-small, so the shared
-- client (scraper/llm_client.py) now records those calls as endpoint
-- 'embeddings'. The Historical Backtest on PR #391 first surfaced the gap: the
-- shared client had no embeddings surface at all.
--
-- Apply BEFORE merging the PR that records 'embeddings' rows. A row outside the
-- CHECK fails the whole batched insert, so those batches would not be recorded.
--
-- Also prices the embedding model so llm_cost_daily can cost it
-- (unpriced_calls would otherwise count it). Embeddings bill input tokens only,
-- and have no cache discount, so cached_input_per_mtok repeats the input price.
-- Price: OpenAI model page for text-embedding-3-small, $0.02 per 1M tokens,
-- checked 2026-10-23.
-- Run in Supabase Dashboard → SQL Editor. Idempotent.

alter table public.llm_usage drop constraint if exists llm_usage_endpoint_check;
alter table public.llm_usage
  add constraint llm_usage_endpoint_check
  check (endpoint in ('chat', 'responses', 'embeddings'));

insert into public.llm_pricing
  (model, effective_from, input_per_mtok, cached_input_per_mtok, output_per_mtok, per_web_search_call, notes)
values
  ('text-embedding-3-small', date '2026-01-01', 0.02, 0.02, 0, 0, 'OpenAI model page, checked 2026-10-23')
on conflict (model, effective_from) do nothing;

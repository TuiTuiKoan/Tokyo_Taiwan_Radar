"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

export interface SourceExclusionRow {
  id: string;
  source_name: string;
  pattern: string;
  pattern_type: "substring" | "regex";
  match_field: "raw_title" | "raw_description" | "raw_title_or_description";
  reason: string | null;
  is_active: boolean;
  created_at: string;
  last_matched_at: string | null;
  match_count: number;
  hits_30d: number;
  sample_title: string | null;
  expires_at: string | null;
  auto_disabled_at: string | null;
  auto_disabled_reason: string | null;
}

type AdminAuth =
  | { ok: true; supabase: Awaited<ReturnType<typeof createClient>>; userId: string }
  | { ok: false; error: string };

async function requireAdmin(): Promise<AdminAuth> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "unauthenticated" };
  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin") {
    return { ok: false, error: "forbidden" };
  }
  return { ok: true, supabase, userId: user.id };
}

export async function listExclusions(): Promise<{
  ok: boolean;
  rows?: SourceExclusionRow[];
  error?: string;
}> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  try {
    const { data: rules, error } = await auth.supabase
      .from("source_exclusions")
      .select("*")
      .order("created_at", { ascending: false });
    if (error) return { ok: false, error: error.message };
    if (!rules || rules.length === 0) return { ok: true, rows: [] };

    const cutoff = new Date(Date.now() - 30 * 86400_000).toISOString();
    const ruleIds = rules.map((r) => r.id);
    const { data: hits } = await auth.supabase
      .from("source_exclusion_hits")
      .select("rule_id, raw_title, matched_at")
      .in("rule_id", ruleIds)
      .gte("matched_at", cutoff)
      .order("matched_at", { ascending: false });

    const hitMap: Record<string, { count: number; sample: string | null }> = {};
    for (const h of hits ?? []) {
      const m = hitMap[h.rule_id] ?? { count: 0, sample: null };
      m.count += 1;
      if (m.sample === null) m.sample = h.raw_title;
      hitMap[h.rule_id] = m;
    }

    const rows: SourceExclusionRow[] = rules.map((r) => ({
      ...r,
      hits_30d: hitMap[r.id]?.count ?? 0,
      sample_title: hitMap[r.id]?.sample ?? null,
    }));
    return { ok: true, rows };
  } catch {
    return { ok: true, rows: [] };
  }
}

export async function createExclusion(input: {
  source_name: string;
  pattern: string;
  pattern_type?: "substring" | "regex";
  match_field?: "raw_title" | "raw_description" | "raw_title_or_description";
  reason?: string;
  expires_at?: string | null;
}): Promise<{ ok: boolean; id?: string; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };

  const sourceName = input.source_name?.trim();
  const pattern = input.pattern?.trim();
  if (!sourceName) return { ok: false, error: "source_name required" };
  if (!pattern || pattern.length < 3) {
    return { ok: false, error: "pattern must be at least 3 characters" };
  }
  const patternType = input.pattern_type ?? "substring";
  const matchField = input.match_field ?? "raw_title";

  if (patternType === "regex") {
    try {
      new RegExp(pattern);
    } catch {
      return { ok: false, error: "invalid regex pattern" };
    }
  }

  const insertRow: Record<string, unknown> = {
    source_name: sourceName,
    pattern,
    pattern_type: patternType,
    match_field: matchField,
    reason: input.reason?.trim() || null,
    created_by: auth.userId,
  };
  if (input.expires_at) insertRow.expires_at = input.expires_at;

  const { data, error } = await auth.supabase
    .from("source_exclusions")
    .insert(insertRow)
    .select("id")
    .single();

  if (error) return { ok: false, error: error.message };
  revalidatePath("/[locale]/admin/exclusions", "page");
  return { ok: true, id: data?.id };
}

export async function toggleExclusion(input: {
  id: string;
  is_active: boolean;
}): Promise<{ ok: boolean; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const { error } = await auth.supabase
    .from("source_exclusions")
    .update({ is_active: input.is_active })
    .eq("id", input.id);
  if (error) return { ok: false, error: error.message };
  revalidatePath("/[locale]/admin/exclusions", "page");
  return { ok: true };
}

export async function deleteExclusion(input: {
  id: string;
}): Promise<{ ok: boolean; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const { error } = await auth.supabase
    .from("source_exclusions")
    .delete()
    .eq("id", input.id);
  if (error) return { ok: false, error: error.message };
  revalidatePath("/[locale]/admin/exclusions", "page");
  return { ok: true };
}

export async function reEnableExclusion(input: {
  id: string;
}): Promise<{ ok: boolean; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const { error } = await auth.supabase
    .from("source_exclusions")
    .update({ auto_disabled_at: null, auto_disabled_reason: null, is_active: true })
    .eq("id", input.id);
  if (error) return { ok: false, error: error.message };
  revalidatePath("/[locale]/admin/exclusions", "page");
  return { ok: true };
}

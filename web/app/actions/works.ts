"use server";

import { createClient } from "@/lib/supabase/server";
import { revalidatePath } from "next/cache";

type WorkInput = {
  work_type: string;
  original_title: string;
  title_ja?: string | null;
  title_zh?: string | null;
  title_en?: string | null;
  director?: string | null;
  cast_summary?: string | null;
  release_year?: number | null;
  country?: string | null;
  description?: string | null;
  poster_url?: string | null;
  external_links?: Record<string, string> | null;
};

const VALID_TYPES = ["film", "stage", "exhibition", "concert_tour", "other"];

async function requireAdmin() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false as const, error: "unauthenticated" };
  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin") {
    return { ok: false as const, error: "forbidden" };
  }
  return { ok: true as const, supabase };
}

function sanitize(input: WorkInput): Partial<WorkInput> {
  const trim = (s?: string | null) => (s == null ? null : s.trim() || null);
  if (!VALID_TYPES.includes(input.work_type)) {
    throw new Error(`invalid work_type: ${input.work_type}`);
  }
  const original = (input.original_title ?? "").trim();
  if (!original) throw new Error("original_title is required");
  return {
    work_type: input.work_type,
    original_title: original,
    title_ja: trim(input.title_ja),
    title_zh: trim(input.title_zh),
    title_en: trim(input.title_en),
    director: trim(input.director),
    cast_summary: trim(input.cast_summary),
    release_year: input.release_year ?? null,
    country: trim(input.country) ?? "TW",
    description: trim(input.description),
    poster_url: trim(input.poster_url),
    external_links: input.external_links ?? null,
  };
}

export async function createWork(input: WorkInput): Promise<{ ok: boolean; id?: string; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  try {
    const row = sanitize(input);
    const { data, error } = await auth.supabase
      .from("works")
      .insert(row)
      .select("id")
      .single();
    if (error) return { ok: false, error: error.message };
    revalidatePath("/[locale]/admin/works", "page");
    return { ok: true, id: data?.id };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

export async function updateWork(id: string, input: WorkInput): Promise<{ ok: boolean; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  try {
    const row = sanitize(input);
    const { error } = await auth.supabase
      .from("works")
      .update(row)
      .eq("id", id);
    if (error) return { ok: false, error: error.message };
    revalidatePath("/[locale]/admin/works", "page");
    revalidatePath(`/[locale]/admin/works/${id}`, "page");
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

export async function deleteWork(id: string): Promise<{ ok: boolean; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const { error } = await auth.supabase
    .from("works")
    .delete()
    .eq("id", id);
  if (error) return { ok: false, error: error.message };
  revalidatePath("/[locale]/admin/works", "page");
  return { ok: true };
}

export async function assignWorkToEvent(eventId: string, workId: string | null): Promise<{ ok: boolean; error?: string }> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const { error } = await auth.supabase
    .from("events")
    .update({ work_id: workId })
    .eq("id", eventId);
  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

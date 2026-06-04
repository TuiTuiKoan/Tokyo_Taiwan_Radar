"use server";

import { requireAdmin } from "./_shared/admin-guard";
import { createClient } from "@/lib/supabase/server";
import type { Event } from "@/lib/types";
import type { FormState } from "@/components/AdminEventForm";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

type ServerSupabase = Awaited<ReturnType<typeof createClient>>;

function genSourceId(): string {
  return `manual-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

type EventInsert = Record<string, unknown>;

function sanitizeForm(form: FormState): EventInsert {
  const f = form as unknown as Record<string, unknown>;
  const empty = (v: unknown) => (typeof v === "string" && v.trim() === "" ? null : v);
  return {
    ...form,
    start_date: empty(f.start_date),
    end_date: empty(f.end_date),
    parent_event_id: empty(f.parent_event_id),
    co_organizers: f.co_organizers ?? null,
    sponsors: f.sponsors ?? null,
  };
}

async function insertWithRetry(
  supabase: ServerSupabase,
  payload: EventInsert,
): Promise<ActionResult<Event>> {
  // events table has composite UNIQUE(source_name, source_id) (migration 001).
  // Manual inserts share source_name='manual', so collisions require same source_id.
  // Random 6-char suffix + ms timestamp makes collision near-impossible; retry once on 23505 just in case.
  for (let attempt = 0; attempt < 2; attempt++) {
    const row = { ...payload, source_id: genSourceId() };
    const { data, error } = await supabase
      .from("events")
      .insert(row)
      .select()
      .single();
    if (!error && data) return { ok: true, data: data as Event };
    if (error && error.code === "23505" && attempt === 0) continue;
    return { ok: false, error: error?.message ?? "insert_failed" };
  }
  return { ok: false, error: "source_id_conflict, retry" };
}

export async function createDraftEvent(form: FormState): Promise<ActionResult<Event>> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const payload: EventInsert = {
    ...sanitizeForm(form),
    is_active: false,
    annotation_status: "pending",
  };
  return insertWithRetry(auth.supabase, payload);
}

export async function createEventNoAnnotate(form: FormState): Promise<ActionResult<Event>> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return insertWithRetry(auth.supabase, sanitizeForm(form));
}

export async function updateAdminEvent(
  eventId: string,
  form: FormState,
  options?: { isActive?: boolean },
): Promise<ActionResult<Event>> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };

  const { data: existing, error: loadError } = await auth.supabase
    .from("events")
    .select("id")
    .eq("id", eventId)
    .single();

  if (loadError || !existing) return { ok: false, error: "eventNotFound" };

  const payload = sanitizeForm(form);
  delete payload.source_id;
  delete payload.source_name;

  if (typeof options?.isActive === "boolean") {
    payload.is_active = options.isActive;
  }

  const { data: updated, error: updateError } = await auth.supabase
    .from("events")
    .update(payload)
    .eq("id", eventId)
    .select()
    .single();

  if (updateError) return { ok: false, error: updateError.message };
  return { ok: true, data: updated as Event };
}

export async function publishEvent(eventId: string): Promise<ActionResult<null>> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const { data, error } = await auth.supabase
    .from("events")
    .update({ is_active: true, annotation_status: "reviewed" })
    .eq("id", eventId)
    .select("id");
  if (error) return { ok: false, error: error.message };
  if (!data || data.length === 0) return { ok: false, error: "publish_no_rows" };
  return { ok: true, data: null };
}

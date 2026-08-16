"use server";

import { requireAdmin } from "./_shared/admin-guard";
import { createClient } from "@/lib/supabase/server";
import { assertWritesAllowed } from "@/lib/maintenanceLock.server";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { Event } from "@/lib/types";
import type { FormState } from "@/components/AdminEventForm";
import { collectMissingRequiredFields } from "@/lib/eventIntakeValidation";
import { persistTranslationLocks } from "@/lib/fieldCorrections.server";
import {
  runChangeAdminEventCategories,
  runDeleteAdminEventExact,
  runReannotateAdminEvent,
  runSaveAdminEditedEvent,
  runSetAdminEventsActive,
  runSetAdminEventsForceRescrape,
  type EventCategoryResult,
} from "@/lib/adminEventMutationsCore";
import { alignParallelOrganizerTypes } from "@/lib/parallelOrganizerTypes";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

type ServerSupabase = Awaited<ReturnType<typeof createClient>>;

function genSourceId(): string {
  return `manual-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

type EventInsert = Record<string, unknown>;

type OrganizerArraySnapshot = Pick<
  Event,
  "co_organizers" | "co_organizer_types" | "sponsors" | "sponsor_types"
>;

function sanitizeForm(form: FormState, existing?: OrganizerArraySnapshot): EventInsert {
  const f = form as unknown as Record<string, unknown>;
  const empty = (v: unknown) => (typeof v === "string" && v.trim() === "" ? null : v);
  const coOrganizers = alignParallelOrganizerTypes(
    f.co_organizers,
    existing?.co_organizers,
    existing?.co_organizer_types,
  );
  const sponsors = alignParallelOrganizerTypes(
    f.sponsors,
    existing?.sponsors,
    existing?.sponsor_types,
  );
  return {
    ...form,
    start_date: empty(f.start_date),
    end_date: empty(f.end_date),
    parent_event_id: empty(f.parent_event_id),
    co_organizers: coOrganizers.names,
    co_organizer_types: coOrganizers.types,
    sponsors: sponsors.names,
    sponsor_types: sponsors.types,
    official_url: empty(f.official_url),
    submission_url: empty(f.submission_url),
    // provenance: explicit source_url wins, else fall back to the announcement URL, else the site URL
    source_url: empty(f.source_url) ?? empty(f.official_url) ?? SITE_URL,
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
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
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
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return insertWithRetry(auth.supabase, sanitizeForm(form));
}

// Admin-only lazy fetch for the parent-event dropdown on the create wizard.
// The create page no longer eager-loads the full events table; the wizard calls
// this the first time an admin opens the parent-event select. Must go through
// requireAdmin() — never a browser-side Supabase read.
export async function fetchParentEventCandidates(): Promise<ActionResult<Event[]>> {
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const { data, error } = await auth.supabase
    .from("events")
    .select("id, name_ja, name_zh, name_en, start_date")
    .order("created_at", { ascending: false });
  if (error) return { ok: false, error: error.message };
  return { ok: true, data: (data ?? []) as Event[] };
}

export async function saveAdminEditedEvent(
  eventId: unknown,
  form: unknown,
): Promise<ActionResult<Event>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return runSaveAdminEditedEvent(auth.supabase, eventId, form, auth.user.id);
}

export async function setAdminEventActive(
  eventId: unknown,
  targetActive: unknown,
): Promise<ActionResult<{ ids: string[] }>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return runSetAdminEventsActive(auth.supabase, [eventId], targetActive, "single");
}

export async function setAdminEventsActive(
  eventIds: unknown,
  targetActive: unknown,
): Promise<ActionResult<{ ids: string[] }>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return runSetAdminEventsActive(auth.supabase, eventIds, targetActive, "bulk");
}

export async function setAdminEventForceRescrape(
  eventId: unknown,
  forceRescrape: unknown,
): Promise<ActionResult<{ ids: string[] }>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return runSetAdminEventsForceRescrape(
    auth.supabase,
    [eventId],
    forceRescrape,
    "single",
  );
}

export async function setAdminEventsForceRescrape(
  eventIds: unknown,
  forceRescrape: unknown,
): Promise<ActionResult<{ ids: string[] }>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return runSetAdminEventsForceRescrape(
    auth.supabase,
    eventIds,
    forceRescrape,
    "bulk",
  );
}

export async function reannotateAdminEvent(
  eventId: unknown,
): Promise<ActionResult<{ ids: string[] }>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return runReannotateAdminEvent(auth.supabase, eventId);
}

export async function changeAdminEventCategories(
  eventIds: unknown,
  operation: unknown,
  categories: unknown,
): Promise<ActionResult<{ events: EventCategoryResult[] }>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  return runChangeAdminEventCategories(
    auth.supabase,
    eventIds,
    operation,
    categories,
    auth.user.id,
  );
}

export async function updateAdminEvent(
  eventId: string,
  form: FormState,
  options?: { isActive?: boolean },
): Promise<ActionResult<Event>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };

  const { data: existing, error: loadError } = await auth.supabase
    .from("events")
    .select("id,co_organizers,co_organizer_types,sponsors,sponsor_types")
    .eq("id", eventId)
    .single();

  if (loadError || !existing) return { ok: false, error: "eventNotFound" };

  const payload = sanitizeForm(form, existing as OrganizerArraySnapshot);
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
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
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

/**
 * Publish an event created through the unified intake wizard (admin context).
 * Enforces the same required-field gate as the owner publish flow and locks
 * admin-confirmed translations into field_corrections (FC-first) before the
 * row is flipped to active/reviewed.
 */
export async function publishAdminWizardEvent(
  eventId: string,
  form: FormState,
  options?: { lockedTranslationFields?: string[]; paidChoiceMade?: boolean; requireBusinessHours?: boolean },
): Promise<ActionResult<Event>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };

  const {
    data: { user },
  } = await auth.supabase.auth.getUser();
  if (!user) return { ok: false, error: "unauthorized" };

  const { data: existing, error: loadError } = await auth.supabase
    .from("events")
    .select("id,co_organizers,co_organizer_types,sponsors,sponsor_types")
    .eq("id", eventId)
    .single();
  if (loadError || !existing) return { ok: false, error: "eventNotFound" };

  const primaryLang =
    typeof form.primary_language === "string" ? form.primary_language : "";
  const missing = collectMissingRequiredFields(form, {
    requirePrimaryContent: true,
    primaryLang,
    paidChoiceMade: options?.paidChoiceMade === true,
    requireBusinessHours: options?.requireBusinessHours === true,
  });
  if (missing.length > 0) return { ok: false, error: "requiredFieldsMissing" };

  const payload = sanitizeForm(form, existing as OrganizerArraySnapshot);
  delete payload.source_id;
  delete payload.source_name;

  const lockResult = await persistTranslationLocks({
    client: auth.supabase as unknown as SupabaseClient,
    eventId,
    userId: user.id,
    form: form as unknown as Record<string, unknown>,
    lockedTranslationFields: options?.lockedTranslationFields ?? [],
  });
  if (!lockResult.ok) return { ok: false, error: lockResult.error };

  const { data: updated, error: updateError } = await auth.supabase
    .from("events")
    .update({ ...payload, is_active: true, annotation_status: "reviewed" })
    .eq("id", eventId)
    .select()
    .single();

  if (updateError) return { ok: false, error: updateError.message };
  return { ok: true, data: updated as Event };
}

export async function deleteUserSubmittedEvent(eventId: string): Promise<ActionResult<null>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };

  const { data: existing, error: loadError } = await auth.supabase
    .from("events")
    .select("id,is_user_submitted")
    .eq("id", eventId)
    .single();

  if (loadError || !existing) return { ok: false, error: "eventNotFound" };
  if (!existing.is_user_submitted) return { ok: false, error: "not_user_submitted" };

  const { data, error } = await auth.supabase
    .from("events")
    .update({
      is_active: false,
      closed_by_owner: true,
      deactivated_at: new Date().toISOString(),
      deactivated_reason: "deleted_by_admin",
      deactivated_by_pass: "admin_manual",
    })
    .eq("id", eventId)
    .select("id");

  if (error) return { ok: false, error: error.message };
  if (!data || data.length === 0) return { ok: false, error: "delete_no_rows" };
  return { ok: true, data: null };
}

export async function deleteAdminEvent(eventId: string): Promise<ActionResult<null>> {
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const auth = await requireAdmin();
  if (!auth.ok) return { ok: false, error: auth.error };
  const result = await runDeleteAdminEventExact(auth.supabase, eventId);
  if (!result.ok) return result;
  return { ok: true, data: null };
}

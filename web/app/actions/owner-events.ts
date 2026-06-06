"use server";

import { createClient } from "@/lib/supabase/server";
import { createClient as createServiceClient } from "@supabase/supabase-js";
import { revalidatePath } from "next/cache";
import type { Event } from "@/lib/types";
import type { FormState } from "@/components/AdminEventForm";

export type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

function genSourceId(): string {
  return `ugc-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// Allowed white-listed content fields for user sumbission (preventing manipulation)
const CONTENT_WHITE_LIST = [
  "name_ja",
  "name_zh",
  "name_en",
  "description_ja",
  "description_zh",
  "description_en",
  "start_date",
  "end_date",
  "location_name",
  "location_name_zh",
  "location_name_en",
  "location_address",
  "location_address_zh",
  "location_address_en",
  "location_url",
  "business_hours",
  "business_hours_zh",
  "business_hours_en",
  "performer",
  "organizer",
  "organizer_url",
  "organizer_type",
  "co_organizers",
  "sponsors",
  "primary_language",
  "has_japanese_support",
  "has_english_support",
  "has_chinese_support",
  "price_amount",
  "price_currency",
  "price_info",
  "source_url",
  "event_form",
  "category",
] as const;

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app";
const OWNER_SUBMISSION_SOURCE_FALLBACK = `${SITE_URL}/ja/account`;
const VALID_PRIMARY_LANGUAGES = new Set(["ja", "zh", "en", "mixed"]);

function sanitizeOwnerForm(form: FormState, ownerUserId: string): Record<string, any> {
  const payload: Record<string, any> = {};
  
  // Extract only white-listed content fields
  for (const field of CONTENT_WHITE_LIST) {
    if (field in form) {
      const val = (form as any)[field];
      if (typeof val === "string") {
        const trimmed = val.trim();
        payload[field] = trimmed === "" ? null : trimmed;
      } else {
        payload[field] = val;
      }
    }
  }

  // Force overrides - OWASP A01 Guard
  payload.source_name = "user_submission";
  payload.owner_user_id = ownerUserId;
  payload.is_user_submitted = true;
  payload.is_active = true; // Auto-publish for UGC
  payload.annotation_status = "annotated"; // Skip scraper processing but mark as annotated

  payload.source_url = payload.source_url || payload.organizer_url || payload.location_url || null;
  if (
    typeof payload.primary_language === "string" &&
    payload.primary_language &&
    !VALID_PRIMARY_LANGUAGES.has(payload.primary_language)
  ) {
    payload.primary_language = null;
  }
  
  return payload;
}

// Post-Oct 30, use service role client to ensure write permissions to public.events
function getServiceRoleClient() {
  return createServiceClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
}

// ⚠️ Sync with auto_qa and field_corrections requirements
async function recordFieldCorrections(
  eventId: string,
  userId: string,
  oldEvent: Event,
  newForm: FormState
) {
  const fieldsToCheck = ["organizer", "co_organizers", "organizer_type"] as const;
  const serviceClient = getServiceRoleClient();

  for (const field of fieldsToCheck) {
    const newVal = (newForm as any)[field];
    const oldVal = (oldEvent as any)[field];

    // Simple robust comparison for strings and arrays
    const normalizedNew = Array.isArray(newVal)
      ? JSON.stringify([...newVal].sort())
      : newVal;
    const normalizedOld = Array.isArray(oldVal)
      ? JSON.stringify([...oldVal].sort())
      : oldVal;

    if (normalizedNew !== normalizedOld) {
      await serviceClient.from("field_corrections").upsert({
        event_id: eventId,
        field_name: field,
        original_value: oldVal === null ? null : (Array.isArray(oldVal) ? oldVal : String(oldVal)),
        corrected_value: newVal === null ? null : (Array.isArray(newVal) ? newVal : String(newVal)),
        corrected_by: `user-${userId}`,
      }, { onConflict: "event_id,field_name" });
    }
  }
}

export async function createOwnerEvent(form: FormState): Promise<ActionResult<Event>> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { ok: false, error: "unauthorized" };

  const serviceClient = getServiceRoleClient();

  // 1. Check if user has registered a creator profile
  const { data: creatorProfile } = await serviceClient
    .from("creators")
    .select("user_handle")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!creatorProfile || !creatorProfile.user_handle) {
    return { ok: false, error: "profileRequired" };
  }

  // 2. Check if banned
  const { data: roleRow } = await serviceClient
    .from("user_roles")
    .select("publish_banned_until")
    .eq("user_id", user.id)
    .maybeSingle();

  if (roleRow?.publish_banned_until) {
    const banDate = new Date(roleRow.publish_banned_until);
    if (banDate > new Date()) {
      return { ok: false, error: `publishBanned|${banDate.toISOString()}` };
    }
  }

  // 3. UGC Required Fields Gate (Server-side validation)
  const startDate = form.start_date?.trim();
  const endDate = form.end_date?.trim();
  const locationName = form.location_name?.trim();
  const locationAddress = form.location_address?.trim();
  const categories = form.category;
  const eventForms = form.event_form;

  if (!startDate || !endDate || !locationName || !locationAddress) {
    return { ok: false, error: "requiredFieldsMissing" };
  }
  if (!Array.isArray(categories) || categories.length < 1) {
    return { ok: false, error: "requiredFieldsMissing" };
  }
  if (!Array.isArray(eventForms) || eventForms.length < 1) {
    return { ok: false, error: "requiredFieldsMissing" };
  }

  // Double check that we have name_ja populated. If missing, copy from zh/en as fallback
  let nameJa = form.name_ja?.trim();
  if (!nameJa) {
    const otherVal = form.name_zh?.trim() || form.name_en?.trim();
    if (otherVal) {
      nameJa = otherVal;
      form.name_ja = otherVal;
    } else {
      return { ok: false, error: "requiredFieldsMissing" };
    }
  }

  // 4. Sanitize and prepare payload
  const payload = sanitizeOwnerForm(form, user.id);
  const needsFallbackSourceUrl = !payload.source_url;

  // 5. Try insert with retry on source_id collision
  for (let attempt = 0; attempt < 2; attempt++) {
    const row = {
      ...payload,
      source_id: genSourceId(),
      source_url: payload.source_url || OWNER_SUBMISSION_SOURCE_FALLBACK,
    };
    const { data: inserted, error } = await serviceClient
      .from("events")
      .insert(row)
      .select()
      .single();

    if (!error && inserted) {
      if (needsFallbackSourceUrl) {
        const canonicalSourceUrl = `${SITE_URL}/ja/events/${inserted.id}`;
        const { error: sourceUrlError } = await serviceClient
          .from("events")
          .update({ source_url: canonicalSourceUrl })
          .eq("id", inserted.id);
        if (sourceUrlError) {
          console.error("[createOwnerEvent] failed to backfill source_url", sourceUrlError);
        } else {
          (inserted as Event).source_url = canonicalSourceUrl;
        }
      }
      return { ok: true, data: inserted as Event };
    }
    if (error && error.code === "23505" && attempt === 0) continue;
    console.error("[createOwnerEvent] insert failed", error);
    return { ok: false, error: error?.message ?? "saveFailed" };
  }

  return { ok: false, error: "source_id_conflict" };
}

export async function createOwnerDraft(form: FormState): Promise<ActionResult<Event>> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { ok: false, error: "unauthorized" };

  const serviceClient = getServiceRoleClient();

  // 1. Check if user has registered a creator profile
  const { data: creatorProfile } = await serviceClient
    .from("creators")
    .select("user_handle")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!creatorProfile || !creatorProfile.user_handle) {
    return { ok: false, error: "profileRequired" };
  }

  // 2. Check if banned
  const { data: roleRow } = await serviceClient
    .from("user_roles")
    .select("publish_banned_until")
    .eq("user_id", user.id)
    .maybeSingle();

  if (roleRow?.publish_banned_until) {
    const banDate = new Date(roleRow.publish_banned_until);
    if (banDate > new Date()) {
      return { ok: false, error: `publishBanned|${banDate.toISOString()}` };
    }
  }

  // 3. Sanitize and prepare payload as Draft (is_active=false)
  const payload = sanitizeOwnerForm(form, user.id);
  payload.is_active = false;
  payload.annotation_status = "pending";
  const needsFallbackSourceUrl = !payload.source_url;

  if (!payload.name_ja) {
    payload.name_ja = payload.name_zh?.trim() || payload.name_en?.trim() || "Draft Event";
  }

  for (let attempt = 0; attempt < 2; attempt++) {
    const row = {
      ...payload,
      source_id: genSourceId(),
      source_url: payload.source_url || OWNER_SUBMISSION_SOURCE_FALLBACK,
    };
    const { data: inserted, error } = await serviceClient
      .from("events")
      .insert(row)
      .select()
      .single();

    if (!error && inserted) {
      if (needsFallbackSourceUrl) {
        const canonicalSourceUrl = `${SITE_URL}/ja/events/${inserted.id}`;
        const { error: sourceUrlError } = await serviceClient
          .from("events")
          .update({ source_url: canonicalSourceUrl })
          .eq("id", inserted.id);
        if (sourceUrlError) {
          console.error("[createOwnerDraft] failed to backfill source_url", sourceUrlError);
        } else {
          (inserted as Event).source_url = canonicalSourceUrl;
        }
      }
      return { ok: true, data: inserted as Event };
    }
    if (error && error.code === "23505" && attempt === 0) continue;
    console.error("[createOwnerDraft] insert failed", error);
    return { ok: false, error: error?.message ?? "saveFailed" };
  }

  return { ok: false, error: "source_id_conflict" };
}

export async function updateOwnerEvent(
  eventId: string,
  form: FormState
): Promise<ActionResult<Event>> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { ok: false, error: "unauthorized" };

  const serviceClient = getServiceRoleClient();

  // Load existing event
  const { data: existing, error: loadError } = await serviceClient
    .from("events")
    .select("*")
    .eq("id", eventId)
    .single();

  if (loadError || !existing) {
    return { ok: false, error: "eventNotFound" };
  }

  // 1. OWASP A01 Gate - verify owner
  if (existing.owner_user_id !== user.id) {
    return { ok: false, error: "forbidden" };
  }

  // 2. UGC Required Fields Gate (Server-side validation)
  const startDate = form.start_date?.trim();
  const endDate = form.end_date?.trim();
  const locationName = form.location_name?.trim();
  const locationAddress = form.location_address?.trim();
  const categories = form.category;
  const eventForms = form.event_form;

  if (!startDate || !endDate || !locationName || !locationAddress) {
    return { ok: false, error: "requiredFieldsMissing" };
  }
  if (!Array.isArray(categories) || categories.length < 1) {
    return { ok: false, error: "requiredFieldsMissing" };
  }
  if (!Array.isArray(eventForms) || eventForms.length < 1) {
    return { ok: false, error: "requiredFieldsMissing" };
  }

  let nameJa = form.name_ja?.trim();
  if (!nameJa) {
    const otherVal = form.name_zh?.trim() || form.name_en?.trim();
    if (otherVal) {
      nameJa = otherVal;
      form.name_ja = otherVal;
    } else {
      return { ok: false, error: "requiredFieldsMissing" };
    }
  }

  // 3. Record field corrections (FC Guard) before writing updates
  await recordFieldCorrections(eventId, user.id, existing as Event, form);

  // 4. Sanitize and update
  const payload = sanitizeOwnerForm(form, user.id);
  // Keep original source_id & source_name
  delete payload.source_name;
  delete payload.source_id;

  const { data: updated, error: updateError } = await serviceClient
    .from("events")
    .update(payload)
    .eq("id", eventId)
    .select()
    .single();

  if (updateError) {
    return { ok: false, error: updateError.message };
  }

  return { ok: true, data: updated as Event };
}

export async function deactivateOwnEvent(eventId: string): Promise<ActionResult<null>> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { ok: false, error: "unauthorized" };

  const serviceClient = getServiceRoleClient();

  // Load existing event
  const { data: existing, error: loadError } = await serviceClient
    .from("events")
    .select("owner_user_id, is_active")
    .eq("id", eventId)
    .single();

  if (loadError || !existing) {
    return { ok: false, error: "eventNotFound" };
  }

  // 1. OWASP A01 Gate - verify owner
  if (existing.owner_user_id !== user.id) {
    return { ok: false, error: "forbidden" };
  }

  // 2. Perform deactivation (one-way only)
  const { error: updateError } = await serviceClient
    .from("events")
    .update({ is_active: false, closed_by_owner: true, deactivated_reason: "closed_by_owner" })
    .eq("id", eventId);

  if (updateError) {
    return { ok: false, error: updateError.message };
  }

  revalidatePath("/[locale]/account", "page");
  revalidatePath("/[locale]/account/events/[id]/edit", "page");

  return { ok: true, data: null };
}

export async function deleteOwnEvent(eventId: string): Promise<ActionResult<null>> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { ok: false, error: "unauthorized" };

  const serviceClient = getServiceRoleClient();

  const { data: existing, error: loadError } = await serviceClient
    .from("events")
    .select("owner_user_id, is_active")
    .eq("id", eventId)
    .single();

  if (loadError || !existing) {
    return { ok: false, error: "eventNotFound" };
  }

  if (existing.owner_user_id !== user.id) {
    return { ok: false, error: "forbidden" };
  }

  const { error: deleteError } = await serviceClient
    .from("events")
    .delete()
    .eq("id", eventId);

  if (deleteError) {
    return { ok: false, error: deleteError.message };
  }

  revalidatePath("/[locale]/account", "page");
  revalidatePath("/[locale]/saved", "page");

  return { ok: true, data: null };
}

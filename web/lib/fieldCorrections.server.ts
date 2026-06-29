// Server-only helpers for persisting field corrections.
// NOTE: must only be imported from "use server" action files. It expects a
// service-role Supabase client (field_corrections is admin/service-role RLS).

import type { SupabaseClient } from "@supabase/supabase-js";
import { TRANSLATION_LOCK_FIELDS } from "./eventIntakeClient";

// field_corrections.corrected_value is `text NOT NULL`, so every value must be
// coerced to a non-null string. Arrays/objects are JSON-serialized; null/""
// collapse to an empty-string sentinel.
export function toFieldCorrectionValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value) || typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "";
    }
  }
  return String(value);
}

type PersistResult = { ok: true } | { ok: false; error: string };

// Record the user-confirmed translation fields so the annotator never
// overwrites them on later re-annotation runs. Writes BEFORE the publish
// update so a lock failure aborts the publish (FC-first).
export async function persistTranslationLocks(params: {
  client: SupabaseClient;
  eventId: string;
  userId: string;
  form: Record<string, unknown>;
  lockedTranslationFields: string[];
}): Promise<PersistResult> {
  const { client, eventId, userId, form, lockedTranslationFields } = params;

  const allowed = new Set<string>(TRANSLATION_LOCK_FIELDS as readonly string[]);
  const fields = Array.from(
    new Set(lockedTranslationFields.filter((field) => allowed.has(field))),
  );
  if (fields.length === 0) return { ok: true };

  const rows = fields.map((field_name) => ({
    event_id: eventId,
    field_name,
    corrected_value: toFieldCorrectionValue(form[field_name]),
    corrected_by: userId,
  }));

  const { error } = await client
    .from("field_corrections")
    .upsert(rows, { onConflict: "event_id,field_name" });

  if (error) {
    console.error("[persistTranslationLocks] upsert failed", error);
    return { ok: false, error: "translationLockFailed" };
  }
  return { ok: true };
}

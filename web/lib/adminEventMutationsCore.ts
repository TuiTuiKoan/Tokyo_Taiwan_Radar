import type { SupabaseClient } from "@supabase/supabase-js";
import { toFieldCorrectionValue } from "./fieldCorrections.server";
import { CATEGORIES, EVENT_FORMS, type Event } from "./types";

export type CoreMutationResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export type EventCategoryResult = {
  id: string;
  category: string[];
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const VALID_CATEGORIES = new Set<string>(CATEGORIES);
const VALID_EVENT_FORMS = new Set<string>(EVENT_FORMS);
const ADMIN_EDIT_STRING_FIELDS = [
  "name_ja",
  "name_zh",
  "name_en",
  "description_ja",
  "description_zh",
  "description_en",
  "start_date",
  "end_date",
  "location_name",
  "location_address",
  "location_url",
  "business_hours",
  "performer",
  "organizer",
  "organizer_url",
  "primary_language",
  "price_info",
  "official_url",
  "submission_url",
  "source_url",
  "original_language",
] as const;
const FORM_BOOLEAN_FIELDS = [
  "has_japanese_support",
  "has_english_support",
  "has_chinese_support",
  "is_paid",
  "is_active",
] as const;
const TRACKED_FIELDS = [
  "name_ja",
  "name_zh",
  "name_en",
  "description_ja",
  "description_zh",
  "description_en",
  "location_name",
  "location_address",
  "business_hours",
  "price_info",
  "performer",
  "organizer",
  "organizer_url",
] as const;
const ADMIN_EDIT_BEFORE_COLUMNS = [
  "id",
  "raw_title",
  "raw_description",
  "category",
  "event_form",
  "co_organizers",
  "sponsors",
  "primary_language",
  "has_japanese_support",
  "has_english_support",
  "has_chinese_support",
  ...TRACKED_FIELDS,
].join(",");

type MutationMode = "single" | "bulk";
type IdRow = { id: string };
type AdminEditStringField = (typeof ADMIN_EDIT_STRING_FIELDS)[number];
type AdminEditRecordLink = {
  title: string;
  url: string;
  recommended?: boolean;
};
type ValidatedAdminEditForm = Record<AdminEditStringField, string> & {
  category: string[];
  event_form: string[];
  co_organizers: string[];
  sponsors: string[];
  has_japanese_support: boolean;
  has_english_support: boolean;
  has_chinese_support: boolean;
  is_paid: boolean;
  is_active: boolean;
  parent_event_id: string | null;
  record_links: AdminEditRecordLink[];
};
type AdminEditBefore = Record<string, unknown> & {
  id: string;
  raw_title: string | null;
  raw_description: string | null;
  category: string[] | null;
};

function failure<T>(error: string): CoreMutationResult<T> {
  return { ok: false, error };
}

function canonicalUuid(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const canonical = value.trim().toLowerCase();
  return UUID_RE.test(canonical) ? canonical : null;
}

function normalizeIds(ids: unknown, label: string): CoreMutationResult<string[]> {
  if (!Array.isArray(ids)) return failure(`${label}_ids_invalid`);
  if (ids.some((id) => typeof id !== "string")) return failure(`${label}_ids_invalid`);
  const canonicalIds = (ids as string[]).map(canonicalUuid);
  if (canonicalIds.some((id) => id === null)) {
    return failure(`${label}_ids_invalid`);
  }
  const normalized = Array.from(new Set(canonicalIds as string[]));
  if (normalized.length === 0) return failure(`${label}_ids_invalid`);
  return { ok: true, data: normalized };
}

function normalizeSingleId(id: unknown, label: string): CoreMutationResult<string> {
  const normalized = normalizeIds([id], label);
  if (!normalized.ok) return normalized;
  return { ok: true, data: normalized.data[0] };
}

function validateMode(ids: string[], mode: MutationMode, label: string): CoreMutationResult<null> {
  if (mode === "single" && ids.length !== 1) return failure(`${label}_single_id_required`);
  return { ok: true, data: null };
}

function exactIds(
  data: unknown,
  requestedIds: string[],
  label: string,
): CoreMutationResult<{ ids: string[] }> {
  if (!Array.isArray(data)) return failure(`${label}_exact_id_mismatch`);
  const returnedIds = data.map((row) => {
    if (!row || typeof row !== "object" || Array.isArray(row)) return null;
    return canonicalUuid((row as IdRow).id);
  });
  const canonicalRequestedIds = requestedIds.map(canonicalUuid);
  if (
    returnedIds.some((id) => id === null)
    || canonicalRequestedIds.some((id) => id === null)
  ) {
    return failure(`${label}_exact_id_mismatch`);
  }
  const validReturnedIds = returnedIds as string[];
  const validRequestedIds = canonicalRequestedIds as string[];
  const returnedSet = new Set(validReturnedIds);
  const requestedSet = new Set(validRequestedIds);
  const matches = validReturnedIds.length === validRequestedIds.length
    && returnedSet.size === validReturnedIds.length
    && requestedSet.size === validRequestedIds.length
    && validRequestedIds.every((id) => returnedSet.has(id))
    && validReturnedIds.every((id) => requestedSet.has(id));
  return matches
    ? { ok: true, data: { ids: validRequestedIds } }
    : failure(`${label}_exact_id_mismatch`);
}

function normalizeCategoryInput(categories: unknown): CoreMutationResult<string[]> {
  if (!Array.isArray(categories)) return failure("categories_invalid");
  if (categories.some((category) => typeof category !== "string")) {
    return failure("categories_invalid");
  }
  const normalized = Array.from(
    new Set((categories as string[]).map((category) => category.trim())),
  );
  if (normalized.length === 0 || normalized.some((category) => !VALID_CATEGORIES.has(category))) {
    return failure("categories_invalid");
  }
  return { ok: true, data: normalized };
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  try {
    const prototype = Object.getPrototypeOf(value);
    return prototype === Object.prototype || prototype === null;
  } catch {
    return false;
  }
}

function normalizeCommaArrayInput(value: unknown): CoreMutationResult<string[]> {
  if (value === null) return { ok: true, data: [] };
  if (typeof value === "string") {
    return {
      ok: true,
      data: value.split(/[,，、]/).map((item) => item.trim()).filter(Boolean),
    };
  }
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string")) {
    return failure("form_invalid");
  }
  return {
    ok: true,
    data: value.map((item) => item.trim()).filter(Boolean),
  };
}

function normalizeRecordLinks(value: unknown): CoreMutationResult<AdminEditRecordLink[]> {
  if (!Array.isArray(value)) return failure("form_invalid");
  const normalized: AdminEditRecordLink[] = [];
  for (const link of value) {
    if (!isPlainRecord(link)) return failure("form_invalid");
    if (Object.keys(link).some((key) => !["title", "url", "recommended"].includes(key))) {
      return failure("form_invalid");
    }
    if (typeof link.title !== "string" || typeof link.url !== "string") {
      return failure("form_invalid");
    }
    if (link.recommended !== undefined && typeof link.recommended !== "boolean") {
      return failure("form_invalid");
    }
    if (!link.url.trim()) continue;
    normalized.push({
      title: link.title,
      url: link.url,
      ...(link.recommended === undefined ? {} : { recommended: link.recommended }),
    });
  }
  return { ok: true, data: normalized };
}

function validateAdminEditFormInput(
  form: unknown,
): CoreMutationResult<ValidatedAdminEditForm> {
  if (!isPlainRecord(form)) return failure("form_invalid");
  try {
    if (
      !Array.isArray(form.category)
      || form.category.some((category) => typeof category !== "string")
      || form.category.some((category) => !VALID_CATEGORIES.has(category))
    ) {
      return failure("categories_invalid");
    }
    if (
      !Array.isArray(form.event_form)
      || form.event_form.some((eventForm) => typeof eventForm !== "string")
      || form.event_form.some((eventForm) => !VALID_EVENT_FORMS.has(eventForm))
    ) {
      return failure("event_forms_invalid");
    }
    if (ADMIN_EDIT_STRING_FIELDS.some((field) => typeof form[field] !== "string")) {
      return failure("form_invalid");
    }
    if (FORM_BOOLEAN_FIELDS.some((field) => typeof form[field] !== "boolean")) {
      return failure("form_invalid");
    }

    const coOrganizers = normalizeCommaArrayInput(form.co_organizers);
    if (!coOrganizers.ok) return coOrganizers;
    const sponsors = normalizeCommaArrayInput(form.sponsors);
    if (!sponsors.ok) return sponsors;
    const recordLinks = normalizeRecordLinks(form.record_links);
    if (!recordLinks.ok) return recordLinks;

    let parentEventId: string | null = null;
    if (form.parent_event_id !== null && form.parent_event_id !== undefined) {
      if (typeof form.parent_event_id !== "string") {
        return failure("parent_event_id_invalid");
      }
      if (form.parent_event_id.trim()) {
        parentEventId = canonicalUuid(form.parent_event_id);
        if (!parentEventId) return failure("parent_event_id_invalid");
      }
    }

    const stringFields = Object.fromEntries(
      ADMIN_EDIT_STRING_FIELDS.map((field) => [field, form[field]]),
    ) as Record<AdminEditStringField, string>;
    return {
      ok: true,
      data: {
        ...stringFields,
        category: [...form.category] as string[],
        event_form: [...form.event_form] as string[],
        co_organizers: coOrganizers.data,
        sponsors: sponsors.data,
        has_japanese_support: form.has_japanese_support as boolean,
        has_english_support: form.has_english_support as boolean,
        has_chinese_support: form.has_chinese_support as boolean,
        is_paid: form.is_paid as boolean,
        is_active: form.is_active as boolean,
        parent_event_id: parentEventId,
        record_links: recordLinks.data,
      },
    };
  } catch {
    return failure("form_invalid");
  }
}

function stripNullBytes(value: unknown, maxLength?: number): string | null {
  if (typeof value !== "string") return null;
  const limited = typeof maxLength === "number" ? value.slice(0, maxLength) : value;
  return limited.replace(/\u0000/g, "");
}

function nullify(value: unknown): string | null {
  return typeof value === "string" ? value.trim() || null : null;
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function sortedJson(value: unknown): string {
  return JSON.stringify([...stringArray(value)].sort());
}

function formCommaText(value: unknown): string {
  if (typeof value === "string") return value;
  return Array.isArray(value) ? value.join(", ") : "";
}

function sanitizeAdminEditForm(
  formRecord: ValidatedAdminEditForm,
  rawTitle: string | null,
): CoreMutationResult<Record<string, unknown>> {
  const payload: Record<string, unknown> = {
    name_ja: nullify(formRecord.name_ja) ?? rawTitle,
    name_zh: nullify(formRecord.name_zh),
    name_en: nullify(formRecord.name_en),
    description_ja: nullify(formRecord.description_ja),
    description_zh: nullify(formRecord.description_zh),
    description_en: nullify(formRecord.description_en),
    category: formRecord.category,
    start_date: nullify(formRecord.start_date),
    end_date: nullify(formRecord.end_date),
    location_name: formRecord.location_name,
    location_address: formRecord.location_address,
    location_url: formRecord.location_url,
    business_hours: formRecord.business_hours,
    performer: nullify(formRecord.performer),
    organizer: nullify(formRecord.organizer),
    organizer_url: nullify(formRecord.organizer_url),
    event_form: formRecord.event_form,
    co_organizers: formRecord.co_organizers,
    sponsors: formRecord.sponsors,
    primary_language: nullify(formRecord.primary_language),
    has_japanese_support: formRecord.has_japanese_support ? true : null,
    has_english_support: formRecord.has_english_support ? true : null,
    has_chinese_support: formRecord.has_chinese_support ? true : null,
    is_paid: formRecord.is_paid,
    price_info: formRecord.price_info,
    official_url: formRecord.official_url,
    submission_url: formRecord.submission_url,
    source_url: formRecord.source_url,
    original_language: formRecord.original_language,
    is_active: formRecord.is_active,
    parent_event_id: formRecord.parent_event_id,
    record_links: formRecord.record_links,
  };
  return { ok: true, data: payload };
}

async function updateEventsExact(
  client: SupabaseClient,
  ids: string[],
  payload: Record<string, unknown>,
  label: string,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const { data, error } = await client
    .from("events")
    .update(payload)
    .in("id", ids)
    .select("id");
  if (error) return failure(error.message);
  return exactIds(data, ids, label);
}

export async function runSetAdminEventsActive(
  client: SupabaseClient,
  eventIds: unknown,
  targetActive: unknown,
  mode: MutationMode,
  now: () => string = () => new Date().toISOString(),
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idsResult = normalizeIds(eventIds, "active");
  if (!idsResult.ok) return idsResult;
  if (typeof targetActive !== "boolean") return failure("active_value_invalid");
  const modeResult = validateMode(idsResult.data, mode, "active");
  if (!modeResult.ok) return modeResult;
  const payload: Record<string, unknown> = { is_active: targetActive };
  if (targetActive) {
    payload.deactivated_at = null;
    payload.deactivated_reason = null;
    payload.deactivated_by_pass = null;
  } else {
    payload.deactivated_at = now();
    payload.deactivated_reason = mode === "bulk"
      ? "manually deactivated by admin (bulk)"
      : "manually deactivated by admin";
    payload.deactivated_by_pass = "admin_manual";
  }
  return updateEventsExact(client, idsResult.data, payload, "active");
}

export async function runSetAdminEventsForceRescrape(
  client: SupabaseClient,
  eventIds: unknown,
  forceRescrape: unknown,
  mode: MutationMode,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idsResult = normalizeIds(eventIds, "force_rescrape");
  if (!idsResult.ok) return idsResult;
  if (typeof forceRescrape !== "boolean") return failure("force_rescrape_value_invalid");
  const modeResult = validateMode(idsResult.data, mode, "force_rescrape");
  if (!modeResult.ok) return modeResult;
  return updateEventsExact(
    client,
    idsResult.data,
    { force_rescrape: forceRescrape },
    "force_rescrape",
  );
}

export async function runReannotateAdminEvent(
  client: SupabaseClient,
  eventId: unknown,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idResult = normalizeSingleId(eventId, "reannotate");
  if (!idResult.ok) return idResult;
  return updateEventsExact(
    client,
    [idResult.data],
    { annotation_status: "pending" },
    "reannotate",
  );
}

export async function runChangeAdminEventCategories(
  client: SupabaseClient,
  eventIds: unknown,
  operation: unknown,
  categories: unknown,
  adminUserId: unknown,
): Promise<CoreMutationResult<{ events: EventCategoryResult[] }>> {
  const idsResult = normalizeIds(eventIds, "category");
  if (!idsResult.ok) return idsResult;
  const adminResult = normalizeSingleId(adminUserId, "admin_user");
  if (!adminResult.ok) return adminResult;
  const categoryResult = normalizeCategoryInput(categories);
  if (!categoryResult.ok) return categoryResult;
  if (operation !== "add" && operation !== "remove") return failure("category_operation_invalid");

  const { data: rows, error: readError } = await client
    .from("events")
    .select("id,category,raw_title,raw_description")
    .in("id", idsResult.data);
  if (readError) return failure(readError.message);
  const readIds = exactIds(rows, idsResult.data, "category_read");
  if (!readIds.ok) return readIds;

  const rowMap = new Map(
    (rows as AdminEditBefore[]).map((row) => [canonicalUuid(row.id), row]),
  );
  const categorySet = new Set(categoryResult.data);
  const results: EventCategoryResult[] = [];

  for (const eventId of idsResult.data) {
    const before = rowMap.get(eventId);
    if (!before) return failure("category_read_exact_id_mismatch");
    const currentCategory = stringArray(before.category);
    const nextCategory = operation === "add"
      ? Array.from(new Set([...currentCategory, ...categoryResult.data]))
      : currentCategory.filter((category) => !categorySet.has(category));

    if (JSON.stringify(nextCategory) !== JSON.stringify(currentCategory)) {
      // Non-transactional: correction upserts run first and are not rolled back; failures are retryable.
      const { error: categoryCorrectionError } = await client
        .from("category_corrections")
        .upsert(
          {
            event_id: eventId,
            raw_title: stripNullBytes(before.raw_title),
            raw_description: stripNullBytes(before.raw_description, 2000),
            ai_category: currentCategory,
            corrected_category: nextCategory,
            corrected_by: adminResult.data,
          },
          { onConflict: "event_id" },
        );
      if (categoryCorrectionError) return failure(categoryCorrectionError.message);

      const { error: fieldCorrectionError } = await client
        .from("field_corrections")
        .upsert(
          {
            event_id: eventId,
            field_name: "category",
            original_value: JSON.stringify(currentCategory),
            corrected_value: JSON.stringify(nextCategory),
            corrected_by: adminResult.data,
          },
          { onConflict: "event_id,field_name" },
        );
      if (fieldCorrectionError) return failure(fieldCorrectionError.message);

      const updateResult = await updateEventsExact(
        client,
        [eventId],
        { category: nextCategory },
        "category_update",
      );
      if (!updateResult.ok) return updateResult;
    }

    results.push({ id: eventId, category: nextCategory });
  }

  return { ok: true, data: { events: results } };
}

export async function runSaveAdminEditedEvent(
  client: SupabaseClient,
  eventId: unknown,
  form: unknown,
  adminUserId: unknown,
): Promise<CoreMutationResult<Event>> {
  const idResult = normalizeSingleId(eventId, "admin_edit");
  if (!idResult.ok) return idResult;
  const adminResult = normalizeSingleId(adminUserId, "admin_user");
  if (!adminResult.ok) return adminResult;
  const formResult = validateAdminEditFormInput(form);
  if (!formResult.ok) return formResult;

  const { data: beforeData, error: beforeError } = await client
    .from("events")
    .select(ADMIN_EDIT_BEFORE_COLUMNS)
    .eq("id", idResult.data)
    .single();
  if (beforeError) return failure(beforeError.message);
  if (!beforeData || typeof beforeData !== "object") return failure("eventNotFound");
  const before = beforeData as AdminEditBefore;
  if (canonicalUuid(before.id) !== idResult.data) {
    return failure("admin_edit_before_exact_id_mismatch");
  }

  const formRecord = formResult.data;
  const payloadResult = sanitizeAdminEditForm(formRecord, before.raw_title);
  if (!payloadResult.ok) return payloadResult;
  const payload = payloadResult.data;
  const resolvedPayload = Object.fromEntries(
    TRACKED_FIELDS.map((field) => [field, nullify(payload[field])]),
  ) as Record<(typeof TRACKED_FIELDS)[number], string | null>;
  const changedFields = TRACKED_FIELDS.filter(
    (field) => (before[field] ?? null) !== resolvedPayload[field],
  );
  const categoryChanged = sortedJson(before.category) !== sortedJson(payload.category);
  const arrayOrBooleanChanged = JSON.stringify(stringArray(formRecord.event_form))
      !== JSON.stringify(stringArray(before.event_form))
    || formCommaText(formRecord.co_organizers) !== stringArray(before.co_organizers).join(", ")
    || formCommaText(formRecord.sponsors) !== stringArray(before.sponsors).join(", ")
    || (formRecord.primary_language ?? "") !== (before.primary_language ?? "")
    || Boolean(formRecord.has_japanese_support) !== Boolean(before.has_japanese_support)
    || Boolean(formRecord.has_english_support) !== Boolean(before.has_english_support)
    || Boolean(formRecord.has_chinese_support) !== Boolean(before.has_chinese_support);

  if (changedFields.length > 0 || categoryChanged || arrayOrBooleanChanged) {
    payload.annotation_status = "reviewed";
  }

  if (changedFields.length > 0) {
    // Non-transactional: correction upserts run first and are not rolled back; failures are retryable.
    const rows = changedFields.map((field) => ({
      event_id: idResult.data,
      field_name: field,
      original_value: before[field] ?? null,
      corrected_value: toFieldCorrectionValue(resolvedPayload[field]),
      corrected_by: adminResult.data,
    }));
    const { error: fieldCorrectionError } = await client
      .from("field_corrections")
      .upsert(rows, { onConflict: "event_id,field_name" });
    if (fieldCorrectionError) return failure(fieldCorrectionError.message);
  }

  if (categoryChanged) {
    const correctedCategory = stringArray(payload.category);
    const originalCategory = stringArray(before.category);
    const { error: categoryCorrectionError } = await client
      .from("category_corrections")
      .upsert(
        {
          event_id: idResult.data,
          raw_title: stripNullBytes(before.raw_title),
          raw_description: stripNullBytes(before.raw_description ?? "", 500),
          ai_category: originalCategory,
          corrected_category: correctedCategory,
          corrected_by: adminResult.data,
        },
        { onConflict: "event_id" },
      );
    if (categoryCorrectionError) return failure(categoryCorrectionError.message);

    const { error: categoryFieldCorrectionError } = await client
      .from("field_corrections")
      .upsert(
        {
          event_id: idResult.data,
          field_name: "category",
          original_value: JSON.stringify(originalCategory),
          corrected_value: JSON.stringify(correctedCategory),
          corrected_by: adminResult.data,
        },
        { onConflict: "event_id,field_name" },
      );
    if (categoryFieldCorrectionError) return failure(categoryFieldCorrectionError.message);
  }

  const { data: updatedData, error: updateError } = await client
    .from("events")
    .update(payload)
    .eq("id", idResult.data)
    .select()
    .single();
  if (updateError) return failure(updateError.message);
  if (
    !updatedData
    || typeof updatedData !== "object"
    || canonicalUuid((updatedData as IdRow).id) !== idResult.data
  ) {
    return failure("admin_edit_exact_id_mismatch");
  }

  return { ok: true, data: updatedData as Event };
}

export async function runAssignWorkToEvents(
  client: SupabaseClient,
  eventIds: unknown,
  workId: unknown,
  mode: MutationMode,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idsResult = normalizeIds(eventIds, "work_assignment");
  if (!idsResult.ok) return idsResult;
  const modeResult = validateMode(idsResult.data, mode, "work_assignment");
  if (!modeResult.ok) return modeResult;
  if (workId !== null && typeof workId !== "string") return failure("work_id_invalid");
  const normalizedWorkId = workId === null ? null : canonicalUuid(workId);
  if (workId !== null && !normalizedWorkId) return failure("work_id_invalid");
  return updateEventsExact(
    client,
    idsResult.data,
    { work_id: normalizedWorkId },
    "work_assignment",
  );
}

export async function runUpdateWorkExact(
  client: SupabaseClient,
  workId: unknown,
  payload: Record<string, unknown>,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idResult = normalizeSingleId(workId, "work_update");
  if (!idResult.ok) return idResult;
  const { data, error } = await client
    .from("works")
    .update(payload)
    .eq("id", idResult.data)
    .select("id");
  if (error) return failure(error.message);
  return exactIds(data, [idResult.data], "work_update");
}

export async function runDeleteWorkExact(
  client: SupabaseClient,
  workId: unknown,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idResult = normalizeSingleId(workId, "work_delete");
  if (!idResult.ok) return idResult;
  const { data, error } = await client
    .from("works")
    .delete()
    .eq("id", idResult.data)
    .select("id");
  if (error) return failure(error.message);
  return exactIds(data, [idResult.data], "work_delete");
}

export async function runDeactivateOwnerEventExact(
  client: SupabaseClient,
  eventId: unknown,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idResult = normalizeSingleId(eventId, "owner_deactivate");
  if (!idResult.ok) return idResult;
  const { data, error } = await client
    .from("events")
    .update({
      is_active: false,
      closed_by_owner: true,
      deactivated_reason: "closed_by_owner",
    })
    .eq("id", idResult.data)
    .select("id");
  if (error) return failure(error.message);
  return exactIds(data, [idResult.data], "owner_deactivate");
}

export async function runDeleteOwnerEventExact(
  client: SupabaseClient,
  eventId: unknown,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idResult = normalizeSingleId(eventId, "owner_delete");
  if (!idResult.ok) return idResult;
  const { data, error } = await client
    .from("events")
    .delete()
    .eq("id", idResult.data)
    .select("id");
  if (error) return failure(error.message);
  return exactIds(data, [idResult.data], "owner_delete");
}

export async function runDeleteAdminEventExact(
  client: SupabaseClient,
  eventId: unknown,
): Promise<CoreMutationResult<{ ids: string[] }>> {
  const idResult = normalizeSingleId(eventId, "admin_delete");
  if (!idResult.ok) return idResult;
  const { data, error } = await client
    .from("events")
    .delete()
    .eq("id", idResult.data)
    .select("id");
  if (error) return failure(error.message);
  return exactIds(data, [idResult.data], "admin_delete");
}

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { type Event, type Locale } from "@/lib/types";
import AdminEventForm, { type FormState } from "@/components/AdminEventForm";

interface Props {
  event: Event;
  allEvents: Event[];
  locale: Locale;
}

export default function AdminEditClient({ event, allEvents, locale }: Props) {
  const t = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tEventForm = useTranslations("eventForm");
  const router = useRouter();
  const supabase = createClient();

  const [form, setForm] = useState<FormState>({
    name_ja: event.name_ja ?? "",
    name_zh: event.name_zh ?? "",
    name_en: event.name_en ?? "",
    description_ja: event.description_ja ?? "",
    description_zh: event.description_zh ?? "",
    description_en: event.description_en ?? "",
    category: event.category ?? [],
    start_date: event.start_date?.slice(0, 10) ?? "",
    end_date: event.end_date?.slice(0, 10) ?? "",
    location_name: event.location_name ?? "",
    location_address: event.location_address ?? "",
    location_url: event.location_url ?? "",
    business_hours: event.business_hours ?? "",
    performer: (event as any).performer ?? "",
    organizer: (event as any).organizer ?? "",
    organizer_url: (event as any).organizer_url ?? "",
    event_form: (event as any).event_form ?? [],
    co_organizers: ((event as any).co_organizers ?? []).join(", "),
    sponsors: ((event as any).sponsors ?? []).join(", "),
    primary_language: (event as any).primary_language ?? "",
    has_japanese_support: (event as any).has_japanese_support ?? false,
    has_english_support: (event as any).has_english_support ?? false,
    has_chinese_support: (event as any).has_chinese_support ?? false,
    is_paid: event.is_paid ?? false,
    price_info: event.price_info ?? "",
    source_url: event.source_url,
    source_name: event.source_name,
    original_language: event.original_language,
    is_active: event.is_active,
    parent_event_id: event.parent_event_id ?? "",
    record_links: (event.record_links as { title: string; url: string }[]) ?? [],
  });
  const [saving, setSaving] = useState(false);

  function updateField(key: string, value: any) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function toggleCategory(cat: string) {
    setForm((prev) => ({
      ...prev,
      category: prev.category.includes(cat)
        ? prev.category.filter((c) => c !== cat)
        : [...prev.category, cat],
    }));
  }

  async function handleSave() {
    setSaving(true);
    try {
    // Convert empty strings to null for nullable fields so that
    // getEventName / getEventDescription can fall back correctly via ||.
    // Without this, "" gets written to the DB and blocks the fallback chain.
    const nullify = (v: string) => v.trim() || null;
    const payload = {
      ...form,
      name_ja: form.name_ja.trim() || event.raw_title || null,
      name_zh: nullify(form.name_zh),
      name_en: nullify(form.name_en),
      description_ja: nullify(form.description_ja),
      description_zh: nullify(form.description_zh),
      description_en: nullify(form.description_en),
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      parent_event_id: form.parent_event_id || null,
      record_links: form.record_links.filter((l) => l.url.trim()),
      // Organizer / event-form fields
      organizer: nullify((form as any).organizer ?? ""),
      organizer_url: nullify((form as any).organizer_url ?? ""),
      event_form: (form as any).event_form ?? [],
      co_organizers: ((form as any).co_organizers as string ?? "").split(",").map((s: string) => s.trim()).filter(Boolean),
      sponsors: ((form as any).sponsors as string ?? "").split(",").map((s: string) => s.trim()).filter(Boolean),
      primary_language: (form as any).primary_language || null,
      has_japanese_support: (form as any).has_japanese_support || null,
      has_english_support: (form as any).has_english_support || null,
      has_chinese_support: (form as any).has_chinese_support || null,
    };

    const categoryChanged =
      JSON.stringify([...(event.category || [])].sort()) !==
      JSON.stringify([...(form.category || [])].sort());

    // Scalar fields that the annotator may overwrite — track changes for field_corrections.
    const TRACKED_FIELDS = [
      "name_ja", "name_zh", "name_en",
      "description_ja", "description_zh", "description_en",
      "location_name", "location_address",
      "business_hours", "price_info", "performer",
      "organizer", "organizer_url",
    ] as const;

    type TrackedField = typeof TRACKED_FIELDS[number];

    // Resolve payload value for a tracked field (same nullify logic as above)
    const resolvedPayload: Record<TrackedField, string | null> = {
      name_ja: payload.name_ja as string | null,
      name_zh: payload.name_zh as string | null,
      name_en: payload.name_en as string | null,
      description_ja: payload.description_ja as string | null,
      description_zh: payload.description_zh as string | null,
      description_en: payload.description_en as string | null,
      location_name: nullify(form.location_name),
      location_address: nullify(form.location_address),
      business_hours: nullify(form.business_hours),
      price_info: nullify(form.price_info),
      performer: nullify((form as any).performer ?? ""),
      organizer: nullify((form as any).organizer ?? ""),
      organizer_url: nullify((form as any).organizer_url ?? ""),
    };

    const changedFields = TRACKED_FIELDS.filter((f) => {
      const original = ((event as unknown as Record<string, unknown>)[f] ?? null) as string | null;
      const updated = resolvedPayload[f];
      return original !== updated;
    });

    // Detect changes in array / boolean fields (not tracked in field_corrections but trigger reviewed)
    const arrBoolChanged =
      JSON.stringify((form as any).event_form ?? []) !== JSON.stringify((event as any).event_form ?? []) ||
      ((form as any).co_organizers ?? "") !== ((event as any).co_organizers ?? []).join(", ") ||
      ((form as any).sponsors ?? "") !== ((event as any).sponsors ?? []).join(", ") ||
      ((form as any).primary_language ?? "") !== ((event as any).primary_language ?? "") ||
      !!(form as any).has_japanese_support !== !!(event as any).has_japanese_support ||
      !!(form as any).has_english_support !== !!(event as any).has_english_support ||
      !!(form as any).has_chinese_support !== !!(event as any).has_chinese_support;

    // If any tracked field changed, auto-upgrade annotation_status to 'reviewed'
    // so the annotator never overwrites admin edits on subsequent runs.
    const needsReviewed = changedFields.length > 0 || categoryChanged || arrBoolChanged;
    const updatePayload: Record<string, unknown> = { ...payload };
    if (needsReviewed) {
      updatePayload["annotation_status"] = "reviewed";
    }

    const { data: authData, error: authError } = await supabase.auth.getUser();
    if (authError) {
      alert("Session 已過期，請重新登入後再試。");
      return;
    }
    const user = authData.user;

    const { error, data: updatedRows } = await supabase
      .from("events")
      .update(updatePayload)
      .eq("id", event.id)
      .select("id");

    if (error) {
      console.error("Update failed:", error);
      alert(`Save failed: ${error.message}`);
      return;
    }
    if (!updatedRows || updatedRows.length === 0) {
      alert("儲存未生效（session 可能已過期），請重新整理頁面後再試。");
      return;
    }

    // Persist field-level corrections to field_corrections table (P3.1).
    // This ensures the annotator's human_field_map protects these values on re-annotation.
    if (changedFields.length > 0 && user) {
      const fcRows = changedFields.map((f) => ({
        event_id: event.id,
        field_name: f,
        original_value: (((event as unknown as Record<string, unknown>)[f] ?? null) as string | null),
        corrected_value: resolvedPayload[f] ?? "",
        corrected_by: user.id,
      }));
      const { error: fcErr } = await supabase
        .from("field_corrections")
        .upsert(fcRows, { onConflict: "event_id,field_name" });
      if (fcErr) console.warn("field_corrections save failed:", fcErr.message);
    }

    if (categoryChanged) {
      supabase
        .from("category_corrections")
        .upsert(
          {
            event_id: event.id,
            raw_title: event.raw_title,
            raw_description: (event.raw_description || "").slice(0, 500),
            ai_category: event.category || [],
            corrected_category: form.category,
          },
          { onConflict: "event_id" }
        )
        .then(({ error: corrErr }) => {
          if (corrErr) console.warn("Category correction save failed:", corrErr.message);
        });
      supabase
        .from("field_corrections")
        .upsert(
          { event_id: event.id, field_name: "category", corrected_value: JSON.stringify(form.category) },
          { onConflict: "event_id,field_name" }
        )
        .then(({ error: fcErr }) => {
          if (fcErr) console.warn("field_corrections category save failed:", fcErr.message);
        });
    }

    router.push(`/${locale}/admin`);
    } catch (err) {
      console.error("Unexpected save error:", err);
      alert(`儲存失敗：${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    router.push(`/${locale}/admin`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={handleCancel}
          className="text-sm font-medium text-fg-muted hover:text-fg-strong transition"
        >
          ← {t("back")}
        </button>
        <h1 className="text-2xl font-bold text-fg-strong">{t("edit")}</h1>
      </div>
      <div className="space-y-6">
        <AdminEventForm
          form={form}
          t={t}
          tCat={tCat}
          tEventForm={tEventForm}
          updateField={updateField}
          toggleCategory={toggleCategory}
          events={allEvents}
          editingId={event.id}
          locale={locale}
        />
        <div className="flex gap-3 pt-4 border-t border-line">
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-green-700 disabled:opacity-50 shadow-sm transition"
          >
            {saving ? "..." : t("save")}
          </button>
          <button
            onClick={handleCancel}
            className="border border-line-strong bg-paper px-4 py-2 rounded-lg text-sm font-semibold hover:bg-elevated transition shadow-sm"
          >
            {t("cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

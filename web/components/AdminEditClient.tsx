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
    business_hours: event.business_hours ?? "",
    is_paid: event.is_paid ?? false,
    price_info: event.price_info ?? "",
    source_url: event.source_url,
    source_name: event.source_name,
    original_language: event.original_language,
    is_active: event.is_active,
    parent_event_id: event.parent_event_id ?? "",
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
    const payload = {
      ...form,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      parent_event_id: form.parent_event_id || null,
    };

    const categoryChanged =
      JSON.stringify([...(event.category || [])].sort()) !==
      JSON.stringify([...(form.category || [])].sort());

    const { error } = await supabase
      .from("events")
      .update(payload)
      .eq("id", event.id);

    if (error) {
      console.error("Update failed:", error);
      alert(`Save failed: ${error.message}`);
      setSaving(false);
      return;
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
    }

    router.push(`/${locale}/admin`);
  }

  function handleCancel() {
    router.push(`/${locale}/admin`);
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={handleCancel}
          className="text-sm text-gray-500 hover:text-gray-800"
        >
          ← {t("back")}
        </button>
        <h1 className="text-2xl font-bold">{t("edit")}</h1>
      </div>
      <div className="border border-green-300 rounded-xl p-6 bg-green-50">
        <AdminEventForm
          form={form}
          t={t}
          tCat={tCat}
          updateField={updateField}
          toggleCategory={toggleCategory}
          events={allEvents}
          editingId={event.id}
          locale={locale}
        />
        <div className="flex gap-3 mt-6">
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
          >
            {saving ? "..." : t("save")}
          </button>
          <button
            onClick={handleCancel}
            className="border border-gray-300 px-4 py-2 rounded-lg text-sm hover:bg-gray-50"
          >
            {t("cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}

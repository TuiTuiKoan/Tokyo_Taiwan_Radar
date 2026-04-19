"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { type Event, type Locale, CATEGORIES, getEventName } from "@/lib/types";
import { useRouter } from "next/navigation";

interface Props {
  events: Event[];
  locale: Locale;
}

const EMPTY_FORM = {
  name_ja: "",
  name_zh: "",
  name_en: "",
  description_ja: "",
  description_zh: "",
  description_en: "",
  category: [] as string[],
  start_date: "",
  end_date: "",
  location_name: "",
  location_address: "",
  business_hours: "",
  is_paid: false,
  price_info: "",
  source_url: "",
  source_name: "manual",
  original_language: "zh",
  is_active: true,
  parent_event_id: "" as string,
};

export default function AdminEventTable({ events: initialEvents, locale }: Props) {
  const t = useTranslations("admin");
  const tCat = useTranslations("categories");
  const router = useRouter();
  const supabase = createClient();

  const [events, setEvents] = useState<Event[]>(initialEvents);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [viewMode, setViewMode] = useState<"annotated" | "raw">("annotated");

  function startEdit(event: Event) {
    setEditingId(event.id);
    setForm({
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
    setShowNew(false);
  }

  function startNew() {
    setShowNew(true);
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
  }

  function cancelEdit() {
    setEditingId(null);
    setShowNew(false);
  }

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
      source_id: editingId ? undefined : `manual-${Date.now()}`,
    };

    if (editingId) {
      const { data, error } = await supabase
        .from("events")
        .update(payload)
        .eq("id", editingId)
        .select()
        .single();
      if (!error && data) {
        setEvents((prev) => prev.map((e) => (e.id === editingId ? (data as Event) : e)));
      }
    } else {
      const { data, error } = await supabase
        .from("events")
        .insert({ ...payload, source_id: `manual-${Date.now()}` })
        .select()
        .single();
      if (!error && data) {
        setEvents((prev) => [data as Event, ...prev]);
      }
    }

    setSaving(false);
    setEditingId(null);
    setShowNew(false);
  }

  async function handleDelete(id: string) {
    if (!window.confirm(t("confirmDelete"))) return;
    await supabase.from("events").delete().eq("id", id);
    setEvents((prev) => prev.filter((e) => e.id !== id));
  }

  async function handleReannotate(id: string) {
    await supabase.from("events").update({ annotation_status: "pending" }).eq("id", id);
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, annotation_status: "pending" } : e))
    );
  }

  const isEditing = editingId !== null || showNew;

  return (
    <div>
      {/* View toggle + New event button */}
      <div className="flex items-center gap-3 mb-4">
        {!isEditing && (
          <button
            onClick={startNew}
            className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 transition"
          >
            + {t("newEvent")}
          </button>
        )}
        <div className="flex rounded-lg border border-gray-300 overflow-hidden ml-auto">
          <button
            onClick={() => setViewMode("annotated")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              viewMode === "annotated"
                ? "bg-green-600 text-white"
                : "bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            {t("viewAnnotated")}
          </button>
          <button
            onClick={() => setViewMode("raw")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              viewMode === "raw"
                ? "bg-green-600 text-white"
                : "bg-white text-gray-600 hover:bg-gray-50"
            }`}
          >
            {t("viewRaw")}
          </button>
        </div>
      </div>

      {/* Inline form */}
      {isEditing && (
        <div className="border border-green-300 rounded-xl p-6 mb-6 bg-green-50">
          <h2 className="font-bold text-lg mb-4">
            {editingId ? t("edit") : t("newEvent")}
          </h2>
          <EventForm
            form={form}
            t={t}
            tCat={tCat}
            updateField={updateField}
            toggleCategory={toggleCategory}
            events={events}
            editingId={editingId}
            locale={locale}
          />
          <div className="flex gap-3 mt-4">
            <button
              onClick={handleSave}
              disabled={saving}
              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              {saving ? "..." : t("save")}
            </button>
            <button
              onClick={cancelEdit}
              className="border border-gray-300 px-4 py-2 rounded-lg text-sm hover:bg-gray-50"
            >
              {t("cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Events table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            {viewMode === "annotated" ? (
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4 font-medium">{t("name")}</th>
                <th className="py-2 pr-4 font-medium">{t("category")}</th>
                <th className="py-2 pr-4 font-medium">{t("startDate")}</th>
                <th className="py-2 pr-4 font-medium">{t("endDate")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceName")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceLink")}</th>
                <th className="py-2 pr-4 font-medium">{t("isPaid")}</th>
                <th className="py-2 pr-4 font-medium">{t("isActive")}</th>
                <th className="py-2" />
              </tr>
            ) : (
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4 font-medium">{t("name")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceName")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceLink")}</th>
                <th className="py-2 pr-4 font-medium">{t("annotationStatus")}</th>
                <th className="py-2" />
              </tr>
            )}
          </thead>
          <tbody>
            {events.map((event) => (
              viewMode === "annotated" ? (
                <tr key={event.id} className="border-b hover:bg-gray-50 transition">
                  <td className="py-2 pr-4 max-w-xs truncate">
                    {getEventName(event, locale)}
                  </td>
                  <td className="py-2 pr-4">
                    <div className="flex flex-wrap gap-1">
                      {event.category?.slice(0, 3).map((cat) => (
                        <span key={cat} className="bg-green-50 text-green-700 text-[10px] px-1.5 py-0.5 rounded-full">
                          {tCat(cat as any)}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 pr-4 text-gray-500 text-xs whitespace-nowrap">
                    {event.start_date
                      ? new Date(event.start_date).toLocaleDateString("zh")
                      : "—"}
                  </td>
                  <td className="py-2 pr-4 text-gray-500 text-xs whitespace-nowrap">
                    {event.end_date
                      ? new Date(event.end_date).toLocaleDateString("zh")
                      : "—"}
                  </td>
                  <td className="py-2 pr-4 text-gray-500 text-xs">
                    {event.source_name}
                  </td>
                  <td className="py-2 pr-4">
                    {event.source_url && (
                      <a
                        href={event.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline text-xs"
                      >
                        ↗
                      </a>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    {event.is_paid === false ? (
                      <span className="text-blue-600 text-xs">免費</span>
                    ) : event.is_paid === true ? (
                      <span className="text-amber-600 text-xs">收費</span>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    <span className={`text-xs ${event.is_active ? "text-green-600" : "text-gray-400"}`}>
                      {event.is_active ? "●" : "○"}
                    </span>
                  </td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <button onClick={() => startEdit(event)} className="text-blue-600 hover:underline text-xs">
                        {t("edit")}
                      </button>
                      <button onClick={() => handleDelete(event.id)} className="text-red-500 hover:underline text-xs">
                        {t("delete")}
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr key={event.id} className="border-b hover:bg-gray-50 transition">
                  <td className="py-2 pr-4 max-w-sm">
                    <p className="text-xs text-gray-800 line-clamp-2">{event.raw_title || getEventName(event, locale)}</p>
                  </td>
                  <td className="py-2 pr-4 text-gray-500 text-xs">
                    {event.source_name}
                  </td>
                  <td className="py-2 pr-4">
                    {event.source_url && (
                      <a href={event.source_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">
                        ↗
                      </a>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      event.annotation_status === "annotated"
                        ? "bg-green-50 text-green-700"
                        : event.annotation_status === "error"
                        ? "bg-red-50 text-red-600"
                        : "bg-yellow-50 text-yellow-700"
                    }`}>
                      {t(event.annotation_status === "annotated" ? "annotated" : "pending")}
                    </span>
                  </td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <button onClick={() => startEdit(event)} className="text-blue-600 hover:underline text-xs">
                        {t("edit")}
                      </button>
                      <button onClick={() => handleReannotate(event.id)} className="text-purple-600 hover:underline text-xs">
                        {t("reannotate")}
                      </button>
                      <button onClick={() => handleDelete(event.id)} className="text-red-500 hover:underline text-xs">
                        {t("delete")}
                      </button>
                    </div>
                  </td>
                </tr>
              )
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ----- Sub-component: form fields -----
function EventForm({
  form,
  t,
  tCat,
  updateField,
  toggleCategory,
  events,
  editingId,
  locale,
}: {
  form: typeof EMPTY_FORM;
  t: any;
  tCat: any;
  updateField: (k: string, v: any) => void;
  toggleCategory: (cat: string) => void;
  events: Event[];
  editingId: string | null;
  locale: Locale;
}) {
  // Exclude self from parent candidates
  const parentCandidates = events.filter((e) => e.id !== editingId);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Multilingual names */}
      {(["ja", "zh", "en"] as const).map((lang) => (
        <div key={lang}>
          <label className="block text-xs text-gray-500 mb-1">
            {t(`name${lang.charAt(0).toUpperCase() + lang.slice(1)}` as any)}
          </label>
          <input
            type="text"
            value={(form as any)[`name_${lang}`]}
            onChange={(e) => updateField(`name_${lang}`, e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
      ))}

      {/* Dates */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("startDate")}</label>
        <input
          type="date"
          value={form.start_date}
          onChange={(e) => updateField("start_date", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("endDate")}</label>
        <input
          type="date"
          value={form.end_date}
          onChange={(e) => updateField("end_date", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Location */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("location")}</label>
        <input
          type="text"
          value={form.location_name}
          onChange={(e) => updateField("location_name", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("address")}</label>
        <input
          type="text"
          value={form.location_address}
          onChange={(e) => updateField("location_address", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Hours */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("hours")}</label>
        <input
          type="text"
          value={form.business_hours}
          onChange={(e) => updateField("business_hours", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Source URL */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("sourceUrl")}</label>
        <input
          type="url"
          value={form.source_url}
          onChange={(e) => updateField("source_url", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Paid */}
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="is_paid"
          checked={form.is_paid}
          onChange={(e) => updateField("is_paid", e.target.checked)}
          className="w-4 h-4"
        />
        <label htmlFor="is_paid" className="text-sm">{t("isPaid")}</label>
      </div>

      {/* Active */}
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="is_active"
          checked={form.is_active}
          onChange={(e) => updateField("is_active", e.target.checked)}
          className="w-4 h-4"
        />
        <label htmlFor="is_active" className="text-sm">{t("isActive")}</label>
      </div>

      {/* Price info */}
      <div className="md:col-span-2">
        <label className="block text-xs text-gray-500 mb-1">{t("priceInfo")}</label>
        <input
          type="text"
          value={form.price_info}
          onChange={(e) => updateField("price_info", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Categories */}
      <div className="md:col-span-2">
        <label className="block text-xs text-gray-500 mb-2">{t("category")}</label>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => toggleCategory(cat)}
              className={`px-3 py-1 rounded-full text-xs border transition ${
                form.category.includes(cat)
                  ? "bg-green-600 text-white border-green-600"
                  : "border-gray-300 hover:border-green-400"
              }`}
            >
              {tCat(cat)}
            </button>
          ))}
        </div>
      </div>

      {/* Parent event */}
      <div className="md:col-span-2">
        <label className="block text-xs text-gray-500 mb-1">{t("parentEvent")}</label>
        <select
          value={form.parent_event_id}
          onChange={(e) => updateField("parent_event_id", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
        >
          <option value="">{t("noParent")}</option>
          {parentCandidates.map((e) => (
            <option key={e.id} value={e.id}>
              {getEventName(e, locale)} ({e.start_date?.slice(0, 10) ?? "—"})
            </option>
          ))}
        </select>
      </div>

      {/* Multilingual descriptions */}
      {(["ja", "zh", "en"] as const).map((lang) => (
        <div key={lang} className="md:col-span-2">
          <label className="block text-xs text-gray-500 mb-1">
            {t(`desc${lang.charAt(0).toUpperCase() + lang.slice(1)}` as any)}
          </label>
          <textarea
            rows={3}
            value={(form as any)[`description_${lang}`]}
            onChange={(e) => updateField(`description_${lang}`, e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
      ))}
    </div>
  );
}

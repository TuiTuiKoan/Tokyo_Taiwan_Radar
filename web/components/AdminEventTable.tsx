"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { type Event, type Locale, getEventName } from "@/lib/types";
import { useRouter } from "next/navigation";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";

interface Props {
  events: Event[];
  locale: Locale;
}

export default function AdminEventTable({ events: initialEvents, locale }: Props) {
  const t = useTranslations("admin");
  const tCat = useTranslations("categories");
  const router = useRouter();
  const supabase = createClient();

  const [events, setEvents] = useState<Event[]>(initialEvents);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [viewMode, setViewMode] = useState<"annotated" | "raw">("annotated");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  function toggleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function getSorted(list: Event[]) {
    if (!sortKey) return list;
    return [...list].sort((a, b) => {
      let va: any, vb: any;
      if (sortKey === "name") {
        va = getEventName(a, locale);
        vb = getEventName(b, locale);
      } else if (sortKey === "raw_title") {
        va = a.raw_title || getEventName(a, locale);
        vb = b.raw_title || getEventName(b, locale);
      } else {
        va = (a as any)[sortKey];
        vb = (b as any)[sortKey];
      }
      if (va == null) va = "";
      if (vb == null) vb = "";
      if (typeof va === "boolean") { va = va ? 1 : 0; vb = vb ? 1 : 0; }
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }

  const sortArrow = (key: string) =>
    sortKey === key
      ? <span className="ml-0.5 text-gray-800">{sortDir === "asc" ? "▲" : "▼"}</span>
      : <span className="ml-0.5 text-gray-300">▲</span>;

  function startNew() {
    setShowNew(true);
    setForm({ ...EMPTY_FORM });
  }

  function cancelNew() {
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

  async function handleSaveNew() {
    setSaving(true);
    const { data, error } = await supabase
      .from("events")
      .insert({
        ...form,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        parent_event_id: form.parent_event_id || null,
        source_id: `manual-${Date.now()}`,
      })
      .select()
      .single();
    if (error) {
      console.error("Insert failed:", error);
      alert(`Save failed: ${error.message}`);
    } else if (data) {
      setEvents((prev) => [data as Event, ...prev]);
    }
    setSaving(false);
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

  return (
    <div>
      {/* View toggle + New event button */}
      <div className="flex items-center gap-3 mb-4">
        {!showNew && (
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

      {/* New event inline form */}
      {showNew && (
        <div className="border border-green-300 rounded-xl p-6 mb-6 bg-green-50">
          <h2 className="font-bold text-lg mb-4">{t("newEvent")}</h2>
          <AdminEventForm
            form={form}
            t={t}
            tCat={tCat}
            updateField={updateField}
            toggleCategory={toggleCategory}
            events={events}
            editingId={null}
            locale={locale}
          />
          <div className="flex gap-3 mt-4">
            <button
              onClick={handleSaveNew}
              disabled={saving}
              className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              {saving ? "..." : t("save")}
            </button>
            <button
              onClick={cancelNew}
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
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("name")}>{t("name")}{sortArrow("name")}</th>
                <th className="py-2 pr-4 font-medium">{t("category")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("start_date")}>{t("startDate")}{sortArrow("start_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("end_date")}>{t("endDate")}{sortArrow("end_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("source_name")}>{t("sourceName")}{sortArrow("source_name")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceLink")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("is_paid")}>{t("isPaid")}{sortArrow("is_paid")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("is_active")}>{t("isActive")}{sortArrow("is_active")}</th>
                <th className="py-2" />
              </tr>
            ) : (
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("raw_title")}>{t("name")}{sortArrow("raw_title")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("source_name")}>{t("sourceName")}{sortArrow("source_name")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceLink")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("annotation_status")}>{t("annotationStatus")}{sortArrow("annotation_status")}</th>
                <th className="py-2" />
              </tr>
            )}
          </thead>
          <tbody>
            {getSorted(events).map((event) => (
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
                      <button
                        onClick={() => router.push(`/${locale}/admin/${event.id}`)}
                        className="text-blue-600 hover:underline text-xs"
                      >
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
                      <button
                        onClick={() => router.push(`/${locale}/admin/${event.id}`)}
                        className="text-blue-600 hover:underline text-xs"
                      >
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

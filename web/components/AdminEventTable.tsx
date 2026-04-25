"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { type Event, type Locale, getEventName, CATEGORIES } from "@/lib/types";
import { useRouter } from "next/navigation";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";

interface Props {
  events: Event[];
  locale: Locale;
}

export default function AdminEventTable({ events: initialEvents, locale }: Props) {
  const t = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tFilters = useTranslations("filters");
  const tEvent = useTranslations("event");
  const router = useRouter();
  const supabase = createClient();

  const [events, setEvents] = useState<Event[]>(initialEvents);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [viewMode, setViewMode] = useState<"annotated" | "raw">("annotated");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // Inline filters
  const [filterQ, setFilterQ] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [filterPaid, setFilterPaid] = useState("");
  const [filterIsActive, setFilterIsActive] = useState<"all" | "active" | "inactive">("all");
  const [filterTimeMode, setFilterTimeMode] = useState<"active" | "all" | "past">("active");
  const [filterDateFrom, setFilterDateFrom] = useState("2024-01-01");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [filterLocation, setFilterLocation] = useState<"" | "tokyo" | "other_japan" | "taiwan">("")
  const [filterAnnotation, setFilterAnnotation] = useState<"" | "pending" | "annotated" | "error">("");;

  const TOKYO_MARKERS_ADMIN = ["東京", "新宿区", "港区", "渋谷区", "千代田区", "文京区", "台東区"];
  const TAIWAN_MARKERS_ADMIN = ["台北", "台中", "台南", "高雄", "台湾", "台灣"];
  function isTokyoAddr(addr: string | null | undefined): boolean {
    if (!addr || addr.trim() === "") return true;
    return TOKYO_MARKERS_ADMIN.some((m) => addr.includes(m));
  }

  function getFiltered(list: Event[]) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return list.filter((e) => {
      if (filterQ) {
        const q = filterQ.toLowerCase();
        const name = getEventName(e, locale).toLowerCase();
        const raw = (e.raw_title || "").toLowerCase();
        if (!name.includes(q) && !raw.includes(q)) return false;
      }
      if (filterCategory && !(e.category || []).includes(filterCategory)) return false;
      if (filterPaid === "free" && e.is_paid !== false) return false;
      if (filterPaid === "paid" && e.is_paid !== true) return false;
      if (filterIsActive === "active" && !e.is_active) return false;
      if (filterIsActive === "inactive" && e.is_active) return false;
      if (filterTimeMode === "active") {
        // Show ongoing: end_date >= today OR end_date is null
        if (e.end_date && new Date(e.end_date) < today) return false;
      } else if (filterTimeMode === "past") {
        // Show historical: end_date < today (or no end_date but start_date < today)
        const isPast = e.end_date
          ? new Date(e.end_date) < today
          : e.start_date
          ? new Date(e.start_date) < today
          : false;
        if (!isPast) return false;
        if (filterDateFrom) {
          const d = e.start_date ? new Date(e.start_date) : null;
          if (!d || d < new Date(filterDateFrom)) return false;
        }
        if (filterDateTo) {
          const d = e.start_date ? new Date(e.start_date) : null;
          if (!d || d > new Date(filterDateTo + "T23:59:59")) return false;
        }
      }
      if (filterLocation === "tokyo") {
        if (!isTokyoAddr(e.location_address)) return false;
      } else if (filterLocation === "taiwan") {
        const addr = e.location_address || "";
        if (!TAIWAN_MARKERS_ADMIN.some((m) => addr.includes(m))) return false;
      } else if (filterLocation === "other_japan") {
        const addr = e.location_address || "";
        if (!addr.trim()) return false;
        if (isTokyoAddr(addr)) return false;
        if (TAIWAN_MARKERS_ADMIN.some((m) => addr.includes(m))) return false;
      }
      if (filterAnnotation && (e as any).annotation_status !== filterAnnotation) return false;
      return true;
    });
  }

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

  function getAnnotationBadgeClass(status: string) {
    if (status === "annotated") return "bg-green-50 text-green-700";
    if (status === "error") return "bg-red-50 text-red-600";
    return "bg-yellow-50 text-yellow-700";
  }

  function getAnnotationLabel(status: string) {
    if (status === "annotated") return t("annotated");
    if (status === "error") return t("error");
    return t("pending");
  }

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
    // Soft-delete: set is_active = false instead of removing the row.
    // This permanently blocks the scraper from re-inserting the event.
    await supabase.from("events").update({ is_active: false }).eq("id", id);
    setEvents((prev) => prev.filter((e) => e.id !== id));
    setSelected((prev) => { const next = new Set(prev); next.delete(id); return next; });
  }

  async function handleBulkDelete() {
    if (selected.size === 0) return;
    const msg = t("confirmBulkDelete", { count: selected.size });
    if (!window.confirm(msg)) return;
    setBulkDeleting(true);
    const ids = Array.from(selected);
    // Soft-delete: set is_active = false instead of removing rows.
    // This permanently blocks the scraper from re-inserting these events.
    await supabase.from("events").update({ is_active: false }).in("id", ids);
    setEvents((prev) => prev.filter((e) => !selected.has(e.id)));
    setSelected(new Set());
    setBulkDeleting(false);
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    const visible = getSorted(getFiltered(events)).map((e) => e.id);
    const allSelected = visible.every((id) => selected.has(id));
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev);
        visible.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelected((prev) => {
        const next = new Set(prev);
        visible.forEach((id) => next.add(id));
        return next;
      });
    }
  }

  async function handleReannotate(id: string) {
    await supabase.from("events").update({ annotation_status: "pending" }).eq("id", id);
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, annotation_status: "pending" } : e))
    );
  }

  async function handleToggleActive(id: string, newValue: boolean) {
    await supabase.from("events").update({ is_active: newValue }).eq("id", id);
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, is_active: newValue } : e))
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

      {/* Inline filter bar */}
      <div className="bg-gray-50 rounded-xl px-4 py-3 mb-3 flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("name")}</label>
          <input
            type="search"
            value={filterQ}
            onChange={(e) => setFilterQ(e.target.value)}
            placeholder={tFilters("searchPlaceholder")}
            className="h-9 border border-gray-300 rounded-lg px-3 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("category")}</label>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("filterAll")}</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>{tCat(cat as any)}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("isPaid")}</label>
          <select
            value={filterPaid}
            onChange={(e) => setFilterPaid(e.target.value)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("filterAll")}</option>
            <option value="free">{tEvent("free")}</option>
            <option value="paid">{tEvent("paid")}</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("isActive")}</label>
          <select
            value={filterIsActive}
            onChange={(e) => setFilterIsActive(e.target.value as any)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="all">{t("filterAll")}</option>
            <option value="active">{t("filterActive")}</option>
            <option value="inactive">{t("filterInactive")}</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{tFilters("timeMode")}</label>
          <select
            value={filterTimeMode}
            onChange={(e) => {
              const mode = e.target.value as "active" | "all" | "past";
              setFilterTimeMode(mode);
              if (mode !== "past") {
                setFilterDateFrom("2024-01-01");
                setFilterDateTo("");
              } else {
                setFilterDateFrom((prev) => prev || "2024-01-01");
              }
            }}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="active">{tFilters("timeModeActive")}</option>
            <option value="all">{t("filterAll")}</option>
            <option value="past">{t("filterPast")}</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{tFilters("location")}</label>
          <select
            value={filterLocation}
            onChange={(e) => setFilterLocation(e.target.value as any)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{tFilters("allLocations")}</option>
            <option value="tokyo">{tFilters("locationTokyo")}</option>
            <option value="other_japan">{tFilters("locationOtherJapan")}</option>
            <option value="taiwan">{tFilters("locationTaiwan")}</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("filterAnnotationStatus")}</label>
          <select
            value={filterAnnotation}
            onChange={(e) => setFilterAnnotation(e.target.value as any)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("filterAll")}</option>
            <option value="annotated">{t("annotated")}</option>
            <option value="pending">{t("filterPendingReannotation")}</option>
            <option value="error">{t("error")}</option>
          </select>
        </div>
        {filterTimeMode === "past" && (
          <>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 font-medium">{tFilters("dateFrom")}</label>
              <input
                type="date"
                value={filterDateFrom}
                onChange={(e) => setFilterDateFrom(e.target.value)}
                className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500 font-medium">{tFilters("dateTo")}</label>
              <input
                type="date"
                value={filterDateTo}
                onChange={(e) => setFilterDateTo(e.target.value)}
                className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              />
            </div>
          </>
        )}
        {(filterQ || filterCategory || filterPaid || filterIsActive !== "all" || filterTimeMode !== "active" || filterDateFrom || filterDateTo || filterLocation || filterAnnotation) && (
          <button
            onClick={() => { setFilterQ(""); setFilterCategory(""); setFilterPaid(""); setFilterIsActive("all"); setFilterTimeMode("active"); setFilterDateFrom("2024-01-01"); setFilterDateTo(""); setFilterLocation(""); setFilterAnnotation(""); }}
            className="text-xs text-red-500 hover:text-red-700 underline self-end pb-1"
          >
            {tFilters("reset")}
          </button>
        )}
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-3 px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm">
          <span className="text-red-700 font-medium">{t("selectedCount", { count: selected.size })}</span>
          <button
            onClick={handleBulkDelete}
            disabled={bulkDeleting}
            className="ml-auto bg-red-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-red-700 disabled:opacity-50 transition"
          >
            {bulkDeleting ? "..." : t("bulkDelete")}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-gray-500 hover:text-gray-700 text-xs transition"
          >
            ✕
          </button>
        </div>
      )}

      {/* Events table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            {viewMode === "annotated" ? (
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-2 w-8">
                  <input
                    type="checkbox"
                    checked={getSorted(getFiltered(events)).length > 0 && getSorted(getFiltered(events)).every((e) => selected.has(e.id))}
                    onChange={toggleSelectAll}
                    className="rounded cursor-pointer"
                    title={t("selectAll")}
                  />
                </th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("name")}>{t("name")}{sortArrow("name")}</th>
                <th className="py-2 pr-4 font-medium">{t("category")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("start_date")}>{t("startDate")}{sortArrow("start_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("end_date")}>{t("endDate")}{sortArrow("end_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("source_name")}>{t("sourceName")}{sortArrow("source_name")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceLink")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("annotation_status")}>{t("annotationStatus")}{sortArrow("annotation_status")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("is_paid")}>{t("isPaid")}{sortArrow("is_paid")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("is_active")}>{t("isActive")}{sortArrow("is_active")}</th>
                <th className="py-2" />
              </tr>
            ) : (
              <tr className="border-b text-left text-gray-500">
                <th className="py-2 pr-2 w-8">
                  <input
                    type="checkbox"
                    checked={getSorted(getFiltered(events)).length > 0 && getSorted(getFiltered(events)).every((e) => selected.has(e.id))}
                    onChange={toggleSelectAll}
                    className="rounded cursor-pointer"
                    title={t("selectAll")}
                  />
                </th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("raw_title")}>{t("name")}{sortArrow("raw_title")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("source_name")}>{t("sourceName")}{sortArrow("source_name")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceLink")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("annotation_status")}>{t("annotationStatus")}{sortArrow("annotation_status")}</th>
                <th className="py-2" />
              </tr>
            )}
          </thead>
          <tbody>
            {getSorted(getFiltered(events)).map((event) => (
              viewMode === "annotated" ? (
                <tr key={event.id} className="border-b hover:bg-gray-50 transition">
                  <td className="py-2 pr-2">
                    <input
                      type="checkbox"
                      checked={selected.has(event.id)}
                      onChange={() => toggleSelect(event.id)}
                      className="rounded cursor-pointer"
                    />
                  </td>
                  <td className="py-2 pr-4 max-w-xs">
                    <a
                      href={`/${locale}/events/${event.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate block hover:underline hover:text-green-700 transition"
                      title={t("viewFrontend")}
                    >
                      {getEventName(event, locale)}
                    </a>
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
                    <span className={`text-xs px-2 py-0.5 rounded-full ${getAnnotationBadgeClass(event.annotation_status)}`}>
                      {getAnnotationLabel(event.annotation_status)}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    {event.is_paid === false ? (
                      <span className="text-blue-600 text-xs">{tEvent("free")}</span>
                    ) : event.is_paid === true ? (
                      <span className="text-amber-600 text-xs">{tEvent("paid")}</span>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="py-2 pr-4">
                    <button
                      onClick={() => handleToggleActive(event.id, !event.is_active)}
                      title={event.is_active ? t("filterActive") : t("filterInactive")}
                      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 focus:outline-none ${
                        event.is_active ? "bg-green-500" : "bg-gray-300"
                      }`}
                    >
                      <span className={`inline-block h-4 w-4 mt-0.5 rounded-full bg-white shadow transition-transform duration-200 ${
                        event.is_active ? "translate-x-4" : "translate-x-0.5"
                      }`} />
                    </button>
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
              ) : (
                <tr key={event.id} className="border-b hover:bg-gray-50 transition">
                  <td className="py-2 pr-2">
                    <input
                      type="checkbox"
                      checked={selected.has(event.id)}
                      onChange={() => toggleSelect(event.id)}
                      className="rounded cursor-pointer"
                    />
                  </td>
                  <td className="py-2 pr-4 max-w-sm">
                    <a
                      href={`/${locale}/events/${event.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-gray-800 line-clamp-2 block hover:underline hover:text-green-700 transition"
                      title={t("viewFrontend")}
                    >
                      {event.raw_title || getEventName(event, locale)}
                    </a>
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
                    <span className={`text-xs px-2 py-0.5 rounded-full ${getAnnotationBadgeClass(event.annotation_status)}`}>
                      {getAnnotationLabel(event.annotation_status)}
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

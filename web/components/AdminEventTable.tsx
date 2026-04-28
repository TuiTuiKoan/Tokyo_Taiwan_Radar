"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { type Event, type Locale, getEventName, CATEGORY_GROUPS } from "@/lib/types";
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
  const [bulkToggling, setBulkToggling] = useState(false);
  const [bulkForceRescrapings, setBulkForceRescrapings] = useState(false);
  const [bulkRemovingCategory, setBulkRemovingCategory] = useState(false);

  // Inline filters
  const [filterQ, setFilterQ] = useState("");
  const [filterCategories, setFilterCategories] = useState<string[]>([]);
  const [catDropdownOpen, setCatDropdownOpen] = useState(false);
  const catDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (catDropdownRef.current && !catDropdownRef.current.contains(e.target as Node)) {
        setCatDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);
  const [filterPaid, setFilterPaid] = useState("");
  const [filterIsActive, setFilterIsActive] = useState<"all" | "active" | "inactive">("active");
  const [filterTimeMode, setFilterTimeMode] = useState<"active" | "all" | "past">("active");
  const [filterDateFrom, setFilterDateFrom] = useState("2024-01-01");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [filterLocation, setFilterLocation] = useState<"" | "tokyo" | "other_japan" | "taiwan" | "online">("")
  const [filterAnnotation, setFilterAnnotation] = useState<"" | "pending" | "annotated" | "reviewed" | "error">("");;  const [filterSource, setFilterSource] = useState("");
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
      if (filterCategories.length > 0 && !filterCategories.some((c) => (e.category || []).includes(c))) return false;
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
        if (addr.includes("オンライン")) return false;
        if (isTokyoAddr(addr)) return false;
        if (TAIWAN_MARKERS_ADMIN.some((m) => addr.includes(m))) return false;
      } else if (filterLocation === "online") {
        if (!(e.location_name || "").includes("オンライン")) return false;
      }
  if (filterAnnotation && (e as any).annotation_status !== filterAnnotation) return false;
      if (filterSource && (e as any).source_name !== filterSource) return false;
      return true;
    });
  }

  /** Counts per source_name, applying all filters EXCEPT filterSource */
  const sourceCountMap = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const base = events.filter((e) => {
      if (filterQ) {
        const q = filterQ.toLowerCase();
        const name = getEventName(e, locale).toLowerCase();
        const raw = (e.raw_title || "").toLowerCase();
        if (!name.includes(q) && !raw.includes(q)) return false;
      }
      if (filterCategories.length > 0 && !filterCategories.some((c) => (e.category || []).includes(c))) return false;
      if (filterPaid === "free" && e.is_paid !== false) return false;
      if (filterPaid === "paid" && e.is_paid !== true) return false;
      if (filterIsActive === "active" && !e.is_active) return false;
      if (filterIsActive === "inactive" && e.is_active) return false;
      if (filterTimeMode === "active") {
        if (e.end_date && new Date(e.end_date) < today) return false;
      } else if (filterTimeMode === "past") {
        const isPast = e.end_date
          ? new Date(e.end_date) < today
          : e.start_date ? new Date(e.start_date) < today : false;
        if (!isPast) return false;
        if (filterDateFrom) { const d = e.start_date ? new Date(e.start_date) : null; if (!d || d < new Date(filterDateFrom)) return false; }
        if (filterDateTo) { const d = e.start_date ? new Date(e.start_date) : null; if (!d || d > new Date(filterDateTo + "T23:59:59")) return false; }
      }
      if (filterLocation === "tokyo") { if (!isTokyoAddr(e.location_address)) return false; }
      else if (filterLocation === "taiwan") { const addr = e.location_address || ""; if (!TAIWAN_MARKERS_ADMIN.some((m) => addr.includes(m))) return false; }
      else if (filterLocation === "other_japan") { const addr = e.location_address || ""; if (!addr.trim() || addr.includes("オンライン") || isTokyoAddr(addr) || TAIWAN_MARKERS_ADMIN.some((m) => addr.includes(m))) return false; }
      else if (filterLocation === "online") { if (!(e.location_name || "").includes("オンライン")) return false; }
      if (filterAnnotation && (e as any).annotation_status !== filterAnnotation) return false;
      return true;
    });
    const map: Record<string, number> = {};
    for (const e of base) {
      const s = (e as any).source_name as string;
      map[s] = (map[s] ?? 0) + 1;
    }
    return map;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, filterQ, filterCategories, filterPaid, filterIsActive, filterTimeMode, filterDateFrom, filterDateTo, filterLocation, filterAnnotation, locale]);

  // Intersection of categories across all selected events
  const commonCategories = useMemo(() => {
    if (selected.size === 0) return [];
    const sel = events.filter((e) => selected.has(e.id));
    if (sel.length === 0) return [];
    const first = sel[0].category ?? [];
    return first.filter((cat) => sel.every((e) => (e.category ?? []).includes(cat)));
  }, [selected, events]);

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
    if (status === "reviewed") return "bg-blue-50 text-blue-700";
    if (status === "error") return "bg-red-50 text-red-600";
    return "bg-yellow-50 text-yellow-700";
  }

  function getAnnotationLabel(status: string) {
    if (status === "annotated") return t("filterAnnotatedShort");
    if (status === "reviewed") return t("filterReviewedShort");
    if (status === "error") return t("filterErrorShort");
    return t("filterPendingShort");
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

  async function handleBulkToggleActive(targetActive: boolean) {
    if (selected.size === 0) return;
    setBulkToggling(true);
    const ids = Array.from(selected);
    const { error } = await supabase.from("events").update({ is_active: targetActive }).in("id", ids);
    if (error) {
      alert(`操作失敗：${error.message}`);
      setBulkToggling(false);
      return;
    }
    setEvents((prev) => prev.map((e) => selected.has(e.id) ? { ...e, is_active: targetActive } : e));
    setSelected(new Set());
    setBulkToggling(false);
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

  async function handleBulkForceRescrape() {
    if (selected.size === 0) return;
    setBulkForceRescrapings(true);
    const ids = Array.from(selected);
    const { error } = await supabase.from("events").update({ force_rescrape: true }).in("id", ids);
    if (error) {
      alert(`操作失敗：${error.message}`);
      setBulkForceRescrapings(false);
      return;
    }
    setEvents((prev) => prev.map((e) => selected.has(e.id) ? { ...e, force_rescrape: true } : e));
    setSelected(new Set());
    setBulkForceRescrapings(false);
  }

  async function handleBulkRemoveCategory(cat: string) {
    if (selected.size === 0) return;
    setBulkRemovingCategory(true);
    const selectedEvents = events.filter((e) => selected.has(e.id));
    let hasError = false;

    await Promise.all(
      selectedEvents.map(async (e) => {
        const prevCategory = e.category ?? [];
        const newCategory = prevCategory.filter((c) => c !== cat);
        // Update event category
        const { error } = await supabase.from("events").update({ category: newCategory }).eq("id", e.id);
        if (error) { hasError = true; return; }
        // Write correction to category_corrections for AI feedback loop
        await supabase.from("category_corrections").upsert(
          {
            event_id: e.id,
            raw_title: e.raw_title ?? null,
            raw_description: e.raw_description ? e.raw_description.slice(0, 2000) : null,
            ai_category: prevCategory,
            corrected_category: newCategory,
          },
          { onConflict: "event_id" }
        );
      })
    );

    if (hasError) {
      alert("部分更新失敗，請重新整理頁面確認結果");
    } else {
      setEvents((prev) =>
        prev.map((e) =>
          selected.has(e.id)
            ? { ...e, category: (e.category ?? []).filter((c) => c !== cat) }
            : e
        )
      );
    }
    setBulkRemovingCategory(false);
  }

  async function handleToggleForceRescrape(id: string) {
    const ev = events.find((e) => e.id === id);
    if (!ev) return;
    const newValue = !ev.force_rescrape;
    await supabase.from("events").update({ force_rescrape: newValue }).eq("id", id);
    setEvents((prev) => prev.map((e) => e.id === id ? { ...e, force_rescrape: newValue } : e));
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
      <div className="bg-gray-50 rounded-xl px-4 py-3 mb-3 space-y-2">
        {/* Row 1: 搜尋、類型、地點、票價、時間、日期 */}
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{tFilters("search")}</label>
            <input
              type="search"
              value={filterQ}
              onChange={(e) => setFilterQ(e.target.value)}
              placeholder={tFilters("searchPlaceholder")}
              className="h-9 border border-gray-300 rounded-lg px-3 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-green-400"
            />
          </div>
          <div className="flex flex-col gap-1" ref={catDropdownRef}>
            <label className="text-xs text-gray-500 font-medium">{tFilters("category")}</label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setCatDropdownOpen((o) => !o)}
                className="h-9 min-w-[9rem] flex items-center justify-between gap-2 border border-gray-300 rounded-lg px-3 text-sm bg-gray-50 hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
              >
                <span className={filterCategories.length > 0 ? "text-green-700 font-medium" : "text-gray-500"}>
                  {filterCategories.length > 0 ? `${t("category")} (${filterCategories.length})` : t("filterAll")}
                </span>
                <span className="text-gray-400 text-xs">{catDropdownOpen ? "▲" : "▼"}</span>
              </button>
              {catDropdownOpen && (
                <div className="absolute z-50 top-10 left-0 w-72 bg-white border border-gray-200 rounded-xl shadow-lg py-2 max-h-80 overflow-y-auto">
                  {filterCategories.length > 0 && (
                    <div className="px-3 pb-1.5 border-b border-gray-100 mb-1">
                      <button type="button" onClick={() => setFilterCategories([])} className="text-xs text-red-500 hover:text-red-700 underline">
                        {t("filterAll")}
                      </button>
                    </div>
                  )}
                  {CATEGORY_GROUPS.map((group) => (
                    <div key={group.labelKey} className="px-3 py-1">
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">{tCat(group.labelKey as any)}</p>
                      {group.categories.map((cat) => {
                        const checked = filterCategories.includes(cat);
                        return (
                          <label key={cat} className="flex items-center gap-2 py-0.5 cursor-pointer hover:text-green-700">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => setFilterCategories((prev) =>
                                prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
                              )}
                              className="accent-green-600 w-3.5 h-3.5"
                            />
                            <span className="text-sm text-gray-700">{tCat(cat as any)}</span>
                          </label>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
            </div>
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
              <option value="online">{tFilters("locationOnline")}</option>
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
              <option value="all">{tFilters("timeModeAll")}</option>
              <option value="past">{tFilters("timeModePast")}</option>
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
        </div>

        {/* Row 2: 來源名稱、開放檢視、標註狀態、清除 */}
        <div className="flex flex-wrap gap-3 items-end border-t border-gray-200 pt-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("sourceName")}</label>
            <select
              value={filterSource}
              onChange={(e) => setFilterSource(e.target.value)}
              className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("filterAll")}</option>
              {Array.from(new Set(events.map((e) => (e as any).source_name as string)))
                .filter(Boolean)
                .sort()
                .map((s) => (
                  <option key={s} value={s}>{s}{sourceCountMap[s] !== undefined ? ` (${sourceCountMap[s]})` : " (0)"}</option>
                ))}
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
            <label className="text-xs text-gray-500 font-medium">{t("annotationStatusLabel")}</label>
            <select
              value={filterAnnotation}
              onChange={(e) => setFilterAnnotation(e.target.value as any)}
              className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("filterAll")}</option>
              <option value="pending">{t("filterPendingShort")}</option>
              <option value="annotated">{t("filterAnnotatedShort")}</option>
              <option value="reviewed">{t("filterReviewedShort")}</option>
              <option value="error">{t("filterErrorShort")}</option>
            </select>
          </div>
          {(filterQ || filterCategories.length > 0 || filterPaid || filterIsActive !== "active" || filterTimeMode !== "active" || filterDateFrom || filterDateTo || filterLocation || filterAnnotation || filterSource) && (
            <button
              onClick={() => { setFilterQ(""); setFilterCategories([]); setFilterPaid(""); setFilterIsActive("active"); setFilterTimeMode("active"); setFilterDateFrom("2024-01-01"); setFilterDateTo(""); setFilterLocation(""); setFilterAnnotation(""); setFilterSource(""); }}
              className="text-xs text-red-500 hover:text-red-700 underline self-end pb-1"
            >
              {tFilters("reset")}
            </button>
          )}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="mb-3 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-2">
          {/* Row 1: count + action buttons */}
          <div className="flex items-center gap-3">
            <span className="text-blue-700 font-medium">{t("selectedCount", { count: selected.size })}</span>
            <button
              onClick={() => handleBulkToggleActive(false)}
              disabled={bulkToggling}
              className="ml-auto bg-gray-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-gray-700 disabled:opacity-50 transition"
            >
              {bulkToggling ? "..." : t("bulkHide")}
            </button>
            <button
              onClick={() => handleBulkToggleActive(true)}
              disabled={bulkToggling}
              className="bg-green-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-green-700 disabled:opacity-50 transition"
            >
              {bulkToggling ? "..." : t("bulkShow")}
            </button>
            <button
              onClick={handleBulkForceRescrape}
              disabled={bulkForceRescrapings}
              className="bg-orange-500 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-orange-600 disabled:opacity-50 transition"
              title={t("bulkForceRescrape")}
            >
              {bulkForceRescrapings ? "..." : `🔁 ${t("bulkForceRescrape")}`}
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="text-gray-500 hover:text-gray-700 text-xs transition"
            >
              ✕
            </button>
          </div>
          {/* Row 2: common category removal — only shown when intersection is non-empty */}
          {commonCategories.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap border-t border-blue-200 pt-2">
              <span className="text-xs text-blue-600 font-medium">{t("bulkCommonCategories")}：</span>
              {commonCategories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => handleBulkRemoveCategory(cat)}
                  disabled={bulkRemovingCategory}
                  className="text-xs bg-white border border-blue-300 text-blue-700 px-2 py-0.5 rounded-full hover:bg-red-50 hover:border-red-300 hover:text-red-700 transition disabled:opacity-50"
                  title={t("bulkRemoveCategoryHint")}
                >
                  {tCat(cat as any)} ×
                </button>
              ))}
            </div>
          )}
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
                <th className="py-2 pr-4 font-medium">{t("address")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("start_date")}>{t("startDate")}{sortArrow("start_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("end_date")}>{t("endDate")}{sortArrow("end_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("source_name")}>{t("sourceName")}{sortArrow("source_name")}</th>
                <th className="py-2 pr-4 font-medium">{t("sourceLink")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("annotation_status")}>{t("annotationStatusLabel")}{sortArrow("annotation_status")}</th>
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
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-gray-800" onClick={() => toggleSort("annotation_status")}>{t("annotationStatusLabel")}{sortArrow("annotation_status")}</th>
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
                    {event.force_rescrape && (
                      <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">
                        🔁 {t("forceRescrapeQueued")}
                      </span>
                    )}
                    {(() => {
                      const missing = [
                        !(event as any).name_zh && "name_zh",
                        !(event as any).name_en && "name_en",
                      ].filter(Boolean) as string[];
                      if (missing.length === 0) return null;
                      return (
                        <span
                          className="inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded-full bg-red-100 text-red-700 font-medium"
                          title={`缺少翻譯：${missing.join(", ")}`}
                        >
                          ⚠ {missing.join(" / ")}
                        </span>
                      );
                    })()}
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
                  <td className="py-2 pr-4 text-xs max-w-[130px]">
                    {(() => {
                      const addr = event.location_address;
                      if (!addr) return <span className="text-gray-300">—</span>;
                      const isOnline = /オンライン|online|線上/i.test(addr);
                      if (isOnline) return <span className="text-blue-500">線上</span>;
                      return <span className="text-gray-500 truncate block" title={addr}>{addr}</span>;
                    })()}
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
                      <button
                        onClick={() => handleToggleForceRescrape(event.id)}
                        title={event.force_rescrape ? t("forceRescrapeOff") : t("forceRescrapeOn")}
                        className={`text-xs hover:underline ${event.force_rescrape ? "text-orange-600 font-medium" : "text-gray-400 hover:text-orange-500"}`}
                      >
                        🔁
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
                    {event.force_rescrape && (
                      <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">
                        🔁 {t("forceRescrapeQueued")}
                      </span>
                    )}
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
                      <button
                        onClick={() => handleToggleForceRescrape(event.id)}
                        title={event.force_rescrape ? t("forceRescrapeOff") : t("forceRescrapeOn")}
                        className={`text-xs hover:underline ${event.force_rescrape ? "text-orange-600 font-medium" : "text-gray-400 hover:text-orange-500"}`}
                      >
                        🔁
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

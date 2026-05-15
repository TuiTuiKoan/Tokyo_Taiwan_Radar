"use client";

import { useState, useRef, useEffect, useMemo } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { type Event, type Locale, getEventName, CATEGORY_GROUPS, type Work, getWorkTitle } from "@/lib/types";
import { useRouter } from "next/navigation";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";
import AdminCreateWorkModal from "@/components/AdminCreateWorkModal";
import DesignSelect from "@/components/DesignSelect";
import { assignWorkToEvent } from "@/app/actions/works";
import { REGIONS_WITH_CITY, REGION_PREFECTURES, PREFECTURE_LABELS_EN, CITY_OTHER, matchesCity, type RegionWithCity } from "@/lib/regionPrefectures";
import { getCityLabel } from "@/lib/cityLabel";

interface Props {
  events: Event[];
  locale: Locale;
  initialWorks?: Work[];
}

export default function AdminEventTable({ events: initialEvents, locale, initialWorks = [] }: Props) {
  const t = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tFilters = useTranslations("filters");
  const tEvent = useTranslations("event");
  const tOrgType = useTranslations("organizerType");
  const tEventForm = useTranslations("eventForm");
  const router = useRouter();
  const supabase = createClient();

  const [events, setEvents] = useState<Event[]>(initialEvents);
  const [showNew, setShowNew] = useState(false);

  // Works list — pre-populated from server-side fetch (initialWorks prop),
  // client-side effect re-fetches after a new work is created via the modal.
  const [works, setWorks] = useState<Work[]>(initialWorks);
  useEffect(() => {
    (async () => {
      const { data } = await supabase
        .from("works")
        .select("id,work_type,original_title,title_ja,title_zh,title_en")
        .order("title_ja", { ascending: true });
      if (data) setWorks(data as Work[]);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const workMap = useMemo<Record<string, Work>>(() => {
    const m: Record<string, Work> = {};
    for (const w of works) m[w.id] = w;
    return m;
  }, [works]);
  const [editingWorkFor, setEditingWorkFor] = useState<string | null>(null);
  const [workQuery, setWorkQuery] = useState("");

  // Build id→event map for parent event name lookup on sub-event rows
  const eventMap = useMemo<Record<string, Event>>(() => {
    const m: Record<string, Event> = {};
    for (const e of events) m[e.id] = e;
    return m;
  }, [events]);

  // Count how many events (across ALL loaded events) are merged into each primary event
  const mergeCountMap = useMemo<Record<string, number>>(() => {
    const m: Record<string, number> = {};
    for (const e of events) {
      if (e.merged_into_event_id) {
        m[e.merged_into_event_id] = (m[e.merged_into_event_id] ?? 0) + 1;
      }
    }
    return m;
  }, [events]);
  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [posterPreview, setPosterPreview] = useState<string | null>(null);
  const [ocrFilled, setOcrFilled] = useState(false);
  const [annotating, setAnnotating] = useState(false);
  const [savedEventId, setSavedEventId] = useState<string | null>(null);
  const [enrichedReady, setEnrichedReady] = useState(false);
  const posterFileRef = useRef<HTMLInputElement>(null);
  const [viewMode, setViewMode] = useState<"annotated" | "raw">("annotated");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkToggling, setBulkToggling] = useState(false);
  const [bulkForceRescrapings, setBulkForceRescrapings] = useState(false);
  const [bulkRemovingCategory, setBulkRemovingCategory] = useState(false);
  const [bulkAddingCategory, setBulkAddingCategory] = useState(false);
  const [bulkAddCatPending, setBulkAddCatPending] = useState<Set<string>>(new Set());
  const [bulkAddCatOpen, setBulkAddCatOpen] = useState(false);
  const [showCreateWorkModal, setShowCreateWorkModal] = useState(false);
  const [bulkWorkOpen, setBulkWorkOpen] = useState(false);
  const [bulkWorkQuery, setBulkWorkQuery] = useState("");
  const [bulkAssigningWork, setBulkAssigningWork] = useState(false);
  const [expandedCategoryId, setExpandedCategoryId] = useState<string | null>(null);
  const bulkAddCatRef = useRef<HTMLDivElement>(null);
  const bulkWorkRef = useRef<HTMLDivElement>(null);

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
      if (bulkAddCatRef.current && !bulkAddCatRef.current.contains(e.target as Node)) {
        setBulkAddCatOpen(false);
      }
      if (bulkWorkRef.current && !bulkWorkRef.current.contains(e.target as Node)) {
        setBulkWorkOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Realtime: reflect event UPDATEs (e.g. from report confirmations) instantly
  // Requires migration 029_realtime_events.sql to be applied first.
  useEffect(() => {
    const channel = supabase
      .channel("admin-events-live")
      .on(
        "postgres_changes",
        { event: "UPDATE", schema: "public", table: "events" },
        async (payload) => {
          const { data } = await supabase
            .from("events")
            .select("*")
            .eq("id", payload.new.id)
            .single();
          if (data) {
            setEvents((prev) => prev.map((e) => (e.id === data.id ? (data as Event) : e)));
          }
        }
      )
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [filterPaid, setFilterPaid] = useState("");
  const [filterIsActive, setFilterIsActive] = useState<"all" | "active" | "inactive" | "merged">("all");
  const [filterTimeMode, setFilterTimeMode] = useState<"active" | "all" | "past">("all");
  const [filterDateFrom, setFilterDateFrom] = useState("2024-01-01");
  const [filterDateTo, setFilterDateTo] = useState("");
  const [filterLocation, setFilterLocation] = useState<"" | "tokyo" | "kanto" | "tohoku" | "chubu" | "chugoku" | "online" | "tv" | "overseas">("")
  const [filterCity, setFilterCity] = useState("");
  const [filterAnnotation, setFilterAnnotation] = useState<"" | "pending" | "annotated" | "reviewed" | "error">("");;  const [filterSource, setFilterSource] = useState("");
  const [filterOrgType, setFilterOrgType] = useState("");
  const [filterEventForm, setFilterEventForm] = useState("");
  const filterBarRef = useRef<HTMLDivElement>(null);
  const [filterBarHeight, setFilterBarHeight] = useState(0);
  useEffect(() => {
    const el = filterBarRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setFilterBarHeight(el.offsetHeight));
    ro.observe(el);
    setFilterBarHeight(el.offsetHeight);
    return () => ro.disconnect();
  }, []);

  // Restore admin filters from sessionStorage on mount
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("ttr_admin_filters");
      if (!saved) return;
      const s = JSON.parse(saved);
      if (s.filterQ !== undefined) setFilterQ(s.filterQ);
      if (s.filterCategories !== undefined) setFilterCategories(s.filterCategories);
      if (s.filterPaid !== undefined) setFilterPaid(s.filterPaid);
      if (s.filterIsActive !== undefined) setFilterIsActive(s.filterIsActive);
      if (s.filterTimeMode !== undefined) setFilterTimeMode(s.filterTimeMode);
      if (s.filterDateFrom !== undefined) setFilterDateFrom(s.filterDateFrom);
      if (s.filterDateTo !== undefined) setFilterDateTo(s.filterDateTo);
      if (s.filterLocation !== undefined) setFilterLocation(s.filterLocation);
      if (s.filterCity !== undefined) setFilterCity(s.filterCity);
      if (s.filterAnnotation !== undefined) setFilterAnnotation(s.filterAnnotation);
      if (s.filterSource !== undefined) setFilterSource(s.filterSource);
      if (s.filterOrgType !== undefined) setFilterOrgType(s.filterOrgType);
      if (s.filterEventForm !== undefined) setFilterEventForm(s.filterEventForm);
      if (s.sortKey !== undefined) setSortKey(s.sortKey);
      if (s.sortDir !== undefined) setSortDir(s.sortDir);
      if (s.viewMode !== undefined) setViewMode(s.viewMode);
    } catch {
      sessionStorage.removeItem("ttr_admin_filters");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save admin filters to sessionStorage whenever they change
  useEffect(() => {
    try {
      sessionStorage.setItem("ttr_admin_filters", JSON.stringify({
        filterQ, filterCategories, filterPaid, filterIsActive, filterTimeMode,
        filterDateFrom, filterDateTo, filterLocation, filterCity, filterAnnotation,
        filterSource, filterOrgType, filterEventForm, sortKey, sortDir, viewMode,
      }));
    } catch {
      // ignore quota errors
    }
  }, [filterQ, filterCategories, filterPaid, filterIsActive, filterTimeMode,
      filterDateFrom, filterDateTo, filterLocation, filterCity, filterAnnotation,
      filterSource, filterOrgType, filterEventForm, sortKey, sortDir, viewMode]);

  // Restore scroll position from sessionStorage on mount (locale switch + edit return)
  useEffect(() => {
    // ttr_locale_scroll: written by Navbar on locale switch
    const localeScroll = sessionStorage.getItem("ttr_locale_scroll");
    if (localeScroll) {
      sessionStorage.removeItem("ttr_locale_scroll");
      const y = parseInt(localeScroll, 10);
      if (!isNaN(y)) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            window.scrollTo({ top: y, behavior: "instant" });
          });
        });
      }
      return;
    }
    // ttr_admin_scroll: written before navigating to admin/[id] edit page
    const adminScroll = sessionStorage.getItem("ttr_admin_scroll");
    if (adminScroll) {
      sessionStorage.removeItem("ttr_admin_scroll");
      const y = parseInt(adminScroll, 10);
      if (!isNaN(y)) {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            window.scrollTo({ top: y, behavior: "instant" });
          });
        });
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const TOKYO_MARKERS_ADMIN = ["東京", "新宿区", "港区", "渋谷区", "千代田区", "文京区", "台東区"];
  const KANTO_MARKERS_ADMIN = ["神奈川", "埼玉", "千葉", "茨城", "栃木", "群馬", "山梨"];
  const TOHOKU_MARKERS_ADMIN = ["北海道", "青森", "岩手", "宮城", "秋田", "山形", "福島"];
  // NOTE: "京都" is a substring of "東京都" — always use "京都府"/"京都市" to avoid false positives
  const CHUBU_KINKI_MARKERS_ADMIN = ["愛知", "静岡", "岐阜", "長野", "新潟", "富山", "石川", "福井", "大阪", "京都府", "京都市", "兵庫", "奈良", "滋賀", "和歌山", "三重"];
  const CHUGOKU_KYUSHU_MARKERS_ADMIN = ["広島", "岡山", "鳥取", "島根", "山口", "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄", "高知", "愛媛", "徳島", "香川"];
  function isTokyoAddr(addr: string | null | undefined, prefectures?: string[] | null): boolean {
    if (prefectures && prefectures.includes("東京")) return true;
    if (!addr || addr.trim() === "") return true;
    return TOKYO_MARKERS_ADMIN.some((m) => addr.includes(m));
  }

  function hasPrefecture(markers: string[], addr: string | null | undefined, prefectures?: string[] | null): boolean {
    if (prefectures && markers.some((m) => prefectures.includes(m))) return true;
    const a = addr || "";
    return markers.some((m) => a.includes(m));
  }

  function getFiltered(list: Event[]) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return list.filter((e) => {
      if (filterQ) {
        const q = filterQ.toLowerCase();
        const ev = e as any;
        const candidates = [
          getEventName(e, locale),
          e.raw_title,
          e.name_ja,
          e.name_zh,
          e.name_en,
          e.work_id && workMap[e.work_id] ? getWorkTitle(workMap[e.work_id], locale) : null,
          e.work_id && workMap[e.work_id] ? workMap[e.work_id].original_title : null,
          e.parent_event_id && eventMap[e.parent_event_id] ? getEventName(eventMap[e.parent_event_id], locale) : null,
          ev.description_zh,
          ev.description_ja,
          ev.description_en,
          ev.raw_description,
          ev.location_name,
          e.location_address,
          e.source_name,
          ev.organizer,
          ev.performer,
          ...(ev.performers ?? []),
        ];
        if (!candidates.some((c) => c && String(c).toLowerCase().includes(q))) return false;
      }
      if (filterCategories.length > 0 && !filterCategories.some((c) => (e.category || []).includes(c))) return false;
      if (filterPaid === "free" && e.is_paid !== false) return false;
      if (filterPaid === "paid" && e.is_paid !== true) return false;
      if (filterIsActive === "active" && !e.is_active) return false;
      if (filterIsActive === "inactive" && e.is_active) return false;
      if (filterIsActive === "merged" && !e.merged_into_event_id) return false;
      if (filterTimeMode === "active") {
        // Show ongoing: end_date >= today OR end_date is null
        if (e.end_date && new Date(e.end_date) < today) return false;
      } else if (filterTimeMode === "past") {
        // Search date range — no past restriction, just apply from/to
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
        if (!isTokyoAddr(e.location_address, (e as any).location_prefectures)) return false;
      } else if (filterLocation === "kanto") {
        if (!hasPrefecture(KANTO_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false;
      } else if (filterLocation === "tohoku") {
        if (!hasPrefecture(TOHOKU_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false;
      } else if (filterLocation === "chubu") {
        if (!hasPrefecture(CHUBU_KINKI_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false;
      } else if (filterLocation === "chugoku") {
        if (!hasPrefecture(CHUGOKU_KYUSHU_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false;
      } else if (filterLocation === "online") {
        if (!(e.location_name || "").includes("オンライン")) return false;
      } else if (filterLocation === "overseas") {
        const TAIWAN_MARKERS_ADMIN = ["台北", "台中", "高雄", "台南", "新竹", "嘉義", "花蓮", "台東", "基隆", "宜蘭", "桃園", "屏東", "南投", "彰化", "雲林", "澎湖"];
        if (!TAIWAN_MARKERS_ADMIN.some((m) => (e.location_address || "").includes(m))) return false;
      }
      // City sub-filter
      if (filterCity && (REGIONS_WITH_CITY as readonly string[]).includes(filterLocation)) {
        if (!matchesCity(filterCity, e.location_address, (e as any).location_prefectures as string[] | null, filterLocation as RegionWithCity)) return false;
      }
  if (filterAnnotation && (e as any).annotation_status !== filterAnnotation) return false;
      if (filterOrgType && !((e as any).organizer_type ?? []).includes(filterOrgType)) return false;
      if (filterEventForm && !((e as any).event_form ?? []).includes(filterEventForm)) return false;
      if (filterSource && (e as any).source_name !== filterSource) return false;
      return true;
    });
  }

  /** Counts per category across ALL events (unfiltered) */
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of events) {
      for (const cat of e.category || []) {
        counts[cat] = (counts[cat] ?? 0) + 1;
      }
    }
    return counts;
  }, [events]);

  /** Counts per source_name, applying all filters EXCEPT filterSource */
  const sourceCountMap = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const base = events.filter((e) => {
      if (filterQ) {
        const q = filterQ.toLowerCase();
        const ev = e as any;
        const candidates = [
          getEventName(e, locale),
          e.raw_title,
          e.name_ja,
          e.name_zh,
          e.name_en,
          e.work_id && workMap[e.work_id] ? getWorkTitle(workMap[e.work_id], locale) : null,
          e.work_id && workMap[e.work_id] ? workMap[e.work_id].original_title : null,
          e.parent_event_id && eventMap[e.parent_event_id] ? getEventName(eventMap[e.parent_event_id], locale) : null,
          ev.description_zh,
          ev.description_ja,
          ev.description_en,
          ev.raw_description,
          ev.location_name,
          e.location_address,
          e.source_name,
          ev.organizer,
          ev.performer,
          ...(ev.performers ?? []),
        ];
        if (!candidates.some((c) => c && String(c).toLowerCase().includes(q))) return false;
      }
      if (filterCategories.length > 0 && !filterCategories.some((c) => (e.category || []).includes(c))) return false;
      if (filterPaid === "free" && e.is_paid !== false) return false;
      if (filterPaid === "paid" && e.is_paid !== true) return false;
      if (filterIsActive === "active" && !e.is_active) return false;
      if (filterIsActive === "inactive" && e.is_active) return false;
      if (filterIsActive === "merged" && !e.merged_into_event_id) return false;
      if (filterTimeMode === "active") {
        if (e.end_date && new Date(e.end_date) < today) return false;
      } else if (filterTimeMode === "past") {
        if (filterDateFrom) { const d = e.start_date ? new Date(e.start_date) : null; if (!d || d < new Date(filterDateFrom)) return false; }
        if (filterDateTo) { const d = e.start_date ? new Date(e.start_date) : null; if (!d || d > new Date(filterDateTo + "T23:59:59")) return false; }
      }
      if (filterLocation === "tokyo") { if (!isTokyoAddr(e.location_address, (e as any).location_prefectures)) return false; }
      else if (filterLocation === "kanto") { if (!hasPrefecture(KANTO_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false; }
      else if (filterLocation === "tohoku") { if (!hasPrefecture(TOHOKU_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false; }
      else if (filterLocation === "chubu") { if (!hasPrefecture(CHUBU_KINKI_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false; }
      else if (filterLocation === "chugoku") { if (!hasPrefecture(CHUGOKU_KYUSHU_MARKERS_ADMIN, e.location_address, (e as any).location_prefectures)) return false; }
      else if (filterLocation === "online") { if (!(e.location_name || "").includes("オンライン")) return false; }
      if (filterCity && (REGIONS_WITH_CITY as readonly string[]).includes(filterLocation)) {
        if (!matchesCity(filterCity, e.location_address, (e as any).location_prefectures as string[] | null, filterLocation as RegionWithCity)) return false;
      }
      if (filterAnnotation && (e as any).annotation_status !== filterAnnotation) return false;
      if (filterOrgType && !((e as any).organizer_type ?? []).includes(filterOrgType)) return false;
      if (filterEventForm && !((e as any).event_form ?? []).includes(filterEventForm)) return false;
      return true;
    });
    const map: Record<string, number> = {};
    for (const e of base) {
      const s = (e as any).source_name as string;
      map[s] = (map[s] ?? 0) + 1;
    }
    return map;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, filterQ, filterCategories, filterPaid, filterIsActive, filterTimeMode, filterDateFrom, filterDateTo, filterLocation, filterCity, filterAnnotation, filterOrgType, filterEventForm, locale]);

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
      ? <span className="ml-0.5 text-fg-strong">{sortDir === "asc" ? "▲" : "▼"}</span>
      : <span className="ml-0.5 text-fg-subtle">▲</span>;

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
    setPosterPreview(null);
    setExtractError(null);
    setOcrFilled(false);
    setAnnotating(false);
    setSavedEventId(null);
    setEnrichedReady(false);
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

  async function handleExtractFromImage(file: File) {
    setExtracting(true);
    setExtractError(null);
    try {
      const reader = new FileReader();
      const dataUrl = await new Promise<string>((resolve, reject) => {
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      setPosterPreview(dataUrl);
      const res = await fetch("/api/admin/extract-from-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Extraction failed");
      const fields = data.fields as Record<string, unknown>;
      const ARRAY_FIELDS = new Set(["event_form", "category"]);
      for (const [key, val] of Object.entries(fields)) {
        if (val === null || val === undefined) continue;
        if (ARRAY_FIELDS.has(key) && Array.isArray(val)) {
          updateField(key, val);
        } else if (!ARRAY_FIELDS.has(key)) {
          updateField(key, val === true ? true : val === false ? false : String(val));
        }
      }
      if (typeof fields.is_paid === "boolean") updateField("is_paid", fields.is_paid);
      if (typeof fields.has_japanese_support === "boolean") updateField("has_japanese_support", fields.has_japanese_support);
      if (typeof fields.has_english_support === "boolean") updateField("has_english_support", fields.has_english_support);
      if (typeof fields.has_chinese_support === "boolean") updateField("has_chinese_support", fields.has_chinese_support);
      setOcrFilled(true);
    } catch (e: unknown) {
      setExtractError(e instanceof Error ? e.message : String(e));
    } finally {
      setExtracting(false);
    }
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
        co_organizers: (form as any).co_organizers || null,
        sponsors: (form as any).sponsors || null,
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

  async function handleSaveAndAnnotate() {
    setSaving(true);
    const { data, error } = await supabase
      .from("events")
      .insert({
        ...form,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        parent_event_id: form.parent_event_id || null,
        co_organizers: (form as any).co_organizers || null,
        sponsors: (form as any).sponsors || null,
        source_id: `manual-${Date.now()}`,
        is_active: false,
        annotation_status: "pending",
      })
      .select()
      .single();

    if (error) {
      console.error("Insert failed:", error);
      alert(`Save failed: ${error.message}`);
      setSaving(false);
      return;
    }

    const eventId = (data as { id: string }).id;
    setSavedEventId(eventId);
    setEvents((prev) => [data as Event, ...prev]);
    setSaving(false);
    setAnnotating(true);
    setEnrichedReady(false);

    // Directly annotate + web-search enrich via API
    try {
      const res = await fetch("/api/admin/annotate-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventId }),
        signal: AbortSignal.timeout(58000), // 58s hard cap — prevents infinite hang on Vercel timeout or localhost
      });
      if (res.ok) {
        const respJson = (await res.json()) as {
          fields: Record<string, unknown>;
          foundUrl: string | null;
          searchDebug: { braveCount: number; ddgCount: number; bingCount: number; candidateCount: number; bestScore: number; queries: string[]; topCandidates: Array<{ url: string; score: number }> } | null;
          webTextLength: number;
          needsUrlEnrichment?: boolean;
          sourceUrlFetchOk?: boolean | null;
          eventUrls?: Record<string, string | null>;
        };
        const { fields, foundUrl } = respJson;
        for (const [k, v] of Object.entries(fields)) {
          if (v !== null && v !== undefined) {
            updateField(k, v);
          }
        }
        if (foundUrl) {
          updateField("source_url", foundUrl);
          updateField("official_url", foundUrl);
        }
        console.info("[annotate]", respJson);
        if (!foundUrl && respJson.needsUrlEnrichment === false) {
          console.warn("[annotate] Web search SKIPPED — all URL fields already had values:", respJson.eventUrls);
        } else if (!foundUrl && respJson.searchDebug) {
          const d = respJson.searchDebug;
          console.warn(
            `[annotate] No URL found. Brave=${d.braveCount} DDG=${d.ddgCount} Bing=${d.bingCount} candidates=${d.candidateCount} bestScore=${d.bestScore}. ` +
            (d.candidateCount === 0
              ? (d.braveCount === 0 && d.ddgCount === 0 && d.bingCount === 0
                  ? "All search engines returned 0 — set BRAVE_SEARCH_API_KEY env var on Vercel."
                  : "")
              : d.bestScore < 1 ? "Found candidates but pages did not match event name." : "")
          );
        }
      } else {
        console.warn("Annotation API failed:", await res.text());
      }
    } catch (e) {
      console.warn("Annotation error:", e);
    }

    setAnnotating(false);
    setEnrichedReady(true);
  }

  async function handlePublish() {
    if (!savedEventId) return;
    setSaving(true);
    const { error, data: publishedRows } = await supabase
      .from("events")
      .update({ is_active: true, annotation_status: "reviewed" })
      .eq("id", savedEventId)
      .select("id");
    if (error) {
      alert(`Publish failed: ${error.message}`);
      setSaving(false);
      return;
    }
    if (!publishedRows || publishedRows.length === 0) {
      alert("發布未生效（session 可能已過期），請重新整理頁面後再試。");
      setSaving(false);
      return;
    }
    // Refresh event in list
    setEvents((prev) =>
      prev.map((e) =>
        e.id === savedEventId ? { ...e, is_active: true, annotation_status: "reviewed" as const } : e
      )
    );
    setSaving(false);
    setShowNew(false);
    cancelNew();
  }

  async function handleBulkToggleActive(targetActive: boolean) {
    if (selected.size === 0) return;
    setBulkToggling(true);
    const ids = Array.from(selected);
    const update: Record<string, unknown> = { is_active: targetActive };
    if (!targetActive) {
      update.deactivated_at = new Date().toISOString();
      update.deactivated_reason = "manually deactivated by admin (bulk)";
      update.deactivated_by_pass = "admin_manual";
    } else {
      update.deactivated_at = null;
      update.deactivated_reason = null;
      update.deactivated_by_pass = null;
    }
    const { error, data: toggleRows } = await supabase.from("events").update(update).in("id", ids).select("id");
    if (error) {
      alert(`操作失敗：${error.message}`);
      setBulkToggling(false);
      return;
    }
    if (!toggleRows || toggleRows.length === 0) {
      alert("批次切換未生效（session 可能已過期），請重新整理頁面後再試。");
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
    const { data: reannRows } = await supabase.from("events").update({ annotation_status: "pending" }).eq("id", id).select("id");
    if (reannRows && reannRows.length > 0) {
      setEvents((prev) =>
        prev.map((e) => (e.id === id ? { ...e, annotation_status: "pending" } : e))
      );
    }
  }

  async function handleBulkForceRescrape() {
    if (selected.size === 0) return;
    setBulkForceRescrapings(true);
    const ids = Array.from(selected);
    const { error, data: rescrapeRows } = await supabase.from("events").update({ force_rescrape: true }).in("id", ids).select("id");
    if (error) {
      alert(`操作失敗：${error.message}`);
      setBulkForceRescrapings(false);
      return;
    }
    if (!rescrapeRows || rescrapeRows.length === 0) {
      alert("批次強制重新爬取標記未生效（session 可能已過期），請重新整理頁面後再試。");
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
        const { error, data: rmCatRows } = await supabase.from("events").update({ category: newCategory }).eq("id", e.id).select("id");
        if (error || !rmCatRows || rmCatRows.length === 0) { hasError = true; return; }
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
        await supabase.from("field_corrections").upsert(
          { event_id: e.id, field_name: "category", corrected_value: JSON.stringify(newCategory) },
          { onConflict: "event_id,field_name" }
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
      setSelected(new Set());
    }
    setBulkRemovingCategory(false);
  }

  async function handleBulkAssignWork(workId: string) {
    if (selected.size === 0) return;
    setBulkAssigningWork(true);
    setBulkWorkOpen(false);
    setBulkWorkQuery("");
    await Promise.all(
      Array.from(selected).map(async (eventId) => {
        const { error, data: workRows } = await supabase.from("events").update({ work_id: workId }).eq("id", eventId).select("id");
        if (!error && workRows && workRows.length > 0) {
          setEvents((prev) => prev.map((e) => e.id === eventId ? { ...e, work_id: workId } : e));
        }
      })
    );
    setBulkAssigningWork(false);
  }

  async function handleBulkAddCategory() {
    if (selected.size === 0 || bulkAddCatPending.size === 0) return;
    setBulkAddingCategory(true);
    const selectedEvents = events.filter((e) => selected.has(e.id));
    const catsToAdd = Array.from(bulkAddCatPending);
    let hasError = false;

    await Promise.all(
      selectedEvents.map(async (e) => {
        const prevCategory = e.category ?? [];
        const newCategory = Array.from(new Set([...prevCategory, ...catsToAdd]));
        if (newCategory.length === prevCategory.length && catsToAdd.every((c) => prevCategory.includes(c))) return;
        const { error, data: addCatRows } = await supabase.from("events").update({ category: newCategory }).eq("id", e.id).select("id");
        if (error || !addCatRows || addCatRows.length === 0) { hasError = true; return; }
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
        await supabase.from("field_corrections").upsert(
          { event_id: e.id, field_name: "category", corrected_value: JSON.stringify(newCategory) },
          { onConflict: "event_id,field_name" }
        );
      })
    );

    if (hasError) {
      alert("部分更新失敗，請重新整理頁面確認結果");
    } else {
      setEvents((prev) =>
        prev.map((e) =>
          selected.has(e.id)
            ? { ...e, category: Array.from(new Set([...(e.category ?? []), ...catsToAdd])) }
            : e
        )
      );
      setSelected(new Set());
      setBulkAddCatPending(new Set());
      setBulkAddCatOpen(false);
    }
    setBulkAddingCategory(false);
  }

  async function handleToggleForceRescrape(id: string) {
    const ev = events.find((e) => e.id === id);
    if (!ev) return;
    const newValue = !ev.force_rescrape;
    const { data: frRows } = await supabase.from("events").update({ force_rescrape: newValue }).eq("id", id).select("id");
    if (frRows && frRows.length > 0) {
      setEvents((prev) => prev.map((e) => e.id === id ? { ...e, force_rescrape: newValue } : e));
    }
  }

  async function handleToggleActive(id: string, newValue: boolean) {
    // Optimistic update — give immediate visual feedback
    setEvents((prev) =>
      prev.map((e) => (e.id === id ? { ...e, is_active: newValue } : e))
    );
    const update: Record<string, unknown> = { is_active: newValue };
    if (!newValue) {
      update.deactivated_at = new Date().toISOString();
      update.deactivated_reason = "manually deactivated by admin";
      update.deactivated_by_pass = "admin_manual";
    } else {
      update.deactivated_at = null;
      update.deactivated_reason = null;
      update.deactivated_by_pass = null;
    }
    const { error, data: activeRows } = await supabase.from("events").update(update).eq("id", id).select("id");
    if (error) {
      // Revert optimistic update
      setEvents((prev) =>
        prev.map((e) => (e.id === id ? { ...e, is_active: !newValue } : e))
      );
      alert(`切換公開狀態失敗：${error.message}`);
      return;
    }
    if (!activeRows || activeRows.length === 0) {
      // Revert optimistic update
      setEvents((prev) =>
        prev.map((e) => (e.id === id ? { ...e, is_active: !newValue } : e))
      );
      alert("切換未生效（session 可能已過期），請重新整理頁面後再試。");
    }
  }

  return (
  <>
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
        <div className="flex rounded-lg border border-line-strong overflow-hidden ml-auto">
          <button
            onClick={() => setViewMode("annotated")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              viewMode === "annotated"
                ? "bg-green-600 text-white"
                : "bg-surface text-fg-muted hover:bg-elevated"
            }`}
          >
            {t("viewAnnotated")}
          </button>
          <button
            onClick={() => setViewMode("raw")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              viewMode === "raw"
                ? "bg-green-600 text-white"
                : "bg-surface text-fg-muted hover:bg-elevated"
            }`}
          >
            {t("viewRaw")}
          </button>
        </div>
      </div>

      {/* New event inline form */}
      {showNew && (
        <div className="border border-green-300 rounded-xl p-6 mb-6 bg-green-50">
          {/* Header: title + image OCR button */}
          <div className="flex items-center gap-3 mb-4">
            <h2 className="font-bold text-lg">{t("newEvent")}</h2>
            <button
              type="button"
              onClick={() => posterFileRef.current?.click()}
              disabled={extracting}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-line-strong rounded-lg hover:bg-elevated disabled:opacity-50 transition"
            >
              {t("extractFromImage")}
            </button>
            <input
              ref={posterFileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleExtractFromImage(file);
                e.target.value = "";
              }}
            />
            {extracting && <span className="text-sm text-blue-500 animate-pulse">{t("extracting")}</span>}
            {extractError && <span className="text-sm text-red-500">{extractError}</span>}
          </div>

          {/* Body: form left + image preview right */}
          <div className={posterPreview ? "flex gap-6 items-start" : undefined}>
            <div className={posterPreview ? "flex-1 min-w-0" : undefined}>
              <AdminEventForm
                form={form}
                t={t}
                tCat={tCat}
                tEventForm={tEventForm}
                updateField={updateField}
                toggleCategory={toggleCategory}
                events={events}
                editingId={null}
                locale={locale}
              />
              <div className="flex flex-col gap-3 mt-4">
                <div className="flex gap-3">
                  {ocrFilled ? (
                    <button
                      onClick={handleSaveAndAnnotate}
                      disabled={saving || annotating}
                      className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
                    >
                      {saving ? t("saving") : annotating ? (
                        <span className="flex items-center gap-1.5">
                          <span className="animate-pulse text-blue-200">●</span>
                          {t("annotating")}
                        </span>
                      ) : enrichedReady ? t("reannotate") : t("saveAndAnnotate")}
                    </button>
                  ) : (
                    <button
                      onClick={handleSaveNew}
                      disabled={saving}
                      className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
                    >
                      {saving ? "..." : t("save")}
                    </button>
                  )}
                  <button
                    onClick={cancelNew}
                    disabled={annotating}
                    className="border border-line-strong px-4 py-2 rounded-lg text-sm hover:bg-elevated disabled:opacity-50"
                  >
                    {t("cancel")}
                  </button>
                </div>

                {enrichedReady && (
                  <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <span className="text-sm text-blue-700">{t("annotationDone")}</span>
                    <button
                      onClick={handlePublish}
                      disabled={saving}
                      className="ml-auto bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 font-medium"
                    >
                      {saving ? "..." : t("publish")}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {posterPreview && (
              <div className="w-[760px] shrink-0 sticky top-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-fg-muted">海報預覽</span>
                  <button
                    type="button"
                    onClick={() => setPosterPreview(null)}
                    className="text-xs text-fg-muted hover:text-fg px-1"
                  >
                    ✕ 關閉
                  </button>
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={posterPreview}
                  alt="poster preview"
                  className="w-full rounded-lg border border-line object-contain max-h-[90vh]"
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Sticky wrapper: filter bar + bulk action bar scroll together */}
      <div ref={filterBarRef} className="sticky top-14 z-20 space-y-2 mb-3">
      {/* Inline filter bar */}
      <div className="bg-elevated rounded-xl px-4 py-3 space-y-2">
        {/* Row 1: 搜尋、類型、地點、票價、時間、日期 */}
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{tFilters("search")}</label>
            <input
              type="search"
              value={filterQ}
              onChange={(e) => setFilterQ(e.target.value)}
              placeholder={tFilters("searchPlaceholder")}
              className="h-9 border border-line-strong rounded-lg px-3 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-green-400"
            />
          </div>
          <div className="flex flex-col gap-1" ref={catDropdownRef}>
            <label className="text-xs text-fg-muted font-medium">{tFilters("category")}</label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setCatDropdownOpen((o) => !o)}
                className="h-9 min-w-[9rem] flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm bg-elevated hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
              >
                <span className={filterCategories.length > 0 ? "text-green-700 font-medium" : "text-fg-muted"}>
                  {filterCategories.length > 0 ? `${t("category")} (${filterCategories.length})` : t("filterAll")}
                </span>
                <span className="text-fg-subtle text-xs">{catDropdownOpen ? "▲" : "▼"}</span>
              </button>
              {catDropdownOpen && (
                <div className="absolute z-50 top-10 left-0 w-72 bg-surface border border-line rounded-xl shadow-lg py-2 max-h-80 overflow-y-auto">
                  {filterCategories.length > 0 && (
                    <div className="px-3 pb-1.5 border-b border-line mb-1">
                      <button type="button" onClick={() => setFilterCategories([])} className="text-xs text-red-500 hover:text-red-700 underline">
                        {t("filterAll")}
                      </button>
                    </div>
                  )}
                  {CATEGORY_GROUPS.map((group) => (
                    <div key={group.labelKey} className="px-3 py-1">
                      <p className="text-xs font-semibold text-fg-subtle uppercase tracking-wide mb-1">{tCat(group.labelKey as any)}</p>
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
                            <span className="text-sm text-fg">{tCat(cat as any)}{(categoryCounts[cat] ?? 0) > 0 ? ` (${categoryCounts[cat]})` : ""}</span>
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
            <label className="text-xs text-fg-muted font-medium">{tFilters("location")}</label>
            <DesignSelect
              value={filterLocation}
              onChange={(v) => { setFilterLocation(v as any); setFilterCity(""); }}
              options={[
                { value: "", label: tFilters("allLocations") },
                { value: "tokyo", label: tFilters("locationTokyo") },
                { value: "kanto", label: tFilters("locationKanto") },
                { value: "tohoku", label: tFilters("locationTohoku") },
                { value: "chubu", label: tFilters("locationChubu") },
                { value: "chugoku", label: tFilters("locationChugoku") },
                { value: "online", label: tFilters("locationOnline") },
                { value: "overseas", label: tFilters("locationOverseas") },
              ]}
            />
          </div>

          {/* City sub-filter */}
          {(REGIONS_WITH_CITY as readonly string[]).includes(filterLocation) && (() => {
            const region = filterLocation as RegionWithCity;
            const prefs = REGION_PREFECTURES[region];
            return (
              <div className="flex flex-col gap-1">
                <label className="text-xs text-fg-muted font-medium">{tFilters("location")}</label>
                <DesignSelect
                  value={filterCity}
                  onChange={setFilterCity}
                  options={[
                    { value: "", label: tFilters("cityAll") },
                    ...prefs.map((p) => ({ value: p, label: locale === "en" ? (PREFECTURE_LABELS_EN[p] ?? p) : p })),
                    { value: CITY_OTHER, label: tFilters("cityOther") },
                  ]}
                />
              </div>
            );
          })()}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{t("isPaid")}</label>
            <DesignSelect
              value={filterPaid}
              onChange={setFilterPaid}
              options={[
                { value: "", label: t("filterAll") },
                { value: "free", label: tEvent("free") },
                { value: "paid", label: tEvent("paid") },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{tFilters("timeMode")}</label>
            <DesignSelect
              value={filterTimeMode}
              onChange={(v) => {
                const mode = v as "active" | "all" | "past";
                setFilterTimeMode(mode);
                if (mode !== "past") {
                  setFilterDateFrom("2024-01-01");
                  setFilterDateTo("");
                } else {
                  setFilterDateFrom((prev) => prev || "2024-01-01");
                }
              }}
              options={[
                { value: "active", label: tFilters("timeModeActive") },
                { value: "all", label: tFilters("timeModeAll") },
                { value: "past", label: tFilters("timeModePast") },
              ]}
            />
          </div>
          {filterTimeMode === "past" && (
            <>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-fg-muted font-medium">{tFilters("dateFrom")}</label>
                <input
                  type="date"
                  value={filterDateFrom}
                  onChange={(e) => setFilterDateFrom(e.target.value)}
                  className="h-9 border border-line-strong rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-fg-muted font-medium">{tFilters("dateTo")}</label>
                <input
                  type="date"
                  value={filterDateTo}
                  onChange={(e) => setFilterDateTo(e.target.value)}
                  className="h-9 border border-line-strong rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
            </>
          )}
        </div>

        {/* Row 2: 來源名稱、開放檢視、標註狀態、清除 */}
        <div className="flex flex-wrap gap-3 items-end border-t border-line pt-2">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{t("sourceName")}</label>
            <DesignSelect
              value={filterSource}
              onChange={setFilterSource}
              options={[
                { value: "", label: t("filterAll") },
                ...Array.from(new Set(events.map((e) => (e as any).source_name as string)))
                  .filter(Boolean)
                  .sort()
                  .map((s) => ({
                    value: s,
                    label: `${s}${sourceCountMap[s] !== undefined ? ` (${sourceCountMap[s]})` : " (0)"}`,
                  })),
              ]}
              className="min-w-[10rem]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{t("isActive")}</label>
            <DesignSelect
              value={filterIsActive}
              onChange={(v) => setFilterIsActive(v as any)}
              options={[
                { value: "all", label: t("filterAll") },
                { value: "active", label: t("filterActive") },
                { value: "inactive", label: t("filterInactive") },
                { value: "merged", label: t("filterMerged") },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{t("annotationStatusLabel")}</label>
            <DesignSelect
              value={filterAnnotation}
              onChange={(v) => setFilterAnnotation(v as any)}
              options={[
                { value: "", label: t("filterAll") },
                { value: "pending", label: t("filterPendingShort") },
                { value: "annotated", label: t("filterAnnotatedShort") },
                { value: "reviewed", label: t("filterReviewedShort") },
                { value: "error", label: t("filterErrorShort") },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{tEvent("organizer")}</label>
            <DesignSelect
              value={filterOrgType}
              onChange={setFilterOrgType}
              options={[
                { value: "", label: t("filterAll") },
                { value: "government", label: tOrgType("government") },
                { value: "semi_official", label: tOrgType("semi_official") },
                { value: "cultural_institution", label: tOrgType("cultural_institution") },
                { value: "academic", label: tOrgType("academic") },
                { value: "commercial_brand", label: tOrgType("commercial_brand") },
                { value: "independent_venue", label: tOrgType("independent_venue") },
                { value: "civic_group", label: tOrgType("civic_group") },
                { value: "media", label: tOrgType("media") },
                { value: "unknown", label: tOrgType("unknown") },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-fg-muted font-medium">{tEvent("eventForm")}</label>
            <DesignSelect
              value={filterEventForm}
              onChange={setFilterEventForm}
              options={[
                { value: "", label: t("filterAll") },
                { value: "exhibition", label: tEventForm("exhibition") },
                { value: "screening", label: tEventForm("screening") },
                { value: "lecture", label: tEventForm("lecture") },
                { value: "performance", label: tEventForm("performance") },
                { value: "market", label: tEventForm("market") },
                { value: "workshop", label: tEventForm("workshop") },
                { value: "conference", label: tEventForm("conference") },
                { value: "networking", label: tEventForm("networking") },
                { value: "screening_with_talk", label: tEventForm("screening_with_talk") },
                { value: "tour", label: tEventForm("tour") },
                { value: "competition", label: tEventForm("competition") },
                { value: "tasting", label: tEventForm("tasting") },
                { value: "other", label: tEventForm("other") },
              ]}
              className="min-w-[10rem]"
            />
          </div>
          {(filterQ || filterCategories.length > 0 || filterPaid || filterIsActive !== "all" || filterTimeMode !== "all" || filterDateFrom || filterDateTo || filterLocation || filterCity || filterAnnotation || filterSource || filterOrgType || filterEventForm) && (
            <button
              onClick={() => { setFilterQ(""); setFilterCategories([]); setFilterPaid(""); setFilterIsActive("all"); setFilterTimeMode("all"); setFilterDateFrom("2024-01-01"); setFilterDateTo(""); setFilterLocation(""); setFilterCity(""); setFilterAnnotation(""); setFilterSource(""); setFilterOrgType(""); setFilterEventForm(""); }}
              className="text-xs text-red-500 hover:text-red-700 underline self-end pb-1"
            >
              {tFilters("reset")}
            </button>
          )}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm space-y-2 shadow-md">
          {/* Row 1: count + action buttons */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-blue-700 font-medium">{t("selectedCount", { count: selected.size })}</span>
            <button
              onClick={() => handleBulkToggleActive(false)}
              disabled={bulkToggling}
              className="bg-gray-600 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-gray-700 disabled:opacity-50 transition"
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
              className="ml-auto text-xs text-fg-muted hover:text-fg-strong underline transition"
            >
              {t("bulkDeselectAll")}
            </button>
            <button
              onClick={() => setSelected(new Set())}
              className="text-fg-subtle hover:text-fg-muted text-sm leading-none transition"
              aria-label="close"
            >
              ✕
            </button>
          </div>
          {/* Row 2: bulk category annotation + work annotation + create work */}
          <div className="flex items-center gap-2 flex-wrap border-t border-blue-200 pt-2" ref={bulkAddCatRef}>
            <span className="text-xs text-blue-600 font-medium">分類標注：</span>
            <div className="relative">
              <button
                onClick={() => setBulkAddCatOpen((v) => !v)}
                className="text-xs h-7 px-2.5 border border-blue-300 rounded-full bg-surface text-blue-700 hover:bg-blue-50 transition flex items-center gap-1"
              >
                {bulkAddCatPending.size === 0 ? "選擇…" : `已選 ${bulkAddCatPending.size} 個`}
                <span className="text-blue-400">▾</span>
              </button>
              {bulkAddCatOpen && (
                <div className="absolute left-0 top-8 z-20 bg-surface border border-line rounded-xl shadow-lg p-3 w-64 max-h-72 overflow-y-auto space-y-2">
                  {CATEGORY_GROUPS.map((group) => (
                    <div key={group.labelKey}>
                      <p className="text-[10px] font-semibold text-fg-subtle uppercase tracking-wide mb-1">{tCat(group.labelKey as any)}</p>
                      <div className="flex flex-wrap gap-1">
                        {group.categories.map((cat) => {
                          const checked = bulkAddCatPending.has(cat);
                          return (
                            <label key={cat} className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border cursor-pointer select-none transition ${
                              checked ? "bg-blue-500 text-white border-blue-500" : "border-line text-fg hover:border-blue-400"
                            }`}>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  setBulkAddCatPending((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(cat)) next.delete(cat); else next.add(cat);
                                    return next;
                                  });
                                }}
                                className="sr-only"
                              />
                              {tCat(cat as any)}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {bulkAddCatPending.size > 0 && (
              <button
                onClick={handleBulkAddCategory}
                disabled={bulkAddingCategory}
                className="text-xs h-7 px-3 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50 transition font-medium"
              >
                {bulkAddingCategory ? "…" : `套用到 ${selected.size} 筆`}
              </button>
            )}
            <span className="text-xs text-blue-600 font-medium ml-2">作品標注：</span>
            <div className="relative" ref={bulkWorkRef}>
              <button
                onClick={() => { setBulkWorkOpen((v) => !v); setBulkWorkQuery(""); }}
                disabled={bulkAssigningWork}
                className="text-xs h-7 px-2.5 border border-blue-300 rounded-full bg-surface text-blue-700 hover:bg-blue-50 transition flex items-center gap-1 disabled:opacity-50"
              >
                {bulkAssigningWork ? "套用中…" : "選擇作品… ▾"}
              </button>
              {bulkWorkOpen && (
                <div className="absolute left-0 top-8 z-20 bg-surface border border-line rounded-xl shadow-lg w-64">
                  <div className="p-2 border-b border-line">
                    <input
                      autoFocus
                      type="text"
                      value={bulkWorkQuery}
                      onChange={(e) => setBulkWorkQuery(e.target.value)}
                      placeholder="搜尋作品…"
                      className="w-full text-xs border border-line rounded px-2 py-1"
                    />
                  </div>
                  <div className="overflow-y-auto max-h-[280px] py-1">
                    {works
                      .filter((w) => {
                        const q = bulkWorkQuery.trim().toLowerCase();
                        if (!q) return true;
                        return [w.original_title, w.title_ja, w.title_zh, w.title_en]
                          .filter(Boolean)
                          .some((s) => (s as string).toLowerCase().includes(q));
                      })
                      .map((w) => (
                        <button
                          key={w.id}
                          onClick={() => handleBulkAssignWork(w.id)}
                          className="w-full text-left px-3 py-1.5 text-xs hover:bg-blue-50 truncate"
                        >
                          {getWorkTitle(w, locale)}
                        </button>
                      ))}
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={() => setShowCreateWorkModal(true)}
              className="text-xs h-7 px-3 bg-surface border border-blue-300 text-blue-700 rounded-full hover:bg-blue-50 transition font-medium flex items-center"
            >
              ＋ 新增作品
            </button>
          </div>
          {/* Row 3: common category removal — only shown when intersection is non-empty */}
          {commonCategories.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap border-t border-blue-200 pt-2">
              <span className="text-xs text-blue-600 font-medium">{t("bulkCommonCategories")}：</span>
              {commonCategories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => handleBulkRemoveCategory(cat)}
                  disabled={bulkRemovingCategory}
                  className="text-xs bg-surface border border-blue-300 text-blue-700 px-2 py-0.5 rounded-full hover:bg-red-50 hover:border-red-300 hover:text-red-700 transition disabled:opacity-50"
                  title={t("bulkRemoveCategoryHint")}
                >
                  {tCat(cat as any)} ×
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      </div>{/* /sticky wrapper */}

      {/* Events table — scroll container so thead sticky top-0 is always reliable */}
      <div className="overflow-auto" style={{ height: `calc(100vh - ${56 + filterBarHeight}px)` }}>
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0 z-10 bg-surface">
            {viewMode === "annotated" ? (
              <tr className="border-b text-left text-fg-muted">
                <th className="py-2 px-2 w-8 text-right text-[11px] select-none">#</th>
                <th className="py-2 px-2 w-8">
                  <input
                    type="checkbox"
                    checked={getSorted(getFiltered(events)).length > 0 && getSorted(getFiltered(events)).every((e) => selected.has(e.id))}
                    onChange={toggleSelectAll}
                    className="rounded cursor-pointer"
                    title={t("selectAll")}
                  />
                </th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("scraped_at")}>{t("scrapedAt")}{sortArrow("scraped_at")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("annotation_status")}>{t("annotationStatusLabel")}{sortArrow("annotation_status")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("is_active")}>{t("isActive")}{sortArrow("is_active")}</th>
                <th className="py-2 pr-6" />
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("name")}>{t("name")}{sortArrow("name")}</th>
                <th className="py-2 pr-4 w-[160px] min-w-[160px] font-medium">{t("category")}</th>
                <th className="py-2 pr-4 w-[160px] min-w-[160px] font-medium">{t("events.columns.work")}</th>
                <th className="py-2 pr-4 font-medium">{t("address")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("start_date")}>{t("startDate")}{sortArrow("start_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("end_date")}>{t("endDate")}{sortArrow("end_date")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("source_name")}>{t("sourceName")}{sortArrow("source_name")}</th>
              </tr>
            ) : (
              <tr className="border-b text-left text-fg-muted">
                <th className="py-2 px-2 w-8 text-right text-[11px] select-none">#</th>
                <th className="py-2 px-2 w-8">
                  <input
                    type="checkbox"
                    checked={getSorted(getFiltered(events)).length > 0 && getSorted(getFiltered(events)).every((e) => selected.has(e.id))}
                    onChange={toggleSelectAll}
                    className="rounded cursor-pointer"
                    title={t("selectAll")}
                  />
                </th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("scraped_at")}>{t("scrapedAt")}{sortArrow("scraped_at")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("annotation_status")}>{t("annotationStatusLabel")}{sortArrow("annotation_status")}</th>
                <th className="py-2 pr-6" />
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("raw_title")}>{t("name")}{sortArrow("raw_title")}</th>
                <th className="py-2 pr-4 font-medium cursor-pointer select-none hover:text-fg-strong" onClick={() => toggleSort("source_name")}>{t("sourceName")}{sortArrow("source_name")}</th>
              </tr>
            )}
          </thead>
          <tbody>
            {(() => {
              const displayEvents = getSorted(getFiltered(events));
              // Map each event id → 1-based row number in current filtered+sorted list
              const rowIndexMap: Record<string, number> = {};
              displayEvents.forEach((e, idx) => { rowIndexMap[e.id] = idx + 1; });
              // Global index across ALL events (unfiltered) — used to show merged_into target number even when filtered out
              const globalIndexMap: Record<string, number> = {};
              getSorted(events).forEach((e, idx) => { globalIndexMap[e.id] = idx + 1; });
              return displayEvents.map((event, rowIdx) => (
              viewMode === "annotated" ? (
                <tr
                  key={event.id}
                  id={`row-${event.id}`}
                  className={`border-b transition ${
                    !event.work_id &&
                    (event.category || []).some((c) => c === "movie" || c === "performing_arts")
                      ? "bg-blush hover:bg-[#FFE4E0] dark:hover:bg-[#35231f]"
                      : "hover:bg-elevated"
                  }`}
                  title={
                    !event.work_id &&
                    (event.category || []).some((c) => c === "movie" || c === "performing_arts")
                      ? t("events.warnings.missingWorkForFilm")
                      : undefined
                  }
                >
                  <td className="py-2 px-2 text-right text-[11px] text-fg-subtle select-none tabular-nums">{rowIdx + 1}</td>
                  <td className="py-2 px-2">
                    <input
                      type="checkbox"
                      checked={selected.has(event.id)}
                      onChange={() => toggleSelect(event.id)}
                      className="rounded cursor-pointer"
                    />
                  </td>
                  <td className="py-2 pr-4 text-fg-muted text-xs whitespace-nowrap">
                    {(() => {
                      const ts = event.scraped_at ?? event.created_at;
                      const label = ts ? new Date(ts).toLocaleDateString("zh") : "—";
                      return event.scraped_at
                        ? <span>{label}</span>
                        : <span className="text-fg-subtle" title="sub-event 生成時間">{label}</span>;
                    })()}
                  </td>
                  <td className="py-2 pr-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${getAnnotationBadgeClass(event.annotation_status)}`}>
                      {getAnnotationLabel(event.annotation_status)}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <button
                      onClick={() => handleToggleActive(event.id, !event.is_active)}
                      title={event.is_active ? t("filterActive") : t("filterInactive")}
                      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full transition-colors duration-200 focus:outline-none ${
                        event.is_active ? "bg-green-500" : "bg-gray-300"
                      }`}
                    >
                      <span className={`inline-block h-4 w-4 mt-0.5 rounded-full bg-surface shadow transition-transform duration-200 ${
                        event.is_active ? "translate-x-4" : "translate-x-0.5"
                      }`} />
                    </button>
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          sessionStorage.setItem("ttr_admin_scroll", String(window.scrollY));
                          router.push(`/${locale}/admin/${event.id}`);
                        }}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        {t("edit")}
                      </button>
                      <button
                        onClick={() => handleToggleForceRescrape(event.id)}
                        title={event.force_rescrape ? t("forceRescrapeOff") : t("forceRescrapeOn")}
                        className={`text-xs hover:underline ${event.force_rescrape ? "text-orange-600 font-medium" : "text-fg-subtle hover:text-orange-500"}`}
                      >
                        🔁
                      </button>
                    </div>
                  </td>
                  <td className="py-2 pr-4 max-w-xs">
                    {event.work_id && workMap[event.work_id] && (
                      <span className="block text-[10px] text-indigo-600 font-normal mb-0.5 truncate" title={`Work: ${workMap[event.work_id].original_title}`}>
                        🎬 {getWorkTitle(workMap[event.work_id], locale)}
                      </span>
                    )}
                    {event.parent_event_id && eventMap[event.parent_event_id] && (
                      <span className="block text-xs text-green-600 font-normal mb-0.5 truncate">
                        ↳ {getEventName(eventMap[event.parent_event_id], locale)}
                      </span>
                    )}
                    {/* Primary event: show row number + merge count */}
                    {mergeCountMap[event.id] > 0 && (
                      <span className="inline-flex items-center gap-0.5 mb-0.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 font-bold border border-green-300">
                          {rowIndexMap[event.id]}
                        </span>
                        <span className="text-[10px] text-green-600 font-medium">
                          {t("mergedPrimaryCount", { count: mergeCountMap[event.id] })}
                        </span>
                      </span>
                    )}
                    {/* Secondary (merged) event: show orange badge + arrow + primary row number */}
                    {event.merged_into_event_id && (
                      <span className="inline-flex items-center gap-0.5 mb-0.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium border border-amber-300">
                          {t("mergedIntoBadge")}
                        </span>
                        <span className="text-green-600 text-[10px] font-bold">→</span>
                        <a
                          href={rowIndexMap[event.merged_into_event_id]
                            ? `#row-${event.merged_into_event_id}`
                            : `/${locale}/admin/${event.merged_into_event_id}`}
                          className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 font-bold border border-green-300 hover:bg-green-200"
                          title={t("mergedIntoBadgeTitle")}
                        >
                          {rowIndexMap[event.merged_into_event_id] ?? "→"}
                        </a>
                      </span>
                    )}
                    <a
                      href={event.is_active ? `/${locale}/events/${event.id}` : `/${locale}/admin/${event.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate block hover:underline hover:text-green-700 transition"
                      title={event.is_active ? t("viewFrontend") : t("edit")}
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
                    {(((event as any).performers ?? []).length > 0 || (event as any).performer) && (
                      <span className="block mt-0.5 text-[10px] text-purple-600 truncate" title={`出演者: ${((event as any).performers ?? []).length > 0 ? (event as any).performers.join('、') : (event as any).performer}`}>
                        🎭 {((event as any).performers ?? []).length > 0 ? (event as any).performers.join('、') : (event as any).performer}
                      </span>
                    )}
                    {(event as any).organizer && (
                      <span className="block mt-0.5 text-[10px] text-fg-muted truncate" title={`主催: ${(event as any).organizer}`}>
                        🏢 {(event as any).organizer}
                      </span>
                    )}
                    {((event as any).event_form ?? []).length > 0 && (
                      <span className="block mt-0.5 text-[10px] text-blue-500">
                        {((event as any).event_form as string[]).map((ef) => {
                          try { return tEventForm(ef as any); } catch { return ef; }
                        }).join("・")}
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-4 w-[160px] min-w-[160px]">
                    <div className="flex flex-wrap gap-1">
                      {(() => {
                        const cats = event.category ?? [];
                        const isExpanded = expandedCategoryId === event.id;
                        const visible = isExpanded ? cats : cats.slice(0, 3);
                        const overflow = cats.length - 3;
                        return (
                          <>
                            {visible.map((cat) => (
                              <span key={cat} className="bg-green-50 text-green-700 text-[10px] px-1.5 py-0.5 rounded-full">
                                {tCat(cat as any)}
                              </span>
                            ))}
                            {overflow > 0 && (
                              <button
                                type="button"
                                onClick={() => setExpandedCategoryId(isExpanded ? null : event.id)}
                                className="text-[10px] text-blue-500 hover:text-blue-700 hover:underline leading-none px-0.5"
                              >
                                {isExpanded ? "−」" : `+${overflow}`}
                              </button>
                            )}
                          </>
                        );
                      })()}
                    </div>
                  </td>
                  <td className="py-2 pr-4 text-xs w-[160px] min-w-[160px]">
                    {(() => {
                      const cur = event.work_id ? workMap[event.work_id] : null;
                      const isEditing = editingWorkFor === event.id;
                      if (isEditing) {
                        const q = workQuery.trim().toLowerCase();
                        const list = q
                          ? works.filter((w) =>
                              [w.original_title, w.title_ja, w.title_zh, w.title_en]
                                .filter(Boolean)
                                .some((s) => (s as string).toLowerCase().includes(q))
                            )
                          : works;
                        return (
                          <div className="relative">
                            <input
                              autoFocus
                              type="text"
                              value={workQuery}
                              onChange={(e) => setWorkQuery(e.target.value)}
                              placeholder={t("events.assignWork.placeholder")}
                              onBlur={() => setTimeout(() => setEditingWorkFor(null), 150)}
                              className="w-full text-xs border rounded px-1.5 py-0.5"
                            />
                            <div className="absolute z-30 mt-0.5 left-0 right-0 bg-surface border rounded shadow max-h-48 overflow-y-auto">
                              {cur && (
                                <button
                                  onClick={async () => {
                                    const r = await assignWorkToEvent(event.id, null);
                                    if (r.ok) {
                                      setEvents((prev) =>
                                        prev.map((p) =>
                                          p.id === event.id ? { ...p, work_id: null } : p
                                        )
                                      );
                                    }
                                    setEditingWorkFor(null);
                                    setWorkQuery("");
                                  }}
                                  className="w-full text-left px-2 py-1 text-xs text-red-600 hover:bg-red-50 border-b"
                                >
                                  ✕ {t("events.assignWork.unassigned")}
                                </button>
                              )}
                              {list.slice(0, 30).map((w) => (
                                <button
                                  key={w.id}
                                  onClick={async () => {
                                    const r = await assignWorkToEvent(event.id, w.id);
                                    if (r.ok) {
                                      setEvents((prev) =>
                                        prev.map((p) =>
                                          p.id === event.id ? { ...p, work_id: w.id } : p
                                        )
                                      );
                                    }
                                    setEditingWorkFor(null);
                                    setWorkQuery("");
                                  }}
                                  className="w-full text-left px-2 py-1 text-xs hover:bg-green-50"
                                >
                                  {getWorkTitle(w, locale)}
                                </button>
                              ))}
                              <button
                                type="button"
                                onClick={() => {
                                  setEditingWorkFor(null);
                                  setShowCreateWorkModal(true);
                                }}
                                className="block w-full text-left px-2 py-1 text-xs text-blue-600 hover:bg-blue-50 border-t"
                              >
                                {t("events.assignWork.createNew")}
                              </button>
                            </div>
                          </div>
                        );
                      }
                      return (
                        <button
                          onClick={() => {
                            setEditingWorkFor(event.id);
                            setWorkQuery("");
                          }}
                          className="text-left w-full hover:underline"
                          title={t("events.assignWork.placeholder")}
                        >
                          {cur ? (
                            <span className="text-fg truncate block">
                              {getWorkTitle(cur, locale)}
                            </span>
                          ) : (
                            <span className="text-fg-subtle">
                              {t("events.assignWork.unassigned")}
                            </span>
                          )}
                        </button>
                      );
                    })()}
                  </td>
                  <td className="py-2 pr-4 text-xs max-w-[130px]">
                    {(() => {
                      const addr = event.location_address;
                      const name = (event as any).location_name as string | null;
                      if (event.source_name === "gguide_tv") return <span className="text-green-600">{tEvent("tvChannel")}</span>;
                      if (!addr && !name) return <span className="text-fg-subtle">—</span>;
                      const display = addr || name || "";
                      const isOnline = /オンライン|online|線上/i.test(display);
                      if (isOnline) return <span className="text-green-600">線上</span>;
                      const cityLabel = getCityLabel(
                        (event as any).location_prefectures as string[] | null,
                        addr,
                      );
                      return (
                        <span className="text-fg-muted truncate block" title={display}>
                          {cityLabel && (
                            <span className="inline-block bg-muted text-fg-muted text-[10px] px-1 py-0.5 rounded mr-1 font-medium whitespace-nowrap">
                              {cityLabel}
                            </span>
                          )}
                          {display}
                        </span>
                      );
                    })()}
                  </td>
                  <td className="py-2 pr-4 text-fg-muted text-xs whitespace-nowrap">
                    {event.start_date
                      ? new Date(event.start_date).toLocaleDateString("zh")
                      : "—"}
                  </td>
                  <td className="py-2 pr-4 text-fg-muted text-xs whitespace-nowrap">
                    {event.end_date
                      ? new Date(event.end_date).toLocaleDateString("zh")
                      : "—"}
                  </td>
                  <td className="py-2 pr-4 text-fg-muted text-xs">
                    {event.source_name}
                  </td>
                </tr>
              ) : (
                <tr key={event.id} className="border-b hover:bg-elevated transition">
                  <td className="py-2 px-2 text-right text-[11px] text-fg-subtle select-none tabular-nums">{rowIdx + 1}</td>
                  <td className="py-2 px-2">
                    <input
                      type="checkbox"
                      checked={selected.has(event.id)}
                      onChange={() => toggleSelect(event.id)}
                      className="rounded cursor-pointer"
                    />
                  </td>
                  <td className="py-2 pr-4 text-fg-muted text-xs whitespace-nowrap">
                    {(() => {
                      const ts = event.scraped_at ?? event.created_at;
                      const label = ts ? new Date(ts).toLocaleDateString("zh") : "—";
                      return event.scraped_at
                        ? <span>{label}</span>
                        : <span className="text-fg-subtle" title="sub-event 生成時間">{label}</span>;
                    })()}
                  </td>
                  <td className="py-2 pr-4">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${getAnnotationBadgeClass(event.annotation_status)}`}>
                      {getAnnotationLabel(event.annotation_status)}
                    </span>
                  </td>
                  <td className="py-2 pr-4 whitespace-nowrap">
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          sessionStorage.setItem("ttr_admin_scroll", String(window.scrollY));
                          router.push(`/${locale}/admin/${event.id}`);
                        }}
                        className="text-blue-600 hover:underline text-xs"
                      >
                        {t("edit")}
                      </button>
                      <button
                        onClick={() => handleToggleForceRescrape(event.id)}
                        title={event.force_rescrape ? t("forceRescrapeOff") : t("forceRescrapeOn")}
                        className={`text-xs hover:underline ${event.force_rescrape ? "text-orange-600 font-medium" : "text-fg-subtle hover:text-orange-500"}`}
                      >
                        🔁
                      </button>
                    </div>
                  </td>
                  <td className="py-2 pr-4 max-w-sm">
                    <a
                      href={event.is_active ? `/${locale}/events/${event.id}` : `/${locale}/admin/${event.id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-fg-strong line-clamp-2 block hover:underline hover:text-green-700 transition"
                      title={event.is_active ? t("viewFrontend") : t("edit")}
                    >
                      {event.raw_title || getEventName(event, locale)}
                    </a>
                    {event.force_rescrape && (
                      <span className="inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium">
                        🔁 {t("forceRescrapeQueued")}
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-fg-muted text-xs">
                    {event.source_name}
                  </td>
                </tr>
              )
            ));
          })()}
          </tbody>
        </table>
      </div>
    </div>

    {showCreateWorkModal && (
      <AdminCreateWorkModal
        locale={locale}
        onClose={() => setShowCreateWorkModal(false)}
      />
    )}
  </>
  );
}

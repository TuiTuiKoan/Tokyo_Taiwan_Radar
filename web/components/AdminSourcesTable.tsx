"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";

export interface ResearchSource {
  id: number;
  created_at: string;
  name: string;
  url: string;
  agent_category: string | null;
  category: string | null;
  status: string;
  scraping_feasibility: string | null;
  event_types: string | null;
  frequency: string | null;
  reason: string | null;
  url_verified: boolean;
  source_profile: Record<string, unknown> | null;
  github_issue_url: string | null;
  first_seen_at: string;
  last_seen_at: string;
  scraper_source_name: string | null;
  scrape_times_per_day: number;
  scrape_hours_jst: number[];
}

interface Props {
  sources: ResearchSource[];
}

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";

const ICONS: Record<string, string> = {
  university: "🏫",
  media: "📰",
  government: "🏛️",
  thinktank: "🔬",
  social: "💬",
};

const FEASIBILITY: Record<string, string> = {
  easy: "⭐⭐⭐",
  medium: "⭐⭐",
  hard: "⭐",
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function buildIssueUrl(src: ResearchSource) {
  const title = encodeURIComponent(`feat(scraper): add ${src.name} source`);
  const body = encodeURIComponent(
    `## 來源資訊\n` +
      `- **名稱**: ${src.name}\n` +
      `- **URL**: ${src.url}\n` +
      `- **活動類型**: ${src.event_types ?? "?"}\n` +
      `- **發佈頻率**: ${src.frequency ?? "?"}\n` +
      `- **爬蟲可行性**: ${src.scraping_feasibility ?? "?"}\n` +
      `- **推薦理由**: ${src.reason ?? ""}\n\n` +
      `## 實作步驟\n` +
      `1. @Scraper Expert 分析頁面結構\n` +
      `2. 建立 \`scraper/sources/<name>.py\`\n` +
      `3. 加入 \`scraper/main.py\` SCRAPERS 清單\n` +
      `4. \`python main.py --dry-run --source <name>\`\n`
  );
  const labels = encodeURIComponent("scraper,enhancement");
  return `https://github.com/${GITHUB_REPO}/issues/new?title=${title}&body=${body}&labels=${labels}`;
}

function StatusBadge({ status }: { status: string }) {
  const t = useTranslations("admin");
  const styles: Record<string, string> = {
    candidate: "bg-amber-100 text-amber-700",
    researched: "bg-blue-100 text-blue-700",
    recommended: "bg-purple-100 text-purple-700",
    implemented: "bg-green-100 text-green-700",
    "not-viable": "bg-gray-100 text-gray-500",
  };
  const labelKey: Record<string, string> = {
    candidate: "sourceStatusCandidate",
    researched: "sourceStatusResearched",
    recommended: "sourceStatusRecommended",
    implemented: "sourceStatusImplemented",
    "not-viable": "sourceStatusNotViable",
  };
  const cls = styles[status] ?? "bg-gray-100 text-gray-500";
  const key = labelKey[status];
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {key ? t(key as Parameters<typeof t>[0]) : status}
    </span>
  );
}

export default function AdminSourcesTable({ sources }: Props) {
  const t = useTranslations("admin");
  const supabase = createClient();
  const [filter, setFilter] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");
  const [sourceList, setSourceList] = useState<ResearchSource[]>(sources);
  const [showAddForm, setShowAddForm] = useState(false);
  const [creatorSlug, setCreatorSlug] = useState("");
  const [creatorName, setCreatorName] = useState("");
  const [creatorLocation, setCreatorLocation] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  // Immediate rescrape state
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [scrapeState, setScrapeState] = useState<"idle" | "starting" | "done">("idle");
  const [scrapeError, setScrapeError] = useState<string | null>(null);

  // Schedule edit state: srcId → { times, hours }
  const [scheduleEdits, setScheduleEdits] = useState<Record<number, { times: number; hours: number[] }>>({});
  const [scheduleSaving, setScheduleSaving] = useState<number | null>(null);
  const [scheduleSaved, setScheduleSaved] = useState<Set<number>>(new Set());

  function toggleSelect(sourceKey: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(sourceKey)) next.delete(sourceKey);
      else next.add(sourceKey);
      return next;
    });
  }

  async function handleScrapeNow() {
    setScrapeState("starting");
    setScrapeError(null);
    try {
      const res = await fetch("/api/admin/scrape-now", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: selected.size > 0 ? [...selected] : [] }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setScrapeError(data.error ?? `HTTP ${res.status}`);
        setScrapeState("idle");
        return;
      }
      setScrapeState("done");
      setTimeout(() => setScrapeState("idle"), 5000);
    } catch (err) {
      setScrapeError(err instanceof Error ? err.message : "Unknown error");
      setScrapeState("idle");
    }
  }

  function getScheduleForSrc(src: ResearchSource) {
    return scheduleEdits[src.id] ?? { times: src.scrape_times_per_day ?? 1, hours: src.scrape_hours_jst ?? [9] };
  }

  function setScheduleTimes(srcId: number, times: number, currentSrc: ResearchSource) {
    const current = getScheduleForSrc(currentSrc);
    const hours = current.hours.slice(0, times);
    while (hours.length < times) hours.push(9);
    setScheduleEdits((prev) => ({ ...prev, [srcId]: { times, hours } }));
  }

  function setScheduleHour(srcId: number, idx: number, hour: number, currentSrc: ResearchSource) {
    const current = getScheduleForSrc(currentSrc);
    const hours = [...current.hours];
    hours[idx] = hour;
    setScheduleEdits((prev) => ({ ...prev, [srcId]: { ...current, hours } }));
  }

  async function handleSaveSchedule(src: ResearchSource) {
    const edit = getScheduleForSrc(src);
    setScheduleSaving(src.id);
    const { error } = await supabase
      .from("research_sources")
      .update({ scrape_times_per_day: edit.times, scrape_hours_jst: edit.hours })
      .eq("id", src.id);
    setScheduleSaving(null);
    if (!error) {
      setSourceList((prev) =>
        prev.map((s) =>
          s.id === src.id ? { ...s, scrape_times_per_day: edit.times, scrape_hours_jst: edit.hours } : s
        )
      );
      setScheduleSaved((prev) => new Set([...prev, src.id]));
      setTimeout(() => setScheduleSaved((prev) => { const n = new Set(prev); n.delete(src.id); return n; }), 2000);
    }
  }

  async function handleAddCreator(e: React.FormEvent) {
    e.preventDefault();
    const slug = creatorSlug.trim().replace(/^https?:\/\/note\.com\/?/, "").replace(/\/$/, "");
    if (!slug || !creatorName.trim()) return;
    setAdding(true);
    setAddError(null);

    const url = `https://note.com/${slug}`;
    const sourceProfile = creatorLocation.trim()
      ? { location_name: creatorLocation.trim(), categories: ["taiwan_japan"] }
      : { categories: ["taiwan_japan"] };

    const { data, error } = await supabase
      .from("research_sources")
      .insert({
        name: creatorName.trim(),
        url,
        status: "implemented",
        agent_category: "social",
        category: "taiwan_japan",
        event_types: "台灣相關活動 (note.com RSS)",
        source_profile: sourceProfile,
        reason: `note.com 創作者 @${slug}，手動新增`,
        url_verified: true,
      })
      .select()
      .single();

    setAdding(false);
    if (error) {
      setAddError(error.message);
      return;
    }
    if (data) {
      setSourceList((prev) => [data as ResearchSource, ...prev]);
    }
    setCreatorSlug("");
    setCreatorName("");
    setCreatorLocation("");
    setShowAddForm(false);
  }

  // 來源分類對照表（依 research_sources.id）
  const SOURCE_TYPE_MAP: Record<number, string> = {
    // 活動平台
    14: "event_platform", 47: "event_platform", 20: "event_platform",
    19: "event_platform", 17: "event_platform", 32: "event_platform",
    45: "event_platform", 15: "event_platform", 77: "event_platform",
    4:  "event_platform",  6: "event_platform", 23: "event_platform",
    79: "event_platform", 83: "event_platform",
    // 學術單位
    28: "academic", 29: "academic", 24: "academic", 25: "academic",
    10: "academic", 26: "academic", 31: "academic", 27: "academic",
    30: "academic", 54: "academic", 55: "academic", 61: "academic",
    62: "academic", 63: "academic", 64: "academic", 65: "academic",
    84: "academic", 92: "academic", 93: "academic",  1: "academic",
     2: "academic",  3: "academic", 12: "academic", 52: "academic",
    74: "academic",
    // 展場
    81: "venue", 76: "venue", 48: "venue", 49: "venue", 75: "venue",
    85: "venue", 53: "venue", 82: "venue",  5: "venue",
    // 電影
    35: "cinema", 56: "cinema", 38: "cinema", 41: "cinema", 33: "cinema",
    34: "cinema", 50: "cinema", 51: "cinema", 36: "cinema", 59: "cinema",
    58: "cinema", 86: "cinema", 70: "cinema", 67: "cinema", 37: "cinema",
    39: "cinema", 40: "cinema",
    // 電視
    95: "tv", 71: "tv", 72: "tv", 73: "tv", 94: "tv",
    // 政府機構
     8: "government", 13: "government", 80: "government", 87: "government",
     7: "government", 16: "government", 60: "government", 66: "government",
    68: "government", 89: "government", 90: "government", 88: "government",
    // 百貨
    46: "department_store",
    // 活動策劃組織
    57: "organizer", 21: "organizer", 69: "organizer", 91: "organizer",
    18: "organizer",  9: "organizer", 22: "organizer",
    // 個人頁面
    78: "personal",
  };

  const SOURCE_TYPE_LABELS: Record<string, string> = {
    all:              "全部分類",
    event_platform:   "活動平台",
    academic:         "學術單位",
    venue:            "展場",
    cinema:           "電影",
    tv:               "電視",
    government:       "政府機構",
    department_store: "百貨",
    organizer:        "活動策劃組織",
    personal:         "個人頁面",
  };

  function getFilteredSources(list: ResearchSource[]) {
    return list.filter((s) => {
      if (filter === "implemented" && s.status !== "implemented") return false;
      if (filter === "not-viable" && s.status !== "not-viable") return false;
      if (filter === "has_issue" && !s.github_issue_url) return false;
      if (filterType !== "all" && (SOURCE_TYPE_MAP[s.id] ?? "other") !== filterType) return false;
      return true;
    });
  }

  const filtered = getFilteredSources(sourceList);

  if (sourceList.length === 0) {
    return <p className="text-sm text-gray-400">{t("sourcesNone")}</p>;
  }

  return (
    <div>
      {/* Add note.com creator form */}
      <div className="mb-4">
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className="text-xs px-3 py-1.5 bg-green-50 text-green-700 border border-green-200 rounded-lg hover:bg-green-100 transition font-medium"
        >
          {showAddForm ? "✕ " : "＋ "}{t("addNoteCreator")}
        </button>

        {showAddForm && (
          <form
            onSubmit={handleAddCreator}
            className="mt-3 p-4 bg-white border border-green-200 rounded-xl space-y-3 max-w-lg"
          >
            <p className="text-xs text-gray-500">{t("addNoteCreatorHint")}</p>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                {t("addNoteCreatorSlug")} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={creatorSlug}
                onChange={(e) => setCreatorSlug(e.target.value)}
                placeholder="kuroshio2026"
                required
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-400"
              />
              {creatorSlug.trim() && (
                <p className="text-xs text-gray-400 mt-1">
                  → https://note.com/{creatorSlug.trim().replace(/^https?:\/\/note\.com\/?/, "").replace(/\/$/, "")}
                </p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                {t("addNoteCreatorName")} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={creatorName}
                onChange={(e) => setCreatorName(e.target.value)}
                placeholder="黒潮ネット"
                required
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-400"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                {t("addNoteCreatorLocation")}
              </label>
              <input
                type="text"
                value={creatorLocation}
                onChange={(e) => setCreatorLocation(e.target.value)}
                placeholder="東京都文京区"
                className="w-full text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-400"
              />
            </div>
            {addError && (
              <p className="text-xs text-red-600">{addError}</p>
            )}
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={adding}
                className="text-xs px-4 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition"
              >
                {adding ? "…" : t("addNoteCreatorSubmit")}
              </button>
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="text-xs px-4 py-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition"
              >
                {t("cancel")}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Filter dropdowns */}
      <div className="flex gap-4 flex-wrap mb-4 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">狀態</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="all">全部</option>
            <option value="implemented">已建立爬蟲</option>
            <option value="not-viable">不適合</option>
            <option value="has_issue">已建立 Issue</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">來源分類</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            {Object.entries(SOURCE_TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>
        <span className="text-xs text-gray-400 self-center">{filtered.length} 筆</span>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="sticky top-0 z-10 flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-4 py-2.5 mb-4">
          <span className="text-xs font-medium text-amber-800">
            已選取 {selected.size} 個來源
          </span>
          <button
            onClick={() => setSelected(new Set())}
            className="text-xs text-amber-600 hover:text-amber-800 underline"
          >
            取消全選
          </button>
          <div className="ml-auto flex items-center gap-2">
            {scrapeState === "done" && (
              <span className="text-xs text-green-700 font-medium">✓ 爬蟲已觸發</span>
            )}
            {scrapeError && (
              <span className="text-xs text-red-600">{t("scrapeNowError")}: {scrapeError}</span>
            )}
            <button
              onClick={handleScrapeNow}
              disabled={scrapeState !== "idle"}
              className="text-xs px-3 py-1.5 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 transition font-medium"
            >
              {scrapeState === "starting" ? "正在啟動…" : t("scrapeNowSelected", { count: selected.size })}
            </button>
          </div>
        </div>
      )}

      {filtered.length === 0 && (
        <p className="text-sm text-gray-400">{t("sourcesNone")}</p>
      )}

      <div className="space-y-2">
        {filtered.map((src) => {
        const catKey = src.agent_category ?? src.category ?? "";
        const isResearched = src.status === "researched";
        const isRecommendedOrDone =
          src.status === "recommended" || src.status === "implemented";
        const hasScraperKey = Boolean(src.scraper_source_name);
        const isChecked = src.scraper_source_name ? selected.has(src.scraper_source_name) : false;
        const schedule = getScheduleForSrc(src);

        return (
          <div
            key={src.id}
            className={`bg-white border rounded-xl p-4 text-sm transition ${isChecked ? "border-amber-400 ring-1 ring-amber-300" : "border-gray-200"}`}
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
                {hasScraperKey && (
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => toggleSelect(src.scraper_source_name!)}
                    className="w-4 h-4 accent-amber-500 cursor-pointer"
                    aria-label={`選取 ${src.name}`}
                  />
                )}
                <span className="text-base">{ICONS[catKey] ?? "📎"}</span>
                <span className="font-medium text-gray-800">{src.name}</span>
                <StatusBadge status={src.status} />
                {src.scraping_feasibility && (
                  <span className="text-gray-400 text-xs">
                    {FEASIBILITY[src.scraping_feasibility] ?? "?"}
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-400 whitespace-nowrap">
                {t("sourcesLastSeen")}: {fmtDate(src.last_seen_at)}
              </span>
            </div>

            {/* URL */}
            <a
              href={src.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline break-all mt-1 block"
            >
              {src.url}
            </a>

            {/* Details */}
            {(src.event_types || src.frequency) && (
              <div className="flex gap-4 mt-2 text-xs text-gray-500">
                {src.event_types && <span>{src.event_types}</span>}
                {src.frequency && <span>{src.frequency}</span>}
              </div>
            )}

            {src.reason && (
              <p className="text-xs text-gray-500 mt-1">{src.reason}</p>
            )}

            {/* Action buttons */}
            <div className="mt-3 flex gap-2 flex-wrap">
              {isResearched && (
                <a
                  href={buildIssueUrl(src)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
                >
                  📋 {t("researchCreateIssue")}
                </a>
              )}

              {src.status === "candidate" && (
                <span
                  className="inline-flex items-center gap-1 text-xs px-3 py-1.5 bg-gray-100 text-gray-400 rounded-lg cursor-not-allowed"
                  title={t("sourcesResearchWith")}
                >
                  🔍 {t("sourcesResearchWith")}
                </span>
              )}

              {isRecommendedOrDone && src.github_issue_url && (
                <a
                  href={src.github_issue_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-purple-600 hover:underline"
                >
                  🔗 GitHub Issue
                </a>
              )}

              {/* Immediate rescrape button (single source) */}
              {hasScraperKey && (
                <button
                  onClick={() => {
                    setSelected(new Set([src.scraper_source_name!]));
                    handleScrapeNow();
                  }}
                  disabled={scrapeState !== "idle"}
                  className="text-xs px-3 py-1.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-lg hover:bg-amber-100 disabled:opacity-40 transition"
                >
                  ↺ {t("scrapeNow")}
                </button>
              )}
            </div>

            {/* Schedule configuration (for sources with a scraper) */}
            {hasScraperKey && (
              <div className="mt-3 pt-3 border-t border-gray-100">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs text-gray-500 font-medium">每天爬取</span>
                  <select
                    value={schedule.times}
                    onChange={(e) => setScheduleTimes(src.id, Number(e.target.value), src)}
                    className="h-7 border border-gray-200 rounded-md px-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400"
                  >
                    {[1, 2, 3, 4, 6, 8].map((n) => (
                      <option key={n} value={n}>{n} 次</option>
                    ))}
                  </select>
                  <span className="text-xs text-gray-500 font-medium">時間（JST）</span>
                  <div className="flex gap-1 flex-wrap">
                    {Array.from({ length: schedule.times }).map((_, i) => (
                      <select
                        key={i}
                        value={schedule.hours[i] ?? 9}
                        onChange={(e) => setScheduleHour(src.id, i, Number(e.target.value), src)}
                        className="h-7 border border-gray-200 rounded-md px-1 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400"
                      >
                        {Array.from({ length: 24 }, (_, h) => (
                          <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>
                        ))}
                      </select>
                    ))}
                  </div>
                  <button
                    onClick={() => handleSaveSchedule(src)}
                    disabled={scheduleSaving === src.id}
                    className="text-xs px-2.5 py-1 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-40 transition"
                  >
                    {scheduleSaving === src.id ? "…" : scheduleSaved.has(src.id) ? "✓ 已儲存" : "儲存"}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
      </div>
    </div>
  );
}

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
  const [filter, setFilter] = useState<string>("all");
  const [filterType, setFilterType] = useState<string>("all");
  const [sourceList, setSourceList] = useState<ResearchSource[]>(sources);
  const [showAddForm, setShowAddForm] = useState(false);
  const [creatorSlug, setCreatorSlug] = useState("");
  const [creatorName, setCreatorName] = useState("");
  const [creatorLocation, setCreatorLocation] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

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

    const supabase = createClient();
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

      {filtered.length === 0 && (
        <p className="text-sm text-gray-400">{t("sourcesNone")}</p>
      )}

      <div className="space-y-2">
        {filtered.map((src) => {
        const catKey = src.agent_category ?? src.category ?? "";
        const isResearched = src.status === "researched";
        const isRecommendedOrDone =
          src.status === "recommended" || src.status === "implemented";

        return (
          <div
            key={src.id}
            className="bg-white border border-gray-200 rounded-xl p-4 text-sm"
          >
            {/* Header */}
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2 flex-wrap">
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
            </div>
          </div>
        );
      })}
      </div>
    </div>
  );
}

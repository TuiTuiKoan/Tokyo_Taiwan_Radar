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

  const STATUS_FILTERS = [
    { key: "all",          label: t("filterAll") },
    { key: "implemented",  label: `✅ ${t("sourceStatusImplemented")}` },
    { key: "not-viable",   label: `🚫 ${t("sourceStatusNotViable")}` },
    { key: "researched",   label: `🔍 ${t("sourceStatusResearched")}` },
    { key: "recommended",  label: `⭐ ${t("sourceStatusRecommended")}` },
    { key: "candidate",    label: `🔄 ${t("sourceStatusCandidate")}` },
  ];

  const filtered = filter === "all" ? sourceList : sourceList.filter((s) => s.status === filter);

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

      {/* Status filter bar */}
      <div className="flex gap-2 flex-wrap mb-4">
        {STATUS_FILTERS.map(({ key, label }) => {
          const count = key === "all" ? sources.length : sources.filter((s) => s.status === key).length;
          if (key !== "all" && count === 0) return null;
          return (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`text-xs px-3 py-1.5 rounded-full font-medium border transition ${
                filter === key
                  ? "bg-green-600 text-white border-green-600"
                  : "bg-white text-gray-600 border-gray-200 hover:border-green-400"
              }`}
            >
              {label} <span className="opacity-60">({count})</span>
            </button>
          );
        })}
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

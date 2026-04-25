"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import type { ResearchSource } from "@/components/AdminSourcesTable";

export interface ResearchReport {
  id: number;
  created_at: string;
  report_type: string;
  content: {
    top_sources?: {
      name: string;
      url: string;
      category: string;
      agent_category?: string;
      event_types: string;
      frequency: string;
      scraping_feasibility: string;
      reason: string;
      url_verified?: boolean;
      url_status?: number;
    }[];
    news_summary?: string[];
    trend_keywords?: string[];
    category_suggestions?: string[];
  };
  status: string;
}

interface Props {
  reports: ResearchReport[];
  locale: string;
  sources?: ResearchSource[];
}

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

const GITHUB_REPO = "TuiTuiKoan/Tokyo_Taiwan_Radar";

type TopSource = NonNullable<ResearchReport["content"]["top_sources"]>[number];

function buildIssueUrl(src: TopSource) {
  const title = encodeURIComponent(`feat(scraper): add ${src.name} source`);
  const body = encodeURIComponent(
    `## 來源資訊\n` +
    `- **名稱**: ${src.name}\n` +
    `- **URL**: ${src.url}\n` +
    `- **活動類型**: ${src.event_types}\n` +
    `- **發佈頻率**: ${src.frequency}\n` +
    `- **爬蟲可行性**: ${src.scraping_feasibility}\n` +
    `- **推薦理由**: ${src.reason}\n\n` +
    `## 實作步驟\n` +
    `1. @Scraper Expert 分析頁面結構\n` +
    `2. 建立 \`scraper/sources/<name>.py\`\n` +
    `3. 加入 \`scraper/main.py\` SCRAPERS 清單\n` +
    `4. \`python main.py --dry-run --source <name>\`\n`
  );
  const labels = encodeURIComponent("scraper,enhancement");
  return `https://github.com/${GITHUB_REPO}/issues/new?title=${title}&body=${body}&labels=${labels}`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AdminResearchTable({ reports, locale, sources = [] }: Props) {
  const t = useTranslations("admin");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [rows, setRows] = useState(reports);
  const [reviewingId, setReviewingId] = useState<number | null>(null);

  // Build a lookup: normalised URL → current status from research_sources
  const sourceStatusMap = new Map<string, string>();
  for (const s of sources) {
    try {
      const key = new URL(s.url).hostname;
      sourceStatusMap.set(key, s.status);
    } catch {
      sourceStatusMap.set(s.url, s.status);
    }
  }

  async function markReviewed(id: number) {
    setReviewingId(id);
    const supabase = createClient();
    const { error } = await supabase
      .from("research_reports")
      .update({ status: "reviewed" })
      .eq("id", id);
    setReviewingId(null);
    if (error) {
      console.error("markReviewed error:", error);
      alert(`更新失敗：${error.message}`);
      return;
    }
    setRows((prev) =>
      prev.map((r) => (r.id === id ? { ...r, status: "reviewed" } : r))
    );
  }

  if (rows.length === 0) {
    return (
      <p className="text-sm text-gray-400">{t("researchNoReports")}</p>
    );
  }

  return (
    <div className="space-y-3">
      {rows.map((report) => {
        const isOpen = expandedId === report.id;
        const content = report.content;

        return (
          <div
            key={report.id}
            className="bg-white border border-gray-200 rounded-xl overflow-hidden"
          >
            {/* Header row */}
            <button
              type="button"
              onClick={() => setExpandedId(isOpen ? null : report.id)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition"
            >
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">
                  {fmtDate(report.created_at)}
                </span>
                <span className="text-sm font-medium text-gray-700">
                  {report.report_type}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    report.status === "pending"
                      ? "bg-amber-100 text-amber-700"
                      : report.status === "reviewed"
                        ? "bg-green-100 text-green-700"
                        : "bg-blue-100 text-blue-700"
                  }`}
                >
                  {t(
                    report.status === "pending"
                      ? "researchStatusPending"
                      : report.status === "reviewed"
                        ? "researchStatusReviewed"
                        : "researchStatusImplemented"
                  )}
                </span>
              </div>
              <span className="text-gray-400 text-sm">
                {isOpen ? "▲" : "▼"}
              </span>
            </button>

            {/* Expanded content */}
            {isOpen && (
              <div className="px-4 pb-4 space-y-4 border-t border-gray-100">
                {/* Top sources */}
                {content.top_sources && content.top_sources.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-600 mt-3 mb-2">
                      📌 {t("researchSources")}
                    </h4>
                    <div className="space-y-2">
                      {/* Deduplicate by URL within this report */}
                      {content.top_sources
                        .filter((src, idx, arr) =>
                          arr.findIndex((s) => s.url === src.url) === idx
                        )
                        .map((src, i) => {
                        const verified = src.url_verified;
                        const catKey = src.agent_category || src.category;
                        // Look up current status from research_sources
                        let currentStatus: string | undefined;
                        try {
                          const hostname = new URL(src.url).hostname;
                          currentStatus = sourceStatusMap.get(hostname);
                        } catch {
                          currentStatus = sourceStatusMap.get(src.url);
                        }
                        const isDone = currentStatus === "implemented";
                        const isNotViable = currentStatus === "not-viable";
                        const isResearched = currentStatus === "researched";
                        const isDimmed = isDone || isNotViable;

                        const statusBadgeStyles: Record<string, string> = {
                          implemented: "bg-green-100 text-green-700",
                          "not-viable": "bg-gray-100 text-gray-500 line-through",
                          researched: "bg-blue-100 text-blue-700",
                          recommended: "bg-purple-100 text-purple-700",
                          candidate: "bg-amber-100 text-amber-700",
                        };
                        const statusLabel: Record<string, string> = {
                          implemented: "✅ 已實作",
                          "not-viable": "🚫 已排除",
                          researched: "🔍 已研究",
                          recommended: "⭐ 推薦",
                          candidate: "🔄 候選",
                        };

                        return (
                          <div
                            key={i}
                            className={`rounded-lg p-3 text-sm border ${
                              isDimmed
                                ? "bg-gray-50 border-gray-100 opacity-50"
                                : verified
                                  ? "bg-green-50 border-green-100"
                                  : "bg-gray-50 border-gray-100 opacity-60"
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <span>{ICONS[catKey] ?? "📎"}</span>
                              <span className={`font-medium ${isDimmed ? "line-through text-gray-400" : ""}`}>
                                {src.name}
                              </span>
                              <span className="text-gray-400 text-xs">
                                {FEASIBILITY[src.scraping_feasibility] ?? "?"}
                              </span>
                              {currentStatus && (
                                <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${statusBadgeStyles[currentStatus] ?? "bg-gray-100 text-gray-500"}`}>
                                  {statusLabel[currentStatus] ?? currentStatus}
                                </span>
                              )}
                              {!currentStatus && verified !== undefined && (
                                <span
                                  className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                                    verified
                                      ? "bg-green-100 text-green-700"
                                      : "bg-red-100 text-red-600"
                                  }`}
                                >
                                  {verified ? "✅ URL 有效" : "❌ URL 無效"}
                                </span>
                              )}
                            </div>
                            <a
                              href={src.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-600 hover:underline break-all"
                            >
                              {src.url}
                            </a>
                            {!isDimmed && (
                              <>
                                <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
                                  <div>{t("researchFrequency")}: {src.frequency}</div>
                                  <div>{t("researchFeasibility")}: {src.scraping_feasibility}</div>
                                </div>
                                <p className="text-xs text-gray-500 mt-1">
                                  {t("researchReason")}: {src.reason}
                                </p>
                                {/* Create scraper GitHub Issue button — only for non-implemented, non-excluded */}
                                {!isResearched && (
                                  <div className="mt-2">
                                    {verified ? (
                                      <a
                                        href={buildIssueUrl(src)}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
                                      >
                                        📋 {t("researchCreateIssue")}
                                      </a>
                                    ) : (
                                      <span
                                        className="inline-flex items-center gap-1 text-xs px-2.5 py-1 bg-gray-200 text-gray-400 rounded-lg cursor-not-allowed"
                                        title="URL 尚未驗證，無法建立 Issue"
                                      >
                                        📋 {t("researchCreateIssue")}
                                      </span>
                                    )}
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* News summary */}
                {content.news_summary && content.news_summary.length > 0 && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-600 mb-2">
                      📰 {t("researchNews")}
                    </h4>
                    <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                      {content.news_summary.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Trend keywords */}
                {content.trend_keywords &&
                  content.trend_keywords.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-600 mb-2">
                        🔑 {t("researchKeywords")}
                      </h4>
                      <div className="flex flex-wrap gap-1">
                        {content.trend_keywords.map((kw, i) => (
                          <span
                            key={i}
                            className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Category suggestions */}
                {content.category_suggestions &&
                  content.category_suggestions.length > 0 && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-600 mb-2">
                        🏷️ {t("researchCategories")}
                      </h4>
                      <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                        {content.category_suggestions.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                {/* Mark as reviewed button */}
                {report.status === "pending" && (
                  <button
                    type="button"
                    onClick={() => markReviewed(report.id)}
                    disabled={reviewingId === report.id}
                    className="mt-2 px-4 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                  >
                    {reviewingId === report.id ? "..." : `✓ ${t("researchMarkReviewed")}`}
                  </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

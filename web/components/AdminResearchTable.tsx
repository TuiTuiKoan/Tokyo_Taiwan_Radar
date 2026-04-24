"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";

export interface ResearchReport {
  id: number;
  created_at: string;
  report_type: string;
  content: {
    top_sources?: {
      name: string;
      url: string;
      category: string;
      event_types: string;
      frequency: string;
      scraping_feasibility: string;
      reason: string;
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

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AdminResearchTable({ reports, locale }: Props) {
  const t = useTranslations("admin");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [rows, setRows] = useState(reports);

  async function markReviewed(id: number) {
    const supabase = createClient();
    await supabase
      .from("research_reports")
      .update({ status: "reviewed" })
      .eq("id", id);
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
                      {content.top_sources.map((src, i) => (
                        <div
                          key={i}
                          className="bg-gray-50 rounded-lg p-3 text-sm"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span>{ICONS[src.category] ?? "📎"}</span>
                            <span className="font-medium">{src.name}</span>
                            <span className="text-gray-400 text-xs">
                              {FEASIBILITY[src.scraping_feasibility] ?? "?"}
                            </span>
                          </div>
                          <a
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-600 hover:underline break-all"
                          >
                            {src.url}
                          </a>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-xs text-gray-500">
                            <div>
                              {t("researchFrequency")}: {src.frequency}
                            </div>
                            <div>
                              {t("researchFeasibility")}:{" "}
                              {src.scraping_feasibility}
                            </div>
                          </div>
                          <p className="text-xs text-gray-500 mt-1">
                            {t("researchReason")}: {src.reason}
                          </p>
                        </div>
                      ))}
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
                    className="mt-2 px-4 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
                  >
                    ✓ {t("researchMarkReviewed")}
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

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import type { Locale } from "@/lib/types";
import Link from "next/link";

export interface ReportRow {
  id: string;
  event_id: string;
  report_types: string[];
  locale: string | null;
  status: string;
  admin_notes: string | null;
  confirmed_at: string | null;
  created_at: string;
  events: {
    name_ja: string | null;
    name_zh: string | null;
    name_en: string | null;
    source_url: string | null;
    source_name: string | null;
  } | null;
}

interface Props {
  reports: ReportRow[];
  locale: Locale;
}

const STATUS_CLASSES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-700",
  confirmed: "bg-green-100 text-green-700",
  dismissed: "bg-gray-100 text-gray-500",
};

export default function AdminReportsTable({ reports: initialReports, locale }: Props) {
  const t = useTranslations("admin");
  const tReport = useTranslations("report");
  const supabase = createClient();

  const [reports, setReports] = useState<ReportRow[]>(initialReports);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  function getEventName(row: ReportRow): string {
    const ev = row.events;
    if (!ev) return row.event_id;
    if (locale === "zh") return ev.name_zh ?? ev.name_ja ?? ev.name_en ?? row.event_id;
    if (locale === "en") return ev.name_en ?? ev.name_ja ?? ev.name_zh ?? row.event_id;
    return ev.name_ja ?? ev.name_zh ?? ev.name_en ?? row.event_id;
  }

  function formatTypes(types: string[]): string {
    return types
      .map((type) => {
        if (type === "irrelevant") return tReport("irrelevant");
        if (type === "wrongDetails") return tReport("wrongDetails");
        if (type === "wrongCategory") return tReport("wrongCategory");
        return type;
      })
      .join("、");
  }

  async function handleAction(id: string, action: "confirmed" | "dismissed") {
    setSaving(id);
    const update: Record<string, unknown> = { status: action };
    if (action === "confirmed") {
      update.confirmed_at = new Date().toISOString();
      update.admin_notes = notes[id] ?? null;
    }
    const { error } = await supabase.from("event_reports").update(update).eq("id", id);
    if (!error) {
      setReports((prev) => prev.map((r) => (r.id === id ? { ...r, ...update } : r)));
      setExpandedId(null);
    }
    setSaving(null);
  }

  async function copySkillNote(row: ReportRow) {
    const name = getEventName(row);
    const types = formatTypes(row.report_types);
    const date = new Date(row.created_at).toLocaleDateString("ja-JP");
    const text = [
      `### Known Issue — ${name}`,
      `- **Source**: ${row.events?.source_url ?? "—"}`,
      `- **Source name**: ${row.events?.source_name ?? "—"}`,
      `- **Report type**: ${types}`,
      `- **Date reported**: ${date}`,
      `- **Admin notes**: ${row.admin_notes ?? "—"}`,
    ].join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(row.id);
    setTimeout(() => setCopied(null), 2000);
  }

  const STATUS_LABELS: Record<string, string> = {
    pending: t("statusPending"),
    confirmed: t("statusConfirmed"),
    dismissed: t("statusDismissed"),
  };

  const pending = reports.filter((r) => r.status === "pending");
  const others = reports.filter((r) => r.status !== "pending");

  if (reports.length === 0) {
    return <p className="text-gray-400 text-sm mt-4">{t("noReports")}</p>;
  }

  function renderRow(row: ReportRow) {
    const isExpanded = expandedId === row.id;
    const statusClass = STATUS_CLASSES[row.status] ?? "bg-gray-100 text-gray-500";
    return (
      <div key={row.id} className="bg-white">
        <button
          className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-gray-50 transition"
          onClick={() => setExpandedId(isExpanded ? null : row.id)}
        >
          <span
            className={`mt-0.5 text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${statusClass}`}
          >
            {STATUS_LABELS[row.status] ?? row.status}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-800 truncate">{getEventName(row)}</p>
            <p className="text-xs text-gray-500 mt-0.5">{formatTypes(row.report_types)}</p>
          </div>
          <span className="text-xs text-gray-400 flex-shrink-0 mt-0.5">
            {new Date(row.created_at).toLocaleDateString("ja-JP")}
          </span>
        </button>

        {isExpanded && (
          <div className="px-4 pb-4 bg-gray-50 border-t border-gray-100 space-y-3">
            <div className="flex gap-3 flex-wrap text-xs pt-2">
              <Link
                href={`/${locale}/events/${row.event_id}`}
                target="_blank"
                className="text-blue-600 hover:underline"
              >
                {t("viewEvent")} ↗
              </Link>
              {row.events?.source_url && (
                <a
                  href={row.events.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  {t("sourceLink")} ↗
                </a>
              )}
            </div>

            {row.status === "pending" && (
              <>
                <div>
                  <label className="text-xs text-gray-500 block mb-1">{t("adminNotes")}</label>
                  <textarea
                    value={notes[row.id] ?? ""}
                    onChange={(e) => setNotes((p) => ({ ...p, [row.id]: e.target.value }))}
                    rows={3}
                    className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-400"
                    placeholder={t("adminNotesPlaceholder")}
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAction(row.id, "confirmed")}
                    disabled={saving === row.id}
                    className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-40 transition"
                  >
                    {saving === row.id ? "…" : t("confirmReport")}
                  </button>
                  <button
                    onClick={() => handleAction(row.id, "dismissed")}
                    disabled={saving === row.id}
                    className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-40 transition"
                  >
                    {t("dismissReport")}
                  </button>
                </div>
              </>
            )}

            {row.status === "confirmed" && (
              <div className="space-y-2">
                {row.admin_notes && (
                  <p className="text-xs text-gray-600">
                    <span className="font-medium">{t("adminNotes")}：</span>
                    {row.admin_notes}
                  </p>
                )}
                <button
                  onClick={() => copySkillNote(row)}
                  className="text-xs bg-amber-600 text-white px-3 py-1.5 rounded-lg hover:bg-amber-700 transition"
                >
                  {copied === row.id ? t("skillNoteCopied") : t("copySkillNote")}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {pending.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-500 mb-2">
            {t("statusPending")} ({pending.length})
          </h2>
          <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
            {pending.map(renderRow)}
          </div>
        </section>
      )}
      {others.length > 0 && (
        <section>
          <h2 className="text-sm font-medium text-gray-500 mb-2">
            {t("statusReviewed")} ({others.length})
          </h2>
          <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
            {others.map(renderRow)}
          </div>
        </section>
      )}
    </div>
  );
}

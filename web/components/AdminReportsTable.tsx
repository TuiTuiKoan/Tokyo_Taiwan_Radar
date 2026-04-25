"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { type Category, CATEGORIES, type Locale } from "@/lib/types";
import Link from "next/link";
import { confirmReport } from "@/app/actions/confirm-report";

export interface ReportRow {
  id: string;
  event_id: string;
  report_types: string[];
  locale: string | null;
  status: string;
  admin_notes: string | null;
  confirmed_at: string | null;
  created_at: string;
  suggested_category: string[] | null;
  events: {
    name_ja: string | null;
    name_zh: string | null;
    name_en: string | null;
    source_url: string | null;
    source_name: string | null;
    category: string[] | null;
    start_date: string | null;
    end_date: string | null;
    location_name: string | null;
    location_address: string | null;
    business_hours: string | null;
    is_paid: boolean | null;
    price_info: string | null;
    description_ja: string | null;
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

// Maps each report field to the event column used for preview
const FIELD_PREVIEW_COL: Record<string, (ev: NonNullable<ReportRow["events"]>) => string> = {
  name: (ev) => ev.name_ja ?? "—",
  start_date: (ev) => ev.start_date ? new Date(ev.start_date).toLocaleDateString("ja-JP") : "—",
  end_date: (ev) => ev.end_date ? new Date(ev.end_date).toLocaleDateString("ja-JP") : "—",
  venue: (ev) => ev.location_name ?? "—",
  address: (ev) => ev.location_address ?? "—",
  business_hours: (ev) => ev.business_hours ?? "—",
  price: (ev) => ev.is_paid === null ? "—" : `${ev.is_paid ? "有料" : "無料"}${ev.price_info ? ` / ${ev.price_info}` : ""}`,
  description: (ev) => ev.description_ja ? ev.description_ja.slice(0, 120) + (ev.description_ja.length > 120 ? "…" : "") : "—",
};

// Which fields support direct admin correction (description excluded — too complex)
const EDITABLE_FIELDS = new Set(["name", "start_date", "end_date", "venue", "address", "business_hours", "price"]);

// Input type for each editable field
const FIELD_INPUT_TYPE: Record<string, string> = {
  start_date: "date",
  end_date: "date",
  name: "text",
  venue: "text",
  address: "text",
  business_hours: "text",
  price: "text",
};

export default function AdminReportsTable({ reports: initialReports, locale }: Props) {
  const t = useTranslations("admin");
  const tReport = useTranslations("report");
  const tCat = useTranslations("categories");
  const supabase = createClient();

  const [reports, setReports] = useState<ReportRow[]>(initialReports);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [confirmFeedback, setConfirmFeedback] = useState<Record<string, { githubUpdated: boolean }>>({});
  const [correctCategory, setCorrectCategory] = useState<Record<string, string[]>>({});
  const [fieldEdits, setFieldEdits] = useState<Record<string, Record<string, string>>>({});

  function getEventName(row: ReportRow): string {
    const ev = row.events;
    if (!ev) return row.event_id;
    if (locale === "zh") return ev.name_zh ?? ev.name_ja ?? ev.name_en ?? row.event_id;
    if (locale === "en") return ev.name_en ?? ev.name_ja ?? ev.name_zh ?? row.event_id;
    return ev.name_ja ?? ev.name_zh ?? ev.name_en ?? row.event_id;
  }

  function formatTypes(types: string[]): string {
    const baseTypes = types.filter((t) => !t.startsWith("field:"));
    const fields = types.filter((t) => t.startsWith("field:")).map((t) => t.replace("field:", ""));
    const labels = baseTypes.map((type) => {
      if (type === "irrelevant") return tReport("irrelevant");
      if (type === "wrongDetails") return tReport("wrongDetails");
      if (type === "wrongCategory") return tReport("wrongCategory");
      return type;
    });
    if (fields.length > 0) {
      labels.push(`[${fields.join(", ")}]`);
    }
    return labels.join("、");
  }

  async function handleConfirm(row: ReportRow) {
    setSaving(row.id);
    const result = await confirmReport({
      reportId: row.id,
      eventId: row.event_id,
      adminNotes: notes[row.id] ?? "",
      reportTypes: row.report_types,
      eventName: getEventName(row),
      sourceName: row.events?.source_name ?? null,
      currentCategory: row.events?.category ?? [],
      correctCategory: correctCategory[row.id] ?? null,
      suggestedCategory: row.suggested_category ?? null,
      fieldCorrections: fieldEdits[row.id] ?? {},
    });
    if (result.ok) {
      const updatedRow: ReportRow = {
        ...row,
        status: "confirmed",
        confirmed_at: new Date().toISOString(),
        admin_notes: notes[row.id] ?? null,
      };
      setReports((prev) => prev.map((r) => (r.id === row.id ? updatedRow : r)));
      setConfirmFeedback((prev) => ({ ...prev, [row.id]: { githubUpdated: result.githubUpdated } }));
      setExpandedId(row.id); // keep expanded to show feedback
    }
    setSaving(null);
  }

  async function handleDismiss(id: string) {
    setSaving(id);
    const update = { status: "dismissed" };
    const { error } = await supabase.from("event_reports").update(update).eq("id", id);
    if (!error) {
      setReports((prev) => prev.map((r) => (r.id === id ? { ...r, ...update } : r)));
      setExpandedId(null);
    }
    setSaving(null);
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
                {/* Field preview + direct correction (only for wrongDetails) */}
                {row.report_types.includes("wrongDetails") && row.events && (() => {
                  const wrongFields = row.report_types
                    .filter((t) => t.startsWith("field:"))
                    .map((t) => t.replace("field:", ""));
                  if (wrongFields.length === 0) return null;
                  return (
                    <div>
                      <p className="text-xs font-medium text-gray-600 mb-2">{t("fieldPreview")}</p>
                      <div className="space-y-2 bg-white border border-gray-200 rounded-lg p-3">
                        {wrongFields.map((field) => {
                          const currentVal = FIELD_PREVIEW_COL[field]?.(row.events!) ?? "—";
                          const isEditable = EDITABLE_FIELDS.has(field);
                          const inputType = FIELD_INPUT_TYPE[field] ?? "text";
                          const editVal = fieldEdits[row.id]?.[field] ?? "";
                          return (
                            <div key={field} className="grid grid-cols-[120px_1fr] gap-2 items-start">
                              <span className="text-xs text-gray-500 font-medium pt-1.5">
                                {tReport(`field${field.charAt(0).toUpperCase() + field.slice(1).replace(/_([a-z])/g, (_, c) => c.toUpperCase())}` as any)}
                              </span>
                              <div className="space-y-1">
                                <div className="text-xs bg-gray-50 border border-gray-100 rounded px-2 py-1 text-gray-600 break-words">
                                  {currentVal}
                                </div>
                                {isEditable ? (
                                  <input
                                    type={inputType}
                                    value={editVal}
                                    onChange={(e) =>
                                      setFieldEdits((p) => ({
                                        ...p,
                                        [row.id]: { ...(p[row.id] ?? {}), [field]: e.target.value },
                                      }))
                                    }
                                    placeholder={t("directCorrect")}
                                    className="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-green-400 placeholder:text-gray-300"
                                  />
                                ) : (
                                  <p className="text-xs text-gray-400 italic">{t("fieldNotEditable")}</p>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}
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
                {row.report_types.includes("wrongCategory") && (
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">{t("correctCategoryLabel")}</label>
                    {/* Show user's suggested categories as a hint */}
                    {row.suggested_category && row.suggested_category.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        <span className="text-xs text-gray-400 mr-1">{t("userSuggested")}:</span>
                        {row.suggested_category.map((cat) => (
                          <span key={cat} className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                            {tCat(cat as any)}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className="flex flex-wrap gap-1.5">
                      {CATEGORIES.map((cat) => {
                        // Admin selection > user suggestion > current category
                        const defaultCats = correctCategory[row.id] !== undefined
                          ? correctCategory[row.id]
                          : (row.suggested_category && row.suggested_category.length > 0)
                            ? row.suggested_category
                            : (row.events?.category ?? []);
                        const selected = defaultCats.includes(cat);
                        return (
                          <button
                            key={cat}
                            type="button"
                            onClick={() => {
                              const base = correctCategory[row.id] !== undefined
                                ? correctCategory[row.id]
                                : (row.suggested_category && row.suggested_category.length > 0)
                                  ? [...row.suggested_category]
                                  : [...(row.events?.category ?? [])];
                              const next = selected
                                ? base.filter((c) => c !== cat)
                                : [...base, cat];
                              setCorrectCategory((p) => ({ ...p, [row.id]: next }));
                            }}
                            className={`text-xs px-2 py-0.5 rounded-full border transition ${
                              selected
                                ? "bg-green-600 text-white border-green-600"
                                : "border-gray-300 text-gray-500 hover:border-green-400"
                            }`}
                          >
                          {tCat(cat as any)}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleConfirm(row)}
                    disabled={saving === row.id}
                    className="text-xs bg-green-600 text-white px-3 py-1.5 rounded-lg hover:bg-green-700 disabled:opacity-40 transition"
                  >
                    {saving === row.id ? "…" : (() => {
                      if (row.report_types.includes("irrelevant")) return t("actionHide");
                      if (row.report_types.includes("wrongCategory")) {
                        const cats = correctCategory[row.id] ?? row.suggested_category ?? [];
                        return cats.length > 0 ? t("actionApplyCategory") : t("actionReannotate");
                      }
                      // wrongDetails: check if admin filled any corrections
                      const edits = fieldEdits[row.id] ?? {};
                      const hasCorrections = Object.values(edits).some((v) => v.trim() !== "");
                      if (hasCorrections) return t("applyCorrections");
                      return t("actionReannotate");
                    })()}
                  </button>
                  <button
                    onClick={() => handleDismiss(row.id)}
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
                <p className="text-xs text-gray-500">
                  {t("eventDeactivated")}
                </p>
                {confirmFeedback[row.id] !== undefined && (
                  <p className={`text-xs ${confirmFeedback[row.id].githubUpdated ? "text-green-700" : "text-amber-600"}`}>
                    {confirmFeedback[row.id].githubUpdated
                      ? t("historyWritten")
                      : t("historySkipped")}
                  </p>
                )}
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

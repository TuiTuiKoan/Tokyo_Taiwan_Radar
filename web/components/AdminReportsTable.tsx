"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { type Category, CATEGORIES, CATEGORY_GROUPS, type Locale } from "@/lib/types";
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
    location_name_zh: string | null;
    location_name_en: string | null;
    location_address: string | null;
    location_address_zh: string | null;
    location_address_en: string | null;
    business_hours: string | null;
    business_hours_zh: string | null;
    business_hours_en: string | null;
    is_paid: boolean | null;
    price_info: string | null;
    description_ja: string | null;
    description_zh: string | null;
    description_en: string | null;
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

type LocaleKey = "zh" | "en" | "ja";
const LOCALE_LABELS: Record<LocaleKey, string> = { zh: "中文", en: "English", ja: "日本語" };
const LOCALES_ORDER: LocaleKey[] = ["zh", "en", "ja"];
// Fields whose value is not localized — show only one row
const NON_LOCALIZED_FIELDS = new Set(["start_date", "end_date", "price"]);

function getFieldLocaleValues(
  field: string,
  ev: NonNullable<ReportRow["events"]>
): Record<LocaleKey, string | null> {
  switch (field) {
    case "name": return { zh: ev.name_zh, en: ev.name_en, ja: ev.name_ja };
    case "venue": return { zh: ev.location_name_zh, en: ev.location_name_en, ja: ev.location_name };
    case "address": return { zh: ev.location_address_zh, en: ev.location_address_en, ja: ev.location_address };
    case "business_hours": return { zh: ev.business_hours_zh, en: ev.business_hours_en, ja: ev.business_hours };
    case "description": return { zh: ev.description_zh, en: ev.description_en, ja: ev.description_ja };
    case "start_date": { const v = ev.start_date ? new Date(ev.start_date).toLocaleDateString("ja-JP") : null; return { zh: v, en: v, ja: v }; }
    case "end_date": { const v = ev.end_date ? new Date(ev.end_date).toLocaleDateString("ja-JP") : null; return { zh: v, en: v, ja: v }; }
    case "price": { const v = ev.is_paid === null ? null : `${ev.is_paid ? "有料" : "無料"}${ev.price_info ? ` / ${ev.price_info}` : ""}`; return { zh: v, en: v, ja: v }; }
    default: return { zh: null, en: null, ja: null };
  }
}

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
  const [confirmFeedback, setConfirmFeedback] = useState<Record<string, { githubUpdated: boolean; wasReviewed?: boolean }>>({}); 
  const [correctCategory, setCorrectCategory] = useState<Record<string, string[]>>({});
  const [fieldEdits, setFieldEdits] = useState<Record<string, Record<string, Record<string, string>>>>({});;

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

    // Re-parse user-submitted fieldEdit suggestions so we can use them as fallback
    // when the admin has not explicitly overridden a value in the input box.
    const parsedUserEdits: Record<string, Record<string, string>> = {};
    for (const entry of row.report_types) {
      if (!entry.startsWith("fieldEdit:")) continue;
      const rest = entry.slice("fieldEdit:".length);
      const i1 = rest.indexOf(":");
      const i2 = rest.indexOf(":", i1 + 1);
      if (i1 === -1 || i2 === -1) continue;
      const f = rest.slice(0, i1);
      const loc = rest.slice(i1 + 1, i2);
      const value = rest.slice(i2 + 1);
      if (!parsedUserEdits[f]) parsedUserEdits[f] = {};
      parsedUserEdits[f][loc] = value;
    }

    // Merge: admin explicit edits take priority; fall back to user suggestions
    const adminEdits = fieldEdits[row.id] ?? {};
    const mergedCorrections: Record<string, Record<string, string>> = { ...parsedUserEdits };
    for (const [field, locales] of Object.entries(adminEdits)) {
      mergedCorrections[field] = { ...(mergedCorrections[field] ?? {}), ...locales };
    }

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
      fieldCorrections: mergedCorrections,
    });
    if (result.ok) {
      const updatedRow: ReportRow = {
        ...row,
        status: "confirmed",
        confirmed_at: new Date().toISOString(),
        admin_notes: notes[row.id] ?? null,
      };
      setReports((prev) => prev.map((r) => (r.id === row.id ? updatedRow : r)));
      setConfirmFeedback((prev) => ({ ...prev, [row.id]: { githubUpdated: result.githubUpdated, wasReviewed: result.wasReviewed } }));
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
                  // Parse user-submitted fieldEdit:<field>:<locale>:<value> entries
                  const parsedUserEdits: Record<string, Record<string, string>> = {};
                  for (const entry of row.report_types) {
                    if (!entry.startsWith("fieldEdit:")) continue;
                    const rest = entry.slice("fieldEdit:".length);
                    const i1 = rest.indexOf(":");
                    const i2 = rest.indexOf(":", i1 + 1);
                    if (i1 === -1 || i2 === -1) continue;
                    const f = rest.slice(0, i1);
                    const loc = rest.slice(i1 + 1, i2);
                    const value = rest.slice(i2 + 1);
                    if (!parsedUserEdits[f]) parsedUserEdits[f] = {};
                    parsedUserEdits[f][loc] = value;
                  }
                  return (
                    <div>
                      <p className="text-xs font-medium text-gray-600 mb-2">{t("fieldPreview")}</p>
                      <div className="space-y-3 bg-white border border-gray-200 rounded-lg p-3">
                        {wrongFields.map((field) => {
                          const vals = getFieldLocaleValues(field, row.events!);
                          const isNonLocalized = NON_LOCALIZED_FIELDS.has(field);
                          const displayLocales = isNonLocalized ? (["ja"] as LocaleKey[]) : LOCALES_ORDER;
                          const isEditable = EDITABLE_FIELDS.has(field);
                          const inputType = FIELD_INPUT_TYPE[field] ?? "text";
                          const userEditsForField = parsedUserEdits[field] ?? {};
                          return (
                            <div key={field} className="space-y-1.5">
                              <p className="text-xs text-gray-500 font-medium">
                                {tReport(`field${field.charAt(0).toUpperCase() + field.slice(1).replace(/_([a-z])/g, (_, c) => c.toUpperCase())}` as any)}
                              </p>
                              <div className="space-y-1">
                                {displayLocales.map((loc) => (
                                  <div key={loc} className="flex gap-2 items-start">
                                    {!isNonLocalized && (
                                      <span className="text-xs text-gray-400 text-right pt-1 shrink-0 w-12 leading-tight">{LOCALE_LABELS[loc]}</span>
                                    )}
                                    <div className={`space-y-0.5 ${isNonLocalized ? "flex-1" : "flex-1 min-w-0"}`}>
                                      <div className="text-xs bg-gray-50 border border-gray-100 rounded px-2 py-1 text-gray-600 break-words">
                                        {vals[loc] ?? "—"}
                                      </div>
                                      {userEditsForField[loc] && (
                                        <div className="text-xs bg-amber-50 border border-amber-200 rounded px-2 py-1 text-amber-800 break-words">
                                          → {userEditsForField[loc]}
                                        </div>
                                      )}
                                      {isEditable && (
                                        <input
                                          type={inputType}
                                          value={fieldEdits[row.id]?.[field]?.[loc] ?? userEditsForField[loc] ?? ""}
                                          onChange={(e) =>
                                            setFieldEdits((p) => ({
                                              ...p,
                                              [row.id]: {
                                                ...(p[row.id] ?? {}),
                                                [field]: { ...(p[row.id]?.[field] ?? {}), [loc]: e.target.value },
                                              },
                                            }))
                                          }
                                          placeholder={t("directCorrect")}
                                          className="w-full text-xs border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-green-400 placeholder:text-gray-300"
                                        />
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                              {!isEditable && (
                                <p className="text-xs text-gray-400 italic">{t("fieldNotEditable")}</p>
                              )}
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
                    <div className="space-y-1.5">
                      {CATEGORY_GROUPS.map((group) => {
                        const defaultCats = correctCategory[row.id] !== undefined
                          ? correctCategory[row.id]
                          : (row.suggested_category && row.suggested_category.length > 0)
                            ? row.suggested_category
                            : (row.events?.category ?? []);
                        return (
                          <div key={group.labelKey} className="grid grid-cols-[4.5rem_1fr] gap-x-3 items-start">
                            <span className="text-xs text-gray-400 font-medium pt-1 text-right leading-tight shrink-0">{tCat(group.labelKey as any)}</span>
                            <div className="flex flex-wrap gap-1.5">
                              {group.categories.map((cat) => {
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
                      const edits = fieldEdits[row.id] ?? {};
                      const hasCorrections = Object.values(edits).some((localeMap) =>
                        Object.values(localeMap).some((v) => v?.trim())
                      );
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
                  {confirmFeedback[row.id]?.wasReviewed
                    ? t("eventAppliedReviewed")
                    : t("eventDeactivated")}
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

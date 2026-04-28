"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { CATEGORY_GROUPS, type Category } from "@/lib/types";

interface Props {
  eventId: string;
  locale: string;
  selectionReason?: string | null;
  eventFields?: Partial<Record<WrongDetailField, string | null>>;
}

const REPORT_TYPES = ["irrelevant", "wrongDetails", "wrongCategory", "wrongSelectionReason"] as const;
type ReportType = (typeof REPORT_TYPES)[number];

// Fields that can be reported as wrong under "wrongDetails"
// Key = field identifier stored in report_types as "field:<key>"
const WRONG_DETAIL_FIELDS = [
  "name",
  "start_date",
  "end_date",
  "venue",
  "address",
  "business_hours",
  "price",
  "description",
] as const;
type WrongDetailField = (typeof WRONG_DETAIL_FIELDS)[number];

// Map field key → i18n key in "report" namespace
const FIELD_I18N: Record<WrongDetailField, string> = {
  name: "fieldName",
  start_date: "fieldStartDate",
  end_date: "fieldEndDate",
  venue: "fieldVenue",
  address: "fieldAddress",
  business_hours: "fieldBusinessHours",
  price: "fieldPrice",
  description: "fieldDescription",
};

export default function ReportSection({ eventId, locale, selectionReason, eventFields }: Props) {
  const t = useTranslations("report");
  const tCat = useTranslations("categories");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<ReportType>>(new Set());
  const [wrongFields, setWrongFields] = useState<Set<WrongDetailField>>(new Set());
  const [fieldEdits, setFieldEdits] = useState<Partial<Record<WrongDetailField, string>>>({});
  const [suggestedCategories, setSuggestedCategories] = useState<Set<Category>>(new Set());
  const [selectionReasonText, setSelectionReasonText] = useState<string>("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  function toggle(type: ReportType) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
        // Clear sub-fields if wrongDetails is deselected
        if (type === "wrongDetails") setWrongFields(new Set());
        // Clear suggested categories if wrongCategory is deselected
        if (type === "wrongCategory") setSuggestedCategories(new Set());
        // Clear text if wrongSelectionReason is deselected
        if (type === "wrongSelectionReason") setSelectionReasonText("");
      } else {
        next.add(type);
        // Pre-fill textarea with current selection reason when ticking
        if (type === "wrongSelectionReason") setSelectionReasonText(selectionReason || "");
      }
      return next;
    });
  }

  function toggleField(field: WrongDetailField) {
    setWrongFields((prev) => {
      const next = new Set(prev);
      if (next.has(field)) {
        next.delete(field);
        setFieldEdits((edits) => {
          const updated = { ...edits };
          delete updated[field];
          return updated;
        });
      } else {
        next.add(field);
        setFieldEdits((edits) => ({
          ...edits,
          [field]: eventFields?.[field] ?? "",
        }));
      }
      return next;
    });
  }

  async function handleSubmit() {
    if (selected.size === 0) return;
    // Require at least one field selected when wrongDetails is checked
    if (selected.has("wrongDetails") && wrongFields.size === 0) return;
    setStatus("loading");

    // Build report_types: base types + "field:xxx" for wrong detail fields
    const reportTypes: string[] = Array.from(selected);
    if (selected.has("wrongDetails")) {
      for (const field of wrongFields) {
        reportTypes.push(`field:${field}`);
        const edit = fieldEdits[field]?.trim();
        if (edit) reportTypes.push(`fieldEdit:${field}:${edit.slice(0, 500)}`);
      }
    }
    if (selected.has("wrongSelectionReason") && selectionReasonText.trim()) {
      reportTypes.push(`selectionReason:${selectionReasonText.trim().slice(0, 500)}`);
    }

    const supabase = createClient();
    const { error } = await supabase.from("event_reports").insert({
      event_id: eventId,
      report_types: reportTypes,
      locale,
      suggested_category: selected.has("wrongCategory") && suggestedCategories.size > 0
        ? Array.from(suggestedCategories)
        : null,
    });
    if (error) {
      setStatus("error");
    } else {
      setStatus("success");
      setOpen(false);
      setSelected(new Set());
      setWrongFields(new Set());
      setFieldEdits({});
      setSuggestedCategories(new Set());
      setSelectionReasonText("");
    }
  }

  const canSubmit =
    selected.size > 0 &&
    (!selected.has("wrongDetails") || wrongFields.size > 0) &&
    status !== "loading";

  if (status === "success") {
    return (
      <div className="mt-3 border-t border-amber-200 pt-3">
        <p className="text-xs text-amber-700">✓ {t("successMessage")}</p>
      </div>
    );
  }

  return (
    <div className="mt-3 border-t border-amber-200 pt-3">
      <p className="text-xs text-amber-700 mb-2">{t("aiDisclaimer")}</p>
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="text-xs text-amber-600 underline hover:text-amber-800 transition"
        >
          {t("submitReport")} →
        </button>
      ) : (
        <div className="space-y-1.5">
          {REPORT_TYPES.map((type) => (
            <div key={type}>
              <label className="flex items-center gap-2 text-xs text-amber-800 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={selected.has(type)}
                  onChange={() => toggle(type)}
                  className="accent-amber-600"
                />
                {t(type)}
              </label>

              {/* Sub-field checkboxes for wrongDetails */}
              {type === "wrongDetails" && selected.has("wrongDetails") && (
                <div className="ml-5 mt-1 space-y-1.5">
                  {WRONG_DETAIL_FIELDS.map((field) => (
                    <div key={field}>
                      <label className="flex items-center gap-2 text-xs text-amber-700 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={wrongFields.has(field)}
                          onChange={() => toggleField(field)}
                          className="accent-amber-500"
                        />
                        {t(FIELD_I18N[field] as any)}
                      </label>
                      {wrongFields.has(field) && (
                        <div className="mt-1 ml-4">
                          <p className="text-xs text-amber-600 mb-1">{t("fieldEditHint")}</p>
                          <textarea
                            rows={3}
                            value={fieldEdits[field] ?? ""}
                            onChange={(e) =>
                              setFieldEdits((prev) => ({ ...prev, [field]: e.target.value }))
                            }
                            className="w-full border border-amber-300 rounded-lg px-3 py-2 text-xs text-amber-900 bg-amber-50 focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y"
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* Suggested category selector for wrongCategory */}
              {type === "wrongCategory" && selected.has("wrongCategory") && (
                <div className="ml-5 mt-1">
                  <p className="text-xs text-amber-600 mb-1.5">{t("suggestCategoryHint")}</p>
                  <div className="grid grid-cols-1 gap-y-2">
                    {CATEGORY_GROUPS.map((group) => (
                      <div key={group.labelKey} className="grid grid-cols-[4.5rem_1fr] gap-x-3 items-start">
                        <span className="text-xs text-amber-400 pt-0.5 leading-tight text-right">{tCat(group.labelKey as any)}</span>
                        <div className="flex flex-wrap gap-1.5">
                          {group.categories.map((cat) => {
                          const isSelected = suggestedCategories.has(cat);
                          return (
                            <button
                              key={cat}
                              type="button"
                              onClick={() => {
                                setSuggestedCategories((prev) => {
                                  const next = new Set(prev);
                                  if (next.has(cat)) next.delete(cat);
                                  else next.add(cat);
                                  return next;
                                });
                              }}
                              className={`text-xs px-2 py-0.5 rounded-full border transition ${
                                isSelected
                                  ? "bg-amber-500 text-white border-amber-500"
                                  : "border-amber-300 text-amber-700 hover:border-amber-500"
                              }`}
                            >
                              {tCat(cat as any)}
                            </button>
                          );
                        })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Textarea for wrongSelectionReason */}
              {type === "wrongSelectionReason" && selected.has("wrongSelectionReason") && (
                <div className="ml-5 mt-1">
                  <p className="text-xs text-amber-600 mb-1">{t("selectionReasonHint")}</p>
                  <textarea
                    rows={4}
                    value={selectionReasonText}
                    onChange={(e) => setSelectionReasonText(e.target.value)}
                    className="w-full border border-amber-300 rounded-lg px-3 py-2 text-xs text-amber-900 bg-amber-50 focus:outline-none focus:ring-2 focus:ring-amber-400 resize-y"
                  />
                </div>
              )}
            </div>
          ))}
          <div className="flex gap-2 mt-2">
            <button
              onClick={handleSubmit}
              disabled={!canSubmit}
              className="text-xs bg-amber-600 text-white px-3 py-1 rounded hover:bg-amber-700 disabled:opacity-40 transition"
            >
              {status === "loading" ? "…" : t("submit")}
            </button>
            <button
              onClick={() => {
                setOpen(false);
                setSelected(new Set());
                setWrongFields(new Set());
                setFieldEdits({});
                setSuggestedCategories(new Set());
                setSelectionReasonText("");
              }}
              className="text-xs text-amber-600 px-2 py-1 hover:text-amber-800 transition"
            >
              {t("cancel")}
            </button>
          </div>
          {status === "error" && (
            <p className="text-xs text-red-600 mt-1">{t("errorMessage")}</p>
          )}
        </div>
      )}
    </div>
  );
}

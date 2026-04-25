"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";

interface Props {
  eventId: string;
  locale: string;
}

const REPORT_TYPES = ["irrelevant", "wrongDetails", "wrongCategory"] as const;
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

export default function ReportSection({ eventId, locale }: Props) {
  const t = useTranslations("report");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<ReportType>>(new Set());
  const [wrongFields, setWrongFields] = useState<Set<WrongDetailField>>(new Set());
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  function toggle(type: ReportType) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
        // Clear sub-fields if wrongDetails is deselected
        if (type === "wrongDetails") setWrongFields(new Set());
      } else {
        next.add(type);
      }
      return next;
    });
  }

  function toggleField(field: WrongDetailField) {
    setWrongFields((prev) => {
      const next = new Set(prev);
      if (next.has(field)) next.delete(field);
      else next.add(field);
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
      }
    }

    const supabase = createClient();
    const { error } = await supabase.from("event_reports").insert({
      event_id: eventId,
      report_types: reportTypes,
      locale,
    });
    if (error) {
      setStatus("error");
    } else {
      setStatus("success");
      setOpen(false);
      setSelected(new Set());
      setWrongFields(new Set());
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
                <div className="ml-5 mt-1 space-y-1">
                  {WRONG_DETAIL_FIELDS.map((field) => (
                    <label
                      key={field}
                      className="flex items-center gap-2 text-xs text-amber-700 cursor-pointer select-none"
                    >
                      <input
                        type="checkbox"
                        checked={wrongFields.has(field)}
                        onChange={() => toggleField(field)}
                        className="accent-amber-500"
                      />
                      {t(FIELD_I18N[field] as any)}
                    </label>
                  ))}
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

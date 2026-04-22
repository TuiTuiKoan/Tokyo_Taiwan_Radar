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

export default function ReportSection({ eventId, locale }: Props) {
  const t = useTranslations("report");
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<Set<ReportType>>(new Set());
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  function toggle(type: ReportType) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  async function handleSubmit() {
    if (selected.size === 0) return;
    setStatus("loading");
    const supabase = createClient();
    const { error } = await supabase.from("event_reports").insert({
      event_id: eventId,
      report_types: Array.from(selected),
      locale,
    });
    if (error) {
      setStatus("error");
    } else {
      setStatus("success");
      setOpen(false);
      setSelected(new Set());
    }
  }

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
            <label
              key={type}
              className="flex items-center gap-2 text-xs text-amber-800 cursor-pointer select-none"
            >
              <input
                type="checkbox"
                checked={selected.has(type)}
                onChange={() => toggle(type)}
                className="accent-amber-600"
              />
              {t(type)}
            </label>
          ))}
          <div className="flex gap-2 mt-2">
            <button
              onClick={handleSubmit}
              disabled={selected.size === 0 || status === "loading"}
              className="text-xs bg-amber-600 text-white px-3 py-1 rounded hover:bg-amber-700 disabled:opacity-40 transition"
            >
              {status === "loading" ? "…" : t("submit")}
            </button>
            <button
              onClick={() => {
                setOpen(false);
                setSelected(new Set());
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

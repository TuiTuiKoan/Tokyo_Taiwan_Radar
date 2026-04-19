"use client";

import { useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { CATEGORIES, type Locale, type Category } from "@/lib/types";
import { useState, useCallback } from "react";

interface Props {
  locale: Locale;
  currentFilters: {
    q?: string;
    category?: string;
    from?: string;
    to?: string;
    paid?: string;
    status?: string;
  };
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default function FilterBar({ locale, currentFilters }: Props) {
  const t = useTranslations("filters");
  const tCat = useTranslations("categories");
  const router = useRouter();
  const pathname = usePathname();

  // Local state — only push to URL when "Apply" is clicked
  const [draft, setDraft] = useState({
    q: currentFilters.q ?? "",
    category: currentFilters.category ?? "",
    from: currentFilters.from ?? todayStr(),
    to: currentFilters.to ?? "",
    paid: currentFilters.paid ?? "",
    status: currentFilters.status ?? "",
  });

  const set = (key: string, value: string) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  const applyFilters = useCallback(() => {
    const params = new URLSearchParams();
    Object.entries(draft).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    router.push(`${pathname}?${params.toString()}`);
  }, [draft, pathname, router]);

  const clearAll = useCallback(() => {
    const reset = { q: "", category: "", from: todayStr(), to: "", paid: "", status: "" };
    setDraft(reset);
    router.push(pathname);
  }, [pathname, router]);

  const hasFilters = Object.entries(draft).some(([k, v]) => {
    if (k === "from") return v !== todayStr();
    if (k === "to") return Boolean(v);
    return Boolean(v);
  });

  return (
    <div className="bg-gray-50 rounded-xl p-4 mb-2">
      <div className="flex flex-wrap gap-3 items-end">
        {/* Keyword search */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("search")}</label>
          <input
            type="search"
            value={draft.q}
            placeholder={t("searchPlaceholder")}
            className="h-12 border border-gray-300 rounded-lg px-3 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-green-400"
            onChange={(e) => set("q", e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") applyFilters(); }}
          />
        </div>

        {/* Category */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("category")}</label>
          <select
            value={draft.category}
            onChange={(e) => set("category", e.target.value)}
            className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("allCategories")}</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {tCat(cat)}
              </option>
            ))}
          </select>
        </div>

        {/* Date from */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("dateFrom")}</label>
          <div className="flex gap-1">
            <input
              type="date"
              value={draft.from}
              onChange={(e) => set("from", e.target.value)}
              className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            />
            <button
              onClick={() => set("from", "")}
              className={`h-12 px-2 text-xs rounded-lg border transition ${
                draft.from === ""
                  ? "bg-green-600 text-white border-green-600"
                  : "bg-white text-gray-500 border-gray-300 hover:bg-gray-50"
              }`}
            >
              ALL
            </button>
          </div>
        </div>

        {/* Date to */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("dateTo")}</label>
          <div className="flex gap-1">
            <input
              type="date"
              value={draft.to}
              onChange={(e) => set("to", e.target.value)}
              className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            />
            <button
              onClick={() => set("to", "")}
              className={`h-12 px-2 text-xs rounded-lg border transition ${
                draft.to === ""
                  ? "bg-green-600 text-white border-green-600"
                  : "bg-white text-gray-500 border-gray-300 hover:bg-gray-50"
              }`}
            >
              ALL
            </button>
          </div>
        </div>

        {/* Paid filter */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("paid")}</label>
          <select
            value={draft.paid}
            onChange={(e) => set("paid", e.target.value)}
            className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("allPaid")}</option>
            <option value="free">{t("freeOnly")}</option>
            <option value="paid">{t("paidOnly")}</option>
          </select>
        </div>

        {/* Status filter */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("status")}</label>
          <select
            value={draft.status}
            onChange={(e) => set("status", e.target.value)}
            className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("allStatus")}</option>
            <option value="active">{t("activeOnly")}</option>
            <option value="ended">{t("endedOnly")}</option>
          </select>
        </div>

        {/* Apply button */}
        <button
          onClick={applyFilters}
          className="h-12 px-5 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition self-end"
        >
          {t("apply")}
        </button>

        {/* Clear button */}
        {hasFilters && (
          <button
            onClick={clearAll}
            className="text-sm text-red-500 hover:text-red-700 underline self-end pb-2"
          >
            {t("reset")}
          </button>
        )}
      </div>
    </div>
  );
}

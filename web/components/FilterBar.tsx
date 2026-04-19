"use client";

import { useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { CATEGORIES, type Locale, type Category } from "@/lib/types";
import { useCallback } from "react";

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

export default function FilterBar({ locale, currentFilters }: Props) {
  const t = useTranslations("filters");
  const tCat = useTranslations("categories");
  const router = useRouter();
  const pathname = usePathname();

  const updateFilter = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams();
      // Preserve all current filters
      Object.entries(currentFilters).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      if (value) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      router.push(`${pathname}?${params.toString()}`);
    },
    [currentFilters, pathname, router]
  );

  function clearAll() {
    router.push(pathname);
  }

  const hasFilters = Object.values(currentFilters).some(Boolean);

  return (
    <div className="bg-gray-50 rounded-xl p-4 mb-2">
      <div className="flex flex-wrap gap-3 items-end">
        {/* Keyword search */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("search")}</label>
          <input
            type="search"
            defaultValue={currentFilters.q ?? ""}
            placeholder={t("searchPlaceholder")}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-green-400"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                updateFilter("q", (e.target as HTMLInputElement).value);
              }
            }}
            onBlur={(e) => updateFilter("q", e.target.value)}
          />
        </div>

        {/* Category */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("category")}</label>
          <select
            value={currentFilters.category ?? ""}
            onChange={(e) => updateFilter("category", e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
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
          <input
            type="date"
            defaultValue={currentFilters.from ?? ""}
            onChange={(e) => updateFilter("from", e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>

        {/* Date to */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("dateTo")}</label>
          <input
            type="date"
            defaultValue={currentFilters.to ?? ""}
            onChange={(e) => updateFilter("to", e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>

        {/* Paid filter */}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("paid")}</label>
          <select
            value={currentFilters.paid ?? ""}
            onChange={(e) => updateFilter("paid", e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
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
            value={currentFilters.status ?? ""}
            onChange={(e) => updateFilter("status", e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("allStatus")}</option>
            <option value="active">{t("activeOnly")}</option>
            <option value="ended">{t("endedOnly")}</option>
          </select>
        </div>

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

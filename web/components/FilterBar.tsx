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
    timeMode?: string;
    location?: string;
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
    from: currentFilters.from ?? "",
    to: currentFilters.to ?? "",
    paid: currentFilters.paid ?? "",
    timeMode: currentFilters.timeMode ?? "active",
    location: currentFilters.location ?? "",
  });

  // Mobile: collapsed by default, expanded if there are active filters
  const [mobileOpen, setMobileOpen] = useState(false);

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
    const reset = { q: "", category: "", from: "", to: "", paid: "", timeMode: "active", location: "" };
    setDraft(reset);
    router.push(pathname);
  }, [pathname, router]);

  const hasFilters = Object.entries(draft).some(([k, v]) => {
    if (k === "timeMode") return v !== "active";
    return Boolean(v);
  });

  return (
    <div className="mb-2">
      {/* Mobile: icon toggle row */}
      <div className="flex items-center justify-between md:hidden mb-1">
        <button
          onClick={() => setMobileOpen((o) => !o)}
          aria-expanded={mobileOpen}
          aria-label={t("search")}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition ${
            mobileOpen || hasFilters
              ? "border-green-500 text-green-700 bg-green-50"
              : "border-gray-300 text-gray-500 bg-white hover:bg-gray-50"
          }`}
        >
          {/* Search magnifier SVG */}
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          {hasFilters ? (
            <span className="text-xs font-medium">{t("apply")}</span>
          ) : (
            <span className="text-xs">{t("search")}</span>
          )}
          {hasFilters && (
            <span className="ml-1 w-2 h-2 rounded-full bg-green-500 inline-block" />
          )}
        </button>
        {hasFilters && (
          <button onClick={clearAll} className="text-xs text-red-500 hover:text-red-700 underline">
            {t("reset")}
          </button>
        )}
      </div>

      {/* Filter panel — always visible on md+, toggled on mobile */}
      <div className={`bg-gray-50 rounded-xl p-4 ${mobileOpen ? "block" : "hidden"} md:block`}>
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

          {/* Location filter */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("location")}</label>
            <select
              value={draft.location}
              onChange={(e) => set("location", e.target.value)}
              className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("allLocations")}</option>
              <option value="tokyo">{t("locationTokyo")}</option>
              <option value="other_japan">{t("locationOtherJapan")}</option>
              <option value="taiwan">{t("locationTaiwan")}</option>
            </select>
          </div>

          {/* Time mode */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("timeMode")}</label>
            <select
              value={draft.timeMode}
              onChange={(e) => {
                set("timeMode", e.target.value);
                if (e.target.value === "active") {
                  setDraft((prev) => ({ ...prev, timeMode: "active", from: "", to: "" }));
                }
              }}
              className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="active">{t("timeModeActive")}</option>
              <option value="past">{t("timeModePast")}</option>
            </select>
          </div>

          {/* Date range (only when searching past) */}
          {draft.timeMode === "past" && (
            <>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 font-medium">{t("dateFrom")}</label>
                <input
                  type="date"
                  value={draft.from}
                  onChange={(e) => set("from", e.target.value)}
                  className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 font-medium">{t("dateTo")}</label>
                <input
                  type="date"
                  value={draft.to}
                  onChange={(e) => set("to", e.target.value)}
                  className="h-12 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
            </>
          )}

          {/* Apply button */}
          <button
            onClick={() => { applyFilters(); setMobileOpen(false); }}
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
    </div>
  );
}

"use client";

import { useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { CATEGORY_GROUPS, type Locale } from "@/lib/types";
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

export default function FilterBar({ locale: _locale, currentFilters }: Props) {
  const t = useTranslations("filters");
  const tCat = useTranslations("categories");
  const router = useRouter();
  const pathname = usePathname();

  const [draft, setDraft] = useState({
    q: currentFilters.q ?? "",
    // category is comma-separated, e.g. "movie,art"
    category: currentFilters.category ?? "",
    from: currentFilters.from ?? "",
    to: currentFilters.to ?? "",
    paid: currentFilters.paid ?? "",
    timeMode: currentFilters.timeMode ?? "active",
    location: currentFilters.location ?? "",
  });

  const [mobileOpen, setMobileOpen] = useState(false);

  const set = (key: string, value: string) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  /** Push URL immediately with an updated state snapshot. */
  const pushWith = useCallback((next: typeof draft) => {
    const params = new URLSearchParams();
    Object.entries(next).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    router.push(`${pathname}?${params.toString()}`);
  }, [pathname, router]);

  /** Immediately push URL when a select changes. */
  const applyWith = useCallback((key: string, value: string) => {
    setDraft((prev) => {
      const next = { ...prev, [key]: value };
      pushWith(next);
      return next;
    });
  }, [pushWith]);

  /** Toggle a category pill — updates URL immediately. */
  const toggleCategory = useCallback((cat: string) => {
    setDraft((prev) => {
      const current = prev.category ? prev.category.split(",") : [];
      const next = current.includes(cat)
        ? current.filter((c) => c !== cat)
        : [...current, cat];
      const nextDraft = { ...prev, category: next.join(",") };
      pushWith(nextDraft);
      return nextDraft;
    });
  }, [pushWith]);

  const applyFilters = useCallback(() => {
    pushWith(draft);
  }, [draft, pushWith]);

  const clearAll = useCallback(() => {
    const reset = { q: "", category: "", from: "", to: "", paid: "", timeMode: "active", location: "" };
    setDraft(reset);
    router.push(pathname);
  }, [pathname, router]);

  const selectedCats = draft.category ? draft.category.split(",") : [];

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
      <div className={`bg-gray-50 rounded-xl p-4 space-y-3 ${mobileOpen ? "block" : "hidden"} md:block`}>

        {/* Row 1: keyword, paid, location, timeMode, apply, reset */}
        <div className="flex flex-wrap gap-3 items-end">
          {/* Keyword search */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("search")}</label>
            <input
              type="search"
              value={draft.q}
              placeholder={t("searchPlaceholder")}
              className="h-10 border border-gray-300 rounded-lg px-3 text-sm w-52 focus:outline-none focus:ring-2 focus:ring-green-400"
              onChange={(e) => set("q", e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") applyFilters(); }}
            />
          </div>

          {/* Paid filter */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("paid")}</label>
            <select
              value={draft.paid}
              onChange={(e) => applyWith("paid", e.target.value)}
              className="h-10 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
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
              onChange={(e) => applyWith("location", e.target.value)}
              className="h-10 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("allLocations")}</option>
              <option value="tokyo">{t("locationTokyo")}</option>
              <option value="other_japan">{t("locationOtherJapan")}</option>
              <option value="taiwan">{t("locationTaiwan")}</option>
              <option value="online">{t("locationOnline")}</option>
            </select>
          </div>

          {/* Time mode */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("timeMode")}</label>
            <select
              value={draft.timeMode}
              onChange={(e) => {
                if (e.target.value === "active") {
                  setDraft((prev) => {
                    const next = { ...prev, timeMode: "active", from: "", to: "" };
                    pushWith(next);
                    return next;
                  });
                } else {
                  applyWith("timeMode", e.target.value);
                }
              }}
              className="h-10 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
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
                  className="h-10 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 font-medium">{t("dateTo")}</label>
                <input
                  type="date"
                  value={draft.to}
                  onChange={(e) => set("to", e.target.value)}
                  className="h-10 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
            </>
          )}

          {/* Apply button (keyword / date) */}
          <button
            onClick={() => { applyFilters(); setMobileOpen(false); }}
            className="h-10 px-5 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition self-end"
          >
            {t("apply")}
          </button>

          {/* Clear all */}
          {hasFilters && (
            <button
              onClick={clearAll}
              className="text-sm text-red-500 hover:text-red-700 underline self-end pb-1"
            >
              {t("reset")}
            </button>
          )}
        </div>

        {/* Row 2: Category multi-select pills */}
        <div className="border-t border-gray-200 pt-3">
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-xs text-gray-500 font-medium">{t("category")}</span>
            {selectedCats.length > 0 && (
              <button
                onClick={() => applyWith("category", "")}
                className="text-xs text-gray-400 hover:text-red-500 underline"
              >
                {t("allCategories")}
              </button>
            )}
          </div>
          <div className="space-y-1.5">
            {CATEGORY_GROUPS.map((group) => (
              <div key={group.labelKey} className="flex flex-wrap gap-1.5 items-center">
                <span className="text-xs text-gray-400 w-16 shrink-0">{tCat(group.labelKey as any)}</span>
                {group.categories.map((cat) => {
                  const active = selectedCats.includes(cat);
                  return (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => toggleCategory(cat)}
                      className={`px-2.5 py-0.5 rounded-full text-xs border transition ${
                        active
                          ? "bg-green-600 text-white border-green-600"
                          : "border-gray-300 text-gray-600 hover:border-green-400"
                      }`}
                    >
                      {tCat(cat as any)}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}


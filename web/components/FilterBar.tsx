"use client";

import { useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { CATEGORY_GROUPS, type Locale } from "@/lib/types";
import { useState, useCallback, useRef, useEffect } from "react";

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
  const [catDropdownOpen, setCatDropdownOpen] = useState(false);
  const catDropdownRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (catDropdownRef.current && !catDropdownRef.current.contains(e.target as Node)) {
        setCatDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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

  /** Toggle a category — multi-select, updates URL immediately. */
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
      <div className={`bg-gray-50 rounded-xl px-4 py-3 ${mobileOpen ? "block" : "hidden"} md:block`}>

        {/* Row 1: keyword, category, location, paid, timeMode, date range, reset */}
        <div className="flex flex-wrap gap-3 items-end">
          {/* Keyword search — debounced immediate */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("search")}</label>
            <input
              type="search"
              value={draft.q}
              placeholder={t("searchPlaceholder")}
              className="h-9 border border-gray-300 rounded-lg px-3 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-green-400"
              onChange={(e) => {
                const v = e.target.value;
                setDraft((prev) => ({ ...prev, q: v }));
                if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
                searchTimerRef.current = setTimeout(() => {
                  setDraft((prev) => { pushWith(prev); return prev; });
                }, 400);
              }}
            />
          </div>

          {/* Category dropdown */}
          <div className="flex flex-col gap-1" ref={catDropdownRef}>
            <label className="text-xs text-gray-500 font-medium">{t("category")}</label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setCatDropdownOpen((o) => !o)}
                className="h-9 min-w-[9rem] flex items-center justify-between gap-2 border border-gray-300 rounded-lg px-3 text-sm bg-gray-50 hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
              >
                <span className={selectedCats.length > 0 ? "text-green-700 font-medium" : "text-gray-500"}>
                  {selectedCats.length > 0 ? `${t("category")} (${selectedCats.length})` : t("allCategories")}
                </span>
                <span className="text-gray-400 text-xs">{catDropdownOpen ? "▲" : "▼"}</span>
              </button>

              {catDropdownOpen && (
                <div className="absolute z-50 top-10 left-0 w-72 bg-white border border-gray-200 rounded-xl shadow-lg py-2 max-h-80 overflow-y-auto">
                  {selectedCats.length > 0 && (
                    <div className="px-3 pb-1.5 border-b border-gray-100 mb-1">
                      <button
                        type="button"
                        onClick={() => { applyWith("category", ""); setCatDropdownOpen(false); }}
                        className="text-xs text-red-500 hover:text-red-700 underline"
                      >
                        {t("allCategories")}
                      </button>
                    </div>
                  )}
                  {CATEGORY_GROUPS.map((group) => (
                    <div key={group.labelKey} className="px-3 py-1">
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">{tCat(group.labelKey as any)}</p>
                      {group.categories.map((cat) => {
                        const checked = selectedCats.includes(cat);
                        return (
                          <label key={cat} className="flex items-center gap-2 py-0.5 cursor-pointer hover:text-green-700">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleCategory(cat)}
                              className="accent-green-600 w-3.5 h-3.5"
                            />
                            <span className="text-sm text-gray-700">{tCat(cat as any)}</span>
                          </label>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Location filter */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("location")}</label>
            <select
              value={draft.location}
              onChange={(e) => applyWith("location", e.target.value)}
              className="h-9 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("allLocations")}</option>
              <option value="tokyo">{t("locationTokyo")}</option>
              <option value="other_japan">{t("locationOtherJapan")}</option>
              <option value="online">{t("locationOnline")}</option>
            </select>
          </div>

          {/* Paid filter */}
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">{t("paid")}</label>
            <select
              value={draft.paid}
              onChange={(e) => applyWith("paid", e.target.value)}
              className="h-9 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("allPaid")}</option>
              <option value="free">{t("freeOnly")}</option>
              <option value="paid">{t("paidOnly")}</option>
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
              className="h-9 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
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
                  onChange={(e) => applyWith("from", e.target.value)}
                  className="h-9 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 font-medium">{t("dateTo")}</label>
                <input
                  type="date"
                  value={draft.to}
                  onChange={(e) => applyWith("to", e.target.value)}
                  className="h-9 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
            </>
          )}

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

      </div>
    </div>
  );
}


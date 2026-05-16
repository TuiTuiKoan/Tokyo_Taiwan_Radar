"use client";

import { useRouter, usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { CATEGORY_GROUPS, type Locale } from "@/lib/types";
import { useState, useCallback, useRef, useEffect } from "react";
import { REGIONS_WITH_CITY, REGION_PREFECTURES, PREFECTURE_LABELS_EN, CITY_OTHER, type RegionWithCity } from "@/lib/regionPrefectures";
import { FilterChip } from "@/lib/design";

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
    city?: string;
  };
  /** Field keys to hide from the filter bar. e.g. ["category", "paid"] */
  hiddenFilters?: Array<"category" | "paid" | "timeMode" | "location" | "date">;
}

export default function FilterBar({ locale: _locale, currentFilters, hiddenFilters = [] }: Props) {
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
    city: currentFilters.city ?? "",
  });

  const [mobileOpen, setMobileOpen] = useState(false);
  const [catDropdownOpen, setCatDropdownOpen] = useState(false);
  const [locationOpen, setLocationOpen] = useState(false);
  const [cityOpen, setCityOpen] = useState(false);
  const [paidOpen, setPaidOpen] = useState(false);
  const [timeModeOpen, setTimeModeOpen] = useState(false);
  const catDropdownRef = useRef<HTMLDivElement>(null);
  const locationRef = useRef<HTMLDivElement>(null);
  const cityRef = useRef<HTMLDivElement>(null);
  const paidRef = useRef<HTMLDivElement>(null);
  const timeModeRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (catDropdownRef.current && !catDropdownRef.current.contains(e.target as Node)) setCatDropdownOpen(false);
      if (locationRef.current && !locationRef.current.contains(e.target as Node)) setLocationOpen(false);
      if (cityRef.current && !cityRef.current.contains(e.target as Node)) setCityOpen(false);
      if (paidRef.current && !paidRef.current.contains(e.target as Node)) setPaidOpen(false);
      if (timeModeRef.current && !timeModeRef.current.contains(e.target as Node)) setTimeModeOpen(false);
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
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
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
    const reset = { q: "", category: "", from: "", to: "", paid: "", timeMode: "active", location: "", city: "" };
    setDraft(reset);
    router.replace(pathname, { scroll: false });
  }, [pathname, router]);

  const selectedCats = draft.category ? draft.category.split(",") : [];
  const fieldIds = {
    search: "filter-search",
    categoryLabel: "filter-category-label",
    categoryTrigger: "filter-category-trigger",
    location: "filter-location",
    city: "filter-city",
    paid: "filter-paid",
    timeMode: "filter-time-mode",
    from: "filter-from",
    to: "filter-to",
  };

  const locationLabel = draft.location
    ? t(`location${draft.location.charAt(0).toUpperCase() + draft.location.slice(1)}` as any)
    : t("allLocations");
  const paidLabel = draft.paid === "free" ? t("freeOnly") : draft.paid === "paid" ? t("paidOnly") : t("allPaid");
  const timeModeLabel = draft.timeMode === "past" ? t("timeModePast") : draft.timeMode === "all" ? t("timeModeAll") : t("timeModeActive");

  const hasFilters = Object.entries(draft).some(([k, v]) => {
    if (k === "timeMode") return v !== "active";
    return Boolean(v);
  });

  return (
    <div className="sticky top-14 z-20 -mx-4 px-4 pt-2 pb-2 mb-0">
      <div className="bg-blush border border-[#EDD8D0]/60 dark:border-[#3a2a27]/60 rounded-2xl px-4 py-3 shadow-sm">

      {/* Mobile: icon toggle row */}
      <div className="flex items-center justify-between md:hidden">
        <button
          onClick={() => setMobileOpen((o) => !o)}
          aria-expanded={mobileOpen}
          aria-label={mobileOpen ? t("confirm") : t("searchOrFilter")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition shadow-sm ${
            mobileOpen
              ? "border border-mascot-pink-deep bg-blush text-mascot-pink-deep hover:bg-mascot-pink/20"
              : "border border-transparent bg-brand text-white hover:bg-brand-strong"
          }`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
            {mobileOpen ? (
              <polyline points="20 6 9 17 4 12" />
            ) : (
              <>
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </>
            )}
          </svg>
          <span>{mobileOpen ? t("confirm") : t("searchOrFilter")}</span>
          {!mobileOpen && hasFilters && (
            <span className="ml-1 w-2 h-2 rounded-full bg-white/90 inline-block" />
          )}
        </button>
        {hasFilters && (
          <button onClick={clearAll} className="text-xs text-red-500 hover:text-red-700 underline">
            {t("reset")}
          </button>
        )}
      </div>

      {/* Filter panel — always visible on md+, toggled on mobile */}
      <div className={`${mobileOpen ? "block mt-3" : "hidden"} md:block md:mt-0`}>

        {/* Row 1: keyword, category, location, paid, timeMode, date range, reset */}
        <div className="flex flex-wrap gap-3 items-end">
          {/* Keyword search — debounced immediate */}
          <div className="flex flex-col gap-1">
            <label htmlFor={fieldIds.search} className="text-xs text-fg-muted font-medium">{t("search")}</label>
            <input
              id={fieldIds.search}
              type="search"
              value={draft.q}
              placeholder={t("searchPlaceholder")}
              className="h-9 border border-line-strong rounded-lg px-3 text-sm w-48 bg-paper dark:bg-elevated appearance-none shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
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
            <label id={fieldIds.categoryLabel} className="text-xs text-fg-muted font-medium">{t("category")}</label>
            <div className="relative">
              <button
                id={fieldIds.categoryTrigger}
                type="button"
                onClick={() => setCatDropdownOpen((o) => !o)}
                aria-labelledby={`${fieldIds.categoryLabel} ${fieldIds.categoryTrigger}-text`}
                className="h-9 min-w-[9rem] flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm bg-paper dark:bg-elevated shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400 cursor-pointer"
              >
                <span id={`${fieldIds.categoryTrigger}-text`} className={selectedCats.length > 0 ? "text-green-700 font-medium" : "text-fg-muted"}>
                  {selectedCats.length > 0 ? `${t("category")} (${selectedCats.length})` : t("allCategories")}
                </span>
                <span className="text-fg-subtle text-xs">{catDropdownOpen ? "▲" : "▼"}</span>
              </button>

              {catDropdownOpen && (
                <div className="absolute z-50 top-10 left-0 w-72 bg-surface border border-line rounded-xl shadow-lg py-2 max-h-80 overflow-y-auto">
                  {selectedCats.length > 0 && (
                    <div className="px-3 pb-1.5 border-b border-line mb-1">
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
                      <p className="text-xs font-semibold text-mascot-pink uppercase tracking-wide mb-1">{tCat(group.labelKey as any)}</p>
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
                            <span className="text-sm text-fg">{tCat(cat as any)}</span>
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
          <div className="flex flex-col gap-1" ref={locationRef}>
            <label className="text-xs text-fg-muted font-medium">{t("location")}</label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setLocationOpen((o) => !o)}
                className={`h-9 min-w-[9rem] flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm bg-paper dark:bg-elevated shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400 cursor-pointer ${draft.location ? "text-green-700 dark:text-green-400 font-medium" : "text-fg-muted"}`}
              >
                <span>{locationLabel}</span>
                <span className="text-fg-subtle text-xs">{locationOpen ? "▲" : "▼"}</span>
              </button>
              {locationOpen && (
                <div className="absolute z-50 top-10 left-0 w-48 bg-surface border border-line rounded-xl shadow-lg py-2">
                  {[
                    { value: "", label: t("allLocations") },
                    { value: "tokyo", label: t("locationTokyo") },
                    { value: "kanto", label: t("locationKanto") },
                    { value: "tohoku", label: t("locationTohoku") },
                    { value: "chubu", label: t("locationChubu") },
                    { value: "chugoku", label: t("locationChugoku") },
                    { value: "online", label: t("locationOnline") },
                    { value: "overseas", label: t("locationOverseas") },
                  ].map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        setDraft((prev) => {
                          const next = { ...prev, location: value, city: "" };
                          pushWith(next);
                          return next;
                        });
                        setLocationOpen(false);
                      }}
                      className={`w-full text-left px-4 py-1.5 text-sm hover:bg-blush dark:hover:bg-[#2a1f1d] hover:text-green-700 dark:hover:text-green-400 ${draft.location === value ? "text-green-700 dark:text-green-400 font-medium" : "text-fg"}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* City sub-filter — shown only when a region with prefectures is selected */}
          {(REGIONS_WITH_CITY as readonly string[]).includes(draft.location) && (() => {
            const region = draft.location as RegionWithCity;
            const prefs = REGION_PREFECTURES[region];
            const cityLabel = draft.city
              ? (_locale === "en" ? (PREFECTURE_LABELS_EN[draft.city] ?? draft.city) : draft.city)
              : t("cityAll");
            return (
              <div className="flex flex-col gap-1" ref={cityRef}>
                <label className="text-xs text-fg-muted font-medium">{t("cityLabel")}</label>
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setCityOpen((o) => !o)}
                    className={`h-9 min-w-[9rem] flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm bg-paper dark:bg-elevated shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400 cursor-pointer ${draft.city ? "text-green-700 dark:text-green-400 font-medium" : "text-fg-muted"}`}
                  >
                    <span>{cityLabel}</span>
                    <span className="text-fg-subtle text-xs">{cityOpen ? "▲" : "▼"}</span>
                  </button>
                  {cityOpen && (
                    <div className="absolute z-50 top-10 left-0 w-48 bg-surface border border-line rounded-xl shadow-lg py-2 max-h-64 overflow-y-auto">
                      <button
                        type="button"
                        onClick={() => { applyWith("city", ""); setCityOpen(false); }}
                        className={`w-full text-left px-4 py-1.5 text-sm hover:bg-blush dark:hover:bg-[#2a1f1d] hover:text-green-700 dark:hover:text-green-400 ${!draft.city ? "text-green-700 dark:text-green-400 font-medium" : "text-fg"}`}
                      >
                        {t("cityAll")}
                      </button>
                      {prefs.map((p) => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => { applyWith("city", p); setCityOpen(false); }}
                          className={`w-full text-left px-4 py-1.5 text-sm hover:bg-blush dark:hover:bg-[#2a1f1d] hover:text-green-700 dark:hover:text-green-400 ${draft.city === p ? "text-green-700 dark:text-green-400 font-medium" : "text-fg"}`}
                        >
                          {_locale === "en" ? (PREFECTURE_LABELS_EN[p] ?? p) : p}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })()}

          {/* Paid filter */}
          <div className="flex flex-col gap-1" ref={paidRef}>
            <label className="text-xs text-fg-muted font-medium">{t("paid")}</label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setPaidOpen((o) => !o)}
                className={`h-9 min-w-[7rem] flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm bg-paper dark:bg-elevated shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400 cursor-pointer ${draft.paid ? "text-green-700 dark:text-green-400 font-medium" : "text-fg-muted"}`}
              >
                <span>{paidLabel}</span>
                <span className="text-fg-subtle text-xs">{paidOpen ? "▲" : "▼"}</span>
              </button>
              {paidOpen && (
                <div className="absolute z-50 top-10 left-0 w-36 bg-surface border border-line rounded-xl shadow-lg py-2">
                  {[
                    { value: "", label: t("allPaid") },
                    { value: "free", label: t("freeOnly") },
                    { value: "paid", label: t("paidOnly") },
                  ].map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => { applyWith("paid", value); setPaidOpen(false); }}
                      className={`w-full text-left px-4 py-1.5 text-sm hover:bg-blush dark:hover:bg-[#2a1f1d] hover:text-green-700 dark:hover:text-green-400 ${draft.paid === value ? "text-green-700 dark:text-green-400 font-medium" : "text-fg"}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Time mode */}
          <div className="flex flex-col gap-1" ref={timeModeRef}>
            <label className="text-xs text-fg-muted font-medium">{t("timeMode")}</label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setTimeModeOpen((o) => !o)}
                className={`h-9 min-w-[7rem] flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm bg-paper dark:bg-elevated shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400 cursor-pointer ${draft.timeMode !== "active" ? "text-green-700 dark:text-green-400 font-medium" : "text-fg-muted"}`}
              >
                <span>{timeModeLabel}</span>
                <span className="text-fg-subtle text-xs">{timeModeOpen ? "▲" : "▼"}</span>
              </button>
              {timeModeOpen && (
                <div className="absolute z-50 top-10 left-0 w-36 bg-surface border border-line rounded-xl shadow-lg py-2">
                  {[
                    { value: "active", label: t("timeModeActive") },
                    { value: "all", label: t("timeModeAll") },
                    { value: "past", label: t("timeModePast") },
                  ].map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        if (value === "active" || value === "all") {
                          setDraft((prev) => {
                            const next = { ...prev, timeMode: value, from: "", to: "" };
                            pushWith(next);
                            return next;
                          });
                        } else if (value === "past") {
                          const today = new Date().toISOString().slice(0, 10);
                          setDraft((prev) => {
                            const next = { ...prev, timeMode: "past", to: prev.to || today };
                            pushWith(next);
                            return next;
                          });
                        }
                        setTimeModeOpen(false);
                      }}
                      className={`w-full text-left px-4 py-1.5 text-sm hover:bg-blush dark:hover:bg-[#2a1f1d] hover:text-green-700 dark:hover:text-green-400 ${draft.timeMode === value ? "text-green-700 dark:text-green-400 font-medium" : "text-fg"}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Date range (only when searching past) */}
          {draft.timeMode === "past" && (
            <>
              <div className="flex flex-col gap-1">
                <label htmlFor={fieldIds.from} className="text-xs text-fg-muted font-medium">{t("dateFrom")}</label>
                <input
                  id={fieldIds.from}
                  type="date"
                  value={draft.from}
                  onChange={(e) => applyWith("from", e.target.value)}
                  className="h-9 border border-line-strong rounded-lg px-3 text-sm bg-paper shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor={fieldIds.to} className="text-xs text-fg-muted font-medium">{t("dateTo")}</label>
                <input
                  id={fieldIds.to}
                  type="date"
                  value={draft.to}
                  onChange={(e) => applyWith("to", e.target.value)}
                  className="h-9 border border-line-strong rounded-lg px-3 text-sm bg-paper shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
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

      {/* Selected-filter chips strip — click any chip to remove it. */}
      {hasFilters && (
        <div className="flex flex-wrap items-center gap-2 mt-2 px-1">
          <span className="text-xs font-medium text-fg-muted shrink-0">
            {t("selectedLabel", { default: "已選：" })}
          </span>
          {selectedCats.map((cat) => (
            <FilterChip
              key={`cat-${cat}`}
              label={tCat(cat as any)}
              onRemove={() => toggleCategory(cat)}
            />
          ))}
          {draft.location && (
            <FilterChip
              label={t(`location${draft.location.charAt(0).toUpperCase() + draft.location.slice(1)}` as any, { default: draft.location })}
              onRemove={() => {
                setDraft((prev) => {
                  const next = { ...prev, location: "", city: "" };
                  pushWith(next);
                  return next;
                });
              }}
            />
          )}
          {draft.city && (
            <FilterChip
              label={_locale === "en" ? (PREFECTURE_LABELS_EN[draft.city] ?? draft.city) : draft.city}
              onRemove={() => applyWith("city", "")}
            />
          )}
          {draft.paid === "free" && (
            <FilterChip label={t("freeOnly")} onRemove={() => applyWith("paid", "")} />
          )}
          {draft.paid === "paid" && (
            <FilterChip label={t("paidOnly")} onRemove={() => applyWith("paid", "")} />
          )}
          {draft.timeMode === "past" && (
            <FilterChip
              label={t("timeModePast")}
              onRemove={() => {
                setDraft((prev) => {
                  const next = { ...prev, timeMode: "active", from: "", to: "" };
                  pushWith(next);
                  return next;
                });
              }}
            />
          )}
          {draft.q && (
            <FilterChip
              label={`"${draft.q}"`}
              onRemove={() => {
                setDraft((prev) => {
                  const next = { ...prev, q: "" };
                  pushWith(next);
                  return next;
                });
              }}
            />
          )}
        </div>
      )}
    </div>
  );
}


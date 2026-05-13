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
    city: currentFilters.city ?? "",
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

  const hasFilters = Object.entries(draft).some(([k, v]) => {
    if (k === "timeMode") return v !== "active";
    return Boolean(v);
  });

  return (
    <div className="sticky top-14 z-20 -mx-4 px-4 pt-2 pb-2 mb-0 bg-[var(--color-bg)]/85 backdrop-blur-sm md:bg-transparent md:backdrop-blur-none">

      {/* Mobile: icon toggle row */}
      <div className="flex items-center justify-between md:hidden mb-1">
        <button
          onClick={() => setMobileOpen((o) => !o)}
          aria-expanded={mobileOpen}
          aria-label={t("search")}
          className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition ${
            mobileOpen || hasFilters
              ? "border-green-500 text-green-700 bg-green-50"
              : "border-line-strong text-fg-muted bg-surface hover:bg-elevated"
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
      <div className={`${mobileOpen ? "block bg-[#FFF1EE] border border-[#EDD8D0]/60 rounded-2xl px-4 py-3 shadow-sm mt-2" : "hidden"} md:block md:bg-[#FFF1EE] md:border md:border-[#EDD8D0]/60 md:rounded-2xl md:px-4 md:py-3 md:shadow-sm md:mt-0`}>

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
              className="h-9 border border-line-strong rounded-lg px-3 text-sm w-48 shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
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
                className="h-9 min-w-[9rem] flex items-center justify-between gap-2 border border-line-strong rounded-lg px-3 text-sm bg-elevated shadow-sm hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400 cursor-pointer"
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
                      <p className="text-xs font-semibold text-fg-subtle uppercase tracking-wide mb-1">{tCat(group.labelKey as any)}</p>
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
          <div className="flex flex-col gap-1">
            <label htmlFor={fieldIds.location} className="text-xs text-fg-muted font-medium">{t("location")}</label>
            <select
              id={fieldIds.location}
              value={draft.location}
              onChange={(e) => {
                const loc = e.target.value;
                setDraft((prev) => {
                  const next = { ...prev, location: loc, city: "" };
                  pushWith(next);
                  return next;
                });
              }}
              className="h-9 border border-line-strong rounded-lg px-3 text-sm shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("allLocations")}</option>
              <option value="tokyo">{t("locationTokyo")}</option>
              <option value="kanto">{t("locationKanto")}</option>
              <option value="tohoku">{t("locationTohoku")}</option>
              <option value="chubu">{t("locationChubu")}</option>
              <option value="chugoku">{t("locationChugoku")}</option>
              <option value="online">{t("locationOnline")}</option>
              <option value="overseas">{t("locationOverseas")}</option>
            </select>
          </div>

          {/* City sub-filter — shown only when a region with prefectures is selected */}
          {(REGIONS_WITH_CITY as readonly string[]).includes(draft.location) && (() => {
            const region = draft.location as RegionWithCity;
            const prefs = REGION_PREFECTURES[region];
            return (
              <div className="flex flex-col gap-1">
                <label htmlFor={fieldIds.city} className="text-xs text-fg-muted font-medium">{t("cityLabel")}</label>
                <select
                  id={fieldIds.city}
                  value={draft.city}
                  onChange={(e) => applyWith("city", e.target.value)}
                  className="h-9 border border-line-strong rounded-lg px-3 text-sm shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
                >
                  <option value="">{t("cityAll")}</option>
                  {prefs.map((p) => (
                    <option key={p} value={p}>
                      {_locale === "en" ? (PREFECTURE_LABELS_EN[p] ?? p) : p}
                    </option>
                  ))}
                </select>
              </div>
            );
          })()}

          {/* Paid filter */}
          <div className="flex flex-col gap-1">
            <label htmlFor={fieldIds.paid} className="text-xs text-fg-muted font-medium">{t("paid")}</label>
            <select
              id={fieldIds.paid}
              value={draft.paid}
              onChange={(e) => applyWith("paid", e.target.value)}
              className="h-9 border border-line-strong rounded-lg px-3 text-sm shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="">{t("allPaid")}</option>
              <option value="free">{t("freeOnly")}</option>
              <option value="paid">{t("paidOnly")}</option>
            </select>
          </div>

          {/* Time mode */}
          <div className="flex flex-col gap-1">
            <label htmlFor={fieldIds.timeMode} className="text-xs text-fg-muted font-medium">{t("timeMode")}</label>
            <select
              id={fieldIds.timeMode}
              value={draft.timeMode}
              onChange={(e) => {
                if (e.target.value === "active" || e.target.value === "all") {
                  setDraft((prev) => {
                    const next = { ...prev, timeMode: e.target.value, from: "", to: "" };
                    pushWith(next);
                    return next;
                  });
                } else if (e.target.value === "past") {
                  const today = new Date().toISOString().slice(0, 10);
                  setDraft((prev) => {
                    const next = { ...prev, timeMode: "past", to: prev.to || today };
                    pushWith(next);
                    return next;
                  });
                } else {
                  applyWith("timeMode", e.target.value);
                }
              }}
              className="h-9 border border-line-strong rounded-lg px-3 text-sm shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
            >
              <option value="active">{t("timeModeActive")}</option>
              <option value="all">{t("timeModeAll")}</option>
              <option value="past">{t("timeModePast")}</option>
            </select>
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
                  className="h-9 border border-line-strong rounded-lg px-3 text-sm shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor={fieldIds.to} className="text-xs text-fg-muted font-medium">{t("dateTo")}</label>
                <input
                  id={fieldIds.to}
                  type="date"
                  value={draft.to}
                  onChange={(e) => applyWith("to", e.target.value)}
                  className="h-9 border border-line-strong rounded-lg px-3 text-sm shadow-sm cursor-pointer hover:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-400"
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


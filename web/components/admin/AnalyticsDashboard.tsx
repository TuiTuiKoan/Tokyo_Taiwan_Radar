"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { CATEGORIES } from "@/lib/types";
import { LOCATION_KEYS, LocationKey } from "@/lib/locationMarkers";
import { REGIONS_WITH_CITY, REGION_PREFECTURES, PREFECTURE_LABELS_EN, RegionWithCity } from "@/lib/regionPrefectures";

interface AnalyticsDashboardProps {
  locale: string;
}

// Generate select options for YYYY-MM based on current date
const currentYear = new Date().getFullYear();
const years = [currentYear - 2, currentYear - 1, currentYear, currentYear + 1];
const months = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0"));
const YM_OPTIONS = years
  .flatMap(y => months.map(m => `${y}-${m}`))
  .sort()
  .reverse();

export default function AnalyticsDashboard({ locale }: AnalyticsDashboardProps) {
  const tAdmin = useTranslations("admin");
  const tFilters = useTranslations("filters");
  const tCat = useTranslations("categories");

  // Initial date window (last 12 months)
  const defaultTo = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, "0")}`;
  const d = new Date();
  d.setMonth(d.getMonth() - 11);
  const defaultFrom = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

  // Filter state
  const [fromYm, setFromYm] = useState(defaultFrom);
  const [toYm, setToYm] = useState(defaultTo);
  const [location, setLocation] = useState<string>("all");
  const [city, setCity] = useState<string>("all");
  const [category, setCategory] = useState<string>("all");
  const [localeFilter, setLocaleFilter] = useState<string>("all");

  const [loading, setLoading] = useState(false);
  const [errorStatus, setErrorStatus] = useState<string | null>(null);

  // Data states
  const [eventData, setEventData] = useState<{
    months: Array<{ month: string; collected: number; ongoing: number }>;
    totals: { collected: number; ongoing: number };
  } | null>(null);

  const [viewData, setViewData] = useState<{
    byMonth: Array<{ month: string; count: number }>;
    byVisitorRegion: Array<{ region: string; count: number }>;
    byVisitorCountry: Array<{ country: string; count: number }>;
    byEventCategory: Array<{ category: string; count: number }>;
    byEventPrefecture: Array<{ prefecture: string; count: number }>;
    byLocale: Array<{ locale: string; count: number }>;
    bySource?: Array<{ source: string; count: number }>;
  } | null>(null);

  // Handle location update to reset/validate city
  const handleLocationChange = (val: string) => {
    setLocation(val);
    setCity("all"); // always reset selected city on region change
  };

  const fetchData = async () => {
    setLoading(true);
    setErrorStatus(null);
    try {
      // Validate date sequence locally
      const partsFrom = fromYm.split("-");
      const partsTo = toYm.split("-");
      const y1 = parseInt(partsFrom[0], 10);
      const m1 = parseInt(partsFrom[1], 10);
      const y2 = parseInt(partsTo[0], 10);
      const m2 = parseInt(partsTo[1], 10);
      const diff = (y2 - y1) * 12 + (m2 - m1) + 1;

      if (diff <= 0) {
        setErrorStatus("toBeforeFrom");
        setLoading(false);
        return;
      }
      if (diff > 24) {
        setErrorStatus("RangeTooWide");
        setLoading(false);
        return;
      }

      const params2A = new URLSearchParams({
        fromMonth: fromYm,
        toMonth: toYm,
        location,
        city,
        category,
      });

      const params2B = new URLSearchParams({
        fromMonth: fromYm,
        toMonth: toYm,
        location,
        city,
        category,
        locale: localeFilter,
      });

      const [resEvents, resViews] = await Promise.all([
        fetch(`/api/admin/insights/events?${params2A.toString()}`),
        fetch(`/api/admin/insights/views?${params2B.toString()}`),
      ]);

      if (!resEvents.ok) {
        const errJson = await resEvents.json().catch(() => ({}));
        if (errJson.error === "RangeTooWide") {
          setErrorStatus("RangeTooWide");
          setLoading(false);
          return;
        }
        throw new Error(errJson.error || "Event stats load failed");
      }

      if (!resViews.ok) {
        const errJson = await resViews.json().catch(() => ({}));
        if (errJson.error === "RangeTooWide") {
          setErrorStatus("RangeTooWide");
          setLoading(false);
          return;
        }
        throw new Error(errJson.error || "View stats load failed");
      }

      const eventsJson = await resEvents.json();
      const viewsJson = await resViews.json();

      setEventData(eventsJson);
      setViewData(viewsJson);
    } catch (err: any) {
      console.error(err);
      setErrorStatus("error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleApply = (e: React.FormEvent) => {
    e.preventDefault();
    fetchData();
  };

  // Helper to map and translate LOCATION_KEYS
  const getLocationLabel = (key: string) => {
    if (key === "all") return tFilters("allLocations");
    if (key === "tokyo") return tFilters("locationTokyo");
    if (key === "kanto") return tFilters("locationKanto");
    if (key === "tohoku") return tFilters("locationTohoku");
    if (key === "chubu") return tFilters("locationChubu");
    if (key === "chugoku") return tFilters("locationChugoku");
    if (key === "online") return tFilters("locationOnline");
    if (key === "overseas") return tFilters("locationOverseas");
    return key;
  };

  const getPrefectureLabel = (pref: string) => {
    if (pref === "all") return tFilters("cityAll");
    if (pref === "_other") return tFilters("cityOther");
    if (locale === "en") {
      return PREFECTURE_LABELS_EN[pref] || pref;
    }
    return pref;
  };

  const getRegionLabel = (reg: string) => {
    if (reg === "japan") return tAdmin("analyticsRegionJapan");
    if (reg === "taiwan") return tAdmin("analyticsRegionTaiwan");
    if (reg === "east_asia") return tAdmin("analyticsRegionEastAsia");
    if (reg === "southeast_asia") return tAdmin("analyticsRegionSoutheastAsia");
    if (reg === "north_america") return tAdmin("analyticsRegionNorthAmerica");
    if (reg === "europe") return tAdmin("analyticsRegionEurope");
    if (reg === "oceania") return tAdmin("analyticsRegionOceania");
    if (reg === "other") return tAdmin("analyticsRegionOther");
    return tAdmin("analyticsUnknownCountry");
  };

  const getSourceLabel = (src: string) => {
    if (src === "google") return tAdmin("trafficSourceGoogle");
    if (src === "line") return tAdmin("trafficSourceLine");
    if (src === "instagram") return tAdmin("trafficSourceInstagram");
    if (src === "threads") return tAdmin("trafficSourceThreads");
    if (src === "facebook") return tAdmin("trafficSourceFacebook");
    if (src === "twitter") return tAdmin("trafficSourceTwitter");
    if (src === "direct") return tAdmin("trafficSourceDirect");
    if (src === "other") return tAdmin("trafficSourceOther");
    return src;
  };

  // Calculate maximums for inline progress bar ratios
  const maxCollected = eventData?.months.reduce((max, m) => Math.max(max, m.collected), 0) || 1;
  const maxOngoing = eventData?.months.reduce((max, m) => Math.max(max, m.ongoing), 0) || 1;
  const maxMonthViews = viewData?.byMonth.reduce((max, m) => Math.max(max, m.count), 0) || 1;
  const maxRegionCount = viewData?.byVisitorRegion.reduce((max, r) => Math.max(max, r.count), 0) || 1;
  const maxCountryCount = viewData?.byVisitorCountry.reduce((max, c) => Math.max(max, c.count), 0) || 1;
  const maxCategoryCount = viewData?.byEventCategory.reduce((max, c) => Math.max(max, c.count), 0) || 1;
  const maxPrefectureCount = viewData?.byEventPrefecture.reduce((max, p) => Math.max(max, p.count), 0) || 1;
  const maxLocaleCount = viewData?.byLocale.reduce((max, l) => Math.max(max, l.count), 0) || 1;
  const maxSourceCount = viewData?.bySource?.reduce((max, s) => Math.max(max, s.count), 0) || 1;

  const totalRegionCount = viewData?.byVisitorRegion.reduce((acc, r) => acc + r.count, 0) || 1;

  return (
    <div className="mb-8 rounded-xl border border-line bg-surface p-5">
      <h2 className="text-base font-semibold text-fg mb-4">{tAdmin("insightsTitle")}</h2>

      {/* Filter Row Form */}
      <form onSubmit={handleApply} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6 items-end">
        {/* From Month */}
        <div>
          <label className="block text-xs font-medium text-fg-subtle mb-1">{tAdmin("FromMonth")}</label>
          <select
            value={fromYm}
            onChange={(e) => setFromYm(e.target.value)}
            className="w-full text-sm bg-elevated border border-line rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-600"
          >
            {YM_OPTIONS.map((ym) => (
              <option key={ym} value={ym}>
                {ym}
              </option>
            ))}
          </select>
        </div>

        {/* To Month */}
        <div>
          <label className="block text-xs font-medium text-fg-subtle mb-1">{tAdmin("ToMonth")}</label>
          <select
            value={toYm}
            onChange={(e) => setToYm(e.target.value)}
            className="w-full text-sm bg-elevated border border-line rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-600"
          >
            {YM_OPTIONS.map((ym) => (
              <option key={ym} value={ym}>
                {ym}
              </option>
            ))}
          </select>
        </div>

        {/* Region */}
        <div>
          <label className="block text-xs font-medium text-fg-subtle mb-1">{tFilters("location")}</label>
          <select
            value={location}
            onChange={(e) => handleLocationChange(e.target.value)}
            className="w-full text-sm bg-elevated border border-line rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-600"
          >
            <option value="all">{getLocationLabel("all")}</option>
            {LOCATION_KEYS.map((key) => (
              <option key={key} value={key}>
                {getLocationLabel(key)}
              </option>
            ))}
          </select>
        </div>

        {/* Prefecture (only for regions with city/prefectures) */}
        <div>
          <label className="block text-xs font-medium text-fg-subtle mb-1">
            {tFilters("cityLabel")}
          </label>
          <select
            value={city}
            onChange={(e) => setCity(e.target.value)}
            disabled={!REGIONS_WITH_CITY.includes(location as any)}
            className="w-full text-sm bg-elevated border border-line rounded-lg px-2.5 py-1.5 disabled:opacity-50 disabled:bg-muted focus:outline-none focus:ring-1 focus:ring-green-600"
          >
            <option value="all">{getPrefectureLabel("all")}</option>
            {REGIONS_WITH_CITY.includes(location as any) &&
              [...REGION_PREFECTURES[location as RegionWithCity], "_other"].map((pref) => (
                <option key={pref} value={pref}>
                  {getPrefectureLabel(pref)}
                </option>
              ))}
          </select>
        </div>

        {/* Category */}
        <div>
          <label className="block text-xs font-medium text-fg-subtle mb-1">{tAdmin("FilterCategory")}</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full text-sm bg-elevated border border-line rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-600"
          >
            <option value="all">{tAdmin("AllCategories")}</option>
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {tCat(cat)}
              </option>
            ))}
          </select>
        </div>

        {/* Language (exclusively targets 2B views!) */}
        <div>
          <label className="block text-xs font-medium text-fg-subtle mb-1">{tAdmin("FilterLocale")}</label>
          <select
            value={localeFilter}
            onChange={(e) => setLocaleFilter(e.target.value)}
            className="w-full text-sm bg-elevated border border-line rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-green-600"
          >
            <option value="all">{tAdmin("AllLocales")}</option>
            <option value="zh">中文</option>
            <option value="ja">日本語</option>
            <option value="en">English</option>
          </select>
        </div>

        {/* Action Button */}
        <div className="sm:col-span-2 md:col-span-3 lg:col-span-6 flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="w-full sm:w-auto bg-green-700 hover:bg-green-800 text-white font-medium text-sm rounded-lg px-5 py-1.5 transition-colors disabled:opacity-50"
          >
            {loading ? tAdmin("Loading") : tAdmin("Apply")}
          </button>
        </div>
      </form>

      {/* Error Displays */}
      {errorStatus === "toBeforeFrom" && (
        <div className="bg-red-50 text-red-700 text-sm border border-red-200 rounded-lg p-3 mb-6">
          {tAdmin("toMonth must be after or equal to fromMonth")}
        </div>
      )}
      {errorStatus === "RangeTooWide" && (
        <div className="bg-red-50 text-red-700 text-sm border border-red-200 rounded-lg p-3 mb-6">
          {tAdmin("RangeTooWide")}
        </div>
      )}
      {errorStatus === "error" && (
        <div className="bg-red-50 text-red-700 text-sm border border-red-200 rounded-lg p-3 mb-6">
          Failed to load stats. Please check console logs or retry.
        </div>
      )}

      {loading && (
        <div className="flex justify-center items-center py-20 text-fg-subtle text-sm">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-700 mr-3"></div>
          {tAdmin("Loading")}
        </div>
      )}

      {!loading && !errorStatus && (!eventData || !viewData) && (
        <div className="text-center py-20 text-fg-subtle text-sm">{tAdmin("NoData")}</div>
      )}

      {/* Data Visualization */}
      {!loading && !errorStatus && eventData && viewData && (
        <div className="space-y-8">
          
          {/* Main events volume overview */}
          <div className="border border-line rounded-lg p-4 bg-elevated">
            <h3 className="text-sm font-semibold text-fg mb-4">
              {tAdmin("analyticsPageTitle")} ({fromYm} ~ {toYm})
            </h3>
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="border border-line rounded-lg p-3 bg-surface">
                <p className="text-xs text-fg-subtle mb-0.5">{tAdmin("Collected")}</p>
                <p className="text-xl font-bold text-amber-500 tabular-nums">{eventData.totals.collected}</p>
              </div>
              <div className="border border-line rounded-lg p-3 bg-surface">
                <p className="text-xs text-fg-subtle mb-0.5">{tAdmin("Ongoing")}</p>
                <p className="text-xl font-bold text-sky-500 tabular-nums">{eventData.totals.ongoing}</p>
              </div>
            </div>

            {/* Event Trend Chart List */}
            {eventData.months.length === 0 ? (
              <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
            ) : (
              <div className="space-y-4">
                {eventData.months.map((m) => {
                  const pctCollected = Math.round((m.collected / maxCollected) * 100) || 0;
                  const pctOngoing = Math.round((m.ongoing / maxOngoing) * 100) || 0;

                  return (
                    <div key={m.month} className="flex flex-col sm:flex-row sm:items-center gap-2 text-sm border-b border-gray-50 pb-2">
                      <span className="w-16 font-medium text-fg-muted shrink-0">{m.month}</span>
                      <div className="flex-1 space-y-1">
                        {/* Collected bar */}
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-3 rounded-full bg-muted min-w-[100px]">
                            <div
                              className="h-3 rounded-full bg-amber-400 transition-all duration-300"
                              style={{ width: `${pctCollected}%` }}
                            />
                          </div>
                          <span className="w-16 text-right text-xs text-fg-subtle tabular-nums uppercase">
                            {m.collected} {tAdmin("Collected").toLowerCase()}
                          </span>
                        </div>
                        {/* Ongoing bar */}
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-3 rounded-full bg-muted min-w-[100px]">
                            <div
                              className="h-3 rounded-full bg-sky-400 transition-all duration-300"
                              style={{ width: `${pctOngoing}%` }}
                            />
                          </div>
                          <span className="w-16 text-right text-xs text-fg-subtle tabular-nums uppercase">
                            {m.ongoing} {tAdmin("Ongoing").toLowerCase()}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Page views breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Views Trend */}
            <div className="border border-line rounded-lg p-4 bg-elevated">
              <h3 className="text-sm font-semibold text-fg mb-4">{tAdmin("ViewsTrend")}</h3>
              {viewData.byMonth.length === 0 ? (
                <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
              ) : (
                <ul className="space-y-2">
                  {viewData.byMonth.map((m) => {
                    const pct = Math.round((m.count / maxMonthViews) * 100) || 0;
                    return (
                      <li key={m.month} className="flex items-center gap-3 text-sm">
                        <span className="w-16 text-xs text-fg-muted shrink-0">{m.month}</span>
                        <div className="flex-1 h-3 rounded-full bg-muted">
                          <div
                            className="h-3 rounded-full bg-green-500 transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-12 text-right text-xs text-fg-subtle shrink-0 tabular-nums">{m.count}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Views by Category */}
            <div className="border border-line rounded-lg p-4 bg-elevated">
              <h3 className="text-sm font-semibold text-fg mb-4">{tAdmin("ByEventCategory")}</h3>
              {viewData.byEventCategory.length === 0 ? (
                <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
              ) : (
                <ul className="space-y-2">
                  {viewData.byEventCategory.map((cat) => {
                    const pct = Math.round((cat.count / maxCategoryCount) * 100) || 0;
                    return (
                      <li key={cat.category} className="flex items-center gap-3 text-sm">
                        <span className="w-32 truncate text-xs text-fg-muted shrink-0">{tCat(cat.category)}</span>
                        <div className="flex-1 h-3 rounded-full bg-muted">
                          <div
                            className="h-3 rounded-full bg-blue-500 transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-12 text-right text-xs text-fg-subtle shrink-0 tabular-nums">{cat.count}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Views by Visitor Region */}
            <div className="border border-line rounded-lg p-4 bg-elevated">
              <h3 className="text-sm font-semibold text-fg mb-4">{tAdmin("ByVisitorRegion")}</h3>
              {viewData.byVisitorRegion.filter(r => r.count > 0).length === 0 ? (
                <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
              ) : (
                <ul className="space-y-2">
                  {viewData.byVisitorRegion
                    .filter((r) => r.count > 0)
                    .map((r) => {
                      const pct = Math.round((r.count / maxRegionCount) * 100) || 0;
                      return (
                        <li key={r.region} className="flex items-center gap-3 text-sm">
                          <span className="w-32 truncate text-xs text-fg-muted shrink-0">{getRegionLabel(r.region)}</span>
                          <div className="flex-1 h-3 rounded-full bg-muted">
                            <div
                              className="h-3 rounded-full bg-amber-500 transition-all duration-300"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="w-12 text-right text-xs text-fg-subtle shrink-0 tabular-nums">{r.count}</span>
                        </li>
                      );
                    })}
                </ul>
              )}
            </div>

            {/* Views by Visitor Country (Top 10) */}
            <div className="border border-line rounded-lg p-4 bg-elevated">
              <h3 className="text-sm font-semibold text-fg mb-4">{tAdmin("ByVisitorCountry")}</h3>
              {viewData.byVisitorCountry.length === 0 ? (
                <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
              ) : (
                <ul className="space-y-2">
                  {viewData.byVisitorCountry.map((c) => {
                    const pct = Math.round((c.count / maxCountryCount) * 100) || 0;
                    const displayLabel = c.country === "UNKNOWN" ? tAdmin("analyticsUnknownCountry") : c.country;
                    return (
                      <li key={c.country} className="flex items-center gap-3 text-sm">
                        <span className="w-20 truncate text-xs text-fg-muted shrink-0 font-mono">{displayLabel}</span>
                        <div className="flex-1 h-3 rounded-full bg-muted">
                          <div
                            className="h-3 rounded-full bg-emerald-500 transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-12 text-right text-xs text-fg-subtle shrink-0 tabular-nums">{c.count}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Views by Event Prefecture */}
            <div className="border border-line rounded-lg p-4 bg-elevated">
              <h3 className="text-sm font-semibold text-fg mb-4">{tAdmin("ByEventPrefecture")}</h3>
              {viewData.byEventPrefecture.length === 0 ? (
                <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
              ) : (
                <ul className="space-y-2 max-h-[350px] overflow-y-auto pr-1">
                  {viewData.byEventPrefecture.map((p) => {
                    const pct = Math.round((p.count / maxPrefectureCount) * 100) || 0;
                    return (
                      <li key={p.prefecture} className="flex items-center gap-3 text-sm">
                        <span className="w-24 truncate text-xs text-fg-muted shrink-0">{getPrefectureLabel(p.prefecture)}</span>
                        <div className="flex-1 h-3 rounded-full bg-muted">
                          <div
                            className="h-3 rounded-full bg-cyan-500 transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-12 text-right text-xs text-fg-subtle shrink-0 tabular-nums">{p.count}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Views by Locale */}
            <div className="border border-line rounded-lg p-4 bg-elevated">
              <h3 className="text-sm font-semibold text-fg mb-4">{tAdmin("ByLocale")}</h3>
              {viewData.byLocale.length === 0 ? (
                <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
              ) : (
                <ul className="space-y-2">
                  {viewData.byLocale.map((l) => {
                    const pct = Math.round((l.count / maxLocaleCount) * 100) || 0;
                    const displayLang = l.locale === "zh" ? "中文" : l.locale === "ja" ? "日本語" : l.locale === "en" ? "English" : l.locale;
                    return (
                      <li key={l.locale} className="flex items-center gap-3 text-sm">
                        <span className="w-24 truncate text-xs text-fg-muted shrink-0 uppercase font-mono">{displayLang}</span>
                        <div className="flex-1 h-3 rounded-full bg-muted">
                          <div
                            className="h-3 rounded-full bg-indigo-500 transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-12 text-right text-xs text-fg-subtle shrink-0 tabular-nums">{l.count}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Views by Traffic Source */}
            <div className="border border-line rounded-lg p-4 bg-elevated">
              <h3 className="text-sm font-semibold text-fg mb-4">{tAdmin("ByTrafficSource")}</h3>
              {!viewData.bySource || viewData.bySource.length === 0 ? (
                <p className="text-sm text-fg-subtle text-center py-4">{tAdmin("NoData")}</p>
              ) : (
                <ul className="space-y-2">
                  {viewData.bySource.map((s) => {
                    const pct = Math.round((s.count / maxSourceCount) * 100) || 0;
                    return (
                      <li key={s.source} className="flex items-center gap-3 text-sm">
                        <span className="w-24 truncate text-xs text-fg-muted shrink-0">{getSourceLabel(s.source)}</span>
                        <div className="flex-1 h-3 rounded-full bg-muted">
                          <div
                            className="h-3 rounded-full bg-orange-500 transition-all duration-300"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-12 text-right text-xs text-fg-subtle shrink-0 tabular-nums">{s.count}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  );
}

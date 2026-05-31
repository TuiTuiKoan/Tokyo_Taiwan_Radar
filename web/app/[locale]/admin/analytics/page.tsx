import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import AnalyticsDashboard from "@/components/admin/AnalyticsDashboard";
import Link from "next/link";
import { fetchGscStats } from "@/lib/gsc";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

interface EventNameRow {
  id: string;
  name_ja: string | null;
  name_zh: string | null;
  name_en: string | null;
}

interface RecentViewRow {
  viewed_at: string;
  locale: string | null;
  event_id: string;
  events: EventNameRow | EventNameRow[] | null;
}

interface TopViewRow {
  event_id: string;
  country: string | null;
}

type RegionKey =
  | "japan"
  | "taiwan"
  | "east_asia"
  | "southeast_asia"
  | "north_america"
  | "europe"
  | "oceania"
  | "other"
  | "unknown";

const COUNTRY_TO_REGION: Record<string, RegionKey> = {
  JP: "japan",
  TW: "taiwan",
  HK: "east_asia",
  KR: "east_asia",
  SG: "southeast_asia",
  TH: "southeast_asia",
  MY: "southeast_asia",
  ID: "southeast_asia",
  PH: "southeast_asia",
  VN: "southeast_asia",
  US: "north_america",
  CA: "north_america",
  GB: "europe",
  DE: "europe",
  FR: "europe",
  ES: "europe",
  IT: "europe",
  NL: "europe",
  AU: "oceania",
  NZ: "oceania",
};

function normalizeCountryCode(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const normalized = raw.trim().toUpperCase().slice(0, 2);
  return /^[A-Z]{2}$/.test(normalized) ? normalized : null;
}

function getRegionKey(countryCode: string | null): RegionKey {
  if (!countryCode) return "unknown";
  return COUNTRY_TO_REGION[countryCode] ?? "other";
}

function getRegionLabel(region: RegionKey, t: (key: string) => string): string {
  if (region === "japan") return t("analyticsRegionJapan");
  if (region === "taiwan") return t("analyticsRegionTaiwan");
  if (region === "east_asia") return t("analyticsRegionEastAsia");
  if (region === "southeast_asia") return t("analyticsRegionSoutheastAsia");
  if (region === "north_america") return t("analyticsRegionNorthAmerica");
  if (region === "europe") return t("analyticsRegionEurope");
  if (region === "oceania") return t("analyticsRegionOceania");
  if (region === "other") return t("analyticsRegionOther");
  return t("analyticsUnknownCountry");
}

function fmtNum(n: number) {
  return n.toLocaleString("en-US");
}

function fmtPercent(n: number) {
  return `${n.toFixed(1)}%`;
}

function fmtDateTime(iso: string, locale: Locale) {
  const localeMap: Record<Locale, string> = {
    zh: "zh-TW",
    en: "en-US",
    ja: "ja-JP",
  };

  return new Date(iso).toLocaleString(localeMap[locale], {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelativeTime(iso: string, locale: Locale, nowMs: number) {
  const localeMap: Record<Locale, string> = {
    zh: "zh-TW",
    en: "en-US",
    ja: "ja-JP",
  };

  const rtf = new Intl.RelativeTimeFormat(localeMap[locale], { numeric: "auto" });
  const deltaSeconds = Math.round((new Date(iso).getTime() - nowMs) / 1000);
  const abs = Math.abs(deltaSeconds);

  if (abs < 60) return rtf.format(deltaSeconds, "second");
  if (abs < 3600) return rtf.format(Math.round(deltaSeconds / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(deltaSeconds / 3600), "hour");
  if (abs < 2592000) return rtf.format(Math.round(deltaSeconds / 86400), "day");
  return rtf.format(Math.round(deltaSeconds / 2592000), "month");
}

function resolveEventName(event: EventNameRow | null, locale: Locale, fallback: string) {
  if (!event) return fallback;
  if (locale === "zh") return event.name_zh ?? event.name_ja ?? event.name_en ?? fallback;
  if (locale === "ja") return event.name_ja ?? event.name_zh ?? event.name_en ?? fallback;
  return event.name_en ?? event.name_ja ?? event.name_zh ?? fallback;
}

export const dynamic = "force-dynamic";

export default async function AdminAnalyticsPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/login`);

  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin") redirect(`/${locale}`);

  const nowMs = new Date().getTime();
  const c24h = new Date(nowMs - 86400e3).toISOString();
  const c7d = new Date(nowMs - 7 * 86400e3).toISOString();
  const c30d = new Date(nowMs - 30 * 86400e3).toISOString();

  const [
    totalRes,
    last24Res,
    last7Res,
    last30Res,
    recentRawRes,
    topViewsRawRes,
    allActiveEventsRes,
    gsc,
  ] = await Promise.all([
      supabase.from("event_views").select("id", { count: "exact", head: true }),
      supabase.from("event_views").select("id", { count: "exact", head: true }).gte("viewed_at", c24h),
      supabase.from("event_views").select("id", { count: "exact", head: true }).gte("viewed_at", c7d),
      supabase.from("event_views").select("id", { count: "exact", head: true }).gte("viewed_at", c30d),
      supabase
        .from("event_views")
        .select("viewed_at, locale, event_id, events(id, name_ja, name_zh, name_en)")
        .order("viewed_at", { ascending: false })
        .limit(20),
      supabase.from("event_views").select("event_id, country").gte("viewed_at", c30d),
      supabase.from("events").select("category").eq("is_active", true).not("category", "is", null),
      fetchGscStats(),
    ]);

  const summary = {
    total: totalRes.count ?? 0,
    last24h: last24Res.count ?? 0,
    last7d: last7Res.count ?? 0,
    last30d: last30Res.count ?? 0,
  };

  const viewCountMap: Record<string, number> = {};
  const topViewRows = (topViewsRawRes.data ?? []) as TopViewRow[];
  for (const row of topViewRows) {
    viewCountMap[row.event_id] = (viewCountMap[row.event_id] ?? 0) + 1;
  }

  const recentRows = ((recentRawRes.data ?? []) as RecentViewRow[]).map((row) => {
    const event = Array.isArray(row.events) ? (row.events[0] ?? null) : row.events;
    return {
      viewed_at: row.viewed_at,
      locale: row.locale,
      event_id: row.event_id,
      viewCount: viewCountMap[row.event_id] ?? 0,
      eventName: resolveEventName(event, locale, row.event_id),
    };
  });

  const topEventIds = Object.entries(viewCountMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([id]) => id);

  let topEvents: Array<{
    id: string;
    name_ja: string | null;
    name_zh: string | null;
    name_en: string | null;
    viewCount: number;
  }> = [];

  if (topEventIds.length > 0) {
    const { data: eventNames } = await supabase
      .from("events")
      .select("id, name_ja, name_zh, name_en")
      .in("id", topEventIds);

    topEvents = (eventNames ?? [])
      .map((event) => ({
        ...event,
        viewCount: viewCountMap[event.id] ?? 0,
      }))
      .sort((a, b) => b.viewCount - a.viewCount);
  }

  const maxViews = topEvents[0]?.viewCount ?? 1;

  const catMap: Record<string, number> = {};
  for (const event of allActiveEventsRes.data ?? []) {
    for (const category of (event.category as string[]) ?? []) {
      catMap[category] = (catMap[category] ?? 0) + 1;
    }
  }
  const totalCatTags = Object.values(catMap).reduce((a, b) => a + b, 0) || 1;
  const catEntries = Object.entries(catMap).sort((a, b) => b[1] - a[1]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("analyticsPageTitle")}</h1>

      <AdminTabNav locale={locale} activeTab="analytics" />

      <AnalyticsDashboard locale={locale} />

      <h2 className="text-base font-semibold text-fg mb-3">{t("analyticsSummaryTitle")}</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {[
          { label: t("analyticsTotalViews"), value: summary.total },
          { label: t("analyticsViews24h"), value: summary.last24h },
          { label: t("analyticsViews7d"), value: summary.last7d },
          { label: t("analyticsViews30d"), value: summary.last30d },
        ].map(({ label, value }) => (
          <div key={label} className="bg-surface border border-line rounded-xl px-4 py-3">
            <p className="text-xs text-fg-subtle mb-1">{label}</p>
            <p className="text-2xl font-bold text-fg-strong">{fmtNum(value)}</p>
          </div>
        ))}
      </div>

      <div className="mb-8 rounded-xl border border-line bg-surface px-5 py-4">
        <h2 className="text-base font-semibold text-fg mb-3">{t("analyticsGscTitle")}</h2>

        {!gsc.configured ? (
          <div className="border border-dashed border-line rounded-lg px-4 py-3 text-sm text-fg-muted">
            <p className="font-medium text-fg mb-1">{t("analyticsGscNotConfigured")}</p>
            <p>{t("analyticsGscConfigGuide")}</p>
          </div>
        ) : gsc.error ? (
          <div className="border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {t("analyticsGscError", { error: gsc.error })}
          </div>
        ) : (
          <>
            <p className="text-xs text-fg-subtle mb-3">
              {gsc.period?.startDate} - {gsc.period?.endDate}
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
              <div className="border border-line rounded-lg px-4 py-3 bg-elevated">
                <p className="text-xs text-fg-subtle mb-1">{t("analyticsGscClicks")}</p>
                <p className="text-2xl font-bold tabular-nums">{fmtNum(gsc.totalClicks ?? 0)}</p>
              </div>
              <div className="border border-line rounded-lg px-4 py-3 bg-elevated">
                <p className="text-xs text-fg-subtle mb-1">{t("analyticsGscImpressions")}</p>
                <p className="text-2xl font-bold tabular-nums">{fmtNum(gsc.totalImpressions ?? 0)}</p>
              </div>
              <div className="border border-line rounded-lg px-4 py-3 bg-elevated">
                <p className="text-xs text-fg-subtle mb-1">{t("analyticsGscCtr")}</p>
                <p className="text-2xl font-bold tabular-nums">{fmtPercent(gsc.avgCtr ?? 0)}</p>
              </div>
              <div className="border border-line rounded-lg px-4 py-3 bg-elevated">
                <p className="text-xs text-fg-subtle mb-1">{t("analyticsGscPosition")}</p>
                <p className="text-2xl font-bold tabular-nums">{(gsc.avgPosition ?? 0).toFixed(1)}</p>
              </div>
            </div>

            <h3 className="text-sm font-semibold text-fg mb-3">{t("analyticsGscTopQueriesTitle")}</h3>
            {!gsc.topQueries || gsc.topQueries.length === 0 ? (
              <p className="text-sm text-fg-subtle">{t("analyticsGscTopQueriesEmpty")}</p>
            ) : (
              <div className="overflow-x-auto mb-6">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="text-xs text-fg-subtle border-b border-line">
                      <th className="text-left py-2 pr-4 font-medium">{t("analyticsGscQuery")}</th>
                      <th className="text-right py-2 pr-4 font-medium">{t("analyticsGscClicks")}</th>
                      <th className="text-right py-2 pr-4 font-medium">{t("analyticsGscImpressions")}</th>
                      <th className="text-right py-2 pr-4 font-medium">{t("analyticsGscCtr")}</th>
                      <th className="text-right py-2 font-medium">{t("analyticsGscPosition")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gsc.topQueries.map((q) => (
                      <tr key={q.query} className="border-b border-gray-50 hover:bg-elevated">
                        <td className="py-2 pr-4 truncate max-w-[26rem]">{q.query}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{fmtNum(q.clicks)}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{fmtNum(q.impressions)}</td>
                        <td className="py-2 pr-4 text-right tabular-nums">{fmtPercent(q.ctr)}</td>
                        <td className="py-2 text-right tabular-nums">{q.position.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <h3 className="text-sm font-semibold text-fg mb-3">{t("analyticsGscTopPagesTitle")}</h3>
            {!gsc.topPages || gsc.topPages.length === 0 ? (
              <p className="text-sm text-fg-subtle">{t("analyticsGscTopPagesEmpty")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="text-xs text-fg-subtle border-b border-line">
                      <th className="text-left py-2 pr-4 font-medium">{t("analyticsGscPage")}</th>
                      <th className="text-right py-2 pr-4 font-medium">{t("analyticsGscClicks")}</th>
                      <th className="text-right py-2 pr-4 font-medium">{t("analyticsGscImpressions")}</th>
                      <th className="text-right py-2 pr-4 font-medium">{t("analyticsGscCtr")}</th>
                      <th className="text-right py-2 font-medium">{t("analyticsGscPosition")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gsc.topPages.map((p) => {
                      let displayPath = p.page;
                      try {
                        const parsed = new URL(p.page);
                        displayPath = parsed.pathname;
                      } catch {
                        displayPath = p.page.replace(/^https?:\/\/[^\/]+/, "");
                      }
                      return (
                        <tr key={p.page} className="border-b border-gray-50 hover:bg-elevated">
                          <td className="py-2 pr-4 truncate max-w-[26rem]">
                            <a
                              href={p.page}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-green-700 hover:text-green-800 hover:underline"
                            >
                              {displayPath || "/"}
                            </a>
                          </td>
                          <td className="py-2 pr-4 text-right tabular-nums">{fmtNum(p.clicks)}</td>
                          <td className="py-2 pr-4 text-right tabular-nums">{fmtNum(p.impressions)}</td>
                          <td className="py-2 pr-4 text-right tabular-nums">{fmtPercent(p.ctr)}</td>
                          <td className="py-2 text-right tabular-nums">{p.position.toFixed(1)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      <div className="mb-8 rounded-xl border border-line bg-surface px-5 py-4">
        <h3 className="text-sm font-semibold text-fg mb-3">{t("analyticsRecentViewsTitle")}</h3>
        {recentRows.length === 0 ? (
          <p className="text-sm text-fg-subtle">{t("analyticsRecentViewsEmpty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs text-fg-subtle border-b border-line">
                  <th className="text-left py-2 pr-4 font-medium">{t("statsRunAt")}</th>
                  <th className="text-left py-2 pr-4 font-medium">{t("language")}</th>
                  <th className="text-left py-2 font-medium">{t("name")}</th>
                  <th className="text-right py-2 pl-4 font-medium">{t("analyticsRecentViewsCount30d")}</th>
                </tr>
              </thead>
              <tbody>
                {recentRows.map((row) => (
                  <tr key={`${row.event_id}-${row.viewed_at}`} className="border-b border-gray-50 hover:bg-elevated">
                    <td className="py-2 pr-4 text-fg-muted whitespace-nowrap">
                      <div>{formatRelativeTime(row.viewed_at, locale, nowMs)}</div>
                      <div className="text-xs text-fg-subtle">{fmtDateTime(row.viewed_at, locale)}</div>
                    </td>
                    <td className="py-2 pr-4">
                      <span className="px-2 py-0.5 rounded-full text-xs bg-muted text-fg-muted font-mono uppercase">
                        {row.locale ?? "-"}
                      </span>
                    </td>
                    <td className="py-2 min-w-0">
                      <Link
                        href={`/${locale}/events/${row.event_id}`}
                        className="text-green-700 hover:text-green-800 hover:underline truncate inline-block max-w-[42rem]"
                      >
                        {row.eventName}
                      </Link>
                    </td>
                    <td className="py-2 pl-4 text-right tabular-nums text-fg-muted">{fmtNum(row.viewCount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="mb-8 rounded-xl border border-line bg-surface px-5 py-4">
        <h3 className="text-sm font-semibold text-fg mb-3">{t("analyticsTopEventsTitle")}</h3>
        {topEvents.length === 0 ? (
          <p className="text-sm text-fg-subtle">{t("analyticsTopEventsEmpty")}</p>
        ) : (
          <ol className="space-y-2">
            {topEvents.map((event, index) => {
              const label = resolveEventName(event, locale, event.id);
              const pct = Math.round((event.viewCount / maxViews) * 100);

              return (
                <li key={event.id} className="flex items-center gap-3 text-sm">
                  <span className="w-5 text-right text-xs text-fg-subtle shrink-0">{index + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="truncate text-fg text-xs">{label}</span>
                      <span className="ml-2 shrink-0 text-xs font-medium text-fg-muted">
                        {t("analyticsTopEventsViews", { count: event.viewCount })}
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-muted">
                      <div className="h-1.5 rounded-full bg-green-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      <div className="mb-8 rounded-xl border border-line bg-surface px-5 py-4">
        <h3 className="text-sm font-semibold text-fg mb-3">{t("analyticsCategoryTitle")}</h3>
        {catEntries.length === 0 ? (
          <p className="text-sm text-fg-subtle">{t("analyticsMonthlyEmpty")}</p>
        ) : (
          <ul className="space-y-2">
            {catEntries.map(([category, count]) => {
              const pct = Math.round((count / totalCatTags) * 100);
              return (
                <li key={category} className="flex items-center gap-3 text-sm">
                  <span className="w-32 shrink-0 truncate text-xs text-fg-muted font-mono">{category}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-muted">
                        <div className="h-2 rounded-full bg-blue-400" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="w-10 text-right text-xs text-fg-muted shrink-0">{pct}%</span>
                      <span className="w-8 text-right text-xs text-fg-subtle shrink-0">{count}</span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

    </div>
  );
}

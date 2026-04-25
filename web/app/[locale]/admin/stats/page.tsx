import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

interface ScraperRun {
  id: number;
  ran_at: string;
  source: string;
  events_processed: number;
  openai_tokens_in: number;
  openai_tokens_out: number;
  deepl_chars: number;
  cost_usd: number;
  notes: string | null;
  success?: boolean;
}

function fmtUsd(n: number) {
  return n === 0 ? "$0.000000" : `$${n.toFixed(6)}`;
}

function fmtNum(n: number) {
  return n.toLocaleString("en-US");
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function AdminStatsPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");
  const tGeneral = await getTranslations("general");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/login`);

  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();
  if (!roleRow || roleRow.role !== "admin") redirect(`/${locale}`);

  // Fetch last 100 runs
  const { data: runs, error } = await supabase
    .from("scraper_runs")
    .select("*")
    .order("ran_at", { ascending: false })
    .limit(100);

  const tableExists = !error || !error.message?.includes("does not exist");
  const rows: ScraperRun[] = (runs ?? []) as ScraperRun[];

  // Aggregates
  const now = new Date();
  const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();

  // Week start (Monday)
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay() + (now.getDay() === 0 ? -6 : 1));
  weekStart.setHours(0, 0, 0, 0);

  // DB health queries
  const [activeEventsRes, pendingRes, weekNewRes, monthNewRes] = await Promise.all([
    supabase.from("events").select("id", { count: "exact", head: true }).eq("is_active", true),
    supabase.from("events").select("id", { count: "exact", head: true }).eq("is_active", true).eq("annotation_status", "pending"),
    supabase.from("events").select("id", { count: "exact", head: true }).eq("is_active", true).gte("created_at", weekStart.toISOString()),
    supabase.from("events").select("id", { count: "exact", head: true }).eq("is_active", true).gte("created_at", startOfMonth),
  ]);
  const dbHealth = {
    activeEvents: activeEventsRes.count ?? 0,
    pendingAnnotation: pendingRes.count ?? 0,
    newThisWeek: weekNewRes.count ?? 0,
    newThisMonth: monthNewRes.count ?? 0,
  };

  const monthRows = rows.filter((r) => r.ran_at >= startOfMonth);

  function sum(arr: ScraperRun[], key: keyof ScraperRun) {
    return arr.reduce((acc, r) => acc + Number(r[key] ?? 0), 0);
  }

  const allTime = {
    runs: rows.length,
    events: sum(rows, "events_processed"),
    tokensIn: sum(rows, "openai_tokens_in"),
    tokensOut: sum(rows, "openai_tokens_out"),
    cost: sum(rows, "cost_usd"),
  };
  const month = {
    runs: monthRows.length,
    events: sum(monthRows, "events_processed"),
    tokensIn: sum(monthRows, "openai_tokens_in"),
    tokensOut: sum(monthRows, "openai_tokens_out"),
    cost: sum(monthRows, "cost_usd"),
  };

  // 30-day cost summary
  const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
  const last30Rows = rows.filter((r) => r.ran_at >= thirtyDaysAgo);
  const last30Cost = sum(last30Rows, "cost_usd");
  const firstRun = rows.length > 0 ? new Date(rows[rows.length - 1].ran_at) : now;
  const monthsElapsed = Math.max(1, (now.getTime() - firstRun.getTime()) / (1000 * 60 * 60 * 24 * 30));
  const avgMonthly = allTime.cost / monthsElapsed;

  // Latest run per source
  const latestBySource = Object.values(
    rows.reduce((acc, r) => {
      if (!acc[r.source] || r.ran_at > acc[r.source].ran_at) acc[r.source] = r;
      return acc;
    }, {} as Record<string, ScraperRun>)
  ).sort((a, b) => a.source.localeCompare(b.source));

  // ── Analytics: top viewed events (last 30 days) ──────────────────────────
  const thirtyDaysAgoIso = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000).toISOString();
  const { data: topViewsRaw } = await supabase
    .from("event_views")
    .select("event_id")
    .gte("viewed_at", thirtyDaysAgoIso);

  // Aggregate client-side (avoids needing a custom RPC for MVP)
  const viewCountMap: Record<string, number> = {};
  for (const row of topViewsRaw ?? []) {
    viewCountMap[row.event_id] = (viewCountMap[row.event_id] ?? 0) + 1;
  }
  const topEventIds = Object.entries(viewCountMap)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([id]) => id);

  let topEvents: Array<{ id: string; name_ja: string | null; name_zh: string | null; name_en: string | null; viewCount: number }> = [];
  if (topEventIds.length > 0) {
    const { data: evNames } = await supabase
      .from("events")
      .select("id, name_ja, name_zh, name_en")
      .in("id", topEventIds);
    topEvents = (evNames ?? []).map((e) => ({
      ...e,
      viewCount: viewCountMap[e.id] ?? 0,
    })).sort((a, b) => b.viewCount - a.viewCount);
  }
  const maxViews = topEvents[0]?.viewCount ?? 1;

  // ── Analytics: category distribution ─────────────────────────────────────
  const { data: allActiveEvents } = await supabase
    .from("events")
    .select("category")
    .eq("is_active", true)
    .not("category", "is", null);

  const catMap: Record<string, number> = {};
  for (const ev of allActiveEvents ?? []) {
    for (const cat of (ev.category as string[]) ?? []) {
      catMap[cat] = (catMap[cat] ?? 0) + 1;
    }
  }
  const totalCatTags = Object.values(catMap).reduce((a, b) => a + b, 0) || 1;
  const catEntries = Object.entries(catMap).sort((a, b) => b[1] - a[1]);

  // ── Analytics: events per month (last 12 months) ─────────────────────────
  const twelveMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 11, 1).toISOString();
  const { data: monthlyRaw } = await supabase
    .from("events")
    .select("start_date")
    .eq("is_active", true)
    .gte("start_date", twelveMonthsAgo)
    .not("start_date", "is", null);

  const monthlyMap: Record<string, number> = {};
  // Pre-fill all 12 months with 0
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - 11 + i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    monthlyMap[key] = 0;
  }
  for (const ev of monthlyRaw ?? []) {
    if (!ev.start_date) continue;
    const d = new Date(ev.start_date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (key in monthlyMap) monthlyMap[key]++;
  }
  const monthlyEntries = Object.entries(monthlyMap).sort((a, b) => a[0].localeCompare(b[0]));
  const maxMonthly = Math.max(...monthlyEntries.map(([, n]) => n), 1);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        <Link
          href={`/${locale}/admin`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("eventsTab")}
        </Link>
        <Link
          href={`/${locale}/admin/reports`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("reports")}
        </Link>
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {t("statsTab")}
        </span>
        <Link
          href={`/${locale}/admin/research`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("researchTab")}
        </Link>
        <Link
          href={`/${locale}/admin/sources`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("sourcesTab")}
        </Link>
        <Link
          href={`/${locale}/admin/users`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("usersTab")}
        </Link>
      </div>

      <h2 className="text-lg font-semibold mb-3">{t("statsTitle")}</h2>

      {!tableExists ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 text-sm text-amber-800">
          <strong>{tGeneral("statsTableMissing")}</strong><br />
          {tGeneral("statsTableMissingHint")}{" "}
          <code className="font-mono">supabase/migrations/007_scraper_runs.sql</code>
        </div>
      ) : (
        <>
          {/* Block 1: DB Health Cards */}
          <h2 className="text-base font-semibold text-gray-700 mb-3">{t("dbHealthTitle")}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
            {[
              { label: t("dbActiveEvents"), value: dbHealth.activeEvents },
              { label: t("dbPendingAnnotation"), value: dbHealth.pendingAnnotation },
              { label: t("dbNewThisWeek"), value: dbHealth.newThisWeek },
              { label: t("dbNewThisMonth"), value: dbHealth.newThisMonth },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white border border-gray-200 rounded-xl px-4 py-3">
                <p className="text-xs text-gray-400 mb-1">{label}</p>
                <p className="text-2xl font-bold text-gray-800">{fmtNum(value)}</p>
              </div>
            ))}
          </div>

          {/* Block 2: Latest run per source */}
          <h2 className="text-base font-semibold text-gray-700 mb-3">{t("sourceStatusTitle")}</h2>
          {latestBySource.length === 0 ? (
            <p className="text-sm text-gray-400 mb-8">{t("statsNoRuns")}</p>
          ) : (
            <div className="overflow-x-auto mb-8">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-xs text-gray-400 border-b border-gray-100">
                    <th className="text-left py-2 pr-4 font-medium">{t("statsSource")}</th>
                    <th className="text-left py-2 pr-4 font-medium">{t("statsRunAt")}</th>
                    <th className="text-right py-2 pr-4 font-medium">{t("statsEventsProcessed")}</th>
                    <th className="text-right py-2 pr-4 font-medium">{t("statsCostUsd")}</th>
                    <th className="text-right py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {latestBySource.map((r) => {
                    const failed = r.success === false;
                    const icon = failed ? "❌" : "✅";
                    return (
                      <tr key={r.source} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-2 pr-4">
                          <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600 font-mono">
                            {r.source}
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-gray-500 whitespace-nowrap">{fmtDate(r.ran_at)}</td>
                        <td className="py-2 pr-4 text-right">
                          {r.events_processed === 0 ? (
                            <span className="text-gray-400">0</span>
                          ) : r.events_processed}
                        </td>
                        <td className="py-2 pr-4 text-right font-mono text-xs">
                          {r.cost_usd > 0 ? fmtUsd(r.cost_usd) : "—"}
                        </td>
                        <td className="py-2 text-right">{icon}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Block 3: 30-day cost summary */}
          <h2 className="text-base font-semibold text-gray-700 mb-3">{t("costSummaryTitle")}</h2>
          <div className="grid grid-cols-3 gap-3 mb-8">
            {[
              { label: t("costLast30d"), value: fmtUsd(last30Cost) },
              { label: t("costAvgMonthly"), value: fmtUsd(avgMonthly) },
              { label: t("statsTotal"), value: fmtUsd(allTime.cost) },
            ].map(({ label, value }) => (
              <div key={label} className="bg-white border border-gray-200 rounded-xl px-4 py-3">
                <p className="text-xs text-gray-400 mb-1">{label}</p>
                <p className="text-xl font-bold text-gray-800 font-mono">{value}</p>
              </div>
            ))}
          </div>

          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-8">
            {[
              { label: t("statsRunsCount"), month: month.runs, all: allTime.runs },
              { label: t("statsEventsProcessed"), month: fmtNum(month.events), all: fmtNum(allTime.events) },
              { label: t("statsTokensIn"), month: fmtNum(month.tokensIn), all: fmtNum(allTime.tokensIn) },
              { label: t("statsTokensOut"), month: fmtNum(month.tokensOut), all: fmtNum(allTime.tokensOut) },
              { label: t("statsCostUsd"), month: fmtUsd(month.cost), all: fmtUsd(allTime.cost) },
            ].map(({ label, month: m, all: a }) => (
              <div key={label} className="bg-white border border-gray-200 rounded-xl px-4 py-3">
                <p className="text-xs text-gray-400 mb-1">{label}</p>
                <p className="text-xl font-bold text-gray-800">{m}</p>
                <p className="text-xs text-gray-400 mt-0.5">{t("statsTotal")}: {a}</p>
              </div>
            ))}
          </div>

          {/* Recent runs table */}
          <h3 className="text-sm font-semibold text-gray-600 mb-2">{t("statsRecentRuns")}</h3>
          {rows.length === 0 ? (
            <p className="text-sm text-gray-400">{t("statsNoRuns")}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="text-xs text-gray-400 border-b border-gray-100">
                    <th className="text-left py-2 pr-4 font-medium">{t("statsRunAt")}</th>
                    <th className="text-left py-2 pr-4 font-medium">{t("statsSource")}</th>
                    <th className="text-right py-2 pr-4 font-medium">{t("statsEventsProcessed")}</th>
                    <th className="text-right py-2 pr-4 font-medium">{t("statsTokensIn")}</th>
                    <th className="text-right py-2 pr-4 font-medium">{t("statsTokensOut")}</th>
                    <th className="text-right py-2 font-medium">{t("statsCostUsd")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="py-2 pr-4 text-gray-500 whitespace-nowrap">{fmtDate(r.ran_at)}</td>
                      <td className="py-2 pr-4">
                        <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600 font-mono">
                          {r.source}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-right">{r.events_processed}</td>
                      <td className="py-2 pr-4 text-right text-gray-500">{fmtNum(r.openai_tokens_in)}</td>
                      <td className="py-2 pr-4 text-right text-gray-500">{fmtNum(r.openai_tokens_out)}</td>
                      <td className="py-2 text-right font-mono text-xs">
                        {r.cost_usd > 0 ? fmtUsd(r.cost_usd) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Analytics section ─────────────────────────────────────────────── */}
      <h2 className="text-lg font-semibold mt-10 mb-4">{t("analyticsTitle")}</h2>

      {/* Block A: Top 10 most-viewed events (last 30 days) */}
      <div className="mb-8 rounded-xl border border-gray-200 bg-white px-5 py-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">{t("analyticsTopEventsTitle")}</h3>
        {topEvents.length === 0 ? (
          <p className="text-sm text-gray-400">{t("analyticsTopEventsEmpty")}</p>
        ) : (
          <ol className="space-y-2">
            {topEvents.map((ev, idx) => {
              const label = ev.name_zh ?? ev.name_ja ?? ev.name_en ?? ev.id;
              const pct = Math.round((ev.viewCount / maxViews) * 100);
              return (
                <li key={ev.id} className="flex items-center gap-3 text-sm">
                  <span className="w-5 text-right text-xs text-gray-400 shrink-0">{idx + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="truncate text-gray-700 text-xs">{label}</span>
                      <span className="ml-2 shrink-0 text-xs font-medium text-gray-500">
                        {t("analyticsTopEventsViews", { count: ev.viewCount })}
                      </span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-gray-100">
                      <div
                        className="h-1.5 rounded-full bg-green-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>

      {/* Block B: Category distribution */}
      <div className="mb-8 rounded-xl border border-gray-200 bg-white px-5 py-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">{t("analyticsCategoryTitle")}</h3>
        {catEntries.length === 0 ? (
          <p className="text-sm text-gray-400">{t("analyticsMonthlyEmpty")}</p>
        ) : (
          <ul className="space-y-2">
            {catEntries.map(([cat, n]) => {
              const pct = Math.round((n / totalCatTags) * 100);
              return (
                <li key={cat} className="flex items-center gap-3 text-sm">
                  <span className="w-32 shrink-0 truncate text-xs text-gray-500 font-mono">{cat}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-gray-100">
                        <div
                          className="h-2 rounded-full bg-blue-400"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="w-10 text-right text-xs text-gray-500 shrink-0">{pct}%</span>
                      <span className="w-8 text-right text-xs text-gray-400 shrink-0">{n}</span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Block C: Monthly event count (last 12 months) */}
      <div className="mb-8 rounded-xl border border-gray-200 bg-white px-5 py-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">{t("analyticsMonthlyTitle")}</h3>
        {monthlyEntries.length === 0 ? (
          <p className="text-sm text-gray-400">{t("analyticsMonthlyEmpty")}</p>
        ) : (
          <ul className="space-y-2">
            {monthlyEntries.map(([month, n]) => {
              const pct = Math.round((n / maxMonthly) * 100);
              return (
                <li key={month} className="flex items-center gap-3 text-sm">
                  <span className="w-16 shrink-0 text-xs text-gray-500">{month}</span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 rounded-full bg-gray-100">
                        <div
                          className="h-2 rounded-full bg-amber-400"
                          style={{ width: n === 0 ? "1px" : `${pct}%` }}
                        />
                      </div>
                      <span className="w-16 text-right text-xs text-gray-500 shrink-0">
                        {n} {t("analyticsEventsUnit")}
                      </span>
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

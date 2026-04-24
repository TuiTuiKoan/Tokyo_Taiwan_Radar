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
      </div>

      <h2 className="text-lg font-semibold mb-3">{t("statsTitle")}</h2>

      {!tableExists ? (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 text-sm text-amber-800">
          <strong>⚠ scraper_runs 表尚未建立</strong><br />
          請在 Supabase Dashboard → SQL Editor 執行{" "}
          <code className="font-mono">supabase/migrations/007_scraper_runs.sql</code>
        </div>
      ) : (
        <>
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
    </div>
  );
}

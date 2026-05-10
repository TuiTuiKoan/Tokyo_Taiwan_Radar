import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import Link from "next/link";
import GscSection from "@/components/GscSection";
import { getTranslations } from "next-intl/server";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

interface AeoVisit {
  id: number;
  visited_at: string;
  visit_type: "bot" | "ai_referral";
  bot_name: string | null;
  ai_source: string | null;
  user_agent: string | null;
  path: string;
  referer: string | null;
  country: string | null;
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

function fmtNum(n: number) {
  return n.toLocaleString("en-US");
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "剛剛";
  if (m < 60) return `${m} 分鐘前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小時前`;
  const d = Math.floor(h / 24);
  return `${d} 天前`;
}

export default async function AdminAeoPage({ params }: PageProps) {
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

  // Fetch last 30 days of AEO visits (capped at 5000 to avoid memory issues)
  const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  const { data: visits, error } = await supabase
    .from("aeo_visits")
    .select("*")
    .gte("visited_at", thirtyDaysAgo)
    .order("visited_at", { ascending: false })
    .limit(5000);

  const tableExists = !error || !error.message?.includes("does not exist");
  const rows: AeoVisit[] = (visits ?? []) as AeoVisit[];

  // Time windows
  const now = Date.now();
  const oneDayAgo = now - 24 * 60 * 60 * 1000;
  const sevenDaysAgo = now - 7 * 24 * 60 * 60 * 1000;

  const last24h = rows.filter((r) => new Date(r.visited_at).getTime() >= oneDayAgo);
  const last7d = rows.filter((r) => new Date(r.visited_at).getTime() >= sevenDaysAgo);

  // Bot aggregates (over 30 days)
  const botStats = new Map<
    string,
    { name: string; count30d: number; count7d: number; count24h: number; lastSeen: string; topPaths: Map<string, number> }
  >();
  for (const r of rows) {
    if (r.visit_type !== "bot" || !r.bot_name) continue;
    const s = botStats.get(r.bot_name) ?? {
      name: r.bot_name,
      count30d: 0,
      count7d: 0,
      count24h: 0,
      lastSeen: r.visited_at,
      topPaths: new Map<string, number>(),
    };
    s.count30d += 1;
    if (new Date(r.visited_at).getTime() >= sevenDaysAgo) s.count7d += 1;
    if (new Date(r.visited_at).getTime() >= oneDayAgo) s.count24h += 1;
    if (r.visited_at > s.lastSeen) s.lastSeen = r.visited_at;
    s.topPaths.set(r.path, (s.topPaths.get(r.path) ?? 0) + 1);
    botStats.set(r.bot_name, s);
  }
  const bots = Array.from(botStats.values()).sort((a, b) => b.count30d - a.count30d);

  // AI referral aggregates
  const referralStats = new Map<
    string,
    { name: string; count30d: number; count7d: number; count24h: number; lastSeen: string; topPaths: Map<string, number> }
  >();
  for (const r of rows) {
    if (r.visit_type !== "ai_referral" || !r.ai_source) continue;
    const s = referralStats.get(r.ai_source) ?? {
      name: r.ai_source,
      count30d: 0,
      count7d: 0,
      count24h: 0,
      lastSeen: r.visited_at,
      topPaths: new Map<string, number>(),
    };
    s.count30d += 1;
    if (new Date(r.visited_at).getTime() >= sevenDaysAgo) s.count7d += 1;
    if (new Date(r.visited_at).getTime() >= oneDayAgo) s.count24h += 1;
    if (r.visited_at > s.lastSeen) s.lastSeen = r.visited_at;
    s.topPaths.set(r.path, (s.topPaths.get(r.path) ?? 0) + 1);
    referralStats.set(r.ai_source, s);
  }
  const referrals = Array.from(referralStats.values()).sort((a, b) => b.count30d - a.count30d);

  const totals = {
    botVisits30d: rows.filter((r) => r.visit_type === "bot").length,
    referrals30d: rows.filter((r) => r.visit_type === "ai_referral").length,
    botVisits7d: last7d.filter((r) => r.visit_type === "bot").length,
    referrals7d: last7d.filter((r) => r.visit_type === "ai_referral").length,
    botVisits24h: last24h.filter((r) => r.visit_type === "bot").length,
    referrals24h: last24h.filter((r) => r.visit_type === "ai_referral").length,
  };

  return (
    <main className="max-w-6xl mx-auto p-4 md:p-6">
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}


      <AdminTabNav locale={locale} activeTab="aeo" />

      {!tableExists && (
        <div className="bg-amber-50 border border-amber-200 rounded p-4 mb-6 text-sm text-amber-800">
          資料表 <code>aeo_visits</code> 尚未建立，請執行 migration{" "}
          <code>029_aeo_visits.sql</code>。
        </div>
      )}

      {/* Google Search Console */}
      <GscSection />

      {/* Summary cards */}
      <section className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
        <SummaryCard label="近 24 小時 Bot 訪問" value={fmtNum(totals.botVisits24h)} />
        <SummaryCard label="近 7 天 Bot 訪問" value={fmtNum(totals.botVisits7d)} />
        <SummaryCard label="近 30 天 Bot 訪問" value={fmtNum(totals.botVisits30d)} />
        <SummaryCard label="近 24 小時 AI 引用" value={fmtNum(totals.referrals24h)} />
        <SummaryCard label="近 7 天 AI 引用" value={fmtNum(totals.referrals7d)} />
        <SummaryCard label="近 30 天 AI 引用" value={fmtNum(totals.referrals30d)} />
      </section>

      {/* Bot table */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">AI 爬蟲（30 天）</h2>
        {bots.length === 0 ? (
          <p className="text-sm text-fg-muted">尚無 AI 爬蟲訪問紀錄。</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-elevated text-left text-fg-muted">
                <tr>
                  <th className="px-3 py-2">爬蟲</th>
                  <th className="px-3 py-2 text-right">24h</th>
                  <th className="px-3 py-2 text-right">7d</th>
                  <th className="px-3 py-2 text-right">30d</th>
                  <th className="px-3 py-2">最近訪問</th>
                  <th className="px-3 py-2">主要路徑（前 3）</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {bots.map((b) => {
                  const top3 = Array.from(b.topPaths.entries())
                    .sort((a, b2) => b2[1] - a[1])
                    .slice(0, 3);
                  return (
                    <tr key={b.name} className="hover:bg-elevated">
                      <td className="px-3 py-2 font-medium">{b.name}</td>
                      <td className="px-3 py-2 text-right">{fmtNum(b.count24h)}</td>
                      <td className="px-3 py-2 text-right">{fmtNum(b.count7d)}</td>
                      <td className="px-3 py-2 text-right font-semibold">{fmtNum(b.count30d)}</td>
                      <td className="px-3 py-2 text-fg-muted">{timeAgo(b.lastSeen)}</td>
                      <td className="px-3 py-2 text-fg-muted">
                        <ul className="space-y-0.5">
                          {top3.map(([path, count]) => (
                            <li key={path} className="truncate max-w-md">
                              <span className="text-fg-subtle">{count}×</span>{" "}
                              <code className="text-xs">{path}</code>
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* AI referrals table */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-3">AI 引擎引用流量（30 天）</h2>
        {referrals.length === 0 ? (
          <p className="text-sm text-fg-muted">尚無 AI 引用流量紀錄。</p>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-elevated text-left text-fg-muted">
                <tr>
                  <th className="px-3 py-2">AI 引擎</th>
                  <th className="px-3 py-2 text-right">24h</th>
                  <th className="px-3 py-2 text-right">7d</th>
                  <th className="px-3 py-2 text-right">30d</th>
                  <th className="px-3 py-2">最近訪問</th>
                  <th className="px-3 py-2">主要路徑（前 3）</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {referrals.map((r) => {
                  const top3 = Array.from(r.topPaths.entries())
                    .sort((a, b2) => b2[1] - a[1])
                    .slice(0, 3);
                  return (
                    <tr key={r.name} className="hover:bg-elevated">
                      <td className="px-3 py-2 font-medium">{r.name}</td>
                      <td className="px-3 py-2 text-right">{fmtNum(r.count24h)}</td>
                      <td className="px-3 py-2 text-right">{fmtNum(r.count7d)}</td>
                      <td className="px-3 py-2 text-right font-semibold">{fmtNum(r.count30d)}</td>
                      <td className="px-3 py-2 text-fg-muted">{timeAgo(r.lastSeen)}</td>
                      <td className="px-3 py-2 text-fg-muted">
                        <ul className="space-y-0.5">
                          {top3.map(([path, count]) => (
                            <li key={path} className="truncate max-w-md">
                              <span className="text-fg-subtle">{count}×</span>{" "}
                              <code className="text-xs">{path}</code>
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Recent log */}
      <section>
        <h2 className="text-lg font-semibold mb-3">最近訪問（前 50 筆）</h2>
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-elevated text-left text-fg-muted">
              <tr>
                <th className="px-3 py-2">時間</th>
                <th className="px-3 py-2">類型</th>
                <th className="px-3 py-2">來源</th>
                <th className="px-3 py-2">路徑</th>
                <th className="px-3 py-2">國家</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.slice(0, 50).map((r) => (
                <tr key={r.id} className="hover:bg-elevated">
                  <td className="px-3 py-2 text-fg-muted whitespace-nowrap">{fmtDate(r.visited_at)}</td>
                  <td className="px-3 py-2">
                    {r.visit_type === "bot" ? (
                      <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">爬蟲</span>
                    ) : (
                      <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">AI 引用</span>
                    )}
                  </td>
                  <td className="px-3 py-2 font-medium">{r.bot_name ?? r.ai_source ?? "—"}</td>
                  <td className="px-3 py-2 truncate max-w-xs">
                    <code className="text-xs">{r.path}</code>
                  </td>
                  <td className="px-3 py-2 text-fg-muted">{r.country ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border rounded-lg p-3 bg-surface">
      <div className="text-xs text-fg-muted mb-1">{label}</div>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import { GUIDE_SLUGS } from "@/lib/analytics/guideTrack";
import { fetchGscQueriesForPage } from "@/lib/gsc";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
  searchParams: Promise<{ guide?: string; days?: string }>;
}

type Counts = Record<string, number>;

interface ViewRow {
  view_kind: string;
  view_id: string | null;
  views?: number;
  sessions?: number;
  median_dwell_ms?: number | null;
}

interface GuideStats {
  summary: {
    sessions: number;
    views: number;
    avg_views_per_session: number | null;
    median_dwell_ms: number | null;
    searches: number;
    outbound: number;
  };
  top_views: ViewRow[];
  entries: ViewRow[];
  transitions: Array<{ from_view: string; to_view: string; n: number }>;
  session_lengths: Counts;
  top_searches: Array<{ q: string; n: number; avg_results: number | null }>;
  zero_result_searches: Array<{ q: string; n: number }>;
  search_targets: Counts;
  traffic_source: Counts;
  device: Counts;
  browser: Counts;
  in_app: Counts;
  country: Counts;
  first_lang: Counts;
  utm_source: Counts;
  outbound: Array<{ target: string; n: number }>;
  lang_switch: Counts;
}

const RANGES = [7, 30, 90] as const;

function fmtNum(n: number | null | undefined) {
  return (n ?? 0).toLocaleString("en-US");
}

function fmtDwell(ms: number | null | undefined) {
  if (ms == null) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

type TFn = (key: string, values?: Record<string, string | number>) => string;

function viewLabel(kind: string, id: string | null, t: TFn) {
  if (kind === "chapter") return t("guidesViewChapter", { n: (id ?? "").replace(/^ch/, "") });
  if (kind === "work") return t("guidesViewWork", { id: id ?? "" });
  if (kind === "doc") return t("guidesViewDoc", { id: id ?? "" });
  return t("guidesViewHome");
}

/** "chapter:ch2" → label; also builds a deep link into the guide. */
function encodedViewLabel(v: string, t: TFn) {
  const [kind, id] = v.split(":");
  return viewLabel(kind, id || null, t);
}

function viewHash(kind: string, id: string | null) {
  if (kind === "work" && id) return `#A${id}`;
  if ((kind === "doc" || kind === "chapter") && id) return `#${id}`;
  return "";
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-line bg-surface px-5 py-4">
      <h2 className="text-base font-semibold text-fg mb-3">{title}</h2>
      {children}
    </div>
  );
}

function Distribution({ data, empty }: { data: Counts; empty: string }) {
  const entries = Object.entries(data ?? {}).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0);
  if (total === 0) return <p className="text-sm text-fg-subtle">{empty}</p>;
  return (
    <ul className="space-y-1.5">
      {entries.map(([k, n]) => (
        <li key={k} className="text-sm">
          <div className="flex justify-between gap-2">
            <span className="text-fg truncate">{k}</span>
            <span className="text-fg-muted tabular-nums">
              {fmtNum(n)} · {((n / total) * 100).toFixed(0)}%
            </span>
          </div>
          <div className="h-1.5 rounded bg-line overflow-hidden">
            <div className="h-full bg-green-600" style={{ width: `${(n / total) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export default async function AdminGuidesPage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  const sp = await searchParams;
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

  const guide = (GUIDE_SLUGS as readonly string[]).includes(sp.guide ?? "") ? sp.guide! : GUIDE_SLUGS[0];
  const days = RANGES.includes(Number(sp.days) as (typeof RANGES)[number]) ? Number(sp.days) : 30;
  const nowMs = new Date().getTime();
  const since = new Date(nowMs - days * 86400e3).toISOString();

  const [statsRes, gsc] = await Promise.all([
    supabase.rpc("guide_stats", { p_slug: guide, p_since: since }),
    fetchGscQueriesForPage(`/${guide}`),
  ]);
  const stats = (statsRes.data ?? null) as GuideStats | null;
  const empty = t("guidesEmpty");
  const href = (g: string, d: number) => `/${locale}/admin/guides?guide=${encodeURIComponent(g)}&days=${d}`;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("guidesPageTitle")}</h1>
      <AdminTabNav locale={locale} activeTab="guides" />

      <p className="text-sm text-fg-muted mb-1">{t("guidesIntro")}</p>
      <p className="text-xs text-fg-subtle mb-4">{t("guidesPrivacyNote")}</p>

      <div className="flex flex-wrap items-center gap-2 mb-6 text-sm">
        <span className="text-fg-subtle">{t("guidesGuideLabel")}</span>
        {GUIDE_SLUGS.map((g) => (
          <Link
            key={g}
            href={href(g, days)}
            className={g === guide ? "px-3 py-1 rounded-full bg-green-600 text-white" : "px-3 py-1 rounded-full border border-line text-fg-muted"}
          >
            {g}
          </Link>
        ))}
        <a href={`/${guide}`} target="_blank" rel="noopener noreferrer" className="text-green-700 hover:underline">
          {t("guidesOpenGuide")}
        </a>
        <span className="mx-2 border-l border-line h-5" />
        {RANGES.map((d) => (
          <Link
            key={d}
            href={href(guide, d)}
            className={d === days ? "px-3 py-1 rounded-full bg-green-600 text-white" : "px-3 py-1 rounded-full border border-line text-fg-muted"}
          >
            {t("guidesRangeDays", { days: d })}
          </Link>
        ))}
      </div>

      {statsRes.error ? (
        <p className="mb-8 rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
          {t("guidesError", { error: statsRes.error.message })}
        </p>
      ) : !stats ? (
        <p className="mb-8 text-sm text-fg-subtle">{empty}</p>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
            {[
              { label: t("guidesSessions"), value: fmtNum(stats.summary.sessions) },
              { label: t("guidesViews"), value: fmtNum(stats.summary.views) },
              { label: t("guidesAvgViews"), value: (stats.summary.avg_views_per_session ?? 0).toString() },
              { label: t("guidesMedianDwell"), value: fmtDwell(stats.summary.median_dwell_ms) },
              { label: t("guidesSearches"), value: fmtNum(stats.summary.searches) },
              { label: t("guidesOutbound"), value: fmtNum(stats.summary.outbound) },
            ].map(({ label, value }) => (
              <div key={label} className="bg-surface border border-line rounded-xl px-4 py-3">
                <p className="text-xs text-fg-subtle mb-1">{label}</p>
                <p className="text-2xl font-bold text-fg-strong">{value}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-2 mb-8">
            <Card title={t("guidesTopViewsTitle")}>
              {stats.top_views.length === 0 ? (
                <p className="text-sm text-fg-subtle">{empty}</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-fg-subtle">
                      <th className="py-1 font-normal">{t("guidesColView")}</th>
                      <th className="py-1 font-normal text-right">{t("guidesColViews")}</th>
                      <th className="py-1 font-normal text-right">{t("guidesColSessions")}</th>
                      <th className="py-1 font-normal text-right">{t("guidesColDwell")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.top_views.map((r) => (
                      <tr key={`${r.view_kind}:${r.view_id}`} className="border-t border-line">
                        <td className="py-1">
                          <a
                            href={`/${guide}${viewHash(r.view_kind, r.view_id)}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-green-700 hover:underline"
                          >
                            {viewLabel(r.view_kind, r.view_id, t)}
                          </a>
                        </td>
                        <td className="py-1 text-right tabular-nums">{fmtNum(r.views)}</td>
                        <td className="py-1 text-right tabular-nums">{fmtNum(r.sessions)}</td>
                        <td className="py-1 text-right tabular-nums">{fmtDwell(r.median_dwell_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>

            <div className="grid gap-4">
              <Card title={t("guidesEntriesTitle")}>
                {stats.entries.length === 0 ? (
                  <p className="text-sm text-fg-subtle">{empty}</p>
                ) : (
                  <ul className="text-sm space-y-1">
                    {stats.entries.map((r) => (
                      <li key={`${r.view_kind}:${r.view_id}`} className="flex justify-between">
                        <span>{viewLabel(r.view_kind, r.view_id, t)}</span>
                        <span className="tabular-nums text-fg-muted">{fmtNum(r.sessions)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card title={t("guidesSessionLengthsTitle")}>
                <Distribution
                  data={Object.fromEntries(
                    ["1", "2-3", "4-9", "10+"].map((k) => [t("guidesSessionLength", { range: k }), stats.session_lengths?.[k] ?? 0]),
                  )}
                  empty={empty}
                />
              </Card>
            </div>
          </div>

          <div className="mb-8">
            <Card title={t("guidesTransitionsTitle")}>
              {stats.transitions.length === 0 ? (
                <p className="text-sm text-fg-subtle">{empty}</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-fg-subtle">
                      <th className="py-1 font-normal">{t("guidesColFrom")}</th>
                      <th className="py-1 font-normal">{t("guidesColTo")}</th>
                      <th className="py-1 font-normal text-right">{t("guidesColCount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.transitions.map((r) => (
                      <tr key={`${r.from_view}>${r.to_view}`} className="border-t border-line">
                        <td className="py-1">{encodedViewLabel(r.from_view, t)}</td>
                        <td className="py-1">→ {encodedViewLabel(r.to_view, t)}</td>
                        <td className="py-1 text-right tabular-nums">{fmtNum(r.n)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3 mb-8">
            <Card title={t("guidesSearchTitle")}>
              {stats.top_searches.length === 0 ? (
                <p className="text-sm text-fg-subtle">{empty}</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-fg-subtle">
                      <th className="py-1 font-normal">{t("guidesColQuery")}</th>
                      <th className="py-1 font-normal text-right">{t("guidesColCount")}</th>
                      <th className="py-1 font-normal text-right">{t("guidesColAvgResults")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.top_searches.map((r) => (
                      <tr key={r.q} className="border-t border-line">
                        <td className="py-1 break-all">{r.q}</td>
                        <td className="py-1 text-right tabular-nums">{fmtNum(r.n)}</td>
                        <td className="py-1 text-right tabular-nums">{r.avg_results ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
            <Card title={t("guidesZeroTitle")}>
              {stats.zero_result_searches.length === 0 ? (
                <p className="text-sm text-fg-subtle">{empty}</p>
              ) : (
                <ul className="text-sm space-y-1">
                  {stats.zero_result_searches.map((r) => (
                    <li key={r.q} className="flex justify-between gap-2">
                      <span className="break-all">{r.q}</span>
                      <span className="tabular-nums text-fg-muted">{fmtNum(r.n)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title={t("guidesSearchViaTitle")}>
              <Distribution
                data={Object.fromEntries(
                  Object.entries(stats.search_targets ?? {}).map(([k, n]) => [
                    k === "input" ? t("guidesViaInput") : k === "chip" ? t("guidesViaChip") : k === "artist" ? t("guidesViaArtist") : k,
                    n,
                  ]),
                )}
                empty={empty}
              />
            </Card>
          </div>

          <h2 className="text-base font-semibold text-fg mb-3">{t("guidesToolsTitle")}</h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
            <Card title={t("guidesTrafficTitle")}>
              <Distribution data={stats.traffic_source} empty={empty} />
            </Card>
            <Card title={t("guidesDeviceTitle")}>
              <Distribution data={stats.device} empty={empty} />
            </Card>
            <Card title={t("guidesBrowserTitle")}>
              <Distribution data={stats.browser} empty={empty} />
            </Card>
            <Card title={t("guidesInAppTitle")}>
              <Distribution data={stats.in_app} empty={empty} />
            </Card>
            <Card title={t("guidesCountryTitle")}>
              <Distribution data={stats.country} empty={empty} />
            </Card>
            <Card title={t("guidesFirstLangTitle")}>
              <Distribution data={stats.first_lang} empty={empty} />
            </Card>
            <Card title={t("guidesUtmTitle")}>
              <Distribution data={stats.utm_source} empty={empty} />
            </Card>
            <Card title={t("guidesLangSwitchTitle")}>
              <Distribution data={stats.lang_switch} empty={empty} />
            </Card>
          </div>

          <div className="mb-8">
            <Card title={t("guidesOutboundTitle")}>
              {stats.outbound.length === 0 ? (
                <p className="text-sm text-fg-subtle">{empty}</p>
              ) : (
                <ul className="text-sm space-y-1">
                  {stats.outbound.map((r) => (
                    <li key={r.target} className="flex justify-between gap-2">
                      <span className="break-all">{r.target}</span>
                      <span className="tabular-nums text-fg-muted">{fmtNum(r.n)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}

      <div className="mb-8">
        <Card title={t("guidesGscTitle")}>
          {!gsc.configured ? (
            <p className="text-sm text-fg-subtle">{t("analyticsGscNotConfigured")}</p>
          ) : gsc.error ? (
            <p className="text-sm text-red-700">{t("analyticsGscError", { error: gsc.error })}</p>
          ) : !gsc.queries || gsc.queries.length === 0 ? (
            <p className="text-sm text-fg-subtle">{t("analyticsGscTopQueriesEmpty")}</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-fg-subtle">
                  <th className="py-1 font-normal">{t("analyticsGscQuery")}</th>
                  <th className="py-1 font-normal text-right">{t("analyticsGscClicks")}</th>
                  <th className="py-1 font-normal text-right">{t("guidesGscImpressions")}</th>
                  <th className="py-1 font-normal text-right">{t("analyticsGscCtr")}</th>
                  <th className="py-1 font-normal text-right">{t("analyticsGscPosition")}</th>
                </tr>
              </thead>
              <tbody>
                {gsc.queries.map((q) => (
                  <tr key={q.query} className="border-t border-line">
                    <td className="py-1 break-all">{q.query}</td>
                    <td className="py-1 text-right tabular-nums">{fmtNum(q.clicks)}</td>
                    <td className="py-1 text-right tabular-nums">{fmtNum(q.impressions)}</td>
                    <td className="py-1 text-right tabular-nums">{q.ctr}%</td>
                    <td className="py-1 text-right tabular-nums">{q.position}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}

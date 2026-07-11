import { createClient } from "@/lib/supabase/server";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { isPublicationMetricIntentionalNull, type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

// ─── Static data: Tier 1+1.5 migration status ──────────────────────────────

const MIGRATIONS = [
  { id: "035", label: "organizer / co_organizers / sponsors / organizer_type / event_form / primary_language / 3 language cols", done: true },
  { id: "036", label: "has_chinese_support", done: true },
  { id: "037", label: "organizer_url / price_amount / price_currency / event_status / schema.org JSON-LD", done: true },
  { id: "038", label: "performer", done: true },
  { id: "038b", label: "field_corrections（人工修正保護）", done: true },
  { id: "039", label: "research_sources.default_organizer（來源預設主辦方）", done: true },
  { id: "040", label: "selection_reason_corrections（few-shot 回饋迴路）", done: true },
  { id: "050",  label: "organizers + venues entity 表（204 主辦方 / 210 場地，report-prototype-gap-fix Phase 2）", done: true },
  { id: "052",  label: "director 欄位（Schema.org）", done: true },
  { id: "052b", label: "event_media_coverage view（媒體曝光 Top 10，Phase 3）", done: true },
  { id: "053+", label: "external_stats（JNTO / e-Stat / 法務省 benchmark data）", done: false },
];

// ─── Product status ─────────────────────────────────────────────────────────

const PRODUCTS = [
  {
    id: "A",
    name: "月度/季度趨勢報告",
    audience: "公部門、文化機構、智庫",
    price: "¥80,000–¥250,000 / 份",
    status: "in-progress" as const,
    statusLabel: "🔄 Prototype 就緒",
    blocker: "report_generator.py 可產出月報草稿（2026-05 已驗證），下一步：人工審核後寄出試樣",
  },
  {
    id: "B",
    name: "城市×類別深度分析（含 briefing）",
    audience: "品牌、策展、地方政府",
    price: "¥300,000–¥800,000 / 份",
    status: "not-started" as const,
    statusLabel: "⬜ 延後（6–12 個月）",
    blocker: "需先有 Product A case study 作為 proof point",
  },
  {
    id: "C",
    name: "機會雷達訂閱（週報 + LINE 推播）",
    audience: "品牌、製作公司、經紀公司",
    price: "¥30,000–¥80,000 / 月",
    status: "in-progress" as const,
    statusLabel: "🔄 設計中（spec 已建立）",
    blocker: "location_prefectures 填充率 81.3%（fillable 100%）— 城市維度已解鎖，可啟動設計",
  },
];

// ─── P-series feedback loop ──────────────────────────────────────────────────

const P_SERIES = [
  { id: "P1",   label: "field_corrections 持久化 + annotator 保護 + few-shot context", commit: "c393e93", done: true },
  { id: "P2",   label: "Admin 回饋統計（/admin/stats 新增 feedback loop section）", commit: "e60e917", done: true },
  { id: "P3.1", label: "AdminEditClient bypass 修補", commit: "837605b", done: true },
  { id: "P3.2", label: "force_rows 保護（database.py 清洗受保護欄位）", commit: "837605b", done: true },
  { id: "P3.3", label: "selection_reason_corrections 表 + annotator few-shot 注入", commit: "307591b", done: true },
  { id: "P4.5", label: "field_protect_hits 計數器（scraper_runs）", commit: "307591b", done: true },
  { id: "P4.6", label: "field_corrections.report_id FK（事件回報可追溯修正）", commit: "307591b", done: true },
  { id: "P4.1–4.4", label: "P4 缺口 #1–#4（待用戶確認具體內容）", commit: "—", done: false },
];

// ─── Field fill rate targets (computed dynamically below from DB) ──────────

const FILL_RATE_TARGETS: { field: string; target: number; note: string }[] = [
  { field: "category",              target: 100, note: "" },
  { field: "start_date",            target: 100, note: "" },
  { field: "location_name",         target: 100, note: "" },
  { field: "organizer",             target: 90,  note: "" },
  { field: "location_address",      target: 80,  note: "" },
  { field: "event_form",            target: 80,  note: "" },
  { field: "organizer_type",        target: 85,  note: "排除 unknown 才計" },
  { field: "location_prefectures",  target: 85,  note: "🔴 Product C 城市維度阻斷點" },
  { field: "performer",             target: 45,  note: "僅 lecture/performance 類需達標" },
];

/**
 * Compute fill rates by counting non-null values across all active+annotated
 * parent events. Uses service role to bypass RLS (already authed as admin
 * via cookie client above). Service-role query selects only the columns
 * needed — never SELECT *.
 */
async function computeFillRates(): Promise<
  { field: string; pct: number; target: number; note: string; total: number }[]
> {
  const sb = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
  const cols = [
    "category",
    "start_date",
    "location_name",
    "organizer",
    "location_address",
    "event_form",
    "organizer_type",
    "location_prefectures",
    "performer",
    "source_name",
  ].join(",");
  const { data } = await sb
    .from("events")
    .select(cols)
    .eq("is_active", true)
    .is("parent_event_id", null)
    .in("annotation_status", ["annotated", "reviewed"]);
  const rows = (data ?? []) as unknown as Record<string, unknown>[];
  const total = rows.length || 1;

  const publicationRecord = (r: Record<string, unknown>) => {
    const eventForm = Array.isArray(r.event_form)
      ? r.event_form.filter((f: unknown): f is string => typeof f === "string")
      : null;
    return { event_form: eventForm };
  };

  const filled = (k: string, predicate: (v: unknown) => boolean) =>
    rows.filter((r) => {
      // Pure publications intentionally omit address and prefectures; location_name remains an actual fill metric.
      if (isPublicationMetricIntentionalNull(publicationRecord(r), k)) {
        return true;
      }
      return predicate(r[k]);
    }).length;

  const nonEmpty = (v: unknown): boolean => {
    if (v === null || v === undefined) return false;
    if (Array.isArray(v)) return v.length > 0;
    if (typeof v === "string") return v.trim().length > 0;
    return true;
  };
  const fillCount: Record<string, number> = {
    category: filled("category", nonEmpty),
    start_date: filled("start_date", nonEmpty),
    location_name: filled("location_name", nonEmpty),
    organizer: filled("organizer", nonEmpty),
    location_address: filled("location_address", nonEmpty),
    event_form: filled("event_form", nonEmpty),
    // organizer_type counted only when array exists AND ≠ ["unknown"]
    organizer_type: filled("organizer_type", (v) => {
      if (!Array.isArray(v) || v.length === 0) return false;
      return !(v.length === 1 && v[0] === "unknown");
    }),
    location_prefectures: filled("location_prefectures", nonEmpty),
    performer: filled("performer", nonEmpty),
  };
  return FILL_RATE_TARGETS.map((t) => ({
    field: t.field,
    pct: Math.round((fillCount[t.field] / total) * 1000) / 10,
    target: t.target,
    note: t.note,
    total: rows.length,
  }));
}

function pctColor(pct: number, target: number) {
  if (pct >= target) return "text-green-700 font-semibold";
  if (pct >= target * 0.85) return "text-amber-600 font-semibold";
  return "text-red-600 font-bold";
}

function pctBar(pct: number, target: number) {
  const bg = pct >= target ? "bg-green-400" : pct >= target * 0.85 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
      <div className={`${bg} h-1.5 rounded-full`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

export default async function AdminRoadmapPage({ params }: PageProps) {
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

  // Latest daily_quality_metrics
  const { data: latestQuality } = await supabase
    .from("daily_quality_metrics")
    .select("metric_date,events_active,precision_rate")
    .order("metric_date", { ascending: false })
    .limit(1);
  const quality = latestQuality?.[0];

  // Dynamic fill rates (replaces hardcoded FILL_RATES)
  const fillRates = await computeFillRates();

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <AdminTabNav locale={locale} activeTab="roadmap" />

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg-strong">{t("tabs.roadmap")}</h1>
        <p className="text-sm text-fg-muted mt-1">
          {t("roadmap.subtitle")}
        </p>
      </div>

      {/* ─── 三層火箭 ──────────────────────────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-fg mb-3">{t("roadmap.strategyTitle")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { layer: t("roadmap.layerSurface"), desc: t("roadmap.layerSurfaceDesc"), status: "✅", color: "border-green-400 bg-green-50" },
            { layer: t("roadmap.layerMiddle"),  desc: t("roadmap.layerMiddleDesc"),  status: "🔄", color: "border-amber-400 bg-amber-50" },
            { layer: t("roadmap.layerDeep"),    desc: t("roadmap.layerDeepDesc"),    status: "⬜", color: "border-line-strong bg-elevated" },
          ].map((l) => (
            <div key={l.layer} className={`rounded-lg border-l-4 p-4 ${l.color}`}>
              <div className="text-lg mb-1">{l.status} {l.layer}</div>
              <div className="text-sm text-fg-muted">{l.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── 資料填充率快照 ────────────────────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-fg mb-3">
          {t("roadmap.fillRateTitle")}
          {quality && (
            <span className="ml-2 text-xs font-normal text-fg-subtle">
              {quality.metric_date} · {quality.events_active} {t("roadmap.activeEvents")}
              {quality.precision_rate !== null && (
                <> · precision {(Number(quality.precision_rate) * 100).toFixed(1)}%</>
              )}
            </span>
          )}
        </h2>
        <div className="bg-surface border border-line rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-elevated border-b border-line">
              <tr>
                <th className="px-4 py-2 text-left text-fg-muted font-medium">{t("roadmap.fieldCol")}</th>
                <th className="px-4 py-2 text-right text-fg-muted font-medium w-20">{t("roadmap.fillPctCol")}</th>
                <th className="px-4 py-2 text-right text-fg-muted font-medium w-20">{t("roadmap.targetCol")}</th>
                <th className="px-4 py-2 text-left text-fg-muted font-medium">{t("roadmap.noteCol")}</th>
              </tr>
            </thead>
            <tbody>
              {fillRates.map((r) => (
                <tr key={r.field} className="border-b border-line last:border-0">
                  <td className="px-4 py-2 font-mono text-xs text-fg">{r.field}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={pctColor(r.pct, r.target)}>{r.pct}%</span>
                    {pctBar(r.pct, r.target)}
                  </td>
                  <td className="px-4 py-2 text-right text-fg-subtle text-xs">{r.target}%</td>
                  <td className="px-4 py-2 text-xs text-fg-muted">{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-fg-subtle mt-1">{t("roadmap.fillRateNote")}</p>
      </section>

      {/* ─── Schema Tier 1+1.5 Migrations ─────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-fg mb-3">{t("roadmap.migrationsTitle")}</h2>
        <div className="space-y-1.5">
          {MIGRATIONS.map((m) => (
            <div key={m.id} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5 shrink-0">{m.done ? "✅" : "⬜"}</span>
              <span className="font-mono text-xs text-fg-muted shrink-0 w-12">{m.id}</span>
              <span className={m.done ? "text-fg" : "text-fg-subtle"}>{m.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ─── 商業產品 ──────────────────────────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-fg mb-3">{t("roadmap.productsTitle")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PRODUCTS.map((p) => (
            <div
              key={p.id}
              className={`rounded-lg border p-4 ${
                p.status === "in-progress"
                  ? "border-amber-300 bg-amber-50"
                  : "border-line bg-elevated"
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <span className="text-xs font-bold text-fg-muted">Product {p.id}</span>
                <span className="text-xs">{p.statusLabel}</span>
              </div>
              <div className="font-medium text-fg-strong mb-1">{p.name}</div>
              <div className="text-xs text-fg-muted mb-1">{p.audience}</div>
              <div className="text-xs font-mono text-green-700 mb-2">{p.price}</div>
              {p.blocker && (
                <div className="text-xs text-fg-subtle bg-surface rounded px-2 py-1 border border-line">
                  {p.blocker}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ─── 回饋迴路 P 系列 ───────────────────────────────────────── */}
      <section className="mb-4">
        <h2 className="text-base font-semibold text-fg mb-3">{t("roadmap.pSeriesTitle")}</h2>
        <div className="space-y-1.5">
          {P_SERIES.map((p) => (
            <div key={p.id} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5 shrink-0">{p.done ? "✅" : "⬜"}</span>
              <span className="font-mono text-xs text-fg-muted shrink-0 w-14">{p.id}</span>
              <span className={p.done ? "text-fg" : "text-fg-subtle italic"}>{p.label}</span>
              {p.commit !== "—" && (
                <span className="ml-auto text-xs font-mono text-fg-subtle shrink-0">{p.commit}</span>
              )}
            </div>
          ))}
        </div>
      </section>

      <p className="text-xs text-fg-subtle mt-6">
        {t("roadmap.updatedNote")}
        <a
          href={`/${locale}/admin/specs`}
          className="ml-1 text-green-600 hover:underline"
        >
          {t("roadmap.specsLink")}
        </a>
      </p>
    </div>
  );
}

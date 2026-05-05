import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
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
  { id: "041+", label: "Tier 2 欄位（媒體 mention / 主辦方 entity 表 / 場地容量）", done: false },
];

// ─── Product status ─────────────────────────────────────────────────────────

const PRODUCTS = [
  {
    id: "A",
    name: "月度/季度趨勢報告",
    audience: "公部門、文化機構、智庫",
    price: "¥80,000–¥250,000 / 份",
    status: "not-started" as const,
    statusLabel: "⬜ 尚未開始",
    blocker: "需先完成 Tier 1 fill rate ≥ 85% + 試樣報告 A",
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
    blocker: "location_prefectures ≥ 85% 解鎖城市維度後啟動",
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

// ─── Field fill rates (last updated 2026-05-05) ──────────────────────────────

const FILL_RATES = [
  { field: "category",             pct: 100,  target: 100, note: "" },
  { field: "start_date",           pct: 100,  target: 100, note: "" },
  { field: "location_name",        pct: 100,  target: 100, note: "" },
  { field: "organizer",            pct: 91.1, target: 90,  note: "" },
  { field: "location_address",     pct: 86.0, target: 80,  note: "" },
  { field: "event_form",           pct: 88.5, target: 80,  note: "" },
  { field: "organizer_type (≠unk)",pct: 80.9, target: 85,  note: "仍有 ~18 件 unknown（organizer=null 的節慶）" },
  { field: "location_prefectures", pct: 68.2, target: 85,  note: "🔴 Product C 城市維度阻斷點" },
  { field: "performer",            pct: 20.4, target: 45,  note: "僅 lecture/performance 類需達標" },
];

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

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <AdminTabNav locale={locale} activeTab="roadmap" />

      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{t("tabs.roadmap")}</h1>
        <p className="text-sm text-gray-500 mt-1">
          {t("roadmap.subtitle")}
        </p>
      </div>

      {/* ─── 三層火箭 ──────────────────────────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-gray-700 mb-3">{t("roadmap.strategyTitle")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[
            { layer: t("roadmap.layerSurface"), desc: t("roadmap.layerSurfaceDesc"), status: "✅", color: "border-green-400 bg-green-50" },
            { layer: t("roadmap.layerMiddle"),  desc: t("roadmap.layerMiddleDesc"),  status: "🔄", color: "border-amber-400 bg-amber-50" },
            { layer: t("roadmap.layerDeep"),    desc: t("roadmap.layerDeepDesc"),    status: "⬜", color: "border-gray-300 bg-gray-50" },
          ].map((l) => (
            <div key={l.layer} className={`rounded-lg border-l-4 p-4 ${l.color}`}>
              <div className="text-lg mb-1">{l.status} {l.layer}</div>
              <div className="text-sm text-gray-600">{l.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ─── 資料填充率快照 ────────────────────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-gray-700 mb-3">
          {t("roadmap.fillRateTitle")}
          {quality && (
            <span className="ml-2 text-xs font-normal text-gray-400">
              {quality.metric_date} · {quality.events_active} {t("roadmap.activeEvents")}
              {quality.precision_rate !== null && (
                <> · precision {(Number(quality.precision_rate) * 100).toFixed(1)}%</>
              )}
            </span>
          )}
        </h2>
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-2 text-left text-gray-600 font-medium">{t("roadmap.fieldCol")}</th>
                <th className="px-4 py-2 text-right text-gray-600 font-medium w-20">{t("roadmap.fillPctCol")}</th>
                <th className="px-4 py-2 text-right text-gray-600 font-medium w-20">{t("roadmap.targetCol")}</th>
                <th className="px-4 py-2 text-left text-gray-600 font-medium">{t("roadmap.noteCol")}</th>
              </tr>
            </thead>
            <tbody>
              {FILL_RATES.map((r) => (
                <tr key={r.field} className="border-b border-gray-100 last:border-0">
                  <td className="px-4 py-2 font-mono text-xs text-gray-700">{r.field}</td>
                  <td className="px-4 py-2 text-right">
                    <span className={pctColor(r.pct, r.target)}>{r.pct}%</span>
                    {pctBar(r.pct, r.target)}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-400 text-xs">{r.target}%</td>
                  <td className="px-4 py-2 text-xs text-gray-500">{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-gray-400 mt-1">{t("roadmap.fillRateNote")}</p>
      </section>

      {/* ─── Schema Tier 1+1.5 Migrations ─────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-gray-700 mb-3">{t("roadmap.migrationsTitle")}</h2>
        <div className="space-y-1.5">
          {MIGRATIONS.map((m) => (
            <div key={m.id} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5 shrink-0">{m.done ? "✅" : "⬜"}</span>
              <span className="font-mono text-xs text-gray-500 shrink-0 w-12">{m.id}</span>
              <span className={m.done ? "text-gray-700" : "text-gray-400"}>{m.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ─── 商業產品 ──────────────────────────────────────────────── */}
      <section className="mb-8">
        <h2 className="text-base font-semibold text-gray-700 mb-3">{t("roadmap.productsTitle")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PRODUCTS.map((p) => (
            <div
              key={p.id}
              className={`rounded-lg border p-4 ${
                p.status === "in-progress"
                  ? "border-amber-300 bg-amber-50"
                  : p.status === "done"
                  ? "border-green-300 bg-green-50"
                  : "border-gray-200 bg-gray-50"
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <span className="text-xs font-bold text-gray-500">Product {p.id}</span>
                <span className="text-xs">{p.statusLabel}</span>
              </div>
              <div className="font-medium text-gray-800 mb-1">{p.name}</div>
              <div className="text-xs text-gray-500 mb-1">{p.audience}</div>
              <div className="text-xs font-mono text-green-700 mb-2">{p.price}</div>
              {p.blocker && (
                <div className="text-xs text-gray-400 bg-white rounded px-2 py-1 border border-gray-100">
                  {p.blocker}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ─── 回饋迴路 P 系列 ───────────────────────────────────────── */}
      <section className="mb-4">
        <h2 className="text-base font-semibold text-gray-700 mb-3">{t("roadmap.pSeriesTitle")}</h2>
        <div className="space-y-1.5">
          {P_SERIES.map((p) => (
            <div key={p.id} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5 shrink-0">{p.done ? "✅" : "⬜"}</span>
              <span className="font-mono text-xs text-gray-500 shrink-0 w-14">{p.id}</span>
              <span className={p.done ? "text-gray-700" : "text-gray-400 italic"}>{p.label}</span>
              {p.commit !== "—" && (
                <span className="ml-auto text-xs font-mono text-gray-300 shrink-0">{p.commit}</span>
              )}
            </div>
          ))}
        </div>
      </section>

      <p className="text-xs text-gray-400 mt-6">
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

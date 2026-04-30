import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

interface ReviewedMissingRow {
  id: string;
  raw_title: string | null;
  name_zh: string | null;
  name_en: string | null;
  source_name: string | null;
}
interface ExpiredActiveRow {
  id: string;
  raw_title: string | null;
  end_date: string | null;
  source_name: string | null;
}
interface AnnotatedNoCatRow {
  id: string;
  raw_title: string | null;
  source_name: string | null;
  created_at: string | null;
}
interface MissingAddrRow {
  id: string;
  raw_title: string | null;
  location_name: string | null;
  source_name: string | null;
}

function SectionHeader({
  title,
  count,
  showingLabel,
}: {
  title: string;
  count: number;
  showingLabel: string | null;
}) {
  return (
    <div className="flex items-baseline gap-3 mb-3">
      <h2 className="text-base font-semibold text-gray-700">{title}</h2>
      <span className={`text-2xl font-bold ${count > 0 ? "text-red-600" : "text-green-600"}`}>
        {count}
      </span>
      {showingLabel && <span className="text-xs text-gray-500">{showingLabel}</span>}
    </div>
  );
}

function renderEventLink(locale: Locale, id: string, title: string | null) {
  return (
    <Link
      href={`/${locale}/admin/${id}`}
      className="text-green-700 hover:underline"
    >
      {title || id.slice(0, 8)}
    </Link>
  );
}

export default async function AdminQualityPage({ params }: PageProps) {
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

  const todayIso = new Date().toISOString().slice(0, 10);

  const [
    reviewedMissingCountRes,
    expiredActiveCountRes,
    annotatedNoCatCountRes,
    missingAddrCountRes,
    reviewedMissingListRes,
    expiredActiveListRes,
    annotatedNoCatListRes,
    missingAddrListRes,
  ] = await Promise.all([
    supabase
      .from("events")
      .select("id", { count: "exact", head: true })
      .eq("annotation_status", "reviewed")
      .or("name_zh.is.null,name_en.is.null"),
    supabase
      .from("events")
      .select("id", { count: "exact", head: true })
      .eq("is_active", true)
      .lt("end_date", todayIso),
    supabase
      .from("events")
      .select("id", { count: "exact", head: true })
      .eq("annotation_status", "annotated")
      .or("category.is.null,category.eq.{}"),
    supabase
      .from("events")
      .select("id", { count: "exact", head: true })
      .eq("is_active", true)
      .is("location_address", null)
      .not("location_name", "ilike", "%オンライン%"),
    supabase
      .from("events")
      .select("id, raw_title, name_zh, name_en, source_name")
      .eq("annotation_status", "reviewed")
      .or("name_zh.is.null,name_en.is.null")
      .limit(50),
    supabase
      .from("events")
      .select("id, raw_title, end_date, source_name")
      .eq("is_active", true)
      .lt("end_date", todayIso)
      .order("end_date", { ascending: false })
      .limit(50),
    supabase
      .from("events")
      .select("id, raw_title, source_name, created_at")
      .eq("annotation_status", "annotated")
      .or("category.is.null,category.eq.{}")
      .order("created_at", { ascending: false })
      .limit(50),
    supabase
      .from("events")
      .select("id, raw_title, location_name, source_name")
      .eq("is_active", true)
      .is("location_address", null)
      .not("location_name", "ilike", "%オンライン%")
      .limit(50),
  ]);

  const reviewedMissingCount = reviewedMissingCountRes.count ?? 0;
  const expiredActiveCount = expiredActiveCountRes.count ?? 0;
  const annotatedNoCatCount = annotatedNoCatCountRes.count ?? 0;
  const missingAddrCount = missingAddrCountRes.count ?? 0;

  const reviewedMissingList = (reviewedMissingListRes.data ?? []) as ReviewedMissingRow[];
  const expiredActiveList = (expiredActiveListRes.data ?? []) as ExpiredActiveRow[];
  const annotatedNoCatList = (annotatedNoCatListRes.data ?? []) as AnnotatedNoCatRow[];
  const missingAddrList = (missingAddrListRes.data ?? []) as MissingAddrRow[];

  function fmtDate(iso: string | null) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("zh-TW");
  }

  function headerProps(title: string, count: number) {
    return {
      title,
      count,
      showingLabel: count > 50 ? t("qualityShowingFirstN", { total: count }) : null,
    };
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("qualityTitle")}</h1>

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
        <Link
          href={`/${locale}/admin/stats`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("statsTab")}
        </Link>
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {t("qualityTab")}
        </span>
      </div>

      {/* Section 1: Reviewed but missing translations */}
      <section className="mb-10">
        <SectionHeader {...headerProps(t("qualityReviewedMissing"), reviewedMissingCount)} />
        {reviewedMissingCount === 0 ? (
          <p className="text-sm text-green-700">✅ {t("qualityAllClear")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs text-gray-400 border-b border-gray-100">
                  <th className="text-left py-2 pr-4 font-medium">Title</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                  <th className="text-left py-2 pr-4 font-medium">name_zh</th>
                  <th className="text-left py-2 pr-4 font-medium">name_en</th>
                </tr>
              </thead>
              <tbody>
                {reviewedMissingList.map((r) => (
                  <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-4">{renderEventLink(locale, r.id, r.raw_title)}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-gray-500">{r.source_name ?? "—"}</td>
                    <td className="py-2 pr-4">{r.name_zh ?? <span className="text-amber-600">⚠</span>}</td>
                    <td className="py-2 pr-4">{r.name_en ?? <span className="text-amber-600">⚠</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Section 2: Expired but active */}
      <section className="mb-10">
        <SectionHeader {...headerProps(t("qualityExpiredActive"), expiredActiveCount)} />
        {expiredActiveCount === 0 ? (
          <p className="text-sm text-green-700">✅ {t("qualityAllClear")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs text-gray-400 border-b border-gray-100">
                  <th className="text-left py-2 pr-4 font-medium">Title</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                  <th className="text-left py-2 pr-4 font-medium">end_date</th>
                </tr>
              </thead>
              <tbody>
                {expiredActiveList.map((r) => (
                  <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-4">{renderEventLink(locale, r.id, r.raw_title)}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-gray-500">{r.source_name ?? "—"}</td>
                    <td className="py-2 pr-4 text-gray-500">{fmtDate(r.end_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Section 3: Annotated without category */}
      <section className="mb-10">
        <SectionHeader {...headerProps(t("qualityAnnotatedNoCat"), annotatedNoCatCount)} />
        {annotatedNoCatCount === 0 ? (
          <p className="text-sm text-green-700">✅ {t("qualityAllClear")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs text-gray-400 border-b border-gray-100">
                  <th className="text-left py-2 pr-4 font-medium">Title</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                  <th className="text-left py-2 pr-4 font-medium">created_at</th>
                </tr>
              </thead>
              <tbody>
                {annotatedNoCatList.map((r) => (
                  <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-4">{renderEventLink(locale, r.id, r.raw_title)}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-gray-500">{r.source_name ?? "—"}</td>
                    <td className="py-2 pr-4 text-gray-500">{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Section 4: Active without address */}
      <section className="mb-10">
        <SectionHeader {...headerProps(t("qualityMissingAddr"), missingAddrCount)} />
        {missingAddrCount === 0 ? (
          <p className="text-sm text-green-700">✅ {t("qualityAllClear")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-xs text-gray-400 border-b border-gray-100">
                  <th className="text-left py-2 pr-4 font-medium">Title</th>
                  <th className="text-left py-2 pr-4 font-medium">Source</th>
                  <th className="text-left py-2 pr-4 font-medium">location_name</th>
                </tr>
              </thead>
              <tbody>
                {missingAddrList.map((r) => (
                  <tr key={r.id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 pr-4">{renderEventLink(locale, r.id, r.raw_title)}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-gray-500">{r.source_name ?? "—"}</td>
                    <td className="py-2 pr-4 text-gray-500">{r.location_name ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

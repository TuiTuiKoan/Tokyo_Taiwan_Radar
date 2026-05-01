import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

interface QualityRow {
  id: string;
  raw_title: string | null;
  source_name: string | null;
}

function renderDetailTable(
  items: QualityRow[],
  locale: Locale,
) {
  if (items.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-xs text-gray-400 border-b border-gray-100">
            <th className="text-left py-2 pr-4 font-medium">Title</th>
            <th className="text-left py-2 pr-4 font-medium">Source</th>
            <th className="text-left py-2 font-medium">ID</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b border-gray-50 hover:bg-gray-50">
              <td className="py-2 pr-4 max-w-xs truncate">
                <Link
                  href={`/${locale}/admin/${item.id}`}
                  className="text-green-700 hover:underline"
                >
                  {item.raw_title ?? item.id}
                </Link>
              </td>
              <td className="py-2 pr-4">
                <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600 font-mono">
                  {item.source_name ?? "—"}
                </span>
              </td>
              <td className="py-2 text-xs text-gray-400 font-mono">{item.id.slice(0, 8)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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

  const today = new Date().toISOString().slice(0, 10);

  const [reviewedMissingRes, expiredActiveRes, annotatedNoCatRes, missingAddrRes] = await Promise.all([
    supabase
      .from("events")
      .select("id, raw_title, source_name")
      .eq("annotation_status", "reviewed")
      .or("name_zh.is.null,name_en.is.null")
      .limit(50),
    supabase
      .from("events")
      .select("id, raw_title, source_name")
      .eq("is_active", true)
      .lt("end_date", today)
      .limit(50),
    supabase
      .from("events")
      .select("id, raw_title, source_name")
      .eq("annotation_status", "annotated")
      .or("category.is.null,category.eq.{}")
      .limit(50),
    supabase
      .from("events")
      .select("id, raw_title, source_name, location_name")
      .eq("is_active", true)
      .is("location_address", null)
      .limit(50),
  ]);

  const reviewedMissing = (reviewedMissingRes.data ?? []) as QualityRow[];
  const expiredActive = (expiredActiveRes.data ?? []) as QualityRow[];
  const annotatedNoCat = (annotatedNoCatRes.data ?? []) as QualityRow[];
  const missingAddrAll = (missingAddrRes.data ?? []) as Array<QualityRow & { location_name: string | null }>;
  const missingAddr = missingAddrAll.filter(
    (e) =>
      !e.location_name ||
      (!e.location_name.includes("\u30AA\u30F3\u30E9\u30A4\u30F3") &&
       !e.location_name.includes("\u96fb\u8996\u983b\u9053") &&
       (e as any).source_name !== "gguide_tv")
  );

  const sections = [
    { key: "qualityReviewedMissing", items: reviewedMissing },
    { key: "qualityExpiredActive", items: expiredActive },
    { key: "qualityAnnotatedNoCat", items: annotatedNoCat },
    { key: "qualityMissingAddr", items: missingAddr },
  ] as const;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-gray-200 mb-6 flex-wrap">
        <Link href={`/${locale}/admin`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("eventsTab")}</Link>
        <Link href={`/${locale}/admin/announcements`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("announcementsTab")}</Link>
        <Link href={`/${locale}/admin/reports`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("reports")}</Link>
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">{t("qualityTab")}</span>
        <span className="mx-1 border-l border-green-300 h-6 self-center" />
        <Link href={`/${locale}/admin/research`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("researchTab")}</Link>
        <Link href={`/${locale}/admin/sources`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("sourcesTab")}</Link>
        <Link href={`/${locale}/admin/creators`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("creatorsTab")}</Link>
        <span className="mx-1 border-l border-green-300 h-6 self-center" />
        <Link href={`/${locale}/admin/users`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("usersTab")}</Link>
        <Link href={`/${locale}/admin/stats`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("statsTab")}</Link>
        <Link href={`/${locale}/admin/aeo`} className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition">{t("aeoTab")}</Link>
      </div>

      <h2 className="text-lg font-semibold mb-4">{t("qualityTitle")}</h2>

      <div className="space-y-8">
        {sections.map(({ key, items }) => (
          <div key={key} className="rounded-xl border border-gray-200 bg-white px-5 py-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700">
                {t(key)}
              </h3>
              <span className={`text-sm font-medium ${items.length === 0 ? "text-green-600" : "text-amber-600"}`}>
                {items.length}
              </span>
            </div>
            {items.length === 0 ? (
              <p className="text-sm text-green-600">{t("qualityAllClear")}</p>
            ) : (
              renderDetailTable(items, locale)
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

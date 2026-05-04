import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import QualitySection, { type QualityRow } from "@/components/QualitySection";

interface PageProps {
  params: Promise<{ locale: Locale }>;
  searchParams: Promise<{ source?: string }>;
}

export default async function AdminQualityPage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  const { source: rawSource } = await searchParams;
  const source = rawSource?.trim() || undefined;

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

  let reviewedMissingQuery = supabase
    .from("events")
    .select("id, raw_title, source_name")
    .eq("annotation_status", "reviewed")
    .eq("is_active", true)
    .or("name_zh.is.null,name_en.is.null")
    .limit(50);

  let annotatedNoCatQuery = supabase
    .from("events")
    .select("id, raw_title, source_name")
    .eq("annotation_status", "annotated")
    .eq("is_active", true)
    .or("category.is.null,category.eq.{}")
    .limit(50);

  let missingAddrQuery = supabase
    .from("events")
    .select("id, raw_title, source_name, location_name, location_prefectures")
    .eq("is_active", true)
    .not("location_name", "is", null)
    .is("location_address", null)
    .neq("source_name", "gguide_tv")
    .not("location_name", "like", "%〒%")
    .not("location_name", "ilike", "%オンライン%")
    .not("location_name", "ilike", "%youtube%")
    .not("location_name", "ilike", "%zoom%")
    .not("location_name", "ilike", "%ウェビナー%")
    .not("location_name", "ilike", "%webinar%")
    .limit(100);

  if (source) {
    reviewedMissingQuery = reviewedMissingQuery.eq("source_name", source) as typeof reviewedMissingQuery;
    annotatedNoCatQuery = annotatedNoCatQuery.eq("source_name", source) as typeof annotatedNoCatQuery;
    missingAddrQuery = missingAddrQuery.eq("source_name", source) as typeof missingAddrQuery;
  }

  const [reviewedMissingRes, annotatedNoCatRes, missingAddrRes] = await Promise.all([
    reviewedMissingQuery,
    annotatedNoCatQuery,
    missingAddrQuery,
  ]);

  const reviewedMissing = (reviewedMissingRes.data ?? []) as QualityRow[];
  const annotatedNoCat = (annotatedNoCatRes.data ?? []) as QualityRow[];
  // DB filters: location_name IS NOT NULL (has venue) AND location_address IS NULL (missing address)
  // Additional client-side filter: exclude short city/area names (≤6 chars, no spaces) and
  // multi-city venue names (contains ・ with location_prefectures implying multiple cities).
  const missingAddr = ((missingAddrRes.data ?? []) as QualityRow[]).filter((e) => {
    const loc = e.location_name ?? "";
    // Short geographic name only (e.g. 東京, 香港, 岡山, 文京区) — no actionable address exists
    if (loc.length <= 6 && !loc.includes(" ") && !loc.includes("　")) return false;
    // Multi-prefecture events (e.g. 東京・京都・大阪) — location_prefectures covers them already
    if ((e.location_prefectures?.length ?? 0) > 1) return false;
    return true;
  });

  const sections = [
    { key: "qualityReviewedMissing" as const, items: reviewedMissing },
    { key: "qualityAnnotatedNoCat" as const, items: annotatedNoCat },
    { key: "qualityMissingAddr" as const, items: missingAddr },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}

      <AdminTabNav locale={locale} activeTab="quality" />

      <h2 className="text-lg font-semibold mb-4">{t("qualityTitle")}</h2>

      {/* Source filter bar */}
      <form method="GET" className="flex items-center gap-2 mb-6">
        <label className="text-sm text-gray-600 shrink-0">
          {t("qualityFilterLabel")}
        </label>
        <input
          type="text"
          name="source"
          defaultValue={source ?? ""}
          placeholder={t("qualityFilterPlaceholder")}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm font-mono w-56 focus:outline-none focus:ring-1 focus:ring-green-400"
        />
        <button
          type="submit"
          className="px-3 py-1.5 text-sm bg-green-700 text-white rounded-lg hover:bg-green-800"
        >
          &#x1F50E;
        </button>
        {source && (
          <a
            href="?"
            className="text-sm text-gray-500 hover:underline"
          >
            {t("qualityFilterClear")}
          </a>
        )}
        {source && (
          <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-mono">
            {t("qualityFilterActive", { source })}
          </span>
        )}
      </form>

      <div className="space-y-4">
        {sections.map(({ key, items }) => (
          <QualitySection
            key={key}
            title={t(key)}
            count={items.length}
            locale={locale}
            items={items}
            allClearLabel={t("qualityAllClear")}
          />
        ))}
      </div>
    </div>
  );
}

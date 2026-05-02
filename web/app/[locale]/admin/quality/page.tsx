import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

interface QualityRow {
  id: string;
  raw_title: string | null;
  source_name: string | null;
  location_name?: string | null;
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
            {items.some((i) => i.location_name !== undefined) && (
              <th className="text-left py-2 pr-4 font-medium">Venue</th>
            )}
            <th className="text-left py-2 pr-4 font-medium">Source</th>
            <th className="text-left py-2 font-medium">ID</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b border-gray-50 hover:bg-gray-50">
              <td className="py-2 pr-4 max-w-xs truncate">
                <Link
                  href={`/${locale}/events/${item.id}`}
                  className="text-green-700 hover:underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {item.raw_title ?? item.id}
                </Link>
              </td>
              {item.location_name !== undefined && (
                <td className="py-2 pr-4 text-xs text-gray-500 max-w-[12rem] truncate">{item.location_name ?? "—"}</td>
              )}
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

  const [reviewedMissingRes, annotatedNoCatRes, missingAddrRes] = await Promise.all([
    supabase
      .from("events")
      .select("id, raw_title, source_name")
      .eq("annotation_status", "reviewed")
      .eq("is_active", true)
      .or("name_zh.is.null,name_en.is.null")
      .limit(50),
    supabase
      .from("events")
      .select("id, raw_title, source_name")
      .eq("annotation_status", "annotated")
      .eq("is_active", true)
      .or("category.is.null,category.eq.{}")
      .limit(50),
    // Flag events that HAVE a venue name but are missing a physical address.
    // Events with no location_name at all (e.g. online, competition/scholarship)
    // are intentionally excluded — they have no fixed venue to geocode.
    // Also exclude:
    //  - location_name containing 〒 (address already embedded in the name)
    //  - location_name containing オンライン (online events without a venue)
    supabase
      .from("events")
      .select("id, raw_title, source_name, location_name")
      .eq("is_active", true)
      .not("location_name", "is", null)
      .is("location_address", null)
      .neq("source_name", "gguide_tv")
      .not("location_name", "like", "%〒%")
      .not("location_name", "ilike", "%オンライン%")
      .limit(100),
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
    return true;
  });

  const sections = [
    { key: "qualityReviewedMissing", items: reviewedMissing },
    { key: "qualityAnnotatedNoCat", items: annotatedNoCat },
    { key: "qualityMissingAddr", items: missingAddr },
  ] as const;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}


      <AdminTabNav locale={locale} activeTab="quality" />

      <h2 className="text-lg font-semibold mb-4">{t("qualityTitle")}</h2>

      <div className="space-y-8">
        {sections.map(({ key, items }) => (
          <div key={key} className="rounded-xl border border-gray-200 bg-white px-5 py-4">
            <div className="flex items-center gap-2 mb-3">
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

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminSourcesTable, {
  type ResearchSource,
} from "@/components/AdminSourcesTable";
import AdminTabNav from "@/components/AdminTabNav";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminSourcesPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login`);
  }

  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();

  if (!roleRow || roleRow.role !== "admin") {
    redirect(`/${locale}`);
  }

  const { data: sources } = await supabase
    .from("research_sources")
    .select("*, scraper_source_name, scrape_times_per_day, scrape_hours_jst")
    .order("last_seen_at", { ascending: false })
    .limit(200);

  // Count active events per source_name for the filter dropdown
  const { data: eventRows } = await supabase
    .from("events")
    .select("source_name")
    .eq("is_active", true);

  const eventCountBySourceName: Record<string, number> = {};
  for (const row of eventRows ?? []) {
    if (row.source_name) {
      eventCountBySourceName[row.source_name] =
        (eventCountBySourceName[row.source_name] ?? 0) + 1;
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}


      <AdminTabNav locale={locale} activeTab="sources" />

      <AdminSourcesTable
        sources={(sources ?? []) as ResearchSource[]}
        eventCountBySourceName={eventCountBySourceName}
      />
    </div>
  );
}

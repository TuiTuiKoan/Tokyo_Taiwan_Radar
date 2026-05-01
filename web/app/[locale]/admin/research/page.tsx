import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminResearchTable, {
  type ResearchReport,
} from "@/components/AdminResearchTable";
import { type ResearchSource } from "@/components/AdminSourcesTable";
import AdminTabNav from "@/components/AdminTabNav";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminResearchPage({ params }: PageProps) {
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

  const { data: reports } = await supabase
    .from("research_reports")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50);

  const { data: sources } = await supabase
    .from("research_sources")
    .select("*")
    .order("last_seen_at", { ascending: false })
    .limit(200);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}


      <AdminTabNav locale={locale} activeTab="research" />

      {/* Daily reports section */}
      <h2 className="text-lg font-semibold mb-3">{t("researchTitle")}</h2>

      <AdminResearchTable
        reports={(reports ?? []) as ResearchReport[]}
        locale={locale}
        sources={(sources ?? []) as ResearchSource[]}
      />
    </div>
  );
}

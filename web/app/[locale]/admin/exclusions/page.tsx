import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import AdminExclusionsTable from "@/components/AdminExclusionsTable";
import { listExclusions } from "@/app/actions/source-exclusions";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminExclusionsPage({ params }: PageProps) {
  const { locale } = await params;
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

  const result = await listExclusions();
  const rows = result.ok ? result.rows ?? [] : [];

  const { data: srcRows } = await supabase
    .from("events")
    .select("source_name")
    .eq("is_active", true)
    .limit(2000);
  const knownSources = Array.from(
    new Set((srcRows ?? []).map((r) => r.source_name).filter(Boolean) as string[])
  ).sort();

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("exclusionsTitle")}</h1>
      <AdminTabNav locale={locale} activeTab="exclusions" />
      <AdminExclusionsTable rows={rows} knownSources={knownSources} locale={locale} />
    </div>
  );
}

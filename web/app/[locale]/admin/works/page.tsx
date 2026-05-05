import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Work } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import AdminWorksTable from "@/components/AdminWorksTable";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminWorksPage({ params }: PageProps) {
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

  const { data: works } = await supabase
    .from("works")
    .select("*")
    .order("created_at", { ascending: false });

  // Count linked events per work
  const { data: countRows } = await supabase
    .from("events")
    .select("work_id")
    .not("work_id", "is", null);
  const counts: Record<string, number> = {};
  for (const r of (countRows ?? []) as { work_id: string | null }[]) {
    if (r.work_id) counts[r.work_id] = (counts[r.work_id] ?? 0) + 1;
  }

  const enriched = ((works ?? []) as Work[]).map((w) => ({
    ...w,
    event_count: counts[w.id] ?? 0,
  }));

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("worksTitle")}</h1>
      <AdminTabNav locale={locale} activeTab="works" />
      <AdminWorksTable works={enriched} locale={locale} />
    </div>
  );
}

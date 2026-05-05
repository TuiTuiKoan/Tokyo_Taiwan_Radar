import { createClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Work, type Event } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import AdminWorkForm from "@/components/AdminWorkForm";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale; id: string }>;
}

export default async function AdminWorkEditPage({ params }: PageProps) {
  const { locale, id } = await params;
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

  const { data: work } = await supabase
    .from("works")
    .select("*")
    .eq("id", id)
    .single();
  if (!work) notFound();

  const { data: linkedEvents } = await supabase
    .from("events")
    .select("id, name_ja, name_zh, name_en, start_date, end_date, location_name, source_name, is_active")
    .eq("work_id", id)
    .order("start_date", { ascending: true });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("worksEdit")}</h1>
      <AdminTabNav locale={locale} activeTab="works" />
      <AdminWorkForm
        work={work as Work}
        linkedEvents={(linkedEvents ?? []) as Event[]}
        locale={locale}
      />
    </div>
  );
}

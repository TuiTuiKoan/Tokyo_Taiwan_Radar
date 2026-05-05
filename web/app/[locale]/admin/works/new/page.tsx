import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import AdminWorkForm from "@/components/AdminWorkForm";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminWorkNewPage({ params }: PageProps) {
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

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("worksNew")}</h1>
      <AdminTabNav locale={locale} activeTab="works" />
      <AdminWorkForm work={null} locale={locale} />
    </div>
  );
}

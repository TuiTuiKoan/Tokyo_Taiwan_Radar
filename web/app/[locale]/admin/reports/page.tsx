import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AdminReportsTable, { type ReportRow } from "@/components/AdminReportsTable";
import AdminTabNav from "@/components/AdminTabNav";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminReportsPage({ params }: PageProps) {
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
    .from("event_reports")
    .select("*, events(name_ja, name_zh, name_en, source_url, source_name, category, start_date, end_date, location_name, location_name_zh, location_name_en, location_address, location_address_zh, location_address_en, business_hours, business_hours_zh, business_hours_en, is_paid, price_info, description_ja, description_zh, description_en, selection_reason)")
    .order("created_at", { ascending: false });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}


      <AdminTabNav locale={locale} activeTab="reports" />

      <AdminReportsTable
        reports={(reports ?? []) as ReportRow[]}
        locale={locale}
      />
    </div>
  );
}

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, CATEGORIES } from "@/lib/types";
import AdminEventTable from "@/components/AdminEventTable";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login`);
  }

  // Check admin role
  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();

  if (!roleRow || roleRow.role !== "admin") {
    redirect(`/${locale}`);
  }

  // Fetch all events (including inactive) for admin view
  const { data: events } = await supabase
    .from("events")
    .select("*")
    .order("created_at", { ascending: false });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>
      <AdminEventTable
        events={(events ?? []) as Event[]}
        locale={locale}
      />
    </div>
  );
}

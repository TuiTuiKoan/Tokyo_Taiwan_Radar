import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event } from "@/lib/types";
import AdminCreateClient from "@/components/AdminCreateClient";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminCreatePage({ params }: PageProps) {
  const { locale } = await params;
  await getTranslations("admin");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

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

  const { data: allEvents } = await supabase
    .from("events")
    .select("id, name_ja, name_zh, name_en, start_date")
    .order("created_at", { ascending: false });

  return (
    <div>
      <AdminCreateClient
        locale={locale}
        allEvents={(allEvents ?? []) as Event[]}
      />
    </div>
  );
}

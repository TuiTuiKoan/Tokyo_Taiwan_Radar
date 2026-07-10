import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { type Locale } from "@/lib/types";
import EventIntakeWizard from "@/components/EventIntakeWizard";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function AdminCreatePage({ params }: PageProps) {
  const { locale } = await params;

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

  return (
    <div>
      <EventIntakeWizard context="admin" locale={locale} />
    </div>
  );
}

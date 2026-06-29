import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import EventIntakeWizard from "@/components/EventIntakeWizard";
import type { Locale } from "@/lib/types";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function OwnerCreatePage({ params }: PageProps) {
  const { locale } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login`);
  }

  const { data: profileRow } = await supabase
    .from("creators")
    .select("user_handle")
    .eq("user_id", user.id)
    .maybeSingle();

  if (!profileRow?.user_handle) {
    redirect(`/${locale}/account/profile`);
  }

  return (
    <EventIntakeWizard context="owner" locale={locale} />
  );
}

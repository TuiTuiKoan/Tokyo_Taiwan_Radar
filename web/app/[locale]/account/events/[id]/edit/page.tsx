import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import OwnerEditClient from "@/components/OwnerEditClient";
import type { Locale, Event } from "@/lib/types";

interface PageProps {
  params: Promise<{ locale: Locale; id: string }>;
}

export default async function OwnerEditPage({ params }: PageProps) {
  const { locale, id } = await params;
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

  // Fetch the event with owner check to prevent unauthorized edits.
  const { data: event } = await supabase
    .from("events")
    .select("*")
    .eq("id", id)
    .eq("owner_user_id", user.id)
    .single();

  if (!event) {
    redirect(`/${locale}/account`);
  }

  return (
    <OwnerEditClient event={event as Event} locale={locale} />
  );
}

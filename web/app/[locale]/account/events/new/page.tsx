import { redirect } from "next/navigation";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
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

  const t = await getTranslations({ locale, namespace: "account" });
  const tIntake = await getTranslations({ locale, namespace: "eventIntake" });

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 space-y-6">
      <nav aria-label="breadcrumb" className="flex items-center gap-2 text-sm">
        <Link
          href={`/${locale}/account?tab=myEvents`}
          className="text-fg-muted hover:text-fg-strong transition"
        >
          {t("title")}
        </Link>
        <span className="text-fg-subtle">›</span>
        <span aria-current="page" className="text-fg-strong font-medium">{tIntake("chooseTitle")}</span>
      </nav>
      <EventIntakeWizard context="owner" locale={locale} />
    </div>
  );
}

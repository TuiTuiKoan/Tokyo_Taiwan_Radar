import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import ProfileForm, { type CreatorProfile } from "@/components/ProfileForm";
import { isActorCategory } from "@/lib/actorTypes";
import type { Locale } from "@/lib/types";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

type CreatorProfileRow = {
  user_handle: string | null;
  organizer_name_zh: string | null;
  organizer_name_ja: string | null;
  organizer_name_en: string | null;
  website_url: string | null;
  social_x: string | null;
  social_instagram: string | null;
  social_note: string | null;
  social_facebook: string | null;
  social_threads: string | null;
  social_youtube: string | null;
  avatar_url: string | null;
  category: string | null;
  region: string | null;
};

function toInitialProfile(row: CreatorProfileRow | null): CreatorProfile | null {
  if (!row) return null;
  return {
    user_handle: row.user_handle ?? "",
    organizer_name_zh: row.organizer_name_zh ?? "",
    organizer_name_ja: row.organizer_name_ja ?? "",
    organizer_name_en: row.organizer_name_en ?? "",
    website_url: row.website_url ?? "",
    social_x: row.social_x ?? "",
    social_instagram: row.social_instagram ?? "",
    social_note: row.social_note ?? "",
    social_facebook: row.social_facebook ?? "",
    social_threads: row.social_threads ?? "",
    social_youtube: row.social_youtube ?? "",
    avatar_url: row.avatar_url ?? "",
    category: isActorCategory(row.category) ? row.category : null,
    region: row.region ?? "",
  };
}

export default async function AccountProfilePage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("profile");
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login`);
  }

  const { data: profile } = await supabase
    .from("creators")
    .select(
      "user_handle, organizer_name_zh, organizer_name_ja, organizer_name_en, website_url, social_x, social_instagram, social_note, social_facebook, social_threads, social_youtube, avatar_url, category, region",
    )
    .eq("user_id", user.id)
    .maybeSingle();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-fg-strong">{t("title")}</h1>
        <p className="mt-2 text-sm text-fg-muted">{t("intro")}</p>
      </div>
      <ProfileForm locale={locale} initialProfile={toInitialProfile((profile ?? null) as CreatorProfileRow | null)} />
    </div>
  );
}

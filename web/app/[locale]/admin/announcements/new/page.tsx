import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import AnnouncementForm from "@/components/AnnouncementForm";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

export default async function NewAnnouncementPage({ params }: PageProps) {
  const { locale } = await params;
  const tAnn = await getTranslations("announcements");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/login`);

  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") redirect(`/${locale}`);

  const { data: recentEvents } = await supabase
    .from("events")
    .select("id, name_ja, name_zh, name_en, location_name, start_date")
    .eq("is_active", true)
    .order("created_at", { ascending: false })
    .limit(500);

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <Link href={`/${locale}/admin/announcements`} className="text-sm text-gray-500 hover:text-green-700">
          ← {tAnn("announcementsTab")}
        </Link>
        <span className="text-gray-300">/</span>
        <h1 className="text-xl font-bold">{tAnn("newAnnouncement")}</h1>
      </div>

      <AnnouncementForm
        recentEvents={recentEvents ?? []}
        locale={locale}
      />
    </div>
  );
}

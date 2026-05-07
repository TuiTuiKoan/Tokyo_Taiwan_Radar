import { createClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Announcement } from "@/lib/types";
import AnnouncementForm from "@/components/AnnouncementForm";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale; id: string }>;
}

export const dynamic = "force-dynamic";

export default async function EditAnnouncementPage({ params }: PageProps) {
  const { locale, id } = await params;
  const tAnn = await getTranslations("announcements");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/login`);

  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") redirect(`/${locale}`);

  const { data: announcement } = await supabase
    .from("announcements")
    .select("*")
    .eq("id", id)
    .single();

  if (!announcement) notFound();

  const { data: linkedRows } = await supabase
    .from("announcement_events")
    .select("event_id")
    .eq("announcement_id", id);

  const announcementWithLinks: Announcement = {
    ...(announcement as Announcement),
    linked_events: linkedRows?.map((r) => r.event_id) ?? [],
  };

  const { data: recentEvents } = await supabase
    .from("events")
    .select("id, name_ja, name_zh, name_en, location_name, start_date")
    .eq("is_active", true)
    .order("created_at", { ascending: false })
    .limit(500);

  const title = announcement[`title_${locale}`] ?? announcement.title_zh ?? announcement.title_ja ?? "（無標題）";

  return (
    <div>
      <div className="flex items-center gap-3 mb-2">
        <Link href={`/${locale}/admin/announcements`} className="text-sm text-gray-500 hover:text-green-700">
          ← {tAnn("announcementsTab")}
        </Link>
        <span className="text-gray-300">/</span>
        <h1 className="text-xl font-bold truncate">{title}</h1>
      </div>
      <p className="text-xs text-gray-400 font-mono mb-6">/{announcement.slug}</p>

      <div className="mb-4 flex gap-2">
        <Link
          href={`/${locale}/announcements/${announcement.slug}`}
          target="_blank"
          className="text-xs text-blue-600 hover:underline"
        >
          {tAnn("viewPublic")} ↗
        </Link>
      </div>

      <AnnouncementForm
        announcement={announcementWithLinks}
        recentEvents={recentEvents ?? []}
        locale={locale}
      />
    </div>
  );
}

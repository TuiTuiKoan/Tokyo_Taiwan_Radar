import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Announcement } from "@/lib/types";
import AdminTabNav from "@/components/AdminTabNav";
import Link from "next/link";
import WeeklyBroadcastPanel from "@/components/WeeklyBroadcastPanel";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

export default async function AdminAnnouncementsPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");
  const tAnn = await getTranslations("announcements");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/login`);

  const { data: roleRow } = await supabase.from("user_roles").select("role").eq("user_id", user.id).single();
  if (!roleRow || roleRow.role !== "admin") redirect(`/${locale}`);

  const { data: announcements } = await supabase
    .from("announcements")
    .select("*")
    .order("created_at", { ascending: false });

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">{tAnn("adminTitle")}</h1>
        <Link
          href={`/${locale}/admin/announcements/new`}
          className="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700"
        >
          {tAnn("newAnnouncement")}
        </Link>
      </div>

      {/* Tab nav */}


      <AdminTabNav locale={locale} activeTab="announcements" />

      {/* Weekly broadcast panel */}
      <WeeklyBroadcastPanel locale={locale} />

      {!announcements || announcements.length === 0 ? (
        <p className="text-gray-400 text-sm">{tAnn("noAnnouncements")}</p>
      ) : (
        <div className="space-y-3">
          {announcements.map((ann: Announcement) => {
            const title = ann[`title_${locale}`] ?? ann.title_zh ?? ann.title_ja ?? ann.title_en ?? "（無標題）";
            const isDraft = !ann.published_at;
            const isFuture = ann.published_at && new Date(ann.published_at) > new Date();
            return (
              <Link
                key={ann.id}
                href={`/${locale}/admin/announcements/${ann.id}`}
                className="flex items-start gap-3 px-4 py-3 bg-white border border-gray-100 rounded-xl hover:border-green-200 hover:bg-green-50 transition"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    {isDraft && (
                      <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{tAnn("draft")}</span>
                    )}
                    {isFuture && !isDraft && (
                      <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">{tAnn("scheduled")}</span>
                    )}
                    {!isDraft && !isFuture && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">{tAnn("published")}</span>
                    )}
                    {ann.is_featured && (
                      <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">{tAnn("featured")}</span>
                    )}
                  </div>
                  <p className="text-sm font-medium truncate">{title}</p>
                  <p className="text-xs text-gray-400 font-mono mt-0.5">/{ann.slug}</p>
                </div>
                <div className="text-xs text-gray-400 shrink-0 text-right">
                  {ann.published_at
                    ? new Date(ann.published_at).toLocaleDateString(locale)
                    : new Date(ann.created_at).toLocaleDateString(locale)}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

import { createClient } from "@/lib/supabase/server";
import { getTranslations } from "next-intl/server";
import { type Locale, type Announcement } from "@/lib/types";
import AnnouncementCard from "@/components/AnnouncementCard";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

export default async function AnnouncementsPage({ params }: PageProps) {
  const { locale } = await params;
  const tAnn = await getTranslations("announcements");

  const supabase = await createClient();
  const now = new Date().toISOString();

  const { data: announcements } = await supabase
    .from("announcements")
    .select("*")
    .not("published_at", "is", null)
    .lte("published_at", now)
    .order("published_at", { ascending: false });

  return (
    <div>
      {/* Top tab navigation (mirrors homepage) */}
      <div className="flex gap-1 border-b border-line mb-6">
        <Link
          href={`/${locale}`}
          className="px-4 py-2 text-sm text-fg-muted hover:text-green-700 transition"
        >
          {tAnn("tabEvents")}
        </Link>
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {tAnn("tabNews")}
        </span>
      </div>

      <h1 className="text-xl font-bold mb-1">{tAnn("pageTitle")}</h1>
      <p className="text-sm text-fg-muted mb-6">{tAnn("pageDesc")}</p>

      {!announcements || announcements.length === 0 ? (
        <p className="text-center text-fg-subtle mt-12 text-sm">{tAnn("noPublished")}</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {announcements.map((ann: Announcement) => (
            <AnnouncementCard key={ann.id} announcement={ann} locale={locale} />
          ))}
        </div>
      )}
    </div>
  );
}

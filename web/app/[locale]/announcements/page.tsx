import type { Metadata } from "next";
import { createClient } from "@/lib/supabase/server";
import { getTranslations } from "next-intl/server";
import { type Locale, type Announcement } from "@/lib/types";
import AnnouncementCard from "@/components/AnnouncementCard";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

const LOCALES: Locale[] = ["zh", "en", "ja"];

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale } = await params;
  const tAnn = await getTranslations({ locale, namespace: "announcements" });
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const title = tAnn("pageTitle");
  const description = tAnn("pageDesc").slice(0, 160);
  const image = `${base}/${locale}/announcements/opengraph-image`;

  return {
    title,
    description,
    alternates: {
      canonical: `${base}/${locale}/announcements`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/announcements`])),
        "x-default": `${base}/ja/announcements`,
      },
    },
    openGraph: {
      title,
      description,
      url: `${base}/${locale}/announcements`,
      type: "website",
      images: [{ url: image, width: 1200, height: 1200, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}

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
    .order("published_at", { ascending: false }) as { data: Announcement[] | null };

  return (
    <div className="max-w-4xl mx-auto">
      <nav className="text-sm text-fg-muted mb-4">
        <Link href={`/${locale}`} className="text-green-500 hover:underline">
          Tokyo Taiwan Radar
        </Link>
        {" › "}
        <span className="text-fg">{tAnn("pageTitle")}</span>
      </nav>

      <h1 className="font-display font-bold text-fg text-2xl mb-1">{tAnn("pageTitle")}</h1>
      <p className="text-sm text-fg-muted mb-6">{tAnn("pageDesc")}</p>

      {!announcements || announcements.length === 0 ? (
        <p className="text-center text-fg-subtle mt-12 text-sm">{tAnn("noPublished")}</p>
      ) : (
        <div className="flex flex-wrap gap-4">
          {announcements.map((ann: Announcement) => (
            <AnnouncementCard key={ann.id} announcement={ann} locale={locale} />
          ))}
        </div>
      )}
    </div>
  );
}

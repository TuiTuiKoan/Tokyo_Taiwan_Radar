import type { Announcement, Locale } from "@/lib/types";
import Link from "next/link";

interface Props {
  announcement: Announcement;
  locale: Locale;
}

export default function AnnouncementCard({ announcement, locale }: Props) {
  const title =
    announcement[`title_${locale}`] ??
    announcement.title_zh ??
    announcement.title_ja ??
    announcement.title_en ??
    "";

  const body =
    announcement[`body_${locale}`] ??
    announcement.body_zh ??
    announcement.body_ja ??
    announcement.body_en ??
    "";

  const image =
    announcement[`image_${locale}`] ??
    announcement.cover_image_url ??
    null;

  const date = announcement.published_at
    ? new Date(announcement.published_at).toLocaleDateString(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  return (
    <Link
      href={`/${locale}/announcements/${announcement.slug}`}
      className="block bg-surface border border-line rounded-xl overflow-hidden hover:border-green-200 hover:shadow-sm transition group"
    >
      {image && (
        <div className="aspect-video overflow-hidden bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={image}
            alt={title}
            className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
          />
        </div>
      )}
      <div className="p-4">
        <div className="flex items-center gap-2 mb-1">
          {announcement.is_featured && (
            <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
              {locale === "zh" ? "精選" : locale === "ja" ? "注目" : "Featured"}
            </span>
          )}
          {date && <span className="text-xs text-fg-subtle">{date}</span>}
        </div>
        <h2 className="text-base font-semibold text-fg-strong group-hover:text-green-700 line-clamp-2 mb-1">
          {title}
        </h2>
        {body && (
          <p className="text-sm text-fg-muted line-clamp-3 whitespace-pre-line">{body}</p>
        )}
      </div>
    </Link>
  );
}

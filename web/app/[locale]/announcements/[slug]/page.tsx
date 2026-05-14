import React from "react";
import { createClient } from "@/lib/supabase/server";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Announcement, type Event, getEventName } from "@/lib/types";
import Link from "next/link";
import { CARD_LINK } from "@/lib/classNames";

interface PageProps {
  params: Promise<{ locale: Locale; slug: string }>;
}

/** Render body text with URLs auto-linked. */
function linkifyBody(text: string) {
  const URL_RE = /https?:\/\/[^\s<>"'）]+/g;
  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  while ((match = URL_RE.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const url = match[0];
    parts.push(
      <a key={match.index} href={url} target="_blank" rel="noopener noreferrer"
         className="text-green-700 underline break-all hover:text-green-900">
        {url}
      </a>
    );
    last = match.index + url.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export const dynamic = "force-dynamic";

export default async function AnnouncementDetailPage({ params }: PageProps) {
  const { locale, slug } = await params;
  const tAnn = await getTranslations("announcements");

  const supabase = await createClient();
  const now = new Date().toISOString();

  const { data: announcement } = await supabase
    .from("announcements")
    .select("*")
    .eq("slug", slug)
    .lte("published_at", now)
    .not("published_at", "is", null)
    .single();

  if (!announcement) notFound();

  const ann = announcement as Announcement;

  const title = ann[`title_${locale}`] ?? ann.title_zh ?? ann.title_ja ?? ann.title_en ?? "";
  const body = ann[`body_${locale}`] ?? ann.body_zh ?? ann.body_ja ?? ann.body_en ?? "";
  const image = ann[`image_${locale}`] ?? ann.cover_image_url ?? null;

  // Linked events
  const { data: linkedRows } = await supabase
    .from("announcement_events")
    .select("event_id")
    .eq("announcement_id", ann.id);

  let linkedEvents: Event[] = [];
  if (linkedRows && linkedRows.length > 0) {
    const { data: events } = await supabase
      .from("events")
      .select("id, name_ja, name_zh, name_en, start_date, end_date, category")
      .in("id", linkedRows.map((r) => r.event_id))
      .eq("is_active", true);
    linkedEvents = (events ?? []) as Event[];
  }

  const date = ann.published_at
    ? new Date(ann.published_at).toLocaleDateString(locale, {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : null;

  return (
    <article className="max-w-2xl mx-auto">
      {/* Breadcrumb */}
      <nav className="text-sm text-fg-subtle mb-4">
        <Link href={`/${locale}/announcements`} className="hover:text-green-700">
          {tAnn("pageTitle")}
        </Link>
        <span className="mx-2">/</span>
        <span className="text-fg-muted">{title}</span>
      </nav>

      {/* Cover image */}
      {image && (
        <div className="rounded-xl overflow-hidden bg-muted mb-6">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={image} alt={title} className="w-full h-auto" />
        </div>
      )}

      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          {ann.is_featured && (
            <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
              {tAnn("featured")}
            </span>
          )}
          {date && <time dateTime={ann.published_at ?? ""} className="text-xs text-fg-subtle">{date}</time>}
        </div>
        <h1 className="text-2xl font-bold text-fg-strong">{title}</h1>
      </div>

      {/* Body */}
      {body && (
        <div className="prose prose-sm max-w-none text-fg whitespace-pre-line mb-8">
          {linkifyBody(body)}
        </div>
      )}

      {/* Linked events */}
      {linkedEvents.length > 0 && (
        <div className="border-t border-line pt-6">
          <p className="text-sm font-semibold text-fg mb-3">{tAnn("relatedEvents")}</p>
          <div className="space-y-2">
            {linkedEvents.map((ev) => (
              <Link
                key={ev.id}
                href={`/${locale}/events/${ev.id}`}
                className={`${CARD_LINK} gap-3 px-3 py-2 bg-elevated rounded-lg text-sm`}
              >
                {ev.start_date && (
                  <span className="text-xs text-fg-subtle shrink-0">
                    {new Date(ev.start_date).toLocaleDateString(locale, { month: "short", day: "numeric" })}
                  </span>
                )}
                <span className="truncate">{getEventName(ev as Event, locale)}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Back link */}
      <div className="mt-8 pt-4 border-t border-line">
        <Link href={`/${locale}/announcements`} className="text-sm text-fg-subtle hover:text-green-700">
          ← {tAnn("backToList")}
        </Link>
      </div>
    </article>
  );
}

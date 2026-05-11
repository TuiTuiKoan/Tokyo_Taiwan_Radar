import { createClient } from "@supabase/supabase-js";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, getEventName } from "@/lib/types";
import FilterBar from "@/components/FilterBar";
import ListScrollManager from "@/components/ListScrollManager";
import EventListClient from "@/components/EventListClient";
import Link from "next/link";
import AnnouncementCard from "@/components/AnnouncementCard";
import { Suspense } from "react";

// ISR: revalidate every 10 minutes. All filter logic runs client-side so
// every URL (with or without query params) shares the same cached payload.
export const revalidate = 600;

interface PageProps {
  params: Promise<{ locale: Locale }>;
  searchParams: Promise<{
    q?: string;
    category?: string;
    from?: string;
    to?: string;
    paid?: string;
    timeMode?: string;
    location?: string;
    city?: string;
  }>;
}

export default async function HomePage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  // searchParams is awaited but not consumed server-side — filter state
  // is read from `useSearchParams()` inside <EventListClient> / <FilterBar>.
  const sp = await searchParams;
  const tAnn = await getTranslations("announcements");
  const tHome = await getTranslations("home");

  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );

  // -- Fetch all active events with the minimum field set the list view
  // needs. No filters applied here; <EventListClient> handles them.
  const { data: rawEvents, error } = await supabase
    .from("events")
    .select(
      "id, source_name, name_ja, name_zh, name_en, organizer, location_name, location_address, location_prefectures, category, start_date, end_date, is_paid, image_url, parent_event_id, work_id",
    )
    .eq("is_active", true)
    .order("start_date", { ascending: true });

  if (error) {
    console.error("Error fetching events:", error);
  }

  const events = (rawEvents ?? []) as unknown as Event[];

  // Build parent event name map for child events (only need names).
  const parentIds = [
    ...new Set(events.map((e) => e.parent_event_id).filter(Boolean)),
  ] as string[];
  const parentMap: Record<string, Event> = {};
  if (parentIds.length > 0) {
    const { data: parents } = await supabase
      .from("events")
      .select("id, name_ja, name_zh, name_en")
      .in("id", parentIds);
    if (parents) {
      for (const p of parents) {
        parentMap[p.id] = p as unknown as Event;
      }
    }
  }

  // Featured announcements strip (unrelated to event filters).
  const now = new Date().toISOString();
  const { data: featuredAnnouncements } = await supabase
    .from("announcements")
    .select("*")
    .eq("is_featured", true)
    .not("published_at", "is", null)
    .lte("published_at", now)
    .order("published_at", { ascending: false })
    .limit(3);

  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";

  // ItemList JSON-LD — always emit the first 20 events of the cached
  // (unfiltered) payload. Filtering now happens client-side and would
  // produce different lists per visitor, so the SEO surface is the
  // unfiltered view.
  const itemListLd =
    events.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "ItemList",
          url: `${base}/${locale}`,
          itemListElement: events.slice(0, 20).map((e, i) => ({
            "@type": "ListItem",
            position: i + 1,
            url: `${base}/${locale}/events/${e.id}`,
            name: getEventName(e, locale) ?? e.name_ja ?? undefined,
          })),
        }
      : null;

  return (
    <div>
      {itemListLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListLd) }}
        />
      )}
      {/* Top tab navigation */}
      <div className="flex gap-1 border-b border-line mb-4">
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {tAnn("tabEvents")}
        </span>
        <Link
          href={`/${locale}/announcements`}
          className="px-4 py-2 text-sm text-fg-muted hover:text-green-700 transition"
        >
          {tAnn("tabNews")}
        </Link>
      </div>

      {/* Brand intro / SEO content */}
      <section className="mt-6 mb-8 max-w-3xl">
        <h1 className="text-2xl sm:text-3xl font-bold text-fg-strong mb-1">
          {tHome("introTitle")}
        </h1>
        <p className="text-sm text-green-700 mb-4 font-medium">
          {tHome("introTagline")}
        </p>
        <div className="space-y-3 text-sm leading-relaxed text-fg-muted">
          <p>{tHome("introP1")}</p>
          <p>{tHome("introP2")}</p>
          <p>{tHome("introP3")}</p>
        </div>
      </section>

      {/* Featured announcements strip */}
      {featuredAnnouncements && featuredAnnouncements.length > 0 && (
        <div className="mt-4 mb-2">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-amber-700">{tAnn("featuredStrip")}</p>
            <Link href={`/${locale}/announcements`} className="text-xs text-fg-subtle hover:text-green-700">
              {tAnn("viewAll")} →
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {featuredAnnouncements.map((ann) => (
              <AnnouncementCard key={ann.id} announcement={ann} locale={locale} />
            ))}
          </div>
        </div>
      )}

      <FilterBar locale={locale} currentFilters={{ ...sp, city: sp.city ?? "" }} />
      <Suspense fallback={null}>
        <ListScrollManager />
      </Suspense>

      <EventListClient events={events} parentMap={parentMap} locale={locale} />
    </div>
  );
}

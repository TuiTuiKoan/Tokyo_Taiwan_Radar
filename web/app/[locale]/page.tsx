import { createClient } from "@supabase/supabase-js";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, getEventName } from "@/lib/types";
import FilterBar from "@/components/FilterBar";
import ListScrollManager from "@/components/ListScrollManager";
import EventListClient from "@/components/EventListClient";
import { FloatingShapes } from "@/lib/design/FloatingShapes";
import { MascotAvatar } from "@/lib/design";
import Link from "next/link";
import AnnouncementCard from "@/components/AnnouncementCard";
import { Suspense } from "react";

// ISR: revalidate every 10 minutes. All filter logic runs client-side so
// every URL (with or without query params) shares the same cached payload.
export const revalidate = 600;

// Attribution required: "Powered by Yahoo! JAPAN" footer when map is visible
// See: https://developer.yahoo.co.jp/webapi/map/openlocalplatform/v1/geocoder.html

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

  // Latest published announcements strip (unrelated to event filters).
  const now = new Date().toISOString();
  const { data: featuredAnnouncements } = await supabase
    .from("announcements")
    .select("*")
    .not("published_at", "is", null)
    .lte("published_at", now)
    .order("published_at", { ascending: false })
    .limit(4);

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
      <FloatingShapes />
      {itemListLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListLd) }}
        />
      )}

      {/* Brand intro / SEO content — Lianbu mascot hero */}
      <section className="mt-6 mb-8 relative grid gap-6 md:grid-cols-[300px_1fr] items-start text-center md:text-left">
        <div className="relative inline-flex flex-col items-center mx-auto md:mx-0 shrink-0">
          <MascotAvatar variant="inline" size={300} antennaFlowAnimation />
          <div
            className="absolute bottom-1 right-[50px] px-3 py-1.5 bg-paper border-2 text-[10px] font-accent font-black tracking-widest text-[#3A261F] dark:text-fg-muted -rotate-6 text-center z-10"
            style={{ borderColor: "var(--color-mocha, #3A261F)" }}
          >
            Lianbu
          </div>
        </div>

        <div className="w-full flex flex-col items-center md:items-start text-center md:text-left mx-auto md:mx-0 md:pt-[36px]">
          <h1 className="font-display font-black text-[#3A261F] dark:text-fg leading-tight text-3xl tracking-tight">
            <span className="block">{tHome("heroLine1")}</span>
            <span className="block">{tHome("heroLine2")}</span>
            <span className="block">{tHome("heroLine3")}</span>
            <span className="block text-mascot-red">{tHome("heroLine4")}</span>
          </h1>

          <div className="mt-3 mb-1 inline-flex items-center px-3 py-1 rounded bg-[#C4E86F]/40 text-[#1F5E2B] dark:bg-green-900/30 dark:text-green-300 text-[10px] sm:text-xs font-bold whitespace-nowrap">
            {tHome("statHero")}
          </div>

          <p className="mt-3 text-[12px] leading-relaxed text-fg-muted max-w-xl">
            {tHome("heroPara")}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3 justify-center md:justify-start w-full">
            <a
              href="https://line.me/R/ti/p/@769qbdkq"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-white text-xs font-semibold shadow-sm hover:opacity-90"
              style={{ background: "#06C755" }}
            >
              <span
                className="w-3.5 h-3.5 rounded-sm bg-white text-[9px] leading-[14px] text-center font-black"
                style={{ color: "#06C755" }}
              >
                L
              </span>
              {tHome("lineCta")}
            </a>
          </div>
        </div>
      </section>

      {/* Featured announcements strip */}
      {featuredAnnouncements && featuredAnnouncements.length > 0 && (
        <section className="mt-6 mb-8 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-display font-bold text-[#3A261F] dark:text-fg text-xl">
              📌 {tAnn("featuredStrip")}
            </h2>
            {featuredAnnouncements.length > 3 && (
              <Link
                href={`/${locale}/announcements`}
                className="text-xs text-mascot-pink-deep hover:underline shrink-0"
              >
                {tAnn("viewAll")} →
              </Link>
            )}
          </div>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {featuredAnnouncements.slice(0, 3).map((ann) => (
              <AnnouncementCard key={ann.id} announcement={ann} locale={locale} />
            ))}
          </div>
        </section>
      )}

      <FilterBar locale={locale} currentFilters={{ ...sp, city: sp.city ?? "" }} />
      <Suspense fallback={null}>
        <ListScrollManager />
      </Suspense>

      <EventListClient events={events} parentMap={parentMap} locale={locale} />
    </div>
  );
}

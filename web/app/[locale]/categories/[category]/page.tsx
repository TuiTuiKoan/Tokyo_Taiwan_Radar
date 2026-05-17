import type { Metadata } from "next";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { type Locale, type Event, type Work, CATEGORIES, type Category, getEventName, getWorkTitle } from "@/lib/types";
import EventCard from "@/components/EventCard";
import FilterBar from "@/components/FilterBar";
import MovieWorksList, { type MovieEventRow, type WorkGroupData } from "@/components/MovieWorksList";
import Link from "next/link";
import { shortPrefecture } from "@/lib/cityLabel";

// ── Types & helpers ───────────────────────────────────────────────────────────

// ── Movie-list helpers (server-side) ──────────────────────────────────────────

type WorkSummary = Pick<Work, "id" | "title_ja" | "title_zh" | "title_en" | "original_title" | "director" | "release_year" | "poster_url">;

function eventCitiesServer(ev: MovieEventRow): string[] {
  const prefs = ev.location_prefectures ?? [];
  if (prefs.length === 0) return ["_other"];
  return prefs.map((p) => shortPrefecture(p.trim())).filter(Boolean);
}

function buildWorkGroups(
  events: MovieEventRow[],
  works: WorkSummary[],
  locale: Locale,
): WorkGroupData[] {
  const workMap = new Map(works.map((w) => [w.id, w]));

  // Group events by work_id; standalone events go into eventsNoWork
  const byWorkId = new Map<string, MovieEventRow[]>();
  const eventsNoWork: MovieEventRow[] = [];
  for (const ev of events) {
    if (ev.work_id) {
      const list = byWorkId.get(ev.work_id) ?? [];
      list.push(ev);
      byWorkId.set(ev.work_id, list);
    } else {
      eventsNoWork.push(ev);
    }
  }

  const groups: WorkGroupData[] = [];

  // Work groups
  for (const [workId, evs] of byWorkId.entries()) {
    const work = workMap.get(workId) ?? null;
    const displayTitle = work
      ? getWorkTitle(work, locale)
      : (evs[0].name_ja ?? evs[0].name_zh ?? evs[0].name_en ?? "（未題）");

    const allCities = new Set<string>();
    let hasOther = false;
    for (const ev of evs) {
      const cities = eventCitiesServer(ev);
      for (const c of cities) {
        if (c === "_other") hasOther = true;
        else allCities.add(c);
      }
    }
    const sortedCities = [...allCities].sort((a, b) =>
      a.localeCompare(b, "ja"),
    );
    if (hasOther) sortedCities.push("_other");

    const earliestDate =
      evs
        .map((e) => e.start_date)
        .filter(Boolean)
        .sort()[0] ?? null;

    groups.push({
      key: workId,
      displayTitle,
      director: work?.director ?? null,
      year: work?.release_year ?? null,
      posterUrl: work?.poster_url ?? null,
      events: evs.slice().sort((a, b) =>
        (a.start_date ?? "").localeCompare(b.start_date ?? ""),
      ),
      cities: sortedCities,
      // Attach earliestDate for sorting (not in interface; spread is fine)
      ...({ earliestDate } as any),
    });
  }

  // Standalone events (no work_id)
  for (const ev of eventsNoWork) {
    const displayTitle =
      (locale === "ja" ? ev.name_ja : locale === "en" ? ev.name_en : ev.name_zh) ??
      ev.name_ja ??
      ev.name_zh ??
      ev.name_en ??
      "（未題）";

    const cities = eventCitiesServer(ev);
    const hasOther = cities.includes("_other");
    const sortedCities = cities
      .filter((c) => c !== "_other")
      .sort((a, b) => a.localeCompare(b, "ja"));
    if (hasOther) sortedCities.push("_other");

    groups.push({
      key: `ev_${ev.id}`,
      displayTitle,
      director: null,
      year: null,
      posterUrl: null,
      events: [ev],
      cities: sortedCities,
      ...({ earliestDate: ev.start_date } as any),
    });
  }

  // Sort all groups by earliest event date
  groups.sort((a, b) => {
    const ea: string | null = (a as any).earliestDate;
    const eb: string | null = (b as any).earliestDate;
    if (!ea) return 1;
    if (!eb) return -1;
    return ea.localeCompare(eb);
  });

  return groups;
}

interface PageProps {
  params: Promise<{ locale: Locale; category: string }>;
}

// ── Metadata ─────────────────────────────────────────────────────────────────

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale, category } = await params;
  if (!CATEGORIES.includes(category as Category)) return {};
  const tCatDesc = await getTranslations("categoryDesc");
  const tCat = await getTranslations("categories");
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const LOCALES: Locale[] = ["zh", "en", "ja"];
  const desc = tCatDesc(category as any) as string;
  const label = tCat(category as any) as string;
  return {
    title: label,
    description: desc.slice(0, 160),
    alternates: {
      canonical: `${base}/${locale}/categories/${category}`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/categories/${category}`])),
        "x-default": `${base}/zh/categories/${category}`,
      },
    },
    openGraph: {
      title: label,
      description: desc.slice(0, 160),
      url: `${base}/${locale}/categories/${category}`,
      type: "website",
    },
  };
}

export function generateStaticParams() {
  const LOCALES: Locale[] = ["zh", "en", "ja"];
  return LOCALES.flatMap((locale) =>
    CATEGORIES.map((category) => ({ locale, category }))
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default async function CategoryPage({ params }: PageProps) {
  const { locale, category } = await params;
  if (!CATEGORIES.includes(category as Category)) notFound();

  const t = await getTranslations("categories");
  const tCatDesc = await getTranslations("categoryDesc");
  const tMovieList = await getTranslations("movieList");

  const supabase = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const today = new Date().toISOString().slice(0, 10);

  // ── Movie: fetch events + works for accordion list view ───────────────────
  let movieGroups: WorkGroupData[] | null = null;
  let movieLabels = { director: "", viewDetails: "", otherCity: "" };

  if (category === "movie") {
    const { data: movieEvents } = await supabase
      .from("events")
      .select(
        "id,name_ja,name_zh,name_en,work_id,location_name,location_address,source_url,start_date,end_date,location_prefectures",
      )
      .eq("is_active", true)
      .in("annotation_status", ["annotated", "reviewed"])
      .is("parent_event_id", null)
      .or(`end_date.gte.${today},end_date.is.null`)
      .contains("category", ["movie"])
      .order("start_date", { ascending: true })
      .limit(200);

    const rows = (movieEvents ?? []) as MovieEventRow[];

    // Fetch works for event with work_id
    const workIds = [...new Set(rows.map((e) => e.work_id).filter(Boolean))] as string[];
    let worksData: WorkSummary[] = [];
    if (workIds.length > 0) {
      const { data: ws } = await supabase
        .from("works")
        .select("id,title_ja,title_zh,title_en,original_title,director,release_year,poster_url")
        .in("id", workIds);
      worksData = (ws ?? []) as WorkSummary[];
    }

    movieGroups = buildWorkGroups(rows, worksData, locale);
    movieLabels = {
      director: tMovieList("director") as string,
      viewDetails: tMovieList("viewDetails") as string,
      otherCity: tMovieList("otherCity") as string,
    };
  }

  // ── General: fetch events for card grid (all non-movie categories) ─────────
  let rows: Event[] = [];
  if (category !== "movie") {
    const { data: events } = await supabase
      .from("events")
      .select("*")
      .eq("is_active", true)
      .eq("annotation_status", "annotated")
      .is("parent_event_id", null)
      .or(`end_date.gte.${today},end_date.is.null`)
      .contains("category", [category])
      .order("start_date", { ascending: true })
      .limit(100);
    rows = (events ?? []) as Event[];
  }

  const categoryLabel = t(category as any) as string;
  const description = tCatDesc(category as any) as string;
  // Long description for FEATURED categories; falls back to short desc otherwise.
  const FEATURED_LONG = new Set([
    "movie", "performing_arts", "senses", "art", "lecture",
    "taiwan_japan", "lifestyle_food", "books_media",
  ]);
  const descriptionLong = FEATURED_LONG.has(category)
    ? (tCatDesc(`${category}_long` as any) as string)
    : description;
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";

  // For structured data: use movieGroups titles for movie, events for others
  const ldItems = movieGroups
    ? movieGroups.slice(0, 50).map((g, i) => ({
        "@type": "ListItem",
        position: i + 1,
        name: g.displayTitle,
      }))
    : rows.slice(0, 50).map((e, i) => ({
        "@type": "ListItem",
        position: i + 1,
        url: `${base}/${locale}/events/${e.id}`,
        name: getEventName(e, locale) ?? e.name_ja ?? undefined,
      }));

  const collectionLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: categoryLabel,
    description,
    url: `${base}/${locale}/categories/${category}`,
    mainEntity: { "@type": "ItemList", itemListElement: ldItems },
  };

  // Featured categories for cross-navigation (exclude current)
  const FEATURED: Category[] = [
    "movie", "performing_arts", "senses", "art", "lecture",
    "taiwan_japan", "lifestyle_food", "books_media",
  ];

  return (
    <main className="max-w-4xl mx-auto">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionLd) }}
      />

      {/* Breadcrumb */}
      <nav className="text-sm text-fg-muted mb-4">
        <Link href={`/${locale}`} className="text-green-500 hover:underline">
          Tokyo Taiwan Radar
        </Link>
        {" › "}
        <span className="text-fg">{categoryLabel}</span>
      </nav>

      {/* Heading + intro */}
      <h1 className="text-2xl font-bold mb-3 text-fg">{categoryLabel}</h1>
      {descriptionLong && (
        <section className="mb-6 space-y-3 text-sm leading-relaxed text-fg-muted">
          <p>{descriptionLong}</p>
        </section>
      )}

      {/* Movie: FilterBar + work accordion list */}
      {movieGroups !== null && (
        <>
          <Suspense>
            <FilterBar locale={locale} currentFilters={{}} hiddenFilters={["category", "paid"]} />
          </Suspense>
          {movieGroups.length === 0 ? (
            <p className="text-fg-muted text-sm">{tCatDesc("noEvents")}</p>
          ) : (
            <Suspense>
              <MovieWorksList
                groups={movieGroups}
                locale={locale}
                labels={movieLabels}
              />
            </Suspense>
          )}
        </>
      )}

      {/* Other categories: event card grid */}
      {movieGroups === null && (
        rows.length === 0 ? (
          <p className="text-fg-muted text-sm">{tCatDesc("noEvents")}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {rows.map((e) => (
              <EventCard key={e.id} event={e} locale={locale} />
            ))}
          </div>
        )
      )}

      {/* Category nav */}
      <nav className="mt-10 flex flex-wrap gap-2 text-sm">
        {FEATURED.filter((c) => c !== category).map((c) => (
          <Link
            key={c}
            href={`/${locale}/categories/${c}`}
            className="px-3 py-1 rounded-full border text-green-500 border-green-200 hover:border-green-600 hover:text-green-700 transition"
          >
            {t(c)}
          </Link>
        ))}
      </nav>
    </main>
  );
}

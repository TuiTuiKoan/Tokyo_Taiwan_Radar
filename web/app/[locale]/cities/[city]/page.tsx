import type { Metadata } from "next";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { type Locale, type Event, CATEGORIES, getEventName } from "@/lib/types";
import EventCard from "@/components/EventCard";
import Link from "next/link";

export const revalidate = 3600;

// ── City definitions ─────────────────────────────────────────────────────────

const CITY_SLUGS = ["tokyo", "osaka", "kyoto", "fukuoka", "sapporo", "nagoya"] as const;
type CitySlug = (typeof CITY_SLUGS)[number];

const CITY_META: Record<CitySlug, { address_markers: string[] }> = {
  tokyo: {
    address_markers: ["東京", "新宿区", "港区", "渋谷区", "千代田区", "文京区", "台東区", "台北駐日"],
  },
  osaka: {
    address_markers: ["大阪", "梅田", "難波", "なんば", "心斎橋", "天王寺"],
  },
  kyoto: {
    address_markers: ["京都"],
  },
  fukuoka: {
    address_markers: ["福岡", "博多", "天神"],
  },
  sapporo: {
    address_markers: ["札幌", "北海道"],
  },
  nagoya: {
    address_markers: ["名古屋", "愛知", "中部"],
  },
};



// ── Metadata ─────────────────────────────────────────────────────────────────

interface PageProps {
  params: Promise<{ locale: Locale; city: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale, city } = await params;
  if (!CITY_META[city as CitySlug]) return {};
  const tCities = await getTranslations("cities");
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";
  const label = tCities(city as any);
  const desc = tCities(`${city}_desc` as any);
  const headingSuffix = tCities("headingSuffix");
  const LOCALES: Locale[] = ["zh", "en", "ja"];
  return {
    title: `${label}${headingSuffix}`,
    description: (desc as string).slice(0, 160),
    alternates: {
      canonical: `${base}/${locale}/cities/${city}`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/cities/${city}`])),
        "x-default": `${base}/zh/cities/${city}`,
      },
    },
    openGraph: {
      title: `${label}${headingSuffix}`,
      description: (desc as string).slice(0, 160),
      url: `${base}/${locale}/cities/${city}`,
      type: "website",
    },
  };
}

export function generateStaticParams() {
  const LOCALES: Locale[] = ["zh", "en", "ja"];
  return LOCALES.flatMap((locale) =>
    CITY_SLUGS.map((city) => ({ locale, city }))
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default async function CityPage({ params }: PageProps) {
  const { locale, city } = await params;
  const meta = CITY_META[city as CitySlug];
  if (!meta) notFound();

  const t = await getTranslations("categories");
  const tCities = await getTranslations("cities");

  const supabase = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const today = new Date().toISOString().slice(0, 10);
  let query = supabase
    .from("events")
    .select("*")
    .eq("is_active", true)
    .eq("annotation_status", "annotated")
    .is("parent_event_id", null)
    .or(`end_date.gte.${today},end_date.is.null`)
    .order("start_date", { ascending: true })
    .limit(100);

  // Filter by city address markers
  const conds = meta.address_markers
    .map((m) => `location_address.ilike.%${m}%`)
    .join(",");
  query = query.or(conds);

  const { data: events } = await query;
  const rows = (events ?? []) as Event[];

  const label = tCities(city as any);
  const description = tCities(`${city}_desc` as any);
  const headingSuffix = tCities("headingSuffix");
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";

  const collectionLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${label}${headingSuffix}`,
    description,
    url: `${base}/${locale}/cities/${city}`,
    mainEntity: {
      "@type": "ItemList",
      itemListElement: rows.slice(0, 50).map((e, i) => ({
        "@type": "ListItem",
        position: i + 1,
        url: `${base}/${locale}/events/${e.id}`,
        name: getEventName(e, locale) ?? e.name_ja ?? undefined,
      })),
    },
  };

  return (
    <main className="max-w-4xl mx-auto px-4 py-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionLd) }}
      />

      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500 mb-4">
        <Link href={`/${locale}`} className="hover:underline">
          Tokyo Taiwan Radar
        </Link>
        {" › "}
        <span>{label as string}</span>
      </nav>

      {/* Heading + intro */}
      <h1 className="text-2xl font-bold mb-3">
        {label as string}{headingSuffix}
      </h1>
      <p className="text-sm text-gray-600 mb-6 leading-relaxed">{description as string}</p>

      {/* Event grid */}
      {rows.length === 0 ? (
        <p className="text-gray-500 text-sm">{tCities("noEvents")}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((e) => (
            <EventCard key={e.id} event={e} locale={locale} />
          ))}
        </div>
      )}

      {/* City nav */}
      <nav className="mt-10 flex flex-wrap gap-2 text-sm">
        {CITY_SLUGS.filter((s) => s !== city).map((s) => (
          <Link
            key={s}
            href={`/${locale}/cities/${s}`}
            className="px-3 py-1 rounded-full border text-gray-600 hover:border-green-600 hover:text-green-700 transition"
          >
            {tCities(s as any) as string}
          </Link>
        ))}
      </nav>
    </main>
  );
}

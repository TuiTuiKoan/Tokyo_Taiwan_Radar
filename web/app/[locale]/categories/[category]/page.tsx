import type { Metadata } from "next";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { type Locale, type Event, CATEGORIES, type Category, getEventName } from "@/lib/types";
import EventCard from "@/components/EventCard";
import Link from "next/link";

// ── Types & helpers ───────────────────────────────────────────────────────────

// ── Types & helpers ───────────────────────────────────────────────────────────

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

  const supabase = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const today = new Date().toISOString().slice(0, 10);
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

  const rows = (events ?? []) as Event[];

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

  const collectionLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: categoryLabel,
    description,
    url: `${base}/${locale}/categories/${category}`,
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

  // Featured categories for cross-navigation (exclude current)
  const FEATURED: Category[] = [
    "movie", "performing_arts", "senses", "art", "lecture",
    "taiwan_japan", "lifestyle_food", "books_media",
  ];

  return (
    <main className="max-w-4xl mx-auto px-4 py-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionLd) }}
      />

      {/* Breadcrumb */}
      <nav className="text-sm text-fg-muted mb-4">
        <Link href={`/${locale}`} className="hover:underline">
          Tokyo Taiwan Radar
        </Link>
        {" › "}
        <span>{categoryLabel}</span>
      </nav>

      {/* Heading + intro */}
      <h1 className="text-2xl font-bold mb-3">{categoryLabel}</h1>
      {descriptionLong && (
        <section className="mb-6 space-y-3 text-sm leading-relaxed text-fg-muted">
          <p>{descriptionLong}</p>
        </section>
      )}

      {/* Event grid */}
      {rows.length === 0 ? (
        <p className="text-fg-muted text-sm">{tCatDesc("noEvents")}</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {rows.map((e) => (
            <EventCard key={e.id} event={e} locale={locale} />
          ))}
        </div>
      )}

      {/* Category nav */}
      <nav className="mt-10 flex flex-wrap gap-2 text-sm">
        {FEATURED.filter((c) => c !== category).map((c) => (
          <Link
            key={c}
            href={`/${locale}/categories/${c}`}
            className="px-3 py-1 rounded-full border text-fg-muted hover:border-green-600 hover:text-green-700 transition"
          >
            {t(c)}
          </Link>
        ))}
      </nav>
    </main>
  );
}

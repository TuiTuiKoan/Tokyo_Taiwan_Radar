import type { MetadataRoute } from "next";
import { createClient } from "@supabase/supabase-js";
import { isPureReportEvent } from "@/lib/types";

const LOCALES = ["zh", "en", "ja"] as const;
const BASE =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyotaiwanradar.com";

const CITY_SLUGS = ["tokyo", "osaka", "kyoto", "fukuoka", "sapporo", "nagoya"] as const;
const FEATURED_CATEGORIES = [
  "movie", "performing_arts", "senses", "art", "lecture",
  "taiwan_japan", "lifestyle_food", "books_media",
] as const;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Use a plain Supabase client (no cookies) — sitemap reads only public data.
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  // Static locale home pages
  const staticPages: MetadataRoute.Sitemap = LOCALES.map((locale) => ({
    url: `${BASE}/${locale}`,
    changeFrequency: "daily",
    priority: 1.0,
    alternates: {
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${BASE}/${l}`])),
        "x-default": `${BASE}/ja`,
      },
    },
  }));

  // Active top-level event pages
  const { data: events } = await supabase
    .from("events")
    .select("id, updated_at, category, event_form")
    .eq("is_active", true)
    .in("annotation_status", ["annotated", "reviewed"])
    .is("parent_event_id", null);

  const indexableEvents = (events ?? []).filter(
    (e) => !isPureReportEvent(e.category, e.event_form)
  );

  const eventPages: MetadataRoute.Sitemap = indexableEvents.flatMap((e) =>
    LOCALES.map((locale) => ({
      url: `${BASE}/${locale}/events/${e.id}`,
      lastModified: new Date(e.updated_at),
      changeFrequency: "weekly" as const,
      priority: 0.8,
      alternates: {
        languages: {
          ...Object.fromEntries(
            LOCALES.map((l) => [l, `${BASE}/${l}/events/${e.id}`])
          ),
          "x-default": `${BASE}/ja/events/${e.id}`,
        },
      },
    }))
  );

  // ── City aggregation pages ───────────────────────────────────────────────
  const cityPages: MetadataRoute.Sitemap = CITY_SLUGS.flatMap((city) =>
    LOCALES.map((locale) => ({
      url: `${BASE}/${locale}/cities/${city}`,
      changeFrequency: "daily" as const,
      priority: 0.7,
      alternates: {
        languages: {
          ...Object.fromEntries(LOCALES.map((l) => [l, `${BASE}/${l}/cities/${city}`])),
          "x-default": `${BASE}/ja/cities/${city}`,
        },
      },
    }))
  );

  // ── Category aggregation pages ───────────────────────────────────────────
  const categoryPages: MetadataRoute.Sitemap = FEATURED_CATEGORIES.flatMap((cat) =>
    LOCALES.map((locale) => ({
      url: `${BASE}/${locale}/categories/${cat}`,
      changeFrequency: "daily" as const,
      priority: 0.7,
      alternates: {
        languages: {
          ...Object.fromEntries(LOCALES.map((l) => [l, `${BASE}/${l}/categories/${cat}`])),
          "x-default": `${BASE}/ja/categories/${cat}`,
        },
      },
    }))
  );

  // ── Static info pages: /about, /sources ─────────────────────────────────
  const INFO_SLUGS = ["about", "sources"] as const;
  const infoPages: MetadataRoute.Sitemap = INFO_SLUGS.flatMap((slug) =>
    LOCALES.map((locale) => ({
      url: `${BASE}/${locale}/${slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
      alternates: {
        languages: {
          ...Object.fromEntries(LOCALES.map((l) => [l, `${BASE}/${l}/${slug}`])),
          "x-default": `${BASE}/ja/${slug}`,
        },
      },
    }))
  );

  return [...staticPages, ...eventPages, ...cityPages, ...categoryPages, ...infoPages];
}

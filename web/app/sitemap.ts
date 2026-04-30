import type { MetadataRoute } from "next";
import { createClient } from "@supabase/supabase-js";

const LOCALES = ["zh", "en", "ja"] as const;
const BASE =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://tokyo-taiwan-radar.vercel.app";

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
      languages: Object.fromEntries(LOCALES.map((l) => [l, `${BASE}/${l}`])),
    },
  }));

  // Active top-level event pages
  const { data: events } = await supabase
    .from("events")
    .select("id, updated_at")
    .eq("is_active", true)
    .is("parent_event_id", null);

  const eventPages: MetadataRoute.Sitemap = (events ?? []).flatMap((e) =>
    LOCALES.map((locale) => ({
      url: `${BASE}/${locale}/events/${e.id}`,
      lastModified: new Date(e.updated_at),
      changeFrequency: "weekly" as const,
      priority: 0.8,
      alternates: {
        languages: Object.fromEntries(
          LOCALES.map((l) => [l, `${BASE}/${l}/events/${e.id}`])
        ),
      },
    }))
  );

  return [...staticPages, ...eventPages];
}

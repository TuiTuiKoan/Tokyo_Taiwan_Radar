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

const CITY_META: Record<
  CitySlug,
  {
    address_markers: string[];
    labels: Record<Locale, string>;
    descriptions: Record<Locale, string>;
  }
> = {
  tokyo: {
    address_markers: ["東京", "新宿区", "港区", "渋谷区", "千代田区", "文京区", "台東区", "台北駐日"],
    labels: { zh: "東京", ja: "東京", en: "Tokyo" },
    descriptions: {
      zh: "東京是日本最多台灣相關文化活動的城市。電影、展覽、音樂演出、講座與台日交流活動在此密集舉辦。本頁彙整目前在東京進行中或即將開始的所有台灣相關活動，每日更新。",
      ja: "東京は日本で最も多くの台湾関連文化イベントが開催される都市です。映画、展示、音楽公演、講演、台日交流イベントなど多彩なプログラムが日々開催されています。このページでは東京で現在開催中または近日開催予定の台湾関連イベントを毎日更新してお届けします。",
      en: "Tokyo hosts the most Taiwan-related cultural events in Japan — films, exhibitions, concerts, lectures, and Japan-Taiwan exchange events. This page aggregates all ongoing and upcoming Taiwan events in Tokyo, updated daily.",
    },
  },
  osaka: {
    address_markers: ["大阪", "梅田", "難波", "なんば", "心斎橋", "天王寺"],
    labels: { zh: "大阪", ja: "大阪", en: "Osaka" },
    descriptions: {
      zh: "大阪是關西地區台灣文化活動的重要據點。美食、藝術展覽與台灣特色活動在此蓬勃發展。本頁彙整目前在大阪進行中或即將舉辦的台灣相關活動。",
      ja: "大阪は関西における台湾文化イベントの重要な拠点です。グルメ、アート展示、台湾フェアなど多彩なイベントが活発に開催されています。このページでは大阪で現在開催中または近日開催予定の台湾関連イベントをまとめています。",
      en: "Osaka is a key hub for Taiwan-related cultural events in the Kansai region — food, art exhibitions, and Taiwan-themed events thrive here. This page aggregates ongoing and upcoming Taiwan events in Osaka.",
    },
  },
  kyoto: {
    address_markers: ["京都"],
    labels: { zh: "京都", ja: "京都", en: "Kyoto" },
    descriptions: {
      zh: "京都的台灣相關活動以學術、藝術與文化交流為主，融合古都氛圍與台灣現代文化。本頁彙整目前在京都進行中或即將舉辦的台灣相關活動。",
      ja: "京都の台湾関連イベントは、学術・芸術・文化交流を中心に、古都の雰囲気と台湾の現代文化が融合したプログラムが特徴です。このページでは京都で開催中または近日予定の台湾関連イベントをまとめています。",
      en: "Kyoto's Taiwan-related events focus on academic, artistic, and cultural exchange, blending the ancient city's atmosphere with contemporary Taiwanese culture. This page aggregates Taiwan events in Kyoto.",
    },
  },
  fukuoka: {
    address_markers: ["福岡", "博多", "天神"],
    labels: { zh: "福岡", ja: "福岡", en: "Fukuoka" },
    descriptions: {
      zh: "福岡是離台灣最近的日本大城市，台日交流活動特別活躍。本頁彙整目前在福岡進行中或即將舉辦的台灣相關活動。",
      ja: "福岡は日本の大都市の中で台湾に最も近い都市であり、台日交流イベントが特に盛んです。このページでは福岡で開催中または近日予定の台湾関連イベントをまとめています。",
      en: "Fukuoka is the Japanese city closest to Taiwan, making it especially active for Japan-Taiwan exchange events. This page aggregates ongoing and upcoming Taiwan events in Fukuoka.",
    },
  },
  sapporo: {
    address_markers: ["札幌", "北海道"],
    labels: { zh: "札幌・北海道", ja: "札幌・北海道", en: "Sapporo / Hokkaido" },
    descriptions: {
      zh: "札幌及北海道地區的台灣相關活動以觀光、飲食文化與自然主題為主。本頁彙整目前在札幌・北海道進行中或即將舉辦的台灣相關活動。",
      ja: "札幌・北海道の台湾関連イベントは、観光・食文化・自然テーマが中心です。このページでは札幌・北海道で開催中または近日予定の台湾関連イベントをまとめています。",
      en: "Sapporo and Hokkaido's Taiwan-related events focus on tourism, food culture, and nature themes. This page aggregates ongoing and upcoming Taiwan events in Sapporo and Hokkaido.",
    },
  },
  nagoya: {
    address_markers: ["名古屋", "愛知", "中部"],
    labels: { zh: "名古屋・愛知", ja: "名古屋・愛知", en: "Nagoya / Aichi" },
    descriptions: {
      zh: "名古屋及愛知地區的台灣相關活動涵蓋飲食、工業文化與台日交流。本頁彙整目前在名古屋・愛知進行中或即將舉辦的台灣相關活動。",
      ja: "名古屋・愛知の台湾関連イベントは、グルメ・産業文化・台日交流など幅広いジャンルが揃っています。このページでは名古屋・愛知で開催中または近日予定の台湾関連イベントをまとめています。",
      en: "Nagoya and Aichi's Taiwan-related events cover food, industrial culture, and Japan-Taiwan exchange. This page aggregates ongoing and upcoming Taiwan events in the Nagoya area.",
    },
  },
};

const SITE_NAMES: Record<Locale, string> = {
  zh: "Tokyo Taiwan Radar 東京台灣雷達",
  en: "Tokyo Taiwan Radar",
  ja: "Tokyo Taiwan Radar 東京台湾レーダー",
};

// ── Metadata ─────────────────────────────────────────────────────────────────

interface PageProps {
  params: Promise<{ locale: Locale; city: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale, city } = await params;
  const meta = CITY_META[city as CitySlug];
  if (!meta) return {};
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  const label = meta.labels[locale] ?? meta.labels.zh;
  const desc = meta.descriptions[locale] ?? meta.descriptions.zh;
  const siteName = SITE_NAMES[locale] ?? SITE_NAMES.zh;
  const LOCALES: Locale[] = ["zh", "en", "ja"];
  return {
    title: `${label}の台湾イベント | ${siteName}`,
    description: desc.slice(0, 160),
    alternates: {
      canonical: `${base}/${locale}/cities/${city}`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/cities/${city}`])),
        "x-default": `${base}/zh/cities/${city}`,
      },
    },
    openGraph: {
      title: `${label}の台湾イベント | ${siteName}`,
      description: desc.slice(0, 160),
      url: `${base}/${locale}/cities/${city}`,
      siteName,
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
  const tEvent = await getTranslations("event");

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

  const label = meta.labels[locale] ?? meta.labels.zh;
  const description = meta.descriptions[locale] ?? meta.descriptions.zh;
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  const siteName = SITE_NAMES[locale] ?? SITE_NAMES.zh;

  const collectionLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${label} 台灣活動 | ${siteName}`,
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
          {siteName}
        </Link>
        {" › "}
        <span>{label}</span>
      </nav>

      {/* Heading + intro */}
      <h1 className="text-2xl font-bold mb-3">
        {label}{" "}
        {locale === "ja" ? "の台湾イベント" : locale === "en" ? "Taiwan Events" : "台灣活動"}
      </h1>
      <p className="text-sm text-gray-600 mb-6 leading-relaxed">{description}</p>

      {/* Event grid */}
      {rows.length === 0 ? (
        <p className="text-gray-500 text-sm">
          {locale === "ja"
            ? "現在開催中のイベントはありません。"
            : locale === "en"
            ? "No ongoing events at the moment."
            : "目前沒有進行中的活動。"}
        </p>
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
            {CITY_META[s].labels[locale]}
          </Link>
        ))}
      </nav>
    </main>
  );
}

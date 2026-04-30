import type { Metadata } from "next";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { type Locale, type Event, CATEGORIES, type Category, getEventName } from "@/lib/types";
import EventCard from "@/components/EventCard";
import Link from "next/link";

export const revalidate = 3600;

// ── Category intro descriptions ───────────────────────────────────────────────

const CATEGORY_DESCRIPTIONS: Partial<Record<Category, Record<Locale, string>>> = {
  movie: {
    zh: "彙整日本全國上映或放映中的台灣電影，包含院線電影、特映會與電影節。每部電影均附官方資訊與日期，每日更新。",
    ja: "日本全国で上映中の台湾映画を集めたページです。劇場公開作品、特別上映会、映画祭作品などを網羅し、公式情報・日程を毎日更新しています。",
    en: "Aggregating Taiwan films screening across Japan — theatrical releases, special screenings, and film festivals. Official info and dates updated daily.",
  },
  performing_arts: {
    zh: "收錄日本各地的台灣音樂演出、舞蹈、戲劇與表演藝術活動，從小型場館到大型音樂廳均有涵蓋。",
    ja: "日本各地で開催される台湾の音楽公演、ダンス、演劇など舞台芸術イベントを収録。小規模会場から大型ホールまで幅広く掲載しています。",
    en: "Taiwan music concerts, dance, theater, and performing arts events across Japan — from intimate venues to major concert halls.",
  },
  senses: {
    zh: "透過飲食、香氣、觸感等感官體驗認識台灣的活動，包含台灣美食節、市集與五感體驗活動。",
    ja: "食・香り・触感など感覚を通じて台湾を知るイベント。台湾グルメフェア、マーケット、五感体験イベントなどを掲載しています。",
    en: "Events to experience Taiwan through the senses — Taiwanese food festivals, markets, and multisensory experiences.",
  },
  art: {
    zh: "收錄日本各地展出的台灣藝術展覽、視覺藝術與當代藝術活動，從畫廊小展到大型美術館均有涵蓋。",
    ja: "日本各地で開催される台湾アートの展覧会、ビジュアルアート、現代美術イベントを収録。ギャラリーから大型美術館まで幅広く掲載。",
    en: "Taiwan art exhibitions, visual arts, and contemporary art events across Japan — from gallery shows to major museum exhibitions.",
  },
  lecture: {
    zh: "收錄以台灣為主題的日本各地講座、研討會與知識型活動，涵蓋歷史、文化、社會、語言等多元主題。",
    ja: "台湾をテーマにした講演会、シンポジウム、知識系イベントを収録。歴史・文化・社会・言語など多様なテーマを網羅しています。",
    en: "Lectures, symposia, and knowledge events about Taiwan across Japan — history, culture, society, language, and more.",
  },
  taiwan_japan: {
    zh: "專注台日交流的活動，包含文化互訪、姐妹城市活動、台日商務交流及民間友好活動。",
    ja: "台日交流に特化したイベント。文化交流、姉妹都市イベント、台日ビジネス交流、民間友好活動などを掲載しています。",
    en: "Events focused on Japan-Taiwan exchange — cultural visits, sister city events, business networking, and people-to-people friendship activities.",
  },
  lifestyle_food: {
    zh: "以台灣飲食文化與生活風格為主題的活動，包含台灣料理教室、食材市集、生活風格工作坊。",
    ja: "台湾の食文化・ライフスタイルをテーマにしたイベント。台湾料理教室、食材マーケット、ライフスタイルワークショップなどを掲載。",
    en: "Events celebrating Taiwanese food culture and lifestyle — cooking classes, food markets, and lifestyle workshops.",
  },
  books_media: {
    zh: "台灣書籍、文學、出版、媒體相關的活動，包含讀書會、作者講座、台灣文學展覽。",
    ja: "台湾の書籍・文学・出版・メディア関連イベント。読書会、著者講演、台湾文学展示などを掲載しています。",
    en: "Events related to Taiwanese books, literature, publishing, and media — book clubs, author talks, and literary exhibitions.",
  },
};

const SITE_NAMES: Record<Locale, string> = {
  zh: "Tokyo Taiwan Radar 東京台灣雷達",
  en: "Tokyo Taiwan Radar",
  ja: "Tokyo Taiwan Radar 東京台湾レーダー",
};

// ── Types & helpers ───────────────────────────────────────────────────────────

interface PageProps {
  params: Promise<{ locale: Locale; category: string }>;
}

// ── Metadata ─────────────────────────────────────────────────────────────────

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale, category } = await params;
  if (!CATEGORIES.includes(category as Category)) return {};
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  const siteName = SITE_NAMES[locale] ?? SITE_NAMES.zh;
  const desc = CATEGORY_DESCRIPTIONS[category as Category]?.[locale];
  const LOCALES: Locale[] = ["zh", "en", "ja"];
  return {
    title: `${category} | ${siteName}`,
    description: desc?.slice(0, 160),
    alternates: {
      canonical: `${base}/${locale}/categories/${category}`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/categories/${category}`])),
        "x-default": `${base}/zh/categories/${category}`,
      },
    },
    openGraph: {
      title: `${category} | ${siteName}`,
      description: desc?.slice(0, 160),
      url: `${base}/${locale}/categories/${category}`,
      siteName,
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

  const categoryLabel = t(category as any);
  const description = CATEGORY_DESCRIPTIONS[category as Category]?.[locale];
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  const siteName = SITE_NAMES[locale] ?? SITE_NAMES.zh;

  const collectionLd = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: `${categoryLabel} | ${siteName}`,
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
      <nav className="text-sm text-gray-500 mb-4">
        <Link href={`/${locale}`} className="hover:underline">
          {siteName}
        </Link>
        {" › "}
        <span>{categoryLabel}</span>
      </nav>

      {/* Heading + intro */}
      <h1 className="text-2xl font-bold mb-3">{categoryLabel}</h1>
      {description && (
        <p className="text-sm text-gray-600 mb-6 leading-relaxed">{description}</p>
      )}

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

      {/* Category nav */}
      <nav className="mt-10 flex flex-wrap gap-2 text-sm">
        {FEATURED.filter((c) => c !== category).map((c) => (
          <Link
            key={c}
            href={`/${locale}/categories/${c}`}
            className="px-3 py-1 rounded-full border text-gray-600 hover:border-green-600 hover:text-green-700 transition"
          >
            {t(c)}
          </Link>
        ))}
      </nav>
    </main>
  );
}

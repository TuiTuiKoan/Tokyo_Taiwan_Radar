import { createClient } from "@/lib/supabase/server";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, CATEGORIES, getEventName } from "@/lib/types";
import FilterBar from "@/components/FilterBar";
import Link from "next/link";
import AnnouncementCard from "@/components/AnnouncementCard";
import { getCityLabel } from "@/lib/cityLabel";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
  searchParams: Promise<{
    q?: string;
    category?: string;
    from?: string;
    to?: string;
    paid?: string;
    timeMode?: string; // "active" | "all" | "past" (search date range)
    location?: string; // "tokyo" | "other_japan" | "taiwan" | "online"
  }>;
}

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

export default async function HomePage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  const sp = await searchParams;
  const t = await getTranslations("filters");
  const tGeneral = await getTranslations("general");
  const tEvent = await getTranslations("event");
  const tCat = await getTranslations("categories");
  const tAnn = await getTranslations("announcements");

  const supabase = await createClient();

  const timeMode = sp.timeMode ?? "active";

  // -- Build query --
  let query = supabase
    .from("events")
    .select("*")
    .eq("is_active", true)
    .order("start_date", { ascending: true });

  // Keyword search (ILIKE across all language name fields)
  if (sp.q) {
    const q = `%${sp.q}%`;
    query = query.or(
      `name_ja.ilike.${q},name_zh.ilike.${q},name_en.ilike.${q},description_ja.ilike.${q},description_zh.ilike.${q},description_en.ilike.${q}`
    );
  }

  // Category filter — supports comma-separated multi-select, e.g. "movie,art"
  if (sp.category) {
    const cats = sp.category
      .split(",")
      .map((c) => c.trim())
      .filter((c) => CATEGORIES.includes(c as any));
    if (cats.length === 1) {
      query = query.contains("category", cats);
    } else if (cats.length > 1) {
      query = query.overlaps("category", cats);
    }
  }

  // Time mode filter
  if (timeMode === "active") {
    // Show only ongoing events: end_date >= today or end_date is null
    const today = todayStr();
    query = query.or(`end_date.gte.${today},end_date.is.null`);
  } else if (timeMode === "past") {
    // Search date range (no past restriction — from/to filters only)
    if (sp.from) {
      query = query.gte("start_date", sp.from);
    }
    if (sp.to) {
      query = query.lte("start_date", sp.to);
    }
  }

  // Paid filter
  if (sp.paid === "free") {
    query = query.eq("is_paid", false);
  } else if (sp.paid === "paid") {
    query = query.eq("is_paid", true);
  }

  // Location filter
  // Tokyo markers used for classification
  // Note: 台北駐日 = Taipei Representative Office in Japan → physically in Tokyo
  const TOKYO_MARKERS = ["東京", "新宿区", "港区", "渋谷区", "千代田区", "文京区", "台東区", "台北駐日"];
  const KANTO_MARKERS = ["神奈川", "埼玉", "千葉", "茨城", "栃木", "群馬", "山梨", "青森", "岩手", "宮城", "秋田", "山形", "福島", "北海道"];
  // NOTE: "京都" is a substring of "東京都" — always use "京都府"/"京都市" to avoid false positives
  const CHUBU_KINKI_MARKERS = ["愛知", "静岡", "岐阜", "長野", "新潟", "富山", "石川", "福井", "大阪", "京都府", "京都市", "兵庫", "奈良", "滋賀", "和歌山", "三重"];
  const CHUGOKU_KYUSHU_MARKERS = ["広島", "岡山", "鳥取", "島根", "山口", "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄", "高知", "愛媛", "徳島", "香川"];
  if (sp.location === "tokyo") {
    // NULL/empty OR contains a Tokyo marker OR location_prefectures includes '東京'
    const conds = [
      "location_address.is.null",
      "location_address.eq.",
      ...TOKYO_MARKERS.map((m) => `location_address.ilike.%${m}%`),
      'location_prefectures.cs.{"東京"}',
    ].join(",");
    query = query.or(conds);
  } else if (sp.location === "kanto") {
    const addrConds = KANTO_MARKERS.map((m) => `location_address.ilike.%${m}%`);
    // Include multi-city parents whose sub-events span Kanto prefectures
    const kantoPrefectures = ["神奈川", "埼玉", "千葉", "茨城", "栃木", "群馬", "山梨",
                              "青森", "岩手", "宮城", "秋田", "山形", "福島", "北海道"];
    const lpConds = kantoPrefectures.map((p) => `location_prefectures.cs.{"${p}"}`);
    query = query.or([...addrConds, ...lpConds].join(","));
  } else if (sp.location === "chubu") {
    const addrConds = CHUBU_KINKI_MARKERS.map((m) => `location_address.ilike.%${m}%`);
    const chubuPrefectures = ["愛知", "静岡", "岐阜", "長野", "新潟", "富山", "石川", "福井",
                              "大阪", "京都", "兵庫", "奈良", "滋賀", "和歌山", "三重"];
    const lpConds = chubuPrefectures.map((p) => `location_prefectures.cs.{"${p}"}`);
    query = query.or([...addrConds, ...lpConds].join(","));
  } else if (sp.location === "chugoku") {
    const addrConds = CHUGOKU_KYUSHU_MARKERS.map((m) => `location_address.ilike.%${m}%`);
    const chugokuPrefectures = ["広島", "岡山", "鳥取", "島根", "山口",
                                "福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄",
                                "高知", "愛媛", "徳島", "香川"];
    const lpConds = chugokuPrefectures.map((p) => `location_prefectures.cs.{"${p}"}`);
    query = query.or([...addrConds, ...lpConds].join(","));
  } else if (sp.location === "online") {
    // Online events: location_name = 'オンライン', location_address = null
    query = query.ilike("location_name", "%オンライン%");
  } else if (sp.location === "overseas") {
    // Overseas (Taiwan cities): location_address contains Taiwan city names
    const TAIWAN_MARKERS = ["台北", "台中", "高雄", "台南", "新竹", "嘉義", "花蓮", "台東", "基隆", "宜蘭", "桃園", "屏東", "南投", "彰化", "雲林", "澎湖"];
    const conds = TAIWAN_MARKERS.map((m) => `location_address.ilike.%${m}%`).join(",");
    query = query.or(conds);
  }

  const { data: events, error } = await query;

  if (error) {
    console.error("Error fetching events:", error);
  }

  // Build parent event name map for child events
  const parentIds = [...new Set(
    (events ?? []).map((e: Event) => e.parent_event_id).filter(Boolean)
  )] as string[];
  let parentMap: Record<string, Event> = {};
  if (parentIds.length > 0) {
    const { data: parents } = await supabase
      .from("events")
      .select("*")
      .in("id", parentIds);
    if (parents) {
      for (const p of parents) {
        parentMap[p.id] = p as Event;
      }
    }
  }

  // Fetch latest 3 featured/published announcements for homepage preview
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

  // ItemList JSON-LD — only on unfiltered active view (first 20 events)
  const isUnfiltered = !sp.q && !sp.category && !sp.from && !sp.to && !sp.paid && !sp.location && timeMode === "active";
  const itemListLd = isUnfiltered && events && events.length > 0
    ? {
        "@context": "https://schema.org",
        "@type": "ItemList",
        url: `${base}/${locale}`,
        itemListElement: (events as Event[]).slice(0, 20).map((e, i) => ({
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
      <div className="flex gap-1 border-b border-gray-200 mb-0">
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {tAnn("tabEvents")}
        </span>
        <Link
          href={`/${locale}/announcements`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {tAnn("tabNews")}
        </Link>
      </div>

      {/* Featured announcements strip */}
      {featuredAnnouncements && featuredAnnouncements.length > 0 && (
        <div className="mt-4 mb-2">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-amber-700">{tAnn("featuredStrip")}</p>
            <Link href={`/${locale}/announcements`} className="text-xs text-gray-400 hover:text-green-700">
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

      <FilterBar locale={locale} currentFilters={sp} />

      {!events || events.length === 0 ? (
        <p className="text-center text-gray-500 mt-16 text-lg">
          {tGeneral("noResults")}
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-gray-100 mt-4 border border-gray-100 rounded-xl overflow-hidden bg-white">
          {events.map((event: Event) => {
            const name = getEventName(event, locale);
            const ended = event.end_date && new Date(event.end_date) < new Date();
            return (
              <Link
                key={event.id}
                href={`/${locale}/events/${event.id}`}
                className="flex items-start gap-4 px-4 py-3 hover:bg-green-50 transition group"
              >
                {/* Date column */}
                <div className="w-16 flex-shrink-0 text-center pt-0.5">
                  {event.start_date ? (
                    <>
                      <div className="text-xs text-gray-400">
                        {new Date(event.start_date).toLocaleDateString(locale, { month: "short" })}
                      </div>
                      <div className="text-2xl font-bold text-gray-700 leading-none">
                        {new Date(event.start_date).getDate()}
                      </div>
                      {event.end_date && event.end_date.slice(0, 10) !== event.start_date.slice(0, 10) && (
                        <div className="text-[10px] text-gray-800 mt-0.5 leading-tight">
                          ~{new Date(event.end_date).toLocaleDateString(locale, { month: "numeric", day: "numeric" })}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-xs text-gray-300">—</div>
                  )}
                </div>

                {/* Main content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                    {ended ? (
                      <span className="text-xs bg-gray-100 text-gray-400 px-2 py-0.5 rounded-full">
                        {tEvent("ended")}
                      </span>
                    ) : (
                      <span className="text-xs text-green-600 font-medium">●</span>
                    )}
                    {event.is_paid === false && (
                      <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
                        {tEvent("free")}
                      </span>
                    )}
                    {event.category?.slice(0, 2).map((cat) => (
                      <span key={cat} className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">
                        {tCat(cat as any)}
                      </span>
                    ))}
                  </div>
                  <p className="text-sm font-medium text-gray-900 group-hover:text-green-700 line-clamp-2 leading-snug">
                    {event.parent_event_id && parentMap[event.parent_event_id] && (
                      <span className="block text-xs text-green-600 font-normal mb-0.5 truncate">
                        ↳ {getEventName(parentMap[event.parent_event_id], locale)}
                      </span>
                    )}
                    {name}
                  </p>
                  {event.location_name && (() => {
                    const cityLabel = getCityLabel(
                      (event as any).location_prefectures as string[] | null | undefined,
                      (event as any).location_address as string | null,
                    );
                    return (
                      <p className="text-xs text-gray-400 mt-0.5">
                        📍{" "}
                        {cityLabel && (
                          <span className="inline-block bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded mr-1 font-medium">
                            {cityLabel}
                          </span>
                        )}
                        {event.location_name}
                      </p>
                    );
                  })()}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}


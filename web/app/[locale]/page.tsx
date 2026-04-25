import { createClient } from "@/lib/supabase/server";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, CATEGORIES, getEventName } from "@/lib/types";
import FilterBar from "@/components/FilterBar";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale }>;
  searchParams: Promise<{
    q?: string;
    category?: string;
    from?: string;
    to?: string;
    paid?: string;
    timeMode?: string; // "active" | "past"
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
    // Show only ongoing/upcoming events:
    // - end_date >= today (still running), OR
    // - end_date IS NULL AND start_date >= today (single-day / open-ended, not yet passed)
    const today = todayStr();
    query = query.or(`end_date.gte.${today},and(end_date.is.null,start_date.gte.${today})`);
  } else if (timeMode === "past") {
    // Search past period with optional date range
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
  const TAIWAN_MARKERS = ["台北", "台中", "台南", "高雄", "台湾", "台灣"];
  // Venues that contain Taiwan keywords but are physically in Japan (exclude from Taiwan filter)
  const JAPAN_DESPITE_TAIWAN_NAME = ["台北駐日", "台湾文化センター", "台北経済文化"];
  if (sp.location === "tokyo") {
    // NULL/empty OR contains a Tokyo marker
    const conds = [
      "location_address.is.null",
      "location_address.eq.",
      ...TOKYO_MARKERS.map((m) => `location_address.ilike.%${m}%`),
    ].join(",");
    query = query.or(conds);
  } else if (sp.location === "taiwan") {
    const conds = TAIWAN_MARKERS.map((m) => `location_address.ilike.%${m}%`).join(",");
    query = query.or(conds);
    // Exclude known Tokyo venues whose names contain Taiwan keywords
    for (const ex of JAPAN_DESPITE_TAIWAN_NAME) {
      query = query.not("location_address", "ilike", `%${ex}%`);
    }
  } else if (sp.location === "other_japan") {
    // Must have a non-empty address that is neither Tokyo nor Taiwan nor Online
    query = query.not("location_address", "is", null).neq("location_address", "");
    for (const m of [...TOKYO_MARKERS, ...TAIWAN_MARKERS]) {
      query = query.not("location_address", "ilike", `%${m}%`);
    }
    // Exclude online events — canonical marker is on location_name
    query = query.not("location_name", "ilike", "%オンライン%");
  } else if (sp.location === "online") {
    // Online events: location_name = 'オンライン', location_address = null
    query = query.ilike("location_name", "%オンライン%");
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

  return (
    <div>
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
                  {event.location_name && (
                    <p className="text-xs text-gray-400 mt-0.5">📍 {event.location_name}</p>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}


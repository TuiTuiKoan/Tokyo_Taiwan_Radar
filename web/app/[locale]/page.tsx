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
    paid?: string;   // "free" | "paid" | ""
    status?: string; // "active" | "ended" | ""
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

  // Default from-date to today if not set
  const fromDate = sp.from ?? todayStr();

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

  // Category filter
  if (sp.category && CATEGORIES.includes(sp.category as any)) {
    query = query.contains("category", [sp.category]);
  }

  // Date filters — use end_date (or start_date when end_date is null) to
  // correctly include ongoing multi-day events and exclude ended ones.
  query = query.or(
    `end_date.gte.${fromDate},and(end_date.is.null,start_date.gte.${fromDate})`
  );
  if (sp.to) {
    query = query.lte("start_date", sp.to);
  }

  // Paid filter
  if (sp.paid === "free") {
    query = query.eq("is_paid", false);
  } else if (sp.paid === "paid") {
    query = query.eq("is_paid", true);
  }

  // Status filter — "ended" means end_date is in the past
  const now = new Date().toISOString();
  if (sp.status === "active") {
    query = query.or(`end_date.gte.${now},end_date.is.null`);
  } else if (sp.status === "ended") {
    query = query.lt("end_date", now);
  }

  const { data: events, error } = await query;

  if (error) {
    console.error("Error fetching events:", error);
  }

  return (
    <div>
      <FilterBar locale={locale} currentFilters={{ ...sp, from: fromDate }} />

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


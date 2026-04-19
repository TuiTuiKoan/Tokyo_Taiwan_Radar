import { createClient } from "@/lib/supabase/server";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, CATEGORIES, getEventName } from "@/lib/types";
import EventCard from "@/components/EventCard";
import FilterBar from "@/components/FilterBar";

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

export default async function HomePage({ params, searchParams }: PageProps) {
  const { locale } = await params;
  const sp = await searchParams;
  const t = await getTranslations("filters");
  const tGeneral = await getTranslations("general");

  const supabase = await createClient();

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

  // Date filters
  if (sp.from) {
    query = query.gte("start_date", sp.from);
  }
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
      <FilterBar locale={locale} currentFilters={sp} />

      {!events || events.length === 0 ? (
        <p className="text-center text-gray-500 mt-16 text-lg">
          {tGeneral("noResults")}
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mt-6">
          {events.map((event: Event) => (
            <EventCard key={event.id} event={event} locale={locale} />
          ))}
        </div>
      )}
    </div>
  );
}

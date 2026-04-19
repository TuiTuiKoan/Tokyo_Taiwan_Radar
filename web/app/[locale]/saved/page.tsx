import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, getEventName } from "@/lib/types";
import EventCard from "@/components/EventCard";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export default async function SavedPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("saved");

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login`);
  }

  const { data: savedRows } = await supabase
    .from("saved_events")
    .select("event_id, events(*)")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const events: Event[] = (savedRows ?? []).map((row: any) => row.events);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">{t("title")}</h1>
      {events.length === 0 ? (
        <p className="text-gray-500 text-center mt-16">{t("empty")}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {events.map((event) => (
            <EventCard key={event.id} event={event} locale={locale} />
          ))}
        </div>
      )}
    </div>
  );
}

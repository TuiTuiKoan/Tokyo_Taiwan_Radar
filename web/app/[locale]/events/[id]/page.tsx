import { createClient } from "@/lib/supabase/server";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, getEventName, getEventDescription } from "@/lib/types";
import SaveButton from "@/components/SaveButton";

interface PageProps {
  params: Promise<{ locale: Locale; id: string }>;
}

export default async function EventDetailPage({ params }: PageProps) {
  const { locale, id } = await params;
  const t = await getTranslations("event");

  const supabase = await createClient();

  const { data: event } = await supabase
    .from("events")
    .select("*")
    .eq("id", id)
    .single();

  if (!event) {
    notFound();
  }

  const { data: { user } } = await supabase.auth.getUser();

  // Check if the current user has saved this event
  let isSaved = false;
  if (user) {
    const { data: saved } = await supabase
      .from("saved_events")
      .select("id")
      .eq("user_id", user.id)
      .eq("event_id", id)
      .single();
    isSaved = !!saved;
  }

  const name = getEventName(event as Event, locale);
  const description = getEventDescription(event as Event, locale);
  const now = new Date();
  const ended = event.end_date && new Date(event.end_date) < now;

  return (
    <article className="max-w-3xl mx-auto">
      <div className="flex items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{name}</h1>
          {ended && (
            <span className="mt-2 inline-block bg-gray-200 text-gray-600 text-xs px-2 py-1 rounded">
              {t("ended")}
            </span>
          )}
        </div>
        {user && (
          <SaveButton
            eventId={event.id}
            initialSaved={isSaved}
            locale={locale}
          />
        )}
      </div>

      {/* Categories */}
      {event.category?.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {event.category.map((cat: string) => (
            <span
              key={cat}
              className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full"
            >
              {cat}
            </span>
          ))}
        </div>
      )}

      {/* Details grid */}
      <div className="bg-gray-50 rounded-lg p-6 mb-6 space-y-3 text-sm">
        {event.start_date && (
          <div className="flex gap-3">
            <span className="text-gray-500 w-28 shrink-0">{t("startDate")}</span>
            <span>{new Date(event.start_date).toLocaleDateString(locale)}</span>
          </div>
        )}
        {event.end_date && (
          <div className="flex gap-3">
            <span className="text-gray-500 w-28 shrink-0">{t("endDate")}</span>
            <span>{new Date(event.end_date).toLocaleDateString(locale)}</span>
          </div>
        )}
        {event.location_name && (
          <div className="flex gap-3">
            <span className="text-gray-500 w-28 shrink-0">{t("location")}</span>
            <span>
              {event.location_name}
              {event.location_address && (
                <span className="text-gray-500 ml-2">
                  {event.location_address}
                </span>
              )}
            </span>
          </div>
        )}
        {event.business_hours && (
          <div className="flex gap-3">
            <span className="text-gray-500 w-28 shrink-0">{t("hours")}</span>
            <span>{event.business_hours}</span>
          </div>
        )}
        <div className="flex gap-3">
          <span className="text-gray-500 w-28 shrink-0">{t("paid")}</span>
          <span>
            {event.is_paid === false
              ? t("free")
              : event.is_paid === true
              ? `${t("paid")}${event.price_info ? ` — ${event.price_info}` : ""}`
              : "—"}
          </span>
        </div>
        {event.source_url && (
          <div className="flex gap-3">
            <span className="text-gray-500 w-28 shrink-0">{t("source")}</span>
            <a
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline truncate"
            >
              {t("viewOriginal")} ↗
            </a>
          </div>
        )}
      </div>

      {/* Description */}
      {description && (
        <div className="prose prose-gray max-w-none">
          <p className="whitespace-pre-wrap text-gray-700 leading-relaxed">
            {description}
          </p>
        </div>
      )}
    </article>
  );
}

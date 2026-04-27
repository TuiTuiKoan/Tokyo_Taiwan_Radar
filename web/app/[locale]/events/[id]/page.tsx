import { createClient } from "@/lib/supabase/server";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, getEventName, getEventDescription, getEventLocationName, getEventLocationAddress, getEventBusinessHours } from "@/lib/types";
import SaveButton from "@/components/SaveButton";
import RawDataSection from "@/components/RawDataSection";
import ReportSection from "@/components/ReportSection";
import ViewTracker from "@/components/ViewTracker";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ locale: Locale; id: string }>;
}

export default async function EventDetailPage({ params }: PageProps) {
  const { locale, id } = await params;
  const t = await getTranslations("event");
  const tCat = await getTranslations("categories");

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
  let isAdmin = false;
  if (user) {
    const [savedResult, roleResult] = await Promise.all([
      supabase.from("saved_events").select("id").eq("user_id", user.id).eq("event_id", id).single(),
      supabase.from("user_roles").select("role").eq("user_id", user.id).single(),
    ]);
    isSaved = !!savedResult.data;
    isAdmin = roleResult.data?.role === "admin";
  }

  // Inactive events are hidden from the public — admins can still view them
  if (!event.is_active && !isAdmin) {
    notFound();
  }

  // Fetch sub-events (children of this event)
  const { data: subEvents } = await supabase
    .from("events")
    .select("id, name_ja, name_zh, name_en, start_date, end_date, category")
    .eq("parent_event_id", id)
    .eq("is_active", true)
    .order("start_date", { ascending: true });

  // Fetch parent event if this is a sub-event
  let parentEvent: { id: string; name_ja: string | null; name_zh: string | null; name_en: string | null } | null = null;
  if (event.parent_event_id) {
    const { data: parent } = await supabase
      .from("events")
      .select("id, name_ja, name_zh, name_en")
      .eq("id", event.parent_event_id)
      .single();
    parentEvent = parent;
  }

  const name = getEventName(event as Event, locale);
  const description = getEventDescription(event as Event, locale);
  const locationName = getEventLocationName(event as Event, locale);
  const locationAddress = getEventLocationAddress(event as Event, locale);
  const businessHours = getEventBusinessHours(event as Event, locale);
  const now = new Date();
  const ended = event.end_date && new Date(event.end_date) < now;

  return (
    <article className="max-w-3xl mx-auto">
      <ViewTracker eventId={id} locale={locale} />
      {/* Back to parent event */}
      {parentEvent && (
        <Link
          href={`/${locale}/events/${parentEvent.id}`}
          className="inline-flex items-center gap-1 text-sm text-green-600 hover:text-green-700 mb-4"
        >
          ← {t("viewParent")}：{getEventName(parentEvent as Event, locale)}
        </Link>
      )}

      {/* Save button */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-2 min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 leading-snug">{name}</h1>
          {isAdmin && (
            <Link
              href={`/${locale}/admin/${event.id}`}
              className="shrink-0 text-xs text-gray-400 hover:text-green-700 border border-gray-200 hover:border-green-400 rounded px-1.5 py-0.5 transition"
              title={t("editEvent")}
            >
              ✎
            </Link>
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

      {/* ===== Summary Card ===== */}
      <div className="border border-gray-200 rounded-xl overflow-hidden mb-6">
        <table className="w-full text-sm">
          <tbody className="divide-y divide-gray-100">
            {/* Categories */}
            {event.category?.length > 0 && (
              <tr>
                <td className="px-4 py-3 text-gray-400 w-28 align-top whitespace-nowrap">{t("category")}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {event.category.map((cat: string) => (
                      <span key={cat} className="bg-green-50 text-green-700 text-xs px-2 py-0.5 rounded-full">
                        {tCat(cat as any)}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            )}
            {/* Start date */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 whitespace-nowrap">{t("startDate")}</td>
              <td className="px-4 py-3">
                {event.start_date
                  ? new Date(event.start_date).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })
                  : "—"}
              </td>
            </tr>
            {/* End date */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 whitespace-nowrap">{t("endDate")}</td>
              <td className="px-4 py-3">
                {event.end_date
                  ? new Date(event.end_date).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })
                  : "—"}
                {ended && (
                  <span className="ml-2 text-xs bg-gray-100 text-gray-400 px-2 py-0.5 rounded-full">
                    {t("ended")}
                  </span>
                )}
              </td>
            </tr>
            {/* Location */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 whitespace-nowrap">{t("location")}</td>
              <td className="px-4 py-3">{locationName || "—"}</td>
            </tr>
            {/* Address */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 whitespace-nowrap">{t("address")}</td>
              <td className="px-4 py-3">
                {(locationAddress || locationName) ? (
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(locationAddress || locationName || "")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {locationAddress || locationName} ↗
                  </a>
                ) : "—"}
              </td>
            </tr>
            {/* Business hours */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 whitespace-nowrap">{t("hours")}</td>
              <td className="px-4 py-3">{businessHours || "—"}</td>
            </tr>
            {/* Price */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 whitespace-nowrap">{t("paid")}</td>
              <td className="px-4 py-3">
                {event.is_paid === false ? (
                  <span className="text-blue-600 font-medium">{t("free")}</span>
                ) : event.is_paid === true ? (
                  <span>
                    <span className="text-amber-600 font-medium">{t("paid")}</span>
                    {event.price_info && <span className="text-gray-500 ml-2">{event.price_info}</span>}
                  </span>
                ) : (
                  "—"
                )}
              </td>
            </tr>
            {/* Source link */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 align-top whitespace-nowrap">{t("source")}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col gap-1">
                  {event.source_url ? (
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {t("viewOriginal")} ↗
                    </a>
                  ) : (
                    "—"
                  )}
                  {(event as Event).secondary_source_urls?.map((url: string, idx: number) => (
                    <a
                      key={idx}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:underline text-xs"
                    >
                      {t("viewAltSource", { n: idx + 1 })} ↗
                    </a>
                  ))}
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ===== Description ===== */}
      {description && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-gray-400 mb-2">{t("description")}</h2>
          <div className="prose prose-gray max-w-none">
            <p className="whitespace-pre-wrap text-gray-700 leading-relaxed text-sm">
              {description}
            </p>
          </div>
        </div>
      )}

      {/* ===== Sub-events ===== */}
      {subEvents && subEvents.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-medium text-gray-400 mb-3">{t("subEvents")}</h2>
          <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
            {subEvents.map((sub) => {
              const subName = getEventName(sub as Event, locale);
              return (
                <Link
                  key={sub.id}
                  href={`/${locale}/events/${sub.id}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-green-50 transition"
                >
                  <div className="w-12 text-center flex-shrink-0">
                    {sub.start_date ? (
                      <>
                        <div className="text-[10px] text-gray-400">
                          {new Date(sub.start_date).toLocaleDateString(locale, { month: "short" })}
                        </div>
                        <div className="text-lg font-bold text-gray-600 leading-none">
                          {new Date(sub.start_date).getDate()}
                        </div>
                      </>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 line-clamp-1">{subName}</p>
                    {sub.category?.slice(0, 2).map((cat: string) => (
                      <span key={cat} className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded mr-1">
                        {tCat(cat as any)}
                      </span>
                    ))}
                  </div>
                  <span className="text-gray-300 text-sm">→</span>
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* ===== Raw Data + Selection Reason + Report (Layer 1) ===== */}
      <RawDataSection
        rawTitle={event.raw_title}
        rawDescription={event.raw_description}
        selectionReason={event.selection_reason}
        locale={locale}
        reportSection={<ReportSection eventId={event.id} locale={locale} />}
      />
    </article>
  );
}

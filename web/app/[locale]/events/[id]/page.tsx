import type { Metadata } from "next";
import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event, getEventName, getEventDescription, getEventLocationName, getEventLocationAddress, getEventBusinessHours } from "@/lib/types";
import SaveButton from "@/components/SaveButton";
import RawDataSection from "@/components/RawDataSection";
import ReportSection from "@/components/ReportSection";
import ViewTracker from "@/components/ViewTracker";
import AdminEventActions from "@/components/AdminEventActions";
import Link from "next/link";

export const revalidate = 3600;

interface PageProps {
  params: Promise<{ locale: Locale; id: string }>;
}

const LOCALES = ["zh", "en", "ja"] as const;

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { locale, id } = await params;
  const supabase = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
  const { data: event } = await supabase
    .from("events")
    .select("name_ja, name_zh, name_en, description_ja, description_zh, description_en, updated_at, start_date")
    .eq("id", id)
    .single();

  if (!event) return {};

  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  const name = getEventName(event as Event, locale);
  const description = getEventDescription(event as Event, locale);

  const SITE_NAMES: Record<string, string> = {
    zh: "Tokyo Taiwan Radar 東京台灣雷達",
    en: "Tokyo Taiwan Radar",
    ja: "Tokyo Taiwan Radar 東京台湾レーダー",
  };
  const siteName = SITE_NAMES[locale] ?? "Tokyo Taiwan Radar";

  return {
    title: name ? `${name} | ${siteName}` : siteName,
    description: description?.slice(0, 160) ?? undefined,
    alternates: {
      canonical: `${base}/${locale}/events/${id}`,
      languages: {
        ...Object.fromEntries(LOCALES.map((l) => [l, `${base}/${l}/events/${id}`])),
        "x-default": `${base}/zh/events/${id}`,
      },
    },
    openGraph: {
      title: name ?? undefined,
      description: description?.slice(0, 160) ?? undefined,
      url: `${base}/${locale}/events/${id}`,
      siteName,
      type: "article",
      publishedTime: event.start_date ?? undefined,
      modifiedTime: event.updated_at,
    },
    twitter: {
      card: "summary",
      title: name ?? undefined,
      description: description?.slice(0, 160) ?? undefined,
    },
  };
}

export default async function EventDetailPage({ params }: PageProps) {
  const { locale, id } = await params;
  const t = await getTranslations("event");
  const tCat = await getTranslations("categories");

  const supabase = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const { data: event } = await supabase
    .from("events")
    .select("*")
    .eq("id", id)
    .eq("is_active", true)
    .single();

  if (!event) {
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

  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  const BREADCRUMB_LABELS: Record<string, string> = {
    zh: "活動列表",
    ja: "イベント一覧",
    en: "Event List",
  };
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Event",
    name: name ?? event.name_ja ?? undefined,
    startDate: event.start_date ?? undefined,
    endDate: event.end_date ?? undefined,
    description: description ?? undefined,
    url: `${base}/${locale}/events/${id}`,
    ...(locationName
      ? {
          location: {
            "@type": "Place",
            name: locationName,
            ...(locationAddress ? { address: locationAddress } : {}),
          },
        }
      : {}),
    organizer: { "@type": "Organization", name: "Tokyo Taiwan Radar" },
    ...(event.is_paid === false ? { isAccessibleForFree: true } : {}),
  };
  const breadcrumbLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Tokyo Taiwan Radar",
        item: `${base}/${locale}`,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: BREADCRUMB_LABELS[locale] ?? BREADCRUMB_LABELS.zh,
        item: `${base}/${locale}`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: name ?? event.name_ja ?? id,
      },
    ],
  };

  return (
    <article className="max-w-3xl mx-auto">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }}
      />
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
          <AdminEventActions eventId={event.id} locale={locale} initialIsActive={event.is_active} />
        </div>
        <SaveButton
          eventId={event.id}
          initialSaved={false}
          locale={locale}
        />
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
                  ? <time dateTime={event.start_date}>{new Date(event.start_date).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })}</time>
                  : "—"}
              </td>
            </tr>
            {/* End date */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 whitespace-nowrap">{t("endDate")}</td>
              <td className="px-4 py-3">
                {event.end_date
                  ? <time dateTime={event.end_date}>{new Date(event.end_date).toLocaleDateString(locale, { year: "numeric", month: "long", day: "numeric" })}</time>
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
            {/* Source link — official first */}
            <tr>
              <td className="px-4 py-3 text-gray-400 w-28 align-top whitespace-nowrap">{t("source")}</td>
              <td className="px-4 py-3">
                <div className="flex flex-col gap-1">
                  {(event as Event).official_url ? (
                    <a
                      href={(event as Event).official_url!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-green-700 font-medium hover:underline"
                    >
                      {t("officialSite")} ↗
                    </a>
                  ) : null}
                  {event.source_url && event.source_url !== (event as Event).official_url ? (
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {t("viewOriginal")} ↗
                    </a>
                  ) : event.source_url && !(event as Event).official_url ? (
                    <a
                      href={event.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {t("viewOriginal")} ↗
                    </a>
                  ) : null}
                  {!(event as Event).official_url && !event.source_url && "—"}
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

      {/* ===== 報導・活動紀錄 ===== */}
      {(() => {
        const hasOfficialUrl = !!(event as Event).official_url;
        const isMovie = event.category?.includes("movie");
        const hasRecordLinks = ((event as Event).record_links?.length || 0) > 0;
        const hasSecondaryUrls = ((event as Event).secondary_source_urls?.length || 0) > 0;
        const showSection = hasOfficialUrl || hasRecordLinks || hasSecondaryUrls || isMovie;
        if (!showSection) return null;
        return (
          <div className="mb-8">
            <h2 className="text-sm font-medium text-gray-400 mb-3">{t("recordLinksSection")}</h2>
            <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-100">
              {/* Movie: official promotional site link */}
              {hasOfficialUrl && isMovie && (
                <a
                  href={(event as Event).official_url!}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center px-4 py-3 hover:bg-green-50 transition text-sm text-green-700 hover:underline gap-2"
                >
                  <span className="flex-1">{t("movieOfficialSite")}</span>
                  <span className="text-gray-300 shrink-0">↗</span>
                </a>
              )}
              {(event as Event).record_links?.map((link: { title: string; url: string; recommended?: boolean }, i: number) => {
                const totalLinks = ((event as Event).record_links?.length || 0) + ((event as Event).secondary_source_urls?.length || 0);
                const showBadge = link.recommended && totalLinks > 1;
                return (
                  <a
                    key={i}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center px-4 py-3 hover:bg-green-50 transition text-sm text-blue-600 hover:underline gap-2"
                  >
                    <span className="flex-1">{link.title || link.url}</span>
                    {showBadge && (
                      <span className="shrink-0 text-xs bg-amber-100 text-amber-700 border border-amber-200 rounded-full px-2 py-0.5 font-medium">
                        {t("recordLinksRecommended")}
                      </span>
                    )}
                    <span className="text-gray-300 shrink-0">↗</span>
                  </a>
                );
              })}
              {(event as Event).secondary_source_urls?.map((secUrl: string, idx: number) => (
                <a
                  key={`sec-${idx}`}
                  href={secUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center px-4 py-3 hover:bg-green-50 transition text-sm text-blue-500 hover:underline gap-2"
                >
                  <span className="flex-1">{t("viewAltSource", { n: idx + 1 })}</span>
                  <span className="text-gray-300 shrink-0">↗</span>
                </a>
              ))}
              {/* Movie without official_url: Google search fallback */}
              {isMovie && !hasOfficialUrl && (
                <a
                  href={`https://www.google.com/search?q=${encodeURIComponent(((event as Event).name_ja || event.raw_title || name || "") + " 公式サイト")}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center px-4 py-3 hover:bg-gray-50 transition text-sm text-gray-500 hover:underline gap-2"
                >
                  <span className="flex-1">{t("searchOfficialSite")}</span>
                  <span className="text-gray-300 shrink-0">↗</span>
                </a>
              )}
            </div>
          </div>
        );
      })()}

      {/* ===== Raw Data + Selection Reason + Report (Layer 1) ===== */}
      <RawDataSection
        rawTitle={event.raw_title}
        rawDescription={event.raw_description}
        selectionReason={event.selection_reason}
        locale={locale}
        reportSection={<ReportSection eventId={event.id} locale={locale} selectionReason={(() => {
          if (!event.selection_reason) return null;
          try {
            const parsed = JSON.parse(event.selection_reason);
            if (parsed && typeof parsed === "object") {
              return (parsed as Record<string, string>)[locale] || (parsed as Record<string, string>)["ja"] || null;
            }
          } catch {}
          return event.selection_reason;
        })()} eventFields={{
          name: { zh: event.name_zh, en: event.name_en, ja: event.name_ja },
          start_date: { zh: event.start_date, en: event.start_date, ja: event.start_date },
          end_date: { zh: event.end_date, en: event.end_date, ja: event.end_date },
          venue: { zh: event.location_name_zh, en: event.location_name_en, ja: event.location_name },
          address: { zh: event.location_address_zh, en: event.location_address_en, ja: event.location_address },
          business_hours: { zh: event.business_hours_zh, en: event.business_hours_en, ja: event.business_hours },
          price: { zh: event.price_info, en: event.price_info, ja: event.price_info },
          description: { zh: event.description_zh, en: event.description_en, ja: event.description_ja },
        }} />}
      />
    </article>
  );
}

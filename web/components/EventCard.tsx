import Link from "next/link";
import { type Event, type Locale, getEventName, getEventLocationName } from "@/lib/types";
import { getTranslations } from "next-intl/server";
import { getCityLabel } from "@/lib/cityLabel";
import { Badge, DateChip } from "@/lib/design";

interface Props {
  event: Event;
  locale: Locale;
  openInNewTab?: boolean;
}

export default async function EventCard({ event, locale, openInNewTab }: Props) {
  const t = await getTranslations("event");
  const tCat = await getTranslations("categories");
  const tOrgType = await getTranslations("organizerType");

  const name = getEventName(event, locale);
  const locationName = getEventLocationName(event, locale);
  const now = new Date();
  const ended = event.end_date && new Date(event.end_date) < now;

  const isPublicationEvent =
    (event.event_form ?? []).includes("publication") ||
    (event.category ?? []).includes("books_media") ||
    event.source_name === "hanmoto";

  // Derive city label (shared helper used by homepage list too).
  const cityLabel = isPublicationEvent
    ? null
    : getCityLabel(
        (event as any).location_prefectures as string[] | null | undefined,
        (event as any).location_address as string | null,
      );

  return (
    <Link
      href={`/${locale}/events/${event.id}`}
      aria-label={t("eventLink", { name })}
      target={openInNewTab ? "_blank" : undefined}
      rel={openInNewTab ? "noopener noreferrer" : undefined}
      className="block border border-line rounded-xl p-4 hover:shadow-md hover:border-green-300 transition bg-surface group"
    >
      {/* Status + paid badges */}
      <div className="flex items-center gap-2 mb-2">
        {ended ? (
          <Badge tone="neutral">{t("ended")}</Badge>
        ) : (
          <Badge tone="success">●&nbsp;Open</Badge>
        )}
        {event.is_paid === false && <Badge tone="info">{t("free")}</Badge>}
        {event.is_paid === true && <Badge tone="warning">{t("paid")}</Badge>}
        {event.organizer_type?.[0] && event.organizer_type[0] !== "unknown" && (
          <Badge tone="accent">{tOrgType(event.organizer_type[0] as any)}</Badge>
        )}
      </div>

      {/* Title */}
      <h2 className="font-display font-bold text-fg-strong group-hover:text-green-700 line-clamp-2 leading-snug mb-2">
        {name}
      </h2>

      {/* Categories */}
      {event.category?.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {event.category.slice(0, 3).map((cat) => (
            <Badge key={cat} tone="neutral">
              {tCat(cat as any)}
            </Badge>
          ))}
        </div>
      )}

      {/* Date + location */}
      <div className="text-xs text-fg-muted space-y-1">
        {event.start_date && (
          <DateChip start={event.start_date} end={isPublicationEvent ? null : event.end_date} locale={locale} />
        )}
        {event.location_name && !isPublicationEvent && (
          <p className="flex items-center gap-1 flex-wrap">
            <span>📍</span>
            {cityLabel && (
              <Badge tone="neutral" size="xs">
                {cityLabel}
              </Badge>
            )}
            <span>{locationName}</span>
          </p>
        )}
      </div>
    </Link>
  );
}


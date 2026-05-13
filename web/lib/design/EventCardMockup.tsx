/**
 * EventCardMockup — horizontal list-row variant matching the M4 design mockup.
 *
 * Scope: /design preview page only. Not used by production routes.
 * If approved later, may replace or coexist with EventCard.
 *
 * Layout (desktop ≥ 640px):
 *   [date col 96px] [icon 80×80] [content flex-1] [actions ~110px]
 *
 * Mobile (<640px): date + icon stack on the left, content wraps below.
 */
import Link from "next/link";
import { type Event, type Locale, getEventName, getEventLocationName } from "@/lib/types";
import { Badge } from "@/lib/design";
import { CategoryThumbnail } from "@/lib/design/CategoryThumbnail";
import { getCityLabel } from "@/lib/cityLabel";

const WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

function formatMonthDay(iso: string): { wday: string; md: string } {
  const d = new Date(iso);
  return {
    wday: WEEKDAYS[d.getUTCDay()] ?? "",
    md: `${String(d.getUTCMonth() + 1).padStart(2, "0")}/${String(d.getUTCDate()).padStart(2, "0")}`,
  };
}

interface Props {
  event: Event;
  locale: Locale;
  /** index used to pick deterministic background pattern (0..5 cycles). */
  index?: number;
  /** Pre-resolved translations to avoid awaiting in this component. */
  labels: {
    open: string;
    ended: string;
    free: string;
    paid: string;
    save: string;
    detail: string;
    eventLink: (name: string) => string;
    categories: Record<string, string>;
  };
}

export function EventCardMockup({ event, locale, labels }: Props) {
  const name = getEventName(event, locale);
  const locationName = getEventLocationName(event, locale);
  const now = new Date();
  const ended = event.end_date ? new Date(event.end_date) < now : false;

  const cityLabel = getCityLabel(
    event.location_prefectures as string[] | null | undefined,
    event.location_address as string | null,
  );

  const dateObj = event.start_date ? formatMonthDay(event.start_date) : null;
  const primaryCat = event.category?.[0];

  return (
    <article className="relative">
      <Link
        href={`/${locale}/events/${event.id}`}
        aria-label={labels.eventLink(name)}
        className="group flex gap-3 sm:gap-4 items-stretch border border-line rounded-xl bg-surface hover:shadow-md hover:border-green-400 transition overflow-hidden"
      >
      {/* Date column */}
      <div
        className="flex flex-col items-center justify-center shrink-0 w-[68px] sm:w-[88px] px-2 py-3 text-center"
        style={{ background: "var(--color-blush)" }}
      >
        {dateObj ? (
          <>
            <div className="text-[10px] sm:text-[11px] font-extrabold tracking-wide text-mascot-pink-deep">
              {dateObj.wday}
            </div>
            <div className="font-display text-xl sm:text-2xl font-black text-[#3A261F] leading-tight mt-0.5">
              {dateObj.md}
            </div>
            {event.end_date && event.end_date !== event.start_date && (
              <div className="text-[9px] sm:text-[10px] text-fg-muted mt-1">
                ～{formatMonthDay(event.end_date).md}
              </div>
            )}
          </>
        ) : (
          <div className="text-[10px] text-fg-muted">TBD</div>
        )}
      </div>

      {/* Icon column — procedural category thumbnail (always visible) */}
      <div className="shrink-0 self-center pl-1">
        <CategoryThumbnail
          seed={event.id}
          categories={event.category as string[] | null | undefined}
          size={80}
          className="w-14 h-14 sm:w-20 sm:h-20"
        />
      </div>

      {/* Main content */}
      <div className="flex-1 min-w-0 py-3 pr-10 sm:pr-20 relative">
        {/* Badges row */}
        <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
          {ended && <Badge tone="neutral" size="xs">{labels.ended}</Badge>}
          {event.is_paid === false && <Badge tone="info" size="xs">{labels.free}</Badge>}
          {event.is_paid === true && <Badge tone="warning" size="xs">{labels.paid}</Badge>}
          {primaryCat && (
            <Badge tone="neutral" size="xs">
              {labels.categories[primaryCat] ?? primaryCat}
            </Badge>
          )}
        </div>

        {/* Title */}
        <h3 className="font-display font-bold text-[#3A261F] text-[15px] sm:text-base leading-snug line-clamp-2 mb-1.5 group-hover:text-green-700 transition-colors">
          {name}
        </h3>

        {/* Location row */}
        {(cityLabel || locationName) && (
          <div className="flex items-center gap-1.5 text-xs text-fg-muted flex-wrap">
            {cityLabel && (
              <Badge tone="neutral" size="xs">{cityLabel}</Badge>
            )}
            {locationName && (
              <span className="truncate">📍 {locationName}</span>
            )}
          </div>
        )}
      </div>
      </Link>

      {/* Bookmark button — independent overlay, hover only on itself */}
      <button
        type="button"
        aria-label={labels.save}
        className="absolute top-2 right-2 md:hidden w-8 h-8 flex items-center justify-center rounded-full text-fg-muted hover:bg-green-50 hover:text-green-700 transition z-10"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
        </svg>
      </button>
      <button
        type="button"
        aria-label={labels.save}
        className="hidden md:flex absolute top-1/2 -translate-y-1/2 right-3 items-center gap-1.5 px-2 py-1.5 rounded-md text-fg-muted hover:bg-green-50 hover:text-green-700 transition z-10"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
        </svg>
        <span className="text-xs font-bold">{labels.save}</span>
      </button>
    </article>
  );
}

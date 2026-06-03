"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { type Locale, type Event, getEventName } from "@/lib/types";
import { getCityLabel } from "@/lib/cityLabel";
import { CategoryThumbnail } from "@/lib/design/CategoryThumbnail";
import SaveButton from "@/components/SaveButton";
import SortControl, { type SortKey } from "@/components/SortControl";
import { filterEvents } from "@/lib/eventFilter";
import { isShelfEvent } from "@/lib/eventClassify";
import { useMaybeEventFilters } from "@/components/EventFilterContext";
import { useSearchParams } from "next/navigation";

interface Props {
  events: Event[];
  parentMap: Record<string, Event>;
  locale: Locale;
}

const SORT_KEYS: SortKey[] = ["newest", "date", "endingSoon"];

function parseSort(value: string | null): SortKey {
  return (SORT_KEYS as string[]).includes(value ?? "")
    ? (value as SortKey)
    : "newest";
}

function sortEvents(events: Event[], sort: SortKey): Event[] {
  const arr = [...events];
  if (sort === "date") {
    arr.sort((a, b) =>
      (a.start_date ?? "\uffff").localeCompare(b.start_date ?? "\uffff"),
    );
  } else if (sort === "endingSoon") {
    // events without end_date sort last
    arr.sort((a, b) =>
      (a.end_date ?? "\uffff").localeCompare(b.end_date ?? "\uffff"),
    );
  } else {
    // newest: created_at desc
    arr.sort((a, b) =>
      (b.created_at ?? "").localeCompare(a.created_at ?? ""),
    );
  }
  return arr;
}

export default function EventListClient({ events, parentMap, locale }: Props) {
  const sp = useSearchParams();
  const tEvent = useTranslations("event");
  const tCat = useTranslations("categories");
  const tGeneral = useTranslations("general");
  const tHome = useTranslations("home");
  const shared = useMaybeEventFilters();

  const sort = parseSort(shared?.filters.sort ?? sp.get("sort"));

  const filtered = useMemo(() => {
    const query = shared
      ? Object.entries(shared.filters).reduce((params, [key, value]) => {
          if (value) params.set(key, value);
          return params;
        }, new URLSearchParams())
      : new URLSearchParams(sp.toString());
    const base = filterEvents(events, query);
    // Long-term / persistent events live in the shelf; exclude them here so
    // they are not double-listed.
    const main = base.filter((e) => !isShelfEvent(e));
    return sortEvents(main, sort);
  }, [events, shared, sort, sp]);

  return (
    <div>
      {/* Main list header: title + sort segmented control */}
      <div className="flex items-center justify-between gap-3 flex-wrap mt-2">
        <h2 className="font-display font-bold text-fg-strong text-xl">
          {tHome("listTitle")}
        </h2>
        <SortControl value={sort} />
      </div>

      {filtered.length === 0 ? (
        <p className="text-center text-fg-muted mt-16 text-lg">
          {tGeneral("noResults")}
        </p>
      ) : (
        <div className="flex flex-col gap-2 mt-4">
          {filtered.map((event: Event) => {
        const name = getEventName(event, locale);
        const ended =
          event.end_date && new Date(event.end_date) < new Date();
        return (
          <div key={event.id} className="relative group/row">
            <Link
              href={`/${locale}/events/${event.id}`}
              className="group flex gap-3 sm:gap-4 items-stretch border border-line rounded-xl bg-paper hover:shadow-md hover:border-green-400 transition overflow-hidden"
          >
            {/* Date column */}
            <div className="w-16 flex-shrink-0 flex flex-col items-center justify-center px-2 py-2">
              {event.start_date ? (
                <>
                  <div className="font-display text-[10px] text-[#E84860] font-bold uppercase tracking-wide leading-none">
                    {new Date(event.start_date).toLocaleDateString(locale, {
                      weekday: "short",
                      timeZone: "UTC",
                    })}
                  </div>
                  <div className="font-display text-[10px] text-fg-muted font-medium uppercase tracking-wide mt-0.5">
                    {new Date(event.start_date).toLocaleDateString(locale, {
                      month: "short",
                      timeZone: "UTC",
                    })}
                  </div>
                  <div className="font-display text-2xl font-bold text-[#3A261F] dark:text-fg leading-none mt-0.5">
                    {new Date(event.start_date).getUTCDate()}
                  </div>
                  {event.end_date &&
                    event.end_date.slice(0, 10) !==
                      event.start_date.slice(0, 10) && (
                      <div className="text-[10px] text-fg-muted mt-0.5 leading-tight">
                        ~
                        {new Date(event.end_date).toLocaleDateString(locale, {
                          month: "numeric",
                          day: "numeric",
                          timeZone: "UTC",
                        })}
                      </div>
                    )}
                </>
              ) : (
                <div className="text-xs text-fg-muted">—</div>
              )}
            </div>

            {/* Procedural category thumbnail */}
            <div className="shrink-0 self-center pl-1">
              <CategoryThumbnail
                id={event.id}
                categories={event.category ?? undefined}
                className="w-14 h-14 sm:w-16 sm:h-16"
              />
            </div>

            {/* Main content */}
            <div className="flex-1 min-w-0 py-3 pr-3">
              <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                {ended ? (
                  <span className="text-[10px] bg-muted dark:bg-stone-700/60 text-fg-muted dark:text-stone-200 px-2 py-0.5 rounded-full font-medium">
                    {tEvent("ended")}
                  </span>
                ) : (
                  <span className="text-[10px] text-green-700 font-bold">●</span>
                )}
                {event.is_paid === false && (
                  <span className="text-[10px] bg-[#C4E86F]/40 text-[#1F5E2B] dark:bg-green-900/70 dark:text-green-200 px-2 py-0.5 rounded-full font-bold">
                    {tEvent("free")}
                  </span>
                )}
                {event.category?.slice(0, 2).map((cat) => (
                  <span
                    key={cat}
                    className="text-[10px] bg-muted dark:bg-stone-700/60 text-fg-muted dark:text-stone-200 px-2 py-0.5 rounded-full font-medium"
                  >
                    {tCat(cat as Parameters<typeof tCat>[0])}
                  </span>
                ))}
              </div>
              <p className="font-display font-bold text-[#3A261F] dark:text-fg text-[14px] sm:text-[15px] group-hover:text-green-700 dark:group-hover:text-green-400 line-clamp-2 leading-snug">
                {event.parent_event_id && parentMap[event.parent_event_id] && (
                  <span className="block text-[11px] text-green-700 font-normal mb-0.5 truncate">
                    ↳ {getEventName(parentMap[event.parent_event_id], locale)}
                  </span>
                )}
                {name}
              </p>
              {event.location_name &&
                (() => {
                  const cityLabel = getCityLabel(
                    (event as { location_prefectures?: string[] | null })
                      .location_prefectures,
                    (event as { location_address?: string | null })
                      .location_address,
                  );
                  return (
                    <p className="text-[11px] text-fg-muted mt-1">
                      📍{" "}
                      {cityLabel && (
                        <span className="inline-block bg-muted dark:bg-stone-700/60 text-fg-muted dark:text-stone-200 px-1.5 py-0.5 rounded mr-1 font-medium">
                          {cityLabel}
                        </span>
                      )}
                      {event.location_name}
                    </p>
                  );
                })()}
            </div>
            </Link>
            {/* Compact save button — absolute overlay, top-right corner */}
            <div className="absolute top-2 right-2 opacity-0 group-hover/row:opacity-100 focus-within:opacity-100 transition-opacity">
              <SaveButton eventId={event.id} initialSaved={false} locale={locale} compact />
            </div>
          </div>
        );
      })}
        </div>
      )}
    </div>
  );
}

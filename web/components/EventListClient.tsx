"use client";

import { useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { type Locale, type Event, getEventName } from "@/lib/types";
import { getCityLabel } from "@/lib/cityLabel";
import {
  REGIONS_WITH_CITY,
  matchesCity,
  type RegionWithCity,
} from "@/lib/regionPrefectures";
import { matchesLocation } from "@/lib/locationMarkers";

interface Props {
  events: Event[];
  parentMap: Record<string, Event>;
  locale: Locale;
}

export default function EventListClient({ events, parentMap, locale }: Props) {
  const sp = useSearchParams();
  const tEvent = useTranslations("event");
  const tCat = useTranslations("categories");
  const tGeneral = useTranslations("general");

  const filtered = useMemo(() => {
    const q = sp.get("q")?.trim().toLowerCase() ?? "";
    const categoryParam = sp.get("category") ?? "";
    const cats = categoryParam ? categoryParam.split(",").filter(Boolean) : [];
    const fromStr = sp.get("from") ?? "";
    const toStr = sp.get("to") ?? "";
    const paid = sp.get("paid") ?? "";
    const timeMode = sp.get("timeMode") ?? "active";
    const location = sp.get("location") ?? "";
    const city = sp.get("city") ?? "";
    const today = new Date().toISOString().slice(0, 10);

    return events.filter((e) => {
      // keyword (name + organizer only — descriptions are not in the payload)
      if (q) {
        const hay = [
          e.name_ja,
          e.name_zh,
          e.name_en,
          e.organizer ?? null,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }

      // category — overlap (event has any of the selected cats)
      if (cats.length > 0) {
        const eventCats = e.category ?? [];
        if (!cats.some((c) => eventCats.includes(c))) return false;
      }

      // time mode
      if (timeMode === "active") {
        if (e.end_date && e.end_date.slice(0, 10) < today) return false;
      } else if (timeMode === "past") {
        if (fromStr && e.start_date && e.start_date.slice(0, 10) < fromStr)
          return false;
        if (toStr && e.start_date && e.start_date.slice(0, 10) > toStr)
          return false;
      }

      // paid
      if (paid === "free" && e.is_paid !== false) return false;
      if (paid === "paid" && e.is_paid !== true) return false;

      // location
      if (location) {
        if (!matchesLocation(e, location)) return false;
      }

      // city sub-filter
      if (city && (REGIONS_WITH_CITY as readonly string[]).includes(location)) {
        const ok = matchesCity(
          city,
          (e as { location_address?: string | null }).location_address,
          (e as { location_prefectures?: string[] | null })
            .location_prefectures,
          location as RegionWithCity,
        );
        if (!ok) return false;
      }

      return true;
    });
  }, [events, sp]);

  if (filtered.length === 0) {
    return (
      <p className="text-center text-fg-muted mt-16 text-lg">
        {tGeneral("noResults")}
      </p>
    );
  }

  return (
      <div className="flex flex-col divide-y divide-line mt-4 border border-line rounded-xl overflow-hidden bg-surface">
      {filtered.map((event: Event) => {
        const name = getEventName(event, locale);
        const ended =
          event.end_date && new Date(event.end_date) < new Date();
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
                  <div className="text-xs text-fg-subtle">
                    {new Date(event.start_date).toLocaleDateString(locale, {
                      month: "short",
                    })}
                  </div>
                  <div className="text-2xl font-bold text-fg leading-none">
                    {new Date(event.start_date).getDate()}
                  </div>
                  {event.end_date &&
                    event.end_date.slice(0, 10) !==
                      event.start_date.slice(0, 10) && (
                      <div className="text-[10px] text-fg mt-0.5 leading-tight">
                        ~
                        {new Date(event.end_date).toLocaleDateString(locale, {
                          month: "numeric",
                          day: "numeric",
                        })}
                      </div>
                    )}
                </>
              ) : (
                <div className="text-xs text-fg-subtle">—</div>
              )}
            </div>

            {/* Main content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                {ended ? (
                  <span className="text-xs bg-muted text-fg-subtle px-2 py-0.5 rounded-full">
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
                  <span
                    key={cat}
                    className="text-xs bg-muted text-fg-muted px-2 py-0.5 rounded-full"
                  >
                    {tCat(cat as Parameters<typeof tCat>[0])}
                  </span>
                ))}
              </div>
              <p className="text-sm font-medium text-fg-strong group-hover:text-green-700 line-clamp-2 leading-snug">
                {event.parent_event_id && parentMap[event.parent_event_id] && (
                  <span className="block text-xs text-green-600 font-normal mb-0.5 truncate">
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
                    <p className="text-xs text-fg-subtle mt-0.5">
                      📍{" "}
                      {cityLabel && (
                        <span className="inline-block bg-muted text-fg-muted px-1.5 py-0.5 rounded mr-1 font-medium">
                          {cityLabel}
                        </span>
                      )}
                      {event.location_name}
                    </p>
                  );
                })()}
            </div>
          </Link>
        );
      })}
    </div>
  );
}

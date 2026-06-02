"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type Locale, type Event, getEventName } from "@/lib/types";
import { CategoryThumbnail } from "@/lib/design/CategoryThumbnail";
import { filterEvents } from "@/lib/eventFilter";
import { isShelfEvent, shelfTab, isNew, type ShelfTab } from "@/lib/eventClassify";

interface Props {
  events: Event[];
  locale: Locale;
}

const TABS: ShelfTab[] = ["longTerm", "persistent"];

const TAB_LABEL: Record<ShelfTab, string> = {
  longTerm: "shelfLongTerm",
  persistent: "shelfPersistent",
};

function dateRange(event: Event, locale: Locale): string | null {
  if (!event.start_date) return null;
  const start = new Date(event.start_date).toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
  if (
    event.end_date &&
    event.end_date.slice(0, 10) !== event.start_date.slice(0, 10)
  ) {
    const end = new Date(event.end_date).toLocaleDateString(locale, {
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
    return `${start} ~ ${end}`;
  }
  return start;
}

export default function EventShelf({ events, locale }: Props) {
  const sp = useSearchParams();
  const t = useTranslations("home");
  const tEvent = useTranslations("event");
  const [tab, setTab] = useState<ShelfTab>("longTerm");

  const { longTerm, persistent } = useMemo(() => {
    const filtered = filterEvents(events, new URLSearchParams(sp.toString()));
    const shelf = filtered.filter(isShelfEvent);
    return {
      longTerm: shelf.filter((e) => shelfTab(e) === "longTerm"),
      persistent: shelf.filter((e) => shelfTab(e) === "persistent"),
    };
  }, [events, sp]);

  const counts: Record<ShelfTab, number> = {
    longTerm: longTerm.length,
    persistent: persistent.length,
  };

  // Empty state: hide the whole shelf (including the heading) when neither
  // tab has any content.
  if (counts.longTerm === 0 && counts.persistent === 0) return null;

  // If the active tab is empty but the other has content, fall back so the
  // shelf is never rendered empty.
  const activeTab: ShelfTab = counts[tab] > 0 ? tab : TABS.find((x) => counts[x] > 0)!;
  const list = activeTab === "longTerm" ? longTerm : persistent;

  return (
    <section className="mt-6 mb-8" aria-label={t("shelfTitle")}>
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <h2 className="font-display font-bold text-fg-strong text-xl">
          {t("shelfTitle")}
        </h2>
        {/* Segmented tab */}
        <div
          role="tablist"
          aria-label={t("shelfTitle")}
          className="relative inline-flex items-center rounded-full bg-muted p-1 text-xs font-medium"
        >
          <span
            aria-hidden
            className="absolute top-1 bottom-1 left-1 rounded-full bg-surface dark:bg-elevated shadow-sm motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out"
            style={{
              width: `calc((100% - 0.5rem) / ${TABS.length})`,
              transform: `translateX(${TABS.indexOf(activeTab) * 100}%)`,
            }}
          />
          {TABS.map((key) => {
            const selected = key === activeTab;
            return (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={selected}
                disabled={counts[key] === 0}
                onClick={() => setTab(key)}
                className={`relative z-10 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full whitespace-nowrap transition-colors hover:text-fg-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-40 disabled:cursor-not-allowed ${
                  selected ? "text-fg-strong font-bold" : "text-fg-muted"
                }`}
              >
                {t(TAB_LABEL[key])}
                <span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-paper text-fg-muted text-[10px] leading-none">
                  {counts[key]}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Horizontal scroll-snap row with edge fade masks */}
      <div className="relative">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-0 w-8 z-10 bg-gradient-to-r from-[var(--color-bg)] to-transparent"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 w-8 z-10 bg-gradient-to-l from-[var(--color-bg)] to-transparent"
        />
        <ul className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 px-1 -mx-1">
          {list.map((event) => {
            const name = getEventName(event, locale);
            const range = dateRange(event, locale);
            return (
              <li
                key={event.id}
                className="snap-start shrink-0 w-[200px] sm:w-[220px]"
              >
                <Link
                  href={`/${locale}/events/${event.id}`}
                  className="group relative flex flex-col h-full rounded-xl border border-line bg-paper/70 backdrop-blur-md overflow-hidden transition hover:shadow-md hover:border-green-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  {isNew(event.created_at) && (
                    <span className="absolute top-2 left-2 z-10 text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#E84860] text-white">
                      {t("badgeNew")}
                    </span>
                  )}
                  <div className="flex items-center justify-center p-3 pb-2">
                    <CategoryThumbnail
                      id={event.id}
                      categories={event.category ?? undefined}
                      className="w-full h-24 rounded-lg"
                    />
                  </div>
                  <div className="px-3 pb-3 flex flex-col gap-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {event.is_paid === false && (
                        <span className="text-[10px] bg-[#C4E86F]/40 text-[#1F5E2B] dark:bg-green-900/70 dark:text-green-200 px-1.5 py-0.5 rounded-full font-bold">
                          {tEvent("free")}
                        </span>
                      )}
                      {range && (
                        <span className="text-[10px] text-fg-muted">
                          {range}
                        </span>
                      )}
                    </div>
                    <p className="font-display font-bold text-fg-strong text-[13px] leading-snug line-clamp-2 group-hover:text-green-700 dark:group-hover:text-green-400">
                      {name}
                    </p>
                    {event.location_name && (
                      <p className="text-[11px] text-fg-muted line-clamp-1">
                        📍 {event.location_name}
                      </p>
                    )}
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

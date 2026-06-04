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

function sortByEndDateAsc(a: Event, b: Event): number {
  const d1 = a.end_date ? new Date(a.end_date).getTime() : Infinity;
  const d2 = b.end_date ? new Date(b.end_date).getTime() : Infinity;
  if (d1 !== d2) return d1 - d2;
  const s1 = a.start_date ? new Date(a.start_date).getTime() : Infinity;
  const s2 = b.start_date ? new Date(b.start_date).getTime() : Infinity;
  if (s1 !== s2) return s1 - s2;
  return new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime();
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
      longTerm: shelf.filter((e) => shelfTab(e) === "longTerm").sort(sortByEndDateAsc),
      persistent: shelf.filter((e) => shelfTab(e) === "persistent").sort(sortByEndDateAsc),
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
          className="relative inline-flex items-center gap-1 rounded-full bg-mascot-pink/20 p-1.5 text-xs font-medium"
        >
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
                className={`inline-flex items-center gap-1.5 px-3 py-1.75 rounded-full whitespace-nowrap transition-colors hover:text-fg-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-40 disabled:cursor-not-allowed ${
                  selected
                    ? "bg-blush text-fg-strong shadow-sm dark:bg-elevated"
                    : "text-fg-muted"
                }`}
              >
                <span className="leading-none">{t(TAB_LABEL[key])}</span>
                <span className="inline-flex shrink-0 items-center justify-center min-w-6 h-6 px-1.5 rounded-full bg-paper border border-[#EDD8D0] text-fg-muted text-[10px] leading-none font-mono tabular-nums shadow-sm">
                  {counts[key]}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Horizontal scroll-snap row with bleeding margins so cards scroll flush to the viewport edges */}
      <div className="relative -mx-4 overflow-hidden">
        <ul className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 px-4 scroll-smooth">
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
                    <span className="absolute top-2 left-2 z-10 text-[9px] font-extrabold px-1.5 py-0.5 rounded-sm border-2 border-[#E84860] text-[#E84860] bg-surface/95 -rotate-3 select-none tracking-wider shadow-sm shadow-[#E84860]/20">
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

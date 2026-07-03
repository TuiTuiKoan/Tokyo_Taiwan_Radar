"use client";

import { useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type Event, type Locale, getEventName } from "@/lib/types";
import { getCityLabel } from "@/lib/cityLabel";
import { CategoryThumbnail } from "@/lib/design/CategoryThumbnail";
import OwnerEventTable from "@/components/OwnerEventTable";

export type AccountEvent = Event & {
  owner_user_id?: string | null;
  closed_by_owner?: boolean | null;
  is_user_submitted?: boolean | null;
};

interface Props {
  locale: Locale;
  favoriteEvents: Event[];
  myEvents: AccountEvent[];
  parentMap: Record<string, Event>;
  hasProfile: boolean;
  displayName?: string | null;
  avatarUrl?: string | null;
}

type AccountTab = "favorites" | "myEvents";

function eventDate(event: Event, locale: Locale): string | null {
  if (!event.start_date) return null;
  return new Date(event.start_date).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export default function AccountHomeClient({
  locale,
  favoriteEvents,
  myEvents,
  parentMap,
  hasProfile,
  displayName,
  avatarUrl,
}: Props) {
  const t = useTranslations("account");
  const tEvent = useTranslations("event");
  const tCat = useTranslations("categories");
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const activeTab: AccountTab = searchParams.get("tab") === "myEvents" ? "myEvents" : "favorites";

  function setTab(tab: AccountTab) {
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "favorites") {
      params.delete("tab");
    } else {
      params.set("tab", tab);
    }
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  const activeEvents = useMemo(
    () => (activeTab === "favorites" ? favoriteEvents : myEvents),
    [activeTab, favoriteEvents, myEvents],
  );

  function renderEvent(event: AccountEvent) {
    const name = getEventName(event, locale);
    const date = eventDate(event, locale);
    const cityLabel = getCityLabel(
      (event as { location_prefectures?: string[] | null }).location_prefectures,
      (event as { location_address?: string | null }).location_address,
    );
    const parent = event.parent_event_id ? parentMap[event.parent_event_id] : null;
    const isNonPublic = activeTab === "myEvents" && !event.is_active;

    const cardInner = (
      <>
        <div className="shrink-0 self-center pl-3">
          <CategoryThumbnail
            id={event.id}
            categories={event.category ?? undefined}
            className="h-14 w-14 sm:h-16 sm:w-16"
          />
        </div>
        <div className="min-w-0 flex-1 py-3 pr-3">
          <div className="mb-1 flex flex-wrap items-center gap-1.5">
            {date && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-fg-muted">
                {date}
              </span>
            )}
            {event.is_paid === false && (
              <span className="rounded-full bg-[#C4E86F]/40 px-2 py-0.5 text-[10px] font-bold text-[#1F5E2B] dark:bg-green-900/70 dark:text-green-200">
                {tEvent("free")}
              </span>
            )}
            {activeTab === "myEvents" && event.closed_by_owner && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-fg-muted">
                {t("closedByOwner")}
              </span>
            )}
            {activeTab === "myEvents" && event.is_user_submitted && (
              <span className="rounded-full bg-green-50 px-2 py-0.5 text-[10px] font-medium text-green-700 dark:bg-green-900/40 dark:text-green-200">
                {t("userSubmitted")}
              </span>
            )}
            {event.category?.slice(0, 2).map((cat) => (
              <span
                key={cat}
                className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-fg-muted dark:bg-stone-700/60 dark:text-stone-200"
              >
                {tCat(cat as Parameters<typeof tCat>[0])}
              </span>
            ))}
          </div>
          <p className={`font-display text-[14px] font-bold leading-snug line-clamp-2 sm:text-[15px] ${isNonPublic ? "text-fg-muted" : "text-[#3A261F] group-hover:text-green-700 dark:text-fg dark:group-hover:text-green-400"}`}>
            {parent && (
              <span className="mb-0.5 block truncate text-[11px] font-normal text-green-700">
                {t("parentEvent", { name: getEventName(parent, locale) })}
              </span>
            )}
            {name}
          </p>
          {event.location_name && (
            <p className="mt-1 text-[11px] text-fg-muted">
              {cityLabel && (
                <span className="mr-1 inline-block rounded bg-muted px-1.5 py-0.5 font-medium text-fg-muted dark:bg-stone-700/60 dark:text-stone-200">
                  {cityLabel}
                </span>
              )}
              {event.location_name}
            </p>
          )}
        </div>
      </>
    );

    if (isNonPublic) {
      return (
        <div
          key={event.id}
          className="flex gap-3 sm:gap-4 items-stretch border border-line rounded-xl bg-paper overflow-hidden opacity-70"
        >
          {cardInner}
        </div>
      );
    }

    return (
      <Link
        key={event.id}
        href={`/${locale}/events/${event.id}`}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex gap-3 sm:gap-4 items-stretch border border-line rounded-xl bg-paper hover:shadow-md hover:border-green-400 transition overflow-hidden"
      >
        {cardInner}
      </Link>
    );
  }

  return (
    <div className="space-y-5">
      {/* Avatar + handle */}
      <div className="flex items-center gap-3">
        {avatarUrl ? (
          <img
            src={avatarUrl}
            alt=""
            className="h-14 w-14 rounded-full object-cover shrink-0 border border-line"
            referrerPolicy="no-referrer"
          />
        ) : (
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/60 text-xl font-bold text-green-700 dark:text-green-300 border border-line">
            {(displayName || "?").charAt(0).toUpperCase()}
          </span>
        )}
        <div className="min-w-0">
          <p className="truncate font-semibold text-fg-strong">{displayName || ""}</p>
          <Link
            href={`/${locale}/account/profile`}
            className="text-xs text-fg-muted hover:text-green-700 transition"
          >
            {t("editProfile")}
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border border-line bg-paper p-1">
          <button
            type="button"
            onClick={() => setTab("favorites")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              activeTab === "favorites"
                ? "bg-green-600 text-white"
                : "text-fg-muted hover:bg-elevated"
            }`}
          >
            {t("favoritesTab")}
          </button>
          <button
            type="button"
            onClick={() => setTab("myEvents")}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
              activeTab === "myEvents"
                ? "bg-green-600 text-white"
                : "text-fg-muted hover:bg-elevated"
            }`}
          >
            {t("myEventsTab")}
          </button>
        </div>
      </div>

      {activeTab === "myEvents" && !hasProfile ? (
        <div className="rounded-xl border border-line bg-surface px-5 py-6 text-center">
          <h2 className="text-lg font-semibold text-fg-strong">{t("profileMissingTitle")}</h2>
          <p className="mt-2 text-sm text-fg-muted">{t("profileMissingDesc")}</p>
          <Link
            href={`/${locale}/account/profile`}
            className="mt-4 inline-flex rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition"
          >
            {t("profileMissingCta")}
          </Link>
        </div>
      ) : activeTab === "myEvents" && hasProfile ? (
        <OwnerEventTable events={myEvents} locale={locale} />
      ) : activeEvents.length === 0 ? (
        <p className="mt-16 text-center text-fg-muted">
          {activeTab === "favorites" ? t("favoritesEmpty") : t("myEventsEmpty")}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {activeEvents.map((event: Event | AccountEvent) => renderEvent(event as AccountEvent))}
        </div>
      )}
    </div>
  );
}

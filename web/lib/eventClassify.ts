import type { Event } from "@/lib/types";

// Long-term threshold: events whose run spans more than this many days are
// pulled out of the main vertical list into the horizontal shelf.
export const LONG_TERM_DAYS = 30;

// Text markers (in name / location) that hint an online / streaming listing.
const ONLINE_MARKERS = ["オンライン", "配信", "ストリーミング", "online", "streaming"];

const ONE_OFF_FORMS = new Set([
  "broadcast",
  "lecture",
  "screening",
  "screening_with_talk",
  "workshop",
  "talk",
  "concert",
  "performing_arts",
]);

/**
 * Whole-day duration between two ISO date(time) strings, or null when either
 * bound is missing. Uses UTC date parts to stay timezone-stable with the rest
 * of the list view.
 */
export function durationDays(
  start: string | null | undefined,
  end: string | null | undefined,
): number | null {
  if (!start || !end) return null;
  const s = new Date(start);
  const e = new Date(end);
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return null;
  const ms = e.getTime() - s.getTime();
  return Math.floor(ms / 86_400_000);
}

function hasOnlineMarker(event: Event): boolean {
  const hay = [event.name_ja, event.name_zh, event.name_en, event.location_name]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return ONLINE_MARKERS.some((m) => hay.includes(m.toLowerCase()));
}

/** Event runs longer than LONG_TERM_DAYS (needs both start_date & end_date). */
export function isLongTerm(event: Event): boolean {
  const d = durationDays(event.start_date, event.end_date);
  return d != null && d > LONG_TERM_DAYS;
}

/** Always-on / streaming style listing: must be online, long duration or without end date, and not a one-off. */
export function isPersistent(event: Event): boolean {
  // 1. Must have online/streaming indicator to be under "常設配信"
  if (!hasOnlineMarker(event)) return false;

  // 2. If it has both start and end dates, its duration must run longer than LONG_TERM_DAYS
  if (event.start_date && event.end_date) {
    const days = durationDays(event.start_date, event.end_date);
    if (days !== null && days <= LONG_TERM_DAYS) return false;
  }

  // 3. If it has only start_date (no end_date) but has a one-off style event form, it is NOT persistent
  if (event.start_date) {
    if (event.event_form?.some((f) => ONE_OFF_FORMS.has(f))) {
      return false;
    }
    // If it has a specific scheduled hour start (not T00:00:00) and starts in the future,
    // it's a scheduled one-off webinar or broadcast, not a permanent archive.
    const isScheduledTime =
      !event.start_date.endsWith("T00:00:00Z") &&
      !event.start_date.endsWith("T00:00:00+00:00");
    if (isScheduledTime) return false;
  }

  return true;
}

/** Whether the event belongs in the horizontal "長期・常設" shelf. */
export function isShelfEvent(event: Event): boolean {
  return isLongTerm(event) || isPersistent(event);
}

export type ShelfTab = "longTerm" | "persistent";

/**
 * Shelf tab assignment — persistent takes priority so the two tabs stay
 * mutually exclusive (常設配信 = isPersistent；長期開催 = isLongTerm && !isPersistent).
 */
export function shelfTab(event: Event): ShelfTab {
  return isPersistent(event) ? "persistent" : "longTerm";
}

/** NEW badge: created within the last `days` days. */
export function isNew(
  createdAt: string | null | undefined,
  days = 7,
): boolean {
  if (!createdAt) return false;
  const c = new Date(createdAt);
  if (Number.isNaN(c.getTime())) return false;
  return Date.now() - c.getTime() < days * 86_400_000;
}

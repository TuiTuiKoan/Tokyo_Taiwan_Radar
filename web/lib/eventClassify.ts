import type { Event } from "@/lib/types";

// Long-term threshold: events whose run spans more than this many days are
// pulled out of the main vertical list into the horizontal shelf.
export const LONG_TERM_DAYS = 30;

// `event_form` values that represent always-on / streaming style listings.
// These are treated as "persistent" (常設配信) regardless of end_date.
const PERSISTENT_FORMS = new Set(["broadcast"]);

// Text markers (in name / location) that hint an online / streaming listing.
const ONLINE_MARKERS = ["オンライン", "配信", "ストリーミング", "online", "streaming"];

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

/** Always-on / streaming style listing: no end_date, streaming form, or online marker. */
export function isPersistent(event: Event): boolean {
  if (!event.end_date) return true;
  if (event.event_form?.some((f) => PERSISTENT_FORMS.has(f))) return true;
  return hasOnlineMarker(event);
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

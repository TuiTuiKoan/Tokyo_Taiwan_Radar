import { type Event } from "@/lib/types";
import {
  REGIONS_WITH_CITY,
  matchesCity,
  type RegionWithCity,
} from "@/lib/regionPrefectures";
import { matchesLocation } from "@/lib/locationMarkers";

/**
 * Shared FilterBar predicate. Mirrors the URL-driven filters (keyword,
 * category, time mode, paid, location, city) so the shelf and the main list
 * stay in sync. Sorting and shelf/main partitioning happen by the callers.
 */
export function filterEvents(
  events: Event[],
  sp: URLSearchParams,
): Event[] {
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
      const hay = [e.name_ja, e.name_zh, e.name_en, e.organizer ?? null]
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
        (e as { location_prefectures?: string[] | null }).location_prefectures,
        location as RegionWithCity,
      );
      if (!ok) return false;
    }

    return true;
  });
}

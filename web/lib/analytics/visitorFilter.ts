// Admin analytics filter over event_views.visitor_class. Spec: view-bot-filter.
import type { VisitorClass } from "./botDetect";

export const VISITOR_FILTERS = ["exclude_bots", "human", "bots", "all"] as const;
export type VisitorFilter = (typeof VISITOR_FILTERS)[number];

export const DEFAULT_VISITOR_FILTER: VisitorFilter = "exclude_bots";

/** Normalise a query-string value; unknown or missing → the default. */
export function parseVisitorFilter(raw: string | null | undefined): VisitorFilter {
  return (VISITOR_FILTERS as readonly string[]).includes(raw ?? "")
    ? (raw as VisitorFilter)
    : DEFAULT_VISITOR_FILTER;
}

/**
 * visitor_class values to keep, or null for no filter.
 * exclude_bots keeps "unclassified" (rows written before migration 109 that the
 * backfill could not match to a known bot), so history stays visible.
 */
export function visitorClassesFor(filter: VisitorFilter): VisitorClass[] | null {
  switch (filter) {
    case "human":
      return ["human"];
    case "bots":
      return ["known_bot", "suspected_bot"];
    case "all":
      return null;
    case "exclude_bots":
    default:
      return ["human", "unclassified"];
  }
}

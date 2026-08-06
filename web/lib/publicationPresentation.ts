import { type Event, getPublicationPresentationFlags } from "@/lib/types";

export type WrongDetailField =
  | "name"
  | "start_date"
  | "end_date"
  | "venue"
  | "address"
  | "business_hours"
  | "price"
  | "description";

export const PURE_PUBLICATION_EXCLUDED_REPORT_FIELDS: WrongDetailField[] = [
  "end_date",
  "venue",
  "address",
  "business_hours",
  "price",
];

export interface DetailPresentationPolicy {
  isPurePublication: boolean;
  showEndDate: boolean;
  showVenue: boolean;
  showAddress: boolean;
  showBusinessHours: boolean;
  showPrice: boolean;
  showCalendar: boolean;
  showEventStatus: boolean;
  showFaqWhere: boolean;
  showFaqPrice: boolean;
  showFaqEndRange: boolean;
}

export interface SourceLinkItem {
  labelKey: "officialSite" | "applyLink" | "publisherWebsite" | "viewOriginal";
  url: string;
}

export function getDetailPresentationPolicy(
  record: Pick<Event, "event_form">
): DetailPresentationPolicy {
  const flags = getPublicationPresentationFlags(record);
  return {
    isPurePublication: flags.isPurePublication,
    showEndDate: !flags.hideEnd,
    showVenue: !flags.hideVenue,
    showAddress: !flags.hideVenue,
    showBusinessHours: !flags.hideHours,
    showPrice: !flags.hidePrice,
    showCalendar: !flags.hideCalendar,
    showEventStatus: !flags.hideEventStatus,
    showFaqWhere: !flags.isPurePublication,
    showFaqPrice: !flags.isPurePublication,
    showFaqEndRange: !flags.isPurePublication,
  };
}

export function getReportExcludedDetailFields(
  record: Pick<Event, "event_form">
): WrongDetailField[] {
  const flags = getPublicationPresentationFlags(record);
  return flags.isPurePublication ? [...PURE_PUBLICATION_EXCLUDED_REPORT_FIELDS] : [];
}

export function canonicalizeHttpUrl(rawUrl: string | null | undefined): string | null {
  if (!rawUrl) return null;
  const trimmed = rawUrl.trim();
  if (!trimmed) return null;

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return null;
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;

  parsed.hash = "";
  if (parsed.pathname !== "/") {
    parsed.pathname = parsed.pathname.replace(/\/+$/, "") || "/";
  }

  return parsed.toString();
}

export function getValidatedPublisherWebsite(
  record: Pick<Event, "organizer_url">
): string | null {
  return canonicalizeHttpUrl(record.organizer_url ?? null);
}

export function buildCanonicalSourceLinks(
  record: Pick<Event, "official_url" | "submission_url" | "organizer_url" | "source_url">
): SourceLinkItem[] {
  const candidates: SourceLinkItem[] = [
    { labelKey: "officialSite", url: record.official_url ?? "" },
    { labelKey: "applyLink", url: record.submission_url ?? "" },
    { labelKey: "publisherWebsite", url: record.organizer_url ?? "" },
    { labelKey: "viewOriginal", url: record.source_url ?? "" },
  ];

  const seen = new Set<string>();
  const links: SourceLinkItem[] = [];

  for (const candidate of candidates) {
    const canonical = canonicalizeHttpUrl(candidate.url);
    if (!canonical || seen.has(canonical)) continue;
    seen.add(canonical);
    links.push({ ...candidate, url: canonical });
  }

  return links;
}

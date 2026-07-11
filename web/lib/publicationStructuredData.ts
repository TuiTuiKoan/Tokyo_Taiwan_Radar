import {
  type Event,
  type Locale,
  getEventDirector,
  getEventOrganizer,
  getEventPerformer,
  getPublicationPresentationFlags,
  isNdlPeriodicalArticle,
} from "@/lib/types";
import { getValidatedPublisherWebsite } from "@/lib/publicationPresentation";

interface BuildStructuredDataParams {
  event: Event;
  locale: Locale;
  eventId: string;
  baseUrl: string;
  canonicalUrl: string;
  imageUrl: string;
  displayName: string | null;
  displayDescription: string | null;
  displayLocationName: string | null;
  displayLocationAddress: string | null;
}

const PLACEHOLDER_AUTHOR_RE = /^(?:n\/a|none|unknown|不明|未定|未公開|待定|未知|作者不詳)$/i;
const MULTI_PERSON_RE = /[、,，;；/／&＆]|\sand\s|\swith\s|・/i;
const ROLE_POLLUTION_RE = /(?:監督|导演|導演|director|出演|cast|声優|voiced\s+by|著者|author)\s*[:：]/i;

function normalizeAuthorName(name: string): string {
  return name.trim().replace(/\s+/g, " ");
}

function isSafeStructuredAuthorName(name: string): boolean {
  const normalized = normalizeAuthorName(name);
  if (!normalized) return false;
  if (normalized.length > 80) return false;
  if (PLACEHOLDER_AUTHOR_RE.test(normalized)) return false;
  if (MULTI_PERSON_RE.test(normalized)) return false;
  if (ROLE_POLLUTION_RE.test(normalized)) return false;
  if (/\r|\n/.test(normalized)) return false;
  return true;
}

function getAuthorCandidates(event: Event, locale: Locale): string[] {
  const localizedPerformers =
    locale === "zh"
      ? event.performers_zh
      : locale === "en"
        ? event.performers_en
        : event.performers;

  const arrayCandidates =
    localizedPerformers && localizedPerformers.length > 0
      ? localizedPerformers
      : (event.performers ?? []);

  if (arrayCandidates.length > 0) {
    return arrayCandidates;
  }

  const singleCandidate =
    locale === "zh"
      ? event.performer_zh ?? event.performer
      : locale === "en"
        ? event.performer_en ?? event.performer
        : event.performer;

  return singleCandidate ? [singleCandidate] : [];
}

function getStructuredAuthors(event: Event, locale: Locale): Array<{ "@type": "Person"; name: string }> {
  const names = getAuthorCandidates(event, locale)
    .map((name) => normalizeAuthorName(name))
    .filter((name) => isSafeStructuredAuthorName(name));

  const unique = Array.from(new Set(names));
  return unique.map((name) => ({ "@type": "Person", name }));
}

export function buildEventStructuredData({
  event,
  locale,
  eventId,
  baseUrl,
  canonicalUrl,
  imageUrl,
  displayName,
  displayDescription,
  displayLocationName,
  displayLocationAddress,
}: BuildStructuredDataParams): Record<string, unknown> {
  const flags = getPublicationPresentationFlags(event);

  if (flags.isPurePublication) {
    const type = isNdlPeriodicalArticle(event) ? "Article" : "Book";
    const publisherName = getEventOrganizer(event, locale) || event.organizer || null;
    const publisherUrl = getValidatedPublisherWebsite(event);
    const authors = getStructuredAuthors(event, locale);

    const structured: Record<string, unknown> = {
      "@context": "https://schema.org",
      "@type": type,
      name: displayName ?? event.name_ja ?? undefined,
      description: displayDescription ?? undefined,
      url: canonicalUrl,
      image: imageUrl,
      datePublished: event.start_date ?? undefined,
    };

    if (type === "Article") {
      structured.headline = displayName ?? event.name_ja ?? undefined;
    }

    if (publisherName) {
      structured.publisher = {
        "@type": "Organization",
        name: publisherName,
        ...(publisherUrl ? { url: publisherUrl } : {}),
      };
    }

    if (authors.length === 1) {
      structured.author = authors[0];
    } else if (authors.length > 1) {
      structured.author = authors;
    }

    return structured;
  }

  const EVENT_STATUS_MAP: Record<string, string> = {
    scheduled: "https://schema.org/EventScheduled",
    cancelled: "https://schema.org/EventCancelled",
    postponed: "https://schema.org/EventPostponed",
    rescheduled: "https://schema.org/EventRescheduled",
  };

  const organizerLd = event.organizer
    ? {
        "@type": "Organization",
        name: getEventOrganizer(event, locale) || event.organizer,
        ...(event.organizer_url ?? event.official_url
          ? { url: event.organizer_url ?? event.official_url }
          : {}),
      }
    : { "@type": "Organization", name: "Tokyo Taiwan Radar", url: baseUrl };

  const performerString = getEventPerformer(event, locale);
  const performerLd =
    event.performers && event.performers.length > 0
      ? event.performers.map((name) => ({ "@type": "Person", name }))
      : performerString
        ? { "@type": "Person", name: performerString }
        : null;

  const directorLd = event.director
    ? { "@type": "Person", name: getEventDirector(event, locale) }
    : null;

  const isOnline =
    displayLocationName === "オンライン" ||
    displayLocationName === "線上" ||
    displayLocationName === "Online";

  let locationLd: Record<string, unknown>;
  let attendanceMode: string;

  if (isOnline) {
    attendanceMode = "https://schema.org/OnlineEventAttendanceMode";
    locationLd = {
      "@type": "VirtualLocation",
      url: event.official_url ?? event.source_url ?? `${baseUrl}/${locale}/events/${eventId}`,
    };
  } else if (displayLocationName) {
    attendanceMode = "https://schema.org/OfflineEventAttendanceMode";
    locationLd = {
      "@type": "Place",
      name: displayLocationName,
      address: displayLocationAddress
        ? {
            "@type": "PostalAddress",
            streetAddress: displayLocationAddress,
            addressCountry: "JP",
          }
        : { "@type": "PostalAddress", addressCountry: "JP" },
    };
  } else {
    attendanceMode = "https://schema.org/OfflineEventAttendanceMode";
    locationLd = {
      "@type": "Place",
      name: locale === "en" ? "Japan" : "日本",
      address: { "@type": "PostalAddress", addressCountry: "JP" },
    };
  }

  const offerUrl = event.official_url ?? event.source_url;
  const priceCurrency = event.price_currency ?? "JPY";
  let offersLd: Record<string, unknown> | null = null;

  if (event.is_paid === false) {
    offersLd = {
      "@type": "Offer",
      price: "0",
      priceCurrency,
      availability: "https://schema.org/InStock",
      ...(event.scraped_at ? { validFrom: event.scraped_at } : {}),
      ...(offerUrl ? { url: offerUrl } : {}),
    };
  } else if (event.is_paid === true) {
    offersLd = {
      "@type": "Offer",
      priceCurrency,
      ...(event.price_amount != null ? { price: String(event.price_amount) } : {}),
      availability: "https://schema.org/InStock",
      ...(event.scraped_at ? { validFrom: event.scraped_at } : {}),
      ...(offerUrl ? { url: offerUrl } : {}),
    };
  }

  return {
    "@context": "https://schema.org",
    "@type": "Event",
    name: displayName ?? event.name_ja ?? undefined,
    startDate: event.start_date ?? undefined,
    endDate: event.end_date ?? undefined,
    description: displayDescription ?? undefined,
    url: canonicalUrl,
    image: imageUrl,
    eventAttendanceMode: attendanceMode,
    eventStatus: EVENT_STATUS_MAP[event.event_status ?? "scheduled"],
    location: locationLd,
    organizer: organizerLd,
    ...(performerLd ? { performer: performerLd } : {}),
    ...(directorLd ? { director: directorLd } : {}),
    ...(offersLd ? { offers: offersLd } : {}),
    ...(event.is_paid === false ? { isAccessibleForFree: true } : {}),
  };
}

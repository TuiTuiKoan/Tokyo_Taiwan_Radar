import assert from "node:assert/strict";
import test from "node:test";

import { getPublicationPresentationFlags } from "../lib/types";
import {
  buildCanonicalSourceLinks,
  getDetailPresentationPolicy,
  getReportExcludedDetailFields,
} from "../lib/publicationPresentation";
import { buildEventStructuredData } from "../lib/publicationStructuredData";
import {
  ordinaryEventFixture,
  physicalBooksMediaTalkFixture,
  pureBookFixture,
  pureNdlPeriodicalFixture,
} from "./fixtures/publication-matrix.fixtures";

function parseJsonLdScript(jsonLd: Record<string, unknown>): Record<string, unknown> {
  const script = `<script type=\"application/ld+json\">${JSON.stringify(jsonLd)}</script>`;
  const match = script.match(/<script[^>]*>([\s\S]*)<\/script>/);
  if (!match) {
    throw new Error("Failed to parse JSON-LD script");
  }
  return JSON.parse(match[1]) as Record<string, unknown>;
}

function buildLd(event: typeof pureBookFixture): Record<string, unknown> {
  return buildEventStructuredData({
    event,
    locale: "en",
    eventId: event.id,
    baseUrl: "https://tokyotaiwanradar.com",
    canonicalUrl: `https://tokyotaiwanradar.com/en/events/${event.id}`,
    imageUrl: `https://tokyotaiwanradar.com/en/events/${event.id}/opengraph-image`,
    displayName: event.name_en,
    displayDescription: event.description_en,
    displayLocationName: event.location_name_en,
    displayLocationAddress: event.location_address_en,
  });
}

test("acceptance matrix: pure publication fixtures hide event-only surfaces", () => {
  const pureBookFlags = getPublicationPresentationFlags(pureBookFixture);
  const purePeriodicalFlags = getPublicationPresentationFlags(pureNdlPeriodicalFixture);

  assert.equal(pureBookFlags.isPurePublication, true);
  assert.equal(purePeriodicalFlags.isPurePublication, true);
  assert.equal(pureBookFlags.hideEnd, true);
  assert.equal(pureBookFlags.hideVenue, true);
  assert.equal(pureBookFlags.hideHours, true);
  assert.equal(pureBookFlags.hidePrice, true);
  assert.equal(pureBookFlags.hideCalendar, true);
  assert.equal(pureBookFlags.hideEventStatus, true);

  const detailPolicy = getDetailPresentationPolicy(pureBookFixture);
  assert.equal(detailPolicy.showEndDate, false);
  assert.equal(detailPolicy.showVenue, false);
  assert.equal(detailPolicy.showAddress, false);
  assert.equal(detailPolicy.showBusinessHours, false);
  assert.equal(detailPolicy.showPrice, false);
  assert.equal(detailPolicy.showCalendar, false);
  assert.equal(detailPolicy.showFaqWhere, false);
  assert.equal(detailPolicy.showFaqPrice, false);
  assert.equal(detailPolicy.showFaqEndRange, false);

  assert.deepEqual(getReportExcludedDetailFields(pureBookFixture), [
    "end_date",
    "venue",
    "address",
    "business_hours",
    "price",
  ]);
});

test("acceptance matrix: physical books_media talk keeps full event presentation", () => {
  const flags = getPublicationPresentationFlags(physicalBooksMediaTalkFixture);
  const detailPolicy = getDetailPresentationPolicy(physicalBooksMediaTalkFixture);

  assert.equal(flags.isPurePublication, false);
  assert.equal(flags.hideEnd, false);
  assert.equal(flags.hideVenue, false);
  assert.equal(flags.hideHours, false);
  assert.equal(flags.hidePrice, false);
  assert.equal(flags.hideCalendar, false);
  assert.equal(flags.hideEventStatus, false);

  assert.equal(detailPolicy.showEndDate, true);
  assert.equal(detailPolicy.showAddress, true);
  assert.equal(detailPolicy.showBusinessHours, true);
  assert.equal(detailPolicy.showPrice, true);
  assert.equal(detailPolicy.showCalendar, true);
  assert.equal(detailPolicy.showFaqWhere, true);
  assert.equal(detailPolicy.showFaqPrice, true);
  assert.deepEqual(getReportExcludedDetailFields(physicalBooksMediaTalkFixture), []);
});

test("acceptance matrix: ordinary non-publication event remains Event semantics", () => {
  const flags = getPublicationPresentationFlags(ordinaryEventFixture);
  assert.equal(flags.isPurePublication, false);
  assert.equal(flags.hideEnd, false);
  assert.equal(flags.hideVenue, false);
  assert.equal(flags.hideHours, false);
  assert.equal(flags.hidePrice, false);
  assert.equal(flags.hideCalendar, false);
  assert.equal(flags.hideEventStatus, false);
});

test("detail source links use canonical dedupe and preserve publisher website when unique", () => {
  const deduped = buildCanonicalSourceLinks({
    ...pureBookFixture,
    official_url: "https://publisher.example.test/books/123/",
    organizer_url: "https://publisher.example.test/books/123",
    source_url: "https://hanmoto.example.test/books/123",
    submission_url: null,
  });
  assert.equal(deduped.filter((link) => link.labelKey === "publisherWebsite").length, 0);

  const withUniquePublisher = buildCanonicalSourceLinks({
    ...pureBookFixture,
    official_url: "https://book.example.test/123",
    organizer_url: "https://publisher.example.test/",
    source_url: "https://hanmoto.example.test/books/123",
    submission_url: null,
  });
  assert.equal(withUniquePublisher.some((link) => link.labelKey === "publisherWebsite"), true);
});

test("JSON-LD: ordinary pure publication emits Book without event-only keys", () => {
  const parsed = parseJsonLdScript(buildLd(pureBookFixture));

  assert.equal(parsed["@type"], "Book");
  assert.equal(parsed.datePublished, pureBookFixture.start_date);
  assert.equal((parsed.publisher as { name?: string }).name, "Example Organizer en");
  assert.equal((parsed.publisher as { url?: string }).url, "https://publisher.example.test/");

  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "endDate"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "location"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "eventAttendanceMode"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "eventStatus"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "offers"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "isAccessibleForFree"), false);

  // polluted single-field multi-person name must not become author
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "author"), false);
});

test("JSON-LD: NDL periodical pure publication emits Article and guarded author array", () => {
  const parsed = parseJsonLdScript(buildLd(pureNdlPeriodicalFixture));

  assert.equal(parsed["@type"], "Article");
  assert.equal(parsed.headline, pureNdlPeriodicalFixture.name_en);
  assert.equal(parsed.datePublished, pureNdlPeriodicalFixture.start_date);
  const author = parsed.author as Array<{ "@type": string; name: string }>;
  assert.equal(Array.isArray(author), true);
  assert.deepEqual(
    author.map((item) => item.name),
    ["Author One", "Author Two"]
  );

  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "endDate"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "location"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "eventAttendanceMode"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "eventStatus"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "offers"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "isAccessibleForFree"), false);
});

test("JSON-LD: physical books_media talk remains Event schema", () => {
  const parsed = parseJsonLdScript(buildLd(physicalBooksMediaTalkFixture));

  assert.equal(parsed["@type"], "Event");
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "startDate"), true);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "endDate"), true);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "location"), true);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "eventAttendanceMode"), true);
  assert.equal(Object.prototype.hasOwnProperty.call(parsed, "eventStatus"), true);
});

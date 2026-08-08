import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  getPublicationPresentationFlags,
  isNdlPeriodicalArticle,
  isPublicationMetricIntentionalNull,
  isPurePublicationRecord,
  normalizeEventForms,
  type Event,
} from "../lib/types";
import {
  getDetailPresentationPolicy,
  getOrganizerFieldLabelKeys,
  getOrganizerSectionTitleKey,
  getReportExcludedDetailFields,
} from "../lib/publicationPresentation";
import { isShelfEvent } from "../lib/eventClassify";

const MESSAGES_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../messages");

function fixture(overrides: Partial<Event>): Event {
  return {
    id: "fixture",
    source_name: "fixture",
    source_id: "fixture",
    source_url: "https://example.test/item",
    original_language: "ja",
    name_ja: "Fixture",
    name_zh: null,
    name_en: null,
    description_ja: null,
    description_zh: null,
    description_en: null,
    category: [],
    start_date: "2026-07-11T00:00:00Z",
    end_date: null,
    location_name: null,
    location_name_zh: null,
    location_name_en: null,
    location_address: null,
    location_address_zh: null,
    location_address_en: null,
    location_url: null,
    business_hours: null,
    business_hours_zh: null,
    business_hours_en: null,
    is_paid: null,
    price_info: null,
    is_active: true,
    parent_event_id: null,
    raw_title: null,
    raw_description: null,
    secondary_source_urls: null,
    record_links: null,
    selection_reason: null,
    annotation_status: "annotated",
    annotated_at: null,
    scraped_at: null,
    created_at: "2026-07-11T00:00:00Z",
    updated_at: "2026-07-11T00:00:00Z",
    ...overrides,
  };
}

test("normalizes duplicate and blank event forms", () => {
  assert.deepEqual(normalizeEventForms([" publication ", "", null, "publication"]), ["publication"]);
});

test("only exact normalized publication form is pure", () => {
  assert.equal(isPurePublicationRecord(fixture({ event_form: ["publication"] })), true);
  assert.equal(isPurePublicationRecord(fixture({ event_form: [" publication ", "publication"] })), true);
  assert.equal(isPurePublicationRecord(fixture({ event_form: ["publication", "lecture"] })), false);
});

test("source category and title never replace the pure invariant", () => {
  const physicalTalk = fixture({
    source_name: "eslite_spectrum",
    category: ["books_media"],
    name_ja: "[新刊出版] 発売記念トーク",
    event_form: ["lecture"],
  });
  assert.equal(isPurePublicationRecord(physicalTalk), false);
  assert.equal(getPublicationPresentationFlags(physicalTalk).hidePrice, false);
  assert.equal(isPurePublicationRecord(fixture({ source_name: "hanmoto", event_form: null })), false);
});

test("pure book hides every event-only presentation surface", () => {
  const flags = getPublicationPresentationFlags(fixture({ event_form: ["publication"] }));
  assert.deepEqual(flags, {
    isPurePublication: true,
    hideEnd: true,
    hideVenue: true,
    hideHours: true,
    hidePrice: true,
    hideCalendar: true,
    hideEventStatus: true,
  });
});

test("pure publication metric exemptions do not include location_name", () => {
  const publication = fixture({ event_form: ["publication"] });
  assert.equal(isPublicationMetricIntentionalNull(publication, "location_address"), true);
  assert.equal(isPublicationMetricIntentionalNull(publication, "location_prefectures"), true);
  assert.equal(isPublicationMetricIntentionalNull(publication, "location_name"), false);
  assert.equal(
    isPublicationMetricIntentionalNull(fixture({ event_form: ["lecture"] }), "location_address"),
    false
  );
});

test("NDL periodical requires record-family URL evidence", () => {
  const periodical = fixture({
    source_name: "ndl_opensearch",
    event_form: ["publication"],
    source_url: "https://ndlsearch.ndl.go.jp/books/item?recordFamily=R000000004",
  });
  assert.equal(isNdlPeriodicalArticle(periodical), true);
  assert.equal(isNdlPeriodicalArticle({ ...periodical, event_form: ["lecture"] }), false);
  assert.equal(isNdlPeriodicalArticle({ ...periodical, source_url: "https://ndlsearch.ndl.go.jp/books/item" }), false);
});

test("ordinary non-publication event keeps event presentation", () => {
  const flags = getPublicationPresentationFlags(fixture({ event_form: ["screening"] }));
  assert.equal(flags.isPurePublication, false);
  assert.equal(flags.hideEnd, false);
  assert.equal(flags.hideVenue, false);
  assert.equal(flags.hideHours, false);
  assert.equal(flags.hidePrice, false);
  assert.equal(flags.hideCalendar, false);
  assert.equal(flags.hideEventStatus, false);
});

test("detail policy hides the venue row only for pure publications", () => {
  assert.equal(getDetailPresentationPolicy(fixture({ event_form: ["publication"] })).showVenue, false);
  assert.equal(getDetailPresentationPolicy(fixture({ event_form: ["screening"] })).showVenue, true);
});

test("venue is not reportable when the venue row is hidden", () => {
  assert.ok(
    getReportExcludedDetailFields(fixture({ event_form: ["publication"] })).includes("venue")
  );
  assert.deepEqual(getReportExcludedDetailFields(fixture({ event_form: ["screening"] })), []);
});

test("noisy event_form values still resolve to pure and hide the venue", () => {
  const noisy = fixture({ event_form: [" publication ", "publication", ""] });
  assert.equal(getDetailPresentationPolicy(noisy).showVenue, false);
  assert.ok(getReportExcludedDetailFields(noisy).includes("venue"));
});

test("mixed publication form keeps the venue row visible", () => {
  const mixed = fixture({ event_form: ["publication", "lecture"] });
  assert.equal(getDetailPresentationPolicy(mixed).showVenue, true);
  assert.deepEqual(getReportExcludedDetailFields(mixed), []);
});

test("exact pure publication never enters the long-term shelf", () => {
  // Vision-polluted books span ~874 days (2023-10-14 → 2026-xx). They must never
  // surface on the horizontal shelf even though their run is longer than 30 days.
  const longRun = fixture({
    event_form: ["publication"],
    start_date: "2024-01-01T00:00:00Z",
    end_date: "2026-05-24T00:00:00Z", // ~874 days
  });
  assert.equal(isShelfEvent(longRun), false);

  // Normalized duplicates / blanks that still resolve to pure publication are excluded too.
  const normalizedPure = fixture({
    event_form: [" publication ", "publication", ""],
    start_date: "2024-01-01T00:00:00Z",
    end_date: "2026-05-24T00:00:00Z",
  });
  assert.equal(isShelfEvent(normalizedPure), false);
});

test("exact pure publication is never persistent even without an end date", () => {
  const onlinePure = fixture({
    event_form: ["publication"],
    name_ja: "オンライン新刊フェア",
    start_date: "2026-01-01T00:00:00Z",
    end_date: null,
  });
  assert.equal(isShelfEvent(onlinePure), false);
});

test("mixed publication + lecture keeps normal shelf behavior", () => {
  const longMixed = fixture({
    event_form: ["publication", "lecture"],
    start_date: "2026-01-01T00:00:00Z",
    end_date: "2026-02-15T00:00:00Z", // 45 days > 30
  });
  assert.equal(isShelfEvent(longMixed), true);

  const shortMixed = fixture({
    event_form: ["publication", "lecture"],
    start_date: "2026-01-01T00:00:00Z",
    end_date: "2026-01-25T00:00:00Z", // 24 days <= 30, no online marker
  });
  assert.equal(isShelfEvent(shortMixed), false);
});

test("ordinary long-term event still belongs on the shelf", () => {
  const longExhibit = fixture({
    event_form: ["exhibition"],
    start_date: "2026-01-01T00:00:00Z",
    end_date: "2026-03-01T00:00:00Z", // 59 days > 30
  });
  assert.equal(isShelfEvent(longExhibit), true);
});

test("organizer section title switches only for exact pure publications", () => {
  assert.equal(
    getOrganizerSectionTitleKey(fixture({ event_form: ["publication"] })),
    "publicationSection"
  );
  assert.equal(
    getOrganizerSectionTitleKey(fixture({ event_form: [" publication ", "publication"] })),
    "publicationSection"
  );
  assert.equal(
    getOrganizerSectionTitleKey(fixture({ event_form: ["publication", "lecture"] })),
    "organizerSection"
  );
  assert.equal(getOrganizerSectionTitleKey(fixture({ event_form: ["screening"] })), "organizerSection");
});

test("exact pure publication uses publisher field label keys", () => {
  assert.deepEqual(getOrganizerFieldLabelKeys(fixture({ event_form: ["publication"] })), {
    organizer: { intakeKey: "fieldPublisher", adminKey: "publisher" },
    organizerUrl: { intakeKey: "fieldPublisherUrl", adminKey: "publisherUrl" },
    placeholder: { intakeKey: "fieldPublisherPlaceholder", adminKey: "publisherPlaceholder" },
  });
});

test("mixed and ordinary events keep organizer field label keys", () => {
  const organizerKeys = {
    organizer: { intakeKey: "fieldOrganizer", adminKey: "organizer" },
    organizerUrl: { intakeKey: "fieldOrganizerUrl", adminKey: "organizerUrl" },
    placeholder: null,
  };
  assert.deepEqual(
    getOrganizerFieldLabelKeys(fixture({ event_form: ["publication", "lecture"] })),
    organizerKeys
  );
  assert.deepEqual(getOrganizerFieldLabelKeys(fixture({ event_form: ["screening"] })), organizerKeys);
  assert.deepEqual(getOrganizerFieldLabelKeys(fixture({ event_form: null })), organizerKeys);
});

// assert-i18n-parity.ts only proves the three key sets match, so it stays green
// when every locale drops the same key. This checks presence per locale.
test("publication label keys are present in every locale", () => {
  const requiredKeys: [namespace: string, key: string][] = [
    ["event", "publicationSection"],
    ["event", "organizerSection"],
    ["admin", "publisher"],
    ["admin", "publisherUrl"],
    ["admin", "publisherPlaceholder"],
  ];

  for (const locale of ["ja", "zh", "en"]) {
    const messages = JSON.parse(
      fs.readFileSync(path.join(MESSAGES_DIR, `${locale}.json`), "utf8")
    ) as Record<string, Record<string, unknown> | undefined>;

    for (const [namespace, key] of requiredKeys) {
      const value = messages[namespace]?.[key];
      assert.equal(typeof value, "string", `${locale}: ${namespace}.${key} must be a string`);
      assert.notEqual(value, "", `${locale}: ${namespace}.${key} must not be empty`);
    }
  }
});

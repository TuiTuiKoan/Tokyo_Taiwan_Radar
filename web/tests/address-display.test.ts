import assert from "node:assert/strict";
import test from "node:test";

import { extractPostalCode, stripPostalCode } from "../lib/addressDisplay";

// Addresses below are values stored in production on 2026-11-22.
const CASES: Array<[string, string, string | null]> = [
  ["〒163-0210 東京都新宿区西新宿2-6-1 新宿住友ビル10階", "東京都新宿区西新宿2-6-1 新宿住友ビル10階", "163-0210"],
  ["〒059‐0902　北海道白老郡白老町若草町2丁目３", "北海道白老郡白老町若草町2丁目３", "059-0902"],
  ["日本、〒106-0045 東京都港区麻布十番２丁目１４−９ 2f", "東京都港区麻布十番２丁目１４−９ 2f", "106-0045"],
  ["〒310-0015　茨城県水戸市宮町1丁目7", "茨城県水戸市宮町1丁目7", "310-0015"],
  ["2F, 12-8 Sarugaku-cho, Shibuya-ku, Tokyo 150-0033", "2F, 12-8 Sarugaku-cho, Shibuya-ku, Tokyo", "150-0033"],
  ["2 Chome-6-1 Nishishinjuku, Shinjuku City, Tokyo 160-0023 日本", "2 Chome-6-1 Nishishinjuku, Shinjuku City, Tokyo", "160-0023"],
  ["106臺北市大安區復興南路一段107巷5弄18號B1樓", "106臺北市大安區復興南路一段107巷5弄18號B1樓", null],
  ["東京都港区虎ノ門1-1-12 虎ノ門ビル2階", "東京都港区虎ノ門1-1-12 虎ノ門ビル2階", null],
  // A lot number that looks like a postal code is left alone when it is not at an end.
  ["長野県松本市蟻ヶ崎2455-11", "長野県松本市蟻ヶ崎2455-11", null],
  ["郵便番号：150-0033 東京都渋谷区猿楽町16-15", "東京都渋谷区猿楽町16-15", "150-0033"],
  ["東京大学（〒113-0033 東京都文京区本郷7-3-1）", "東京大学（東京都文京区本郷7-3-1）", "113-0033"],
];

test("stripPostalCode removes postal codes and a bare country name", () => {
  for (const [input, expected] of CASES) {
    assert.equal(stripPostalCode(input), expected, input);
  }
});

test("extractPostalCode returns the code as NNN-NNNN", () => {
  for (const [input, , expected] of CASES) {
    assert.equal(extractPostalCode(input), expected, input);
  }
});

test("phone numbers are not postal codes", () => {
  assert.equal(stripPostalCode("姫路市観光コンベンション室：079-221-1520"), "姫路市観光コンベンション室：079-221-1520");
  assert.equal(extractPostalCode("090-1234-5678"), null);
});

test("empty and missing values", () => {
  assert.equal(stripPostalCode(null), null);
  assert.equal(stripPostalCode(undefined), null);
  assert.equal(stripPostalCode("〒163-0210"), null);
  assert.equal(extractPostalCode(""), null);
});

test("structured data carries the stripped postal code as postalCode", async () => {
  const { buildEventStructuredData } = await import("../lib/publicationStructuredData");
  const { ordinaryEventFixture } = await import("./fixtures/publication-matrix.fixtures");
  const stored = "〒163-0210 東京都新宿区西新宿2-6-1 新宿住友ビル10階";
  const event = { ...ordinaryEventFixture, location_name: "新宿住友ビル", location_address: stored };
  const build = (postal: string | null) =>
    buildEventStructuredData({
      event,
      locale: "ja",
      eventId: event.id,
      baseUrl: "https://tokyotaiwanradar.com",
      canonicalUrl: `https://tokyotaiwanradar.com/ja/events/${event.id}`,
      imageUrl: `https://tokyotaiwanradar.com/ja/events/${event.id}/opengraph-image`,
      displayName: event.name_ja,
      displayDescription: event.description_ja,
      displayLocationName: "新宿住友ビル",
      displayLocationAddress: stripPostalCode(stored),
      displayPostalCode: postal,
    }) as { location: { address: Record<string, unknown> } };

  assert.deepEqual(build(extractPostalCode(stored)).location.address, {
    "@type": "PostalAddress",
    streetAddress: "東京都新宿区西新宿2-6-1 新宿住友ビル10階",
    postalCode: "163-0210",
    addressCountry: "JP",
  });
  assert.equal("postalCode" in build(null).location.address, false);
});

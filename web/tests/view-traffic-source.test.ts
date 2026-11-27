import { test } from "node:test";
import assert from "node:assert/strict";

import { resolveViewTrafficSource } from "../lib/analytics/trafficSource";

const OWN_PAGE = "https://tokyotaiwanradar.com/ja/events/abc";

test("client referrer wins over the action's own-page Referer header", () => {
  assert.equal(resolveViewTrafficSource(null, "https://www.google.com/", OWN_PAGE), "google");
  assert.equal(resolveViewTrafficSource(null, "https://www.google.co.jp/", OWN_PAGE), "google");
  assert.equal(resolveViewTrafficSource(null, "https://l.instagram.com/?u=x", OWN_PAGE), "instagram");
  assert.equal(resolveViewTrafficSource(null, "https://t.co/xyz", OWN_PAGE), "twitter");
});

test("empty client referrer is direct, not the header", () => {
  assert.equal(resolveViewTrafficSource(null, "", "https://www.google.com/"), "direct");
});

test("utm_source still takes priority", () => {
  assert.equal(resolveViewTrafficSource("line", "https://www.google.com/", OWN_PAGE), "line");
});

test("old clients without a referrer argument fall back to the header", () => {
  assert.equal(resolveViewTrafficSource(null, undefined, OWN_PAGE), "direct");
  assert.equal(resolveViewTrafficSource(null, undefined, "https://www.bing.com/"), "other");
});

test("own-site referrer stays direct", () => {
  assert.equal(resolveViewTrafficSource(null, "https://tokyotaiwanradar.com/ja", OWN_PAGE), "direct");
});

import assert from "node:assert/strict";
import test from "node:test";

import {
  isSameOrigin,
  MAX_BODY_BYTES,
  MAX_DWELL_MS,
  outboundTarget,
  parseBatch,
  parseUserAgent,
  trafficSourceFor,
} from "../lib/analytics/guideTrack";
import { classifyReferrer } from "../lib/analytics/trafficSource";

const SLUG = "202611/synchronic-constellation";
const SID = "0123456789abcdef01234567";
const IPHONE_SAFARI =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1";
const IPHONE_LINE =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari Line/14.19.0";
const ctx = { userAgent: IPHONE_SAFARI, country: "jp", region: "13" };

function batch(events: unknown[], extra: Record<string, unknown> = {}) {
  return JSON.stringify({ slug: SLUG, sid: SID, ref: "https://www.google.com/", utm: {}, events, ...extra });
}

test("event_views classification is unchanged without the ai option", () => {
  assert.equal(classifyReferrer("https://chatgpt.com/"), "other");
  assert.equal(classifyReferrer("https://gemini.google.com/app"), "google");
  assert.equal(classifyReferrer("https://l.instagram.com/?u=x"), "instagram");
  assert.equal(classifyReferrer("https://tokyotaiwanradar.com/ja"), "direct");
  assert.equal(classifyReferrer(null), "direct");
  assert.equal(classifyReferrer("not a url"), "other");
});

test("the ai option recognises AI engines before google", () => {
  assert.equal(classifyReferrer("https://chatgpt.com/", { ai: true }), "chatgpt");
  assert.equal(classifyReferrer("https://www.perplexity.ai/search", { ai: true }), "perplexity");
  assert.equal(classifyReferrer("https://gemini.google.com/app", { ai: true }), "gemini");
  assert.equal(classifyReferrer("https://www.google.co.jp/", { ai: true }), "google");
});

test("an empty referrer inside LINE counts as line, UTM wins over both", () => {
  assert.equal(trafficSourceFor("", null, "line"), "line");
  assert.equal(trafficSourceFor("", null, null), "direct");
  assert.equal(trafficSourceFor("https://www.google.com/", "ig", "line"), "instagram");
});

test("user agents map to coarse labels only", () => {
  assert.deepEqual(parseUserAgent(IPHONE_SAFARI), { device: "mobile", browser: "safari", inApp: null });
  assert.deepEqual(parseUserAgent(IPHONE_LINE), { device: "mobile", browser: "in_app", inApp: "line" });
  assert.equal(parseUserAgent("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) Version/17.0 Safari/604.1").device, "tablet");
  assert.equal(
    parseUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36").browser,
    "chrome",
  );
  assert.equal(parseUserAgent(null).device, "desktop");
});

test("only same-origin posts are accepted", () => {
  assert.equal(isSameOrigin("https://tokyotaiwanradar.com", "same-origin", "tokyotaiwanradar.com"), true);
  assert.equal(isSameOrigin(null, "same-origin", "tokyotaiwanradar.com"), true);
  assert.equal(isSameOrigin("https://evil.example", null, "tokyotaiwanradar.com"), false);
  assert.equal(isSameOrigin("https://tokyotaiwanradar.com", "cross-site", "tokyotaiwanradar.com"), false);
  assert.equal(isSameOrigin(null, null, "tokyotaiwanradar.com"), false);
});

test("a valid batch becomes rows with server-side classification", () => {
  const r = parseBatch(
    batch([
      { t: "view", kind: "chapter", id: "ch2", seq: 1, lang: "ja" },
      { t: "leave", kind: "chapter", id: "ch2", seq: 1, ms: 4200, lang: "ja" },
      { t: "search", q: "  陳澄波 ", n: 3, via: "chip", lang: "zh" },
      { t: "outbound", url: "https://www.mot-art-museum.jp/x.pdf?token=1#p", lang: "en" },
      { t: "lang", to: "en" },
    ]),
    ctx,
  );
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(r.rows.length, 5);
  const [view, leave, search, out, lang] = r.rows;
  assert.equal(view.view_kind, "chapter");
  assert.equal(view.traffic_source, "google");
  assert.equal(view.referrer_host, "www.google.com");
  assert.equal(view.country, "JP");
  assert.equal(view.device, "mobile");
  assert.equal(leave.dwell_ms, 4200);
  assert.equal(search.search_query, "陳澄波");
  assert.equal(search.target, "chip");
  assert.equal(out.target, "https://www.mot-art-museum.jp/x.pdf");
  assert.equal(lang.target, "en");
});

test("invalid slugs, sessions and oversize bodies are rejected", () => {
  assert.deepEqual(parseBatch(batch([], { slug: "202611/other" }), ctx), { ok: false, status: 400, error: "bad_slug" });
  assert.deepEqual(parseBatch(batch([], { sid: "x" }), ctx), { ok: false, status: 400, error: "bad_session" });
  assert.deepEqual(parseBatch("{", ctx), { ok: false, status: 400, error: "bad_json" });
  assert.deepEqual(parseBatch("x".repeat(MAX_BODY_BYTES + 1), ctx), { ok: false, status: 413, error: "too_large" });
});

test("bad events are skipped, values are capped, and the batch is limited to 20", () => {
  const r = parseBatch(
    batch([
      { t: "drop_table" },
      { t: "view", kind: "home", id: "should-be-cleared", seq: 0 },
      { t: "view", kind: "work" },
      { t: "leave", kind: "doc", id: "D1-001", seq: 2, ms: 99_999_999 },
      { t: "search", q: "" },
      { t: "outbound", url: "javascript:alert(1)" },
      { t: "lang", to: "fr" },
      { t: "view", kind: "doc", id: "<script>", seq: 3 },
    ]),
    ctx,
  );
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(r.rows.length, 3);
  assert.equal(r.rows[0].view_id, null);
  assert.equal(r.rows[1].dwell_ms, MAX_DWELL_MS);
  assert.equal(r.rows[2].view_id, null);

  const many = Array.from({ length: 30 }, (_, i) => ({ t: "view", kind: "home", seq: i }));
  const r2 = parseBatch(batch(many), ctx);
  assert.ok(r2.ok && r2.rows.length === 20);
});

test("outbound targets drop query strings and fragments", () => {
  assert.equal(outboundTarget("mailto:tokyotaiwanradar@gmail.com?subject=hi"), "mailto:tokyotaiwanradar@gmail.com");
  assert.equal(outboundTarget("https://tokyotaiwanradar.com/ja?utm_source=x"), "https://tokyotaiwanradar.com/ja");
  assert.equal(outboundTarget("ftp://x"), null);
});

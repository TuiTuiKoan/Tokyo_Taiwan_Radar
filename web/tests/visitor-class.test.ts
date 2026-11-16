import assert from "node:assert/strict";
import test from "node:test";

import { AEO_BOT_PATTERNS, classifyVisitor, detectAeoBot } from "../lib/analytics/botDetect";
import { parseVisitorFilter, visitorClassesFor } from "../lib/analytics/visitorFilter";

const LANG = "ja,en-US;q=0.9,en;q=0.8";

const HUMANS: Record<string, string> = {
  iphoneSafari:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
  iphoneLine:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari Line/14.19.0",
  instagramInApp:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 350.0.0.0.0",
  androidChrome:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
  cubotPhone:
    "Mozilla/5.0 (Linux; Android 12; CUBOT X50) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
  macChrome:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  winFirefox: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
  winEdge:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
};

// The bots seen in event_views on 2026-11-16, plus the other AEO entries.
const KNOWN: Array<[string, string]> = [
  ["Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html) Chrome/131.0.6778.204 Safari/537.36", "Googlebot"],
  ["Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.204 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", "Googlebot"],
  ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)", "Applebot"],
  ["Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm) Chrome/116.0.1938.76 Safari/537.36", "Bingbot"],
  ["meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)", "Meta-ExternalAgent"],
  ["Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot", "OAI-SearchBot"],
  ["Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot", "GPTBot"],
  ["Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", "ClaudeBot"],
  ["Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", "PerplexityBot"],
  ["DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)", "DuckDuckBot"],
  ["Mozilla/5.0 (Linux; Android 5.0) AppleWebKit/537.36 (KHTML, like Gecko) Mobile Safari/537.36 (compatible; Bytespider; spider-feedback@bytedance.com)", "Bytespider"],
];

const GENERIC: Array<[string, string]> = [
  ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/131.0.0.0 Safari/537.36", "HeadlessChrome"],
  ["python-requests/2.32.3", "python"],
  ["curl/8.7.1", "curl"],
  ["Go-http-client/2.0", "go"],
  ["Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)", "bot"],
  ["Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)", "bot"],
  ["Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Amazonbot/0.1; +https://developer.amazon.com/support/amazonbot) Chrome/119.0.6045.214 Safari/537.36", "Amazonbot"],
  ["Mozilla/5.0 (Linux; Android 11; moto g power (2022)) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36 Chrome-Lighthouse", "Lighthouse"],
  ["facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)", "facebookexternalhit"],
];

test("real browsers with Accept-Language are human", () => {
  for (const [name, ua] of Object.entries(HUMANS)) {
    assert.deepEqual(classifyVisitor({ userAgent: ua, acceptLanguage: LANG }), { visitorClass: "human", botName: null }, name);
  }
});

test("AEO bots are known_bot with the aeo_visits name", () => {
  for (const [ua, name] of KNOWN) {
    assert.deepEqual(classifyVisitor({ userAgent: ua, acceptLanguage: LANG }), { visitorClass: "known_bot", botName: name }, ua);
    // Bots that send Accept-Language are still bots.
    assert.equal(classifyVisitor({ userAgent: ua, acceptLanguage: null }).visitorClass, "known_bot");
  }
});

test("generic automation is known_bot/generic", () => {
  for (const [ua, token] of GENERIC) {
    assert.deepEqual(classifyVisitor({ userAgent: ua, acceptLanguage: LANG }), { visitorClass: "known_bot", botName: `generic:${token}` }, ua);
  }
});

test("missing UA or Accept-Language is suspected_bot", () => {
  const noUa = { visitorClass: "suspected_bot", botName: "suspect:no_ua" };
  const noLang = { visitorClass: "suspected_bot", botName: "suspect:no_accept_language" };
  assert.deepEqual(classifyVisitor({ userAgent: null, acceptLanguage: LANG }), noUa);
  assert.deepEqual(classifyVisitor({ userAgent: "  ", acceptLanguage: LANG }), noUa);
  assert.deepEqual(classifyVisitor({ userAgent: HUMANS.macChrome, acceptLanguage: null }), noLang);
  assert.deepEqual(classifyVisitor({ userAgent: HUMANS.macChrome, acceptLanguage: "" }), noLang);
});

test("detectAeoBot keeps proxy.ts behaviour (aeo_visits unchanged)", () => {
  assert.equal(AEO_BOT_PATTERNS.length, 18);
  assert.equal(detectAeoBot(null), null);
  assert.equal(detectAeoBot(HUMANS.macChrome), null);
  // Generic bots are not AEO bots: aeo_visits must not start logging them.
  for (const [ua] of GENERIC) assert.equal(detectAeoBot(ua), null, ua);
  for (const [ua, name] of KNOWN) assert.equal(detectAeoBot(ua), name, ua);
  // Order: ChatGPT-User before generic OpenAI names, Google-Extended before Googlebot.
  assert.equal(detectAeoBot("Mozilla/5.0 ChatGPT-User/1.0"), "ChatGPT-User");
  assert.equal(detectAeoBot("Google-Extended Googlebot"), "Google-Extended");
});

test("visitor filters map to visitor_class sets", () => {
  assert.deepEqual(visitorClassesFor("exclude_bots"), ["human", "unclassified"]);
  assert.deepEqual(visitorClassesFor("human"), ["human"]);
  assert.deepEqual(visitorClassesFor("bots"), ["known_bot", "suspected_bot"]);
  assert.equal(visitorClassesFor("all"), null);
  assert.equal(parseVisitorFilter(null), "exclude_bots");
  assert.equal(parseVisitorFilter("nonsense"), "exclude_bots");
  assert.equal(parseVisitorFilter("bots"), "bots");
});

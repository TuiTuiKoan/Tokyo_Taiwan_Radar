// Bot detection shared by proxy.ts (aeo_visits) and record-view.ts (event_views).
// Pure functions; no request context. Spec: docs/specs/active/view-bot-filter.

/**
 * AEO monitoring — User-Agent → bot name. Moved verbatim from proxy.ts; the
 * names are what aeo_visits.bot_name stores, so do not rename entries.
 * Order matters: more specific patterns first.
 */
export const AEO_BOT_PATTERNS: ReadonlyArray<readonly [RegExp, string]> = [
  [/GPTBot/i, "GPTBot"],
  [/OAI-SearchBot/i, "OAI-SearchBot"],
  [/ChatGPT-User/i, "ChatGPT-User"],
  [/anthropic-ai/i, "Anthropic-ai"],
  [/Claude-Web/i, "Claude-Web"],
  [/ClaudeBot/i, "ClaudeBot"],
  [/PerplexityBot/i, "PerplexityBot"],
  [/Perplexity-User/i, "Perplexity-User"],
  [/Google-Extended/i, "Google-Extended"],
  [/Googlebot/i, "Googlebot"],
  [/bingbot/i, "Bingbot"],
  [/cohere-ai/i, "cohere-ai"],
  [/Meta-ExternalAgent/i, "Meta-ExternalAgent"],
  [/FacebookBot/i, "FacebookBot"],
  [/YouBot/i, "YouBot"],
  [/DuckDuckBot/i, "DuckDuckBot"],
  [/Applebot/i, "Applebot"],
  [/Bytespider/i, "Bytespider"],
];

/** The aeo_visits bot name for a User-Agent, or null. Behaviour unchanged from proxy.ts. */
export function detectAeoBot(ua: string | null | undefined): string | null {
  if (!ua) return null;
  for (const [pattern, name] of AEO_BOT_PATTERNS) {
    if (pattern.test(ua)) return name;
  }
  return null;
}

/**
 * Generic automation / crawler markers that are not in AEO_BOT_PATTERNS.
 * Only used for event_views classification, never for aeo_visits. The matched
 * token is stored as `generic:<token>` so misclassification can be audited.
 */
const GENERIC_BOT_TOKENS: ReadonlyArray<readonly [RegExp, string]> = [
  [/HeadlessChrome/i, "HeadlessChrome"],
  [/Lighthouse/i, "Lighthouse"],
  [/PhantomJS/i, "PhantomJS"],
  [/Puppeteer/i, "Puppeteer"],
  [/Playwright/i, "Playwright"],
  [/Selenium/i, "Selenium"],
  [/python-requests|python-urllib|aiohttp|httpx/i, "python"],
  [/^curl\//i, "curl"],
  [/^wget\//i, "wget"],
  [/Go-http-client/i, "go"],
  [/axios\/|node-fetch|undici/i, "node"],
  [/okhttp/i, "okhttp"],
  [/^Java\/|Apache-HttpClient/i, "java"],
  [/Scrapy/i, "scrapy"],
  [/libwww-perl/i, "perl"],
  [/facebookexternalhit/i, "facebookexternalhit"],
  [/Google-InspectionTool|Mediapartners-Google|Google-Read-Aloud/i, "google-other"],
  [/Amazonbot/i, "Amazonbot"],
  // Catch-all last: "…bot", "bot/…", crawlers and spiders.
  [/bot\b|bot\/|crawl|spider|slurp/i, "bot"],
];

/** The generic automation token for a User-Agent, or null. */
export function detectGenericBot(ua: string): string | null {
  // CUBOT is an Android phone brand whose model names would match "bot\b".
  const cleaned = ua.replace(/\bcubot\b/gi, "");
  for (const [pattern, token] of GENERIC_BOT_TOKENS) {
    if (pattern.test(cleaned)) return token;
  }
  return null;
}

export const VISITOR_CLASSES = ["human", "known_bot", "suspected_bot", "unclassified"] as const;
export type VisitorClass = (typeof VISITOR_CLASSES)[number];

export interface VisitorHeaders {
  userAgent: string | null | undefined;
  acceptLanguage: string | null | undefined;
}

export interface VisitorClassification {
  visitorClass: Exclude<VisitorClass, "unclassified">;
  /**
   * known_bot: aeo_visits bot name, or `generic:<token>`.
   * suspected_bot: `suspect:no_ua` or `suspect:no_accept_language`.
   * human: null.
   */
  botName: string | null;
}

/**
 * Classify one event_views write from its request headers. First match wins:
 * no UA → suspected_bot; AEO bot → known_bot (its name); generic automation →
 * known_bot (`generic:<token>`); no Accept-Language → suspected_bot; otherwise
 * human. Browsers send Accept-Language on fetch (the Server Action transport);
 * many HTTP libraries and older headless setups do not, so it is only "suspected".
 */
export function classifyVisitor({ userAgent, acceptLanguage }: VisitorHeaders): VisitorClassification {
  const ua = userAgent?.trim() ?? "";
  if (!ua) return { visitorClass: "suspected_bot", botName: "suspect:no_ua" };

  const aeo = detectAeoBot(ua);
  if (aeo) return { visitorClass: "known_bot", botName: aeo };

  const generic = detectGenericBot(ua);
  if (generic) return { visitorClass: "known_bot", botName: `generic:${generic}` };

  if (!acceptLanguage?.trim()) return { visitorClass: "suspected_bot", botName: "suspect:no_accept_language" };

  return { visitorClass: "human", botName: null };
}

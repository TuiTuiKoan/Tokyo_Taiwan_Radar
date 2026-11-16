// Traffic-source classification shared by event_views (record-view.ts) and
// guide_events (/api/guide/track). Pure functions; no request context.

export const BASE_SOURCES = [
  "google", "line", "instagram", "threads", "facebook", "twitter", "direct", "other",
] as const;

export const AI_SOURCES = ["perplexity", "chatgpt", "claude", "gemini", "copilot"] as const;

const KNOWN_UTM_SOURCES = new Set<string>(BASE_SOURCES);

/** Normalise a utm_source value to one of BASE_SOURCES, or null when unknown. */
export function normalizeUtmSource(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let v = raw.trim().toLowerCase().slice(0, 32);
  if (v === "x" || v === "x.com") v = "twitter";
  if (v === "ig") v = "instagram";
  if (v === "fb") v = "facebook";
  return KNOWN_UTM_SOURCES.has(v) ? v : null;
}

const AI_HOSTS: Array<[RegExp, (typeof AI_SOURCES)[number]]> = [
  [/(^|\.)perplexity\.ai$/, "perplexity"],
  [/(^|\.)chatgpt\.com$/, "chatgpt"],
  [/^chat\.openai\.com$/, "chatgpt"],
  [/^claude\.ai$/, "claude"],
  [/^gemini\.google\.com$/, "gemini"],
  [/^bard\.google\.com$/, "gemini"],
  [/^copilot\.microsoft\.com$/, "copilot"],
];

export interface ClassifyOptions {
  /** Also recognise AI answer engines. event_views keeps this off so its numbers do not change. */
  ai?: boolean;
}

/**
 * Classify a referrer URL. Own-site and Vercel preview hosts count as direct
 * (internal navigation). With `ai`, AI engines are checked before Google so
 * gemini.google.com is not counted as google.
 */
export function classifyReferrer(referrer: string | null | undefined, opts: ClassifyOptions = {}): string {
  if (!referrer) return "direct";
  let host = "";
  try {
    host = new URL(referrer).hostname.toLowerCase();
  } catch {
    return "other";
  }
  if (opts.ai) {
    for (const [pattern, name] of AI_HOSTS) if (pattern.test(host)) return name;
  }
  if (host.includes("google.")) return "google";
  if (host.includes("line.")) return "line";
  if (host.includes("instagram.")) return "instagram"; // includes l.instagram.com
  if (host.includes("threads.")) return "threads"; // includes l.threads.net
  if (host.includes("facebook.")) return "facebook"; // includes l.facebook.com
  if (host.includes("twitter.") || host === "t.co" || host.includes("x.com")) return "twitter";
  if (host.includes("tokyotaiwanradar.com") || host.includes("vercel.app")) return "direct";
  return "other";
}

/** Hostname of a referrer, lower-cased and capped, or null. */
export function referrerHost(referrer: string | null | undefined): string | null {
  if (!referrer) return null;
  try {
    return new URL(referrer).hostname.toLowerCase().slice(0, 120) || null;
  } catch {
    return null;
  }
}

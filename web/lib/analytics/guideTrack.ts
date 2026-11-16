// Pure helpers for /api/guide/track (spec guide-analytics). No request context,
// so they can be unit-tested with tsx --test.

import { classifyReferrer, normalizeUtmSource, referrerHost } from "./trafficSource";

/** Guides that may write to guide_events. Add a slug here when a new /YYYYMM/* guide ships. */
export const GUIDE_SLUGS = ["202611/synchronic-constellation"] as const;
export type GuideSlug = (typeof GUIDE_SLUGS)[number];

export const MAX_BODY_BYTES = 16 * 1024;
export const MAX_EVENTS_PER_BATCH = 20;
export const MAX_DWELL_MS = 30 * 60 * 1000;

const EVENT_TYPES = new Set(["view", "leave", "search", "outbound", "lang"]);
const VIEW_KINDS = new Set(["home", "chapter", "work", "doc"]);
const LANGS = new Set(["ja", "en", "zh"]);
const SEARCH_TARGETS = new Set(["input", "chip", "artist"]);
const SESSION_RE = /^[A-Za-z0-9_-]{8,40}$/;
const VIEW_ID_RE = /^[A-Za-z0-9-]{1,40}$/;

export interface UaInfo {
  device: "mobile" | "tablet" | "desktop";
  browser: string;
  inApp: string | null;
}

/** Coarse UA classification. Only these labels are stored, never the raw UA. */
export function parseUserAgent(ua: string | null | undefined): UaInfo {
  const s = ua ?? "";
  let inApp: string | null = null;
  if (/\bLine\//i.test(s)) inApp = "line";
  else if (/Barcelona/i.test(s)) inApp = "threads"; // Threads' in-app browser token
  else if (/Instagram/i.test(s)) inApp = "instagram";
  else if (/FBAN|FBAV|FB_IAB/i.test(s)) inApp = "facebook";
  else if (/MicroMessenger/i.test(s)) inApp = "wechat";
  else if (/Twitter/i.test(s)) inApp = "twitter";

  const tablet = /iPad|Tablet/i.test(s) || (/Android/i.test(s) && !/Mobile/i.test(s));
  const mobile = !tablet && /Mobi|iPhone|iPod|Android/i.test(s);
  const device: UaInfo["device"] = tablet ? "tablet" : mobile ? "mobile" : "desktop";

  let browser = "other";
  if (inApp) browser = "in_app";
  else if (/Edg\//.test(s)) browser = "edge";
  else if (/SamsungBrowser/.test(s)) browser = "samsung";
  else if (/CriOS|Chrome\//.test(s)) browser = "chrome";
  else if (/FxiOS|Firefox\//.test(s)) browser = "firefox";
  else if (/Safari\//.test(s) && /Version\//.test(s)) browser = "safari";
  return { device, browser, inApp };
}

/** Allow only same-origin posts. A missing Origin is accepted when Sec-Fetch-Site says same-origin. */
export function isSameOrigin(origin: string | null, secFetchSite: string | null, host: string | null): boolean {
  if (secFetchSite && secFetchSite !== "same-origin") return false;
  if (!origin) return secFetchSite === "same-origin";
  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

function str(v: unknown, max: number): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t ? t.slice(0, max) : null;
}

function int(v: unknown, min: number, max: number): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  return Math.min(max, Math.max(min, Math.round(v)));
}

export interface RequestContext {
  userAgent: string | null;
  country: string | null;
  region: string | null;
}

export interface GuideEventRow {
  guide_slug: string;
  session_id: string;
  event_type: string;
  seq: number | null;
  view_kind: string | null;
  view_id: string | null;
  lang: string | null;
  dwell_ms: number | null;
  search_query: string | null;
  result_count: number | null;
  target: string | null;
  traffic_source: string;
  referrer_host: string | null;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  device: string;
  browser: string;
  in_app: string | null;
  country: string | null;
  region: string | null;
}

/** Session-level traffic source: UTM, then document.referrer (AI-aware), then the in-app browser. */
export function trafficSourceFor(referrer: string | null, utmSource: string | null, inApp: string | null): string {
  const fromUtm = normalizeUtmSource(utmSource);
  if (fromUtm) return fromUtm;
  const fromRef = classifyReferrer(referrer, { ai: true });
  if (fromRef === "direct" && !referrer && inApp && ["line", "instagram", "threads", "facebook", "twitter"].includes(inApp)) {
    return inApp;
  }
  return fromRef;
}

function normCountry(raw: string | null): string | null {
  const v = (raw ?? "").trim().toUpperCase().slice(0, 2);
  return /^[A-Z]{2}$/.test(v) ? v : null;
}

function normRegion(raw: string | null): string | null {
  const v = (raw ?? "").trim().toUpperCase().slice(0, 8);
  return /^[A-Z0-9]{1,8}$/.test(v) ? v : null;
}

/** Keep only scheme + host + path for http(s), and the bare address for mailto (drop query and fragment). */
export function outboundTarget(raw: string | null): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (u.protocol === "mailto:") return `mailto:${u.pathname}`.slice(0, 300);
    if (u.protocol === "http:" || u.protocol === "https:") return `${u.origin}${u.pathname}`.slice(0, 300);
  } catch {
    return null;
  }
  return null;
}

export type ParseResult = { ok: true; rows: GuideEventRow[] } | { ok: false; status: number; error: string };

/**
 * Validate a tracker batch and turn it into guide_events rows. Unknown fields are
 * dropped, strings are capped, and invalid events are skipped (not the whole batch).
 */
export function parseBatch(raw: string, ctx: RequestContext): ParseResult {
  if (raw.length > MAX_BODY_BYTES) return { ok: false, status: 413, error: "too_large" };
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return { ok: false, status: 400, error: "bad_json" };
  }
  if (!body || typeof body !== "object") return { ok: false, status: 400, error: "bad_body" };
  const b = body as Record<string, unknown>;

  const slug = str(b.slug, 100);
  if (!slug || !(GUIDE_SLUGS as readonly string[]).includes(slug)) return { ok: false, status: 400, error: "bad_slug" };
  const sid = str(b.sid, 40);
  if (!sid || !SESSION_RE.test(sid)) return { ok: false, status: 400, error: "bad_session" };
  if (!Array.isArray(b.events)) return { ok: false, status: 400, error: "bad_events" };

  const referrer = str(b.ref, 500);
  const utm = (b.utm && typeof b.utm === "object" ? b.utm : {}) as Record<string, unknown>;
  const utmSource = str(utm.source, 64);
  const ua = parseUserAgent(ctx.userAgent);
  const shared = {
    guide_slug: slug,
    session_id: sid,
    traffic_source: trafficSourceFor(referrer, utmSource, ua.inApp),
    referrer_host: referrerHost(referrer),
    utm_source: utmSource,
    utm_medium: str(utm.medium, 64),
    utm_campaign: str(utm.campaign, 64),
    device: ua.device,
    browser: ua.browser,
    in_app: ua.inApp,
    country: normCountry(ctx.country),
    region: normRegion(ctx.region),
  };

  const rows: GuideEventRow[] = [];
  for (const e of b.events.slice(0, MAX_EVENTS_PER_BATCH)) {
    if (!e || typeof e !== "object") continue;
    const ev = e as Record<string, unknown>;
    const type = str(ev.t, 16);
    if (!type || !EVENT_TYPES.has(type)) continue;
    const lang = str(ev.lang, 2);
    const kind = str(ev.kind, 16);
    const viewId = str(ev.id, 40);
    const row: GuideEventRow = {
      ...shared,
      event_type: type,
      seq: int(ev.seq, 0, 10000),
      view_kind: kind && VIEW_KINDS.has(kind) ? kind : null,
      view_id: viewId && VIEW_ID_RE.test(viewId) ? viewId : null,
      lang: lang && LANGS.has(lang) ? lang : null,
      dwell_ms: null,
      search_query: null,
      result_count: null,
      target: null,
    };
    if (type === "view" || type === "leave") {
      if (!row.view_kind || row.seq === null) continue;
      if (row.view_kind === "home") row.view_id = null;
      if (type === "leave") {
        row.dwell_ms = int(ev.ms, 0, MAX_DWELL_MS);
        if (row.dwell_ms === null) continue;
      }
    } else if (type === "search") {
      row.search_query = str(ev.q, 100);
      if (!row.search_query) continue;
      row.result_count = int(ev.n, 0, 10000);
      const tgt = str(ev.via, 16);
      row.target = tgt && SEARCH_TARGETS.has(tgt) ? tgt : null;
    } else if (type === "outbound") {
      const url = outboundTarget(str(ev.url, 1000));
      if (!url) continue;
      row.target = url;
    } else if (type === "lang") {
      const to = str(ev.to, 2);
      if (!to || !LANGS.has(to)) continue;
      row.target = to;
    }
    rows.push(row);
  }
  return { ok: true, rows };
}

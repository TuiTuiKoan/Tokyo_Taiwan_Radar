"use server";

import { createClient } from "@/lib/supabase/server";
import { headers } from "next/headers";

function normalizeCountry(raw: string | null): string | null {
  if (!raw) return null;
  const normalized = raw.trim().toUpperCase().slice(0, 2);
  return /^[A-Z]{2}$/.test(normalized) ? normalized : null;
}

function normalizeRegion(raw: string | null): string | null {
  if (!raw) return null;
  const v = raw.trim().toUpperCase().slice(0, 8);
  return /^[A-Z0-9]{1,8}$/.test(v) ? v : null;
}

const KNOWN_SOURCES = new Set([
  "google", "line", "instagram", "threads", "facebook", "twitter", "direct", "other",
]);

function normalizeUtmSource(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let v = raw.trim().toLowerCase().slice(0, 32);
  if (v === "x" || v === "x.com") v = "twitter";
  if (v === "ig") v = "instagram";
  if (v === "fb") v = "facebook";
  return KNOWN_SOURCES.has(v) ? v : null;
}

function classifyReferer(referer: string | null): string {
  if (!referer) return "direct";
  let host = "";
  try { host = new URL(referer).hostname.toLowerCase(); } catch { return "other"; }
  if (host.includes("google.")) return "google";
  if (host.includes("line.")) return "line";
  if (host.includes("instagram.")) return "instagram";   // 含 l.instagram.com
  if (host.includes("threads.")) return "threads";        // 含 l.threads.net
  if (host.includes("facebook.")) return "facebook";      // 含 l.facebook.com
  if (host.includes("twitter.") || host === "t.co" || host.includes("x.com")) return "twitter";
  // 自家網域 → 內部導覽，視為 direct（避免被算成 other）
  if (host.includes("tokyotaiwanradar.com") || host.includes("vercel.app")) return "direct";
  return "other";
}

export async function recordEventView(
  eventId: string,
  locale: string,
  utmSource?: string | null
): Promise<void> {
  try {
    // Dev environment has no x-vercel-ip-country header → pollutes prod with null country
    if (process.env.NODE_ENV === "development") return;

    const headerList = await headers();
    const country = normalizeCountry(headerList.get("x-vercel-ip-country"));
    const region = normalizeRegion(headerList.get("x-vercel-ip-country-region"));
    const trafficSource = normalizeUtmSource(utmSource) ?? classifyReferer(headerList.get("referer"));
    const supabase = await createClient();

    // Exclude admin self-views (public visitors have no session → getUser returns null, no extra query)
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (user) {
      const { data: roleRow } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", user.id)
        .single();
      if (roleRow?.role === "admin") return;
    }

    await supabase.from("event_views").insert({
      event_id: eventId,
      locale,
      country,
      country_region: region,
      traffic_source: trafficSource,
    });
  } catch {
    // Analytics failures should never surface to the user — swallow silently.
  }
}

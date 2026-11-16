"use server";

import { createClient } from "@/lib/supabase/server";
import { headers } from "next/headers";
import { classifyReferrer, normalizeUtmSource } from "@/lib/analytics/trafficSource";
import { classifyVisitor } from "@/lib/analytics/botDetect";

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
    const trafficSource = normalizeUtmSource(utmSource) ?? classifyReferrer(headerList.get("referer"));
    // Crawlers that run JS (Googlebot, Applebot, Bingbot…) fire this action too.
    // Keep their rows, labelled, so dashboards can exclude them (spec view-bot-filter).
    const { visitorClass, botName } = classifyVisitor({
      userAgent: headerList.get("user-agent"),
      acceptLanguage: headerList.get("accept-language"),
    });
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
      visitor_class: visitorClass,
      bot_name: botName,
    });
  } catch {
    // Analytics failures should never surface to the user — swallow silently.
  }
}

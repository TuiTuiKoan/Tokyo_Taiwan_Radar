"use server";

import { createClient } from "@/lib/supabase/server";
import { headers } from "next/headers";

function normalizeCountry(raw: string | null): string | null {
  if (!raw) return null;
  const normalized = raw.trim().toUpperCase().slice(0, 2);
  return /^[A-Z]{2}$/.test(normalized) ? normalized : null;
}

export async function recordEventView(eventId: string, locale: string): Promise<void> {
  try {
    const headerList = await headers();
    const country = normalizeCountry(headerList.get("x-vercel-ip-country"));
    const supabase = await createClient();
    await supabase.from("event_views").insert({ event_id: eventId, locale, country });
  } catch {
    // Analytics failures should never surface to the user — swallow silently.
  }
}

"use server";

import { createClient } from "@/lib/supabase/server";

export async function recordEventView(eventId: string, locale: string): Promise<void> {
  try {
    const supabase = await createClient();
    await supabase.from("event_views").insert({ event_id: eventId, locale });
  } catch {
    // Analytics failures should never surface to the user — swallow silently.
  }
}

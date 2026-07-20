"use server";

import { createClient } from "@/lib/supabase/server";
import { assertWritesAllowed } from "@/lib/maintenanceLock.server";

export async function submitReport(payload: {
  eventId: string;
  reportTypes: string[];
  locale: string;
  suggestedCategory: string[] | null;
}): Promise<{ ok: boolean; error?: string }> {
  // Maintenance-lock gate (decision-16a): refuse the public report insert while
  // the Admin Reports cleanup window is open.
  const gate = await assertWritesAllowed();
  if (!gate.allowed) return { ok: false, error: "maintenance_active" };
  const supabase = await createClient();

  const { error } = await supabase.from("event_reports").insert({
    event_id: payload.eventId,
    report_types: payload.reportTypes,
    locale: payload.locale,
    suggested_category: payload.suggestedCategory,
  });

  if (error) {
    return { ok: false, error: error.message };
  }

  return { ok: true };
}

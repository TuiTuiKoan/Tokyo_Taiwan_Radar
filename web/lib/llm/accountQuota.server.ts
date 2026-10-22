// Daily limits for the two account AI routes (llm-cost-reset #322, migration 104).
//
// /api/account/annotate-event (gpt-4o-mini) and /api/account/extract-from-image
// (gpt-4o Vision) are open to every signed-in organizer. Each route consumes one
// unit of its own daily counter in account_usage through the service-role RPC
// consume_account_ai_quota() before it calls OpenAI. Days follow the Japan date.
// A unit is consumed even when the OpenAI call later fails, so retries count.
//
// Fail closed: when the RPC errors (or migration 104 is missing) the route
// refuses instead of calling OpenAI without a limit.
// Server-only by the `.server.ts` naming discipline (see lib/maintenanceLock.server.ts).

import type { SupabaseClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

export const ACCOUNT_AI_LIMITS = {
  annotate: { perUser: 30, system: 300 },
  extract: { perUser: 10, system: 100 },
} as const;

export type AccountAiKind = keyof typeof ACCOUNT_AI_LIMITS;

export type QuotaRefusal = { status: number; body: { error: string; limit?: number } };

/** Turn the RPC result into a refusal, or null when the call may go ahead. */
export function quotaRefusal(kind: AccountAiKind, data: unknown, error: unknown): QuotaRefusal | null {
  if (error || typeof data !== "number") {
    return { status: 503, body: { error: "aiQuotaUnavailable" } };
  }
  if (data === -1) {
    return { status: 429, body: { error: "aiQuotaExceeded", limit: ACCOUNT_AI_LIMITS[kind].perUser } };
  }
  if (data === -2) {
    return { status: 429, body: { error: "aiSystemQuotaExceeded" } };
  }
  return null;
}

/** Consume one unit of today's quota; returns the refusal response, or null to proceed. */
export async function consumeAccountAiQuota(
  serviceClient: SupabaseClient,
  userId: string,
  kind: AccountAiKind,
): Promise<NextResponse | null> {
  const limits = ACCOUNT_AI_LIMITS[kind];
  const { data, error } = await serviceClient.rpc("consume_account_ai_quota", {
    p_user_id: userId,
    p_kind: kind,
    p_limit_per_user: limits.perUser,
    p_limit_system: limits.system,
  });
  if (error) console.error(`[account-ai-quota] ${kind} RPC failed:`, error.message);
  const refusal = quotaRefusal(kind, data, error);
  return refusal ? NextResponse.json(refusal.body, { status: refusal.status }) : null;
}

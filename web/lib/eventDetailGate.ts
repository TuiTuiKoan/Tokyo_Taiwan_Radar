/**
 * Decides, before any route renders, whether an event detail URL is served,
 * redirected or answered with 404.
 *
 * It runs from proxy.ts because `[locale]/loading.tsx` wraps every page under
 * `[locale]`: once that skeleton is flushed the status is already 200, so a
 * `notFound()` or `permanentRedirect()` thrown by page.tsx (or by a layout
 * below the skeleton) cannot change it. page.tsx keeps its own checks as the
 * fallback when this gate fails open.
 */

export const EVENT_DETAIL_PATH =
  /^\/(zh|en|ja)\/events\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?$/i;

export interface EventStub {
  id: string;
  merged_into_event_id: string | null;
  is_active: boolean;
  annotation_status: string | null;
}

export type EventDetailDecision =
  | { kind: "serve" }
  | { kind: "redirect"; targetId: string }
  | { kind: "not-found" };

export function decideEventDetail(stub: EventStub | null): EventDetailDecision {
  if (stub?.merged_into_event_id) {
    return { kind: "redirect", targetId: stub.merged_into_event_id };
  }
  if (!stub || !stub.is_active) return { kind: "not-found" };
  if (stub.annotation_status !== "annotated" && stub.annotation_status !== "reviewed") {
    return { kind: "not-found" };
  }
  return { kind: "serve" };
}

/**
 * Reads the stub with the service-role key (merged and inactive rows are not
 * visible to anon). Returns `undefined` when the lookup itself failed, so the
 * caller can fail open and let page.tsx decide.
 */
export async function fetchEventStub(
  id: string,
  env: { url: string | undefined; serviceRoleKey: string | undefined },
  fetchImpl: typeof fetch = fetch
): Promise<EventStub | null | undefined> {
  if (!env.url || !env.serviceRoleKey) return undefined;
  const query = new URLSearchParams({
    select: "id,merged_into_event_id,is_active,annotation_status",
    id: `eq.${id}`,
    limit: "1",
  });
  try {
    const res = await fetchImpl(`${env.url}/rest/v1/events?${query}`, {
      headers: {
        apikey: env.serviceRoleKey,
        Authorization: `Bearer ${env.serviceRoleKey}`,
      },
      cache: "no-store",
      signal: AbortSignal.timeout(2500),
    });
    if (!res.ok) return undefined;
    const rows = (await res.json()) as EventStub[];
    return Array.isArray(rows) ? (rows[0] ?? null) : undefined;
  } catch {
    return undefined;
  }
}

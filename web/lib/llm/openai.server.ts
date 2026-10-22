// Every OpenAI call from the web app goes through openaiChat() (llm-cost-reset, #363).
//
// It sends the request, records one public.llm_usage row (ok or error) after
// the response is sent, and hands back a standard Response rebuilt from
// OpenAI's body, so route code keeps its `res.ok` / `res.text()` / `res.json()`
// handling unchanged. Recording never affects the route: a failed insert is
// only logged. Prices live in llm_pricing; nothing here knows a price.
// Server-only by the `.server.ts` naming discipline (the `server-only` package
// is not a dependency here; see lib/maintenanceLock.server.ts). It reads the
// service role key, so never import it from a client component.

import { createClient } from "@supabase/supabase-js";
import { after } from "next/server";

import { assertWebCaller, errorCodeFrom, openaiApiKey, usageRow, type LlmUsageRow } from "./usage";

export { openaiApiKey };

const CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions";

async function insertUsage(row: LlmUsageRow): Promise<void> {
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    console.warn("[llm-usage] not recorded: Supabase service credentials missing");
    return;
  }
  const { error } = await createClient(url, key).from("llm_usage").insert(row);
  if (error) console.warn("[llm-usage] insert failed:", error.message);
}

function record(row: LlmUsageRow): void {
  const task = () => insertUsage(row).catch((err) => console.warn("[llm-usage] insert failed:", err));
  try {
    after(task);
  } catch {
    // Outside a request scope (e.g. a script): record without deferring.
    void task();
  }
}

export async function openaiChat(opts: {
  /** "web.<name>", e.g. "web.account.extract-from-image". */
  caller: string;
  /** The chat.completions request body. */
  body: Record<string, unknown>;
  /** Signed-in user for per-user quota checks; omit for admin and webhook calls. */
  userId?: string | null;
  apiKey?: string;
  signal?: AbortSignal;
}): Promise<Response> {
  assertWebCaller(opts.caller);
  const apiKey = opts.apiKey ?? openaiApiKey();
  const base = { caller: opts.caller, model: opts.body.model, userId: opts.userId };

  let res: Response;
  try {
    res = await fetch(CHAT_COMPLETIONS_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify(opts.body),
      signal: opts.signal,
    });
  } catch (err) {
    const name = err instanceof Error ? err.name : "";
    record(usageRow({ ...base, errorCode: name === "TimeoutError" || name === "AbortError" ? "timeout" : "network" }));
    throw err;
  }

  const text = await res.text();
  if (res.ok) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = undefined;
    }
    record(usageRow({ ...base, body: parsed }));
  } else {
    record(usageRow({ ...base, errorCode: errorCodeFrom(res.status, text) }));
  }
  return new Response(text, { status: res.status, statusText: res.statusText, headers: res.headers });
}

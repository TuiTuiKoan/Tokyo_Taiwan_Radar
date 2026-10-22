// Pure helpers for the shared OpenAI usage ledger (llm-cost-reset, #363).
// The server wrapper lives in openai.server.ts; this file has no Next.js or
// Supabase imports so it can be unit-tested directly.

/** One row of public.llm_usage (migration 099). Cost is computed by the llm_cost_daily view. */
export type LlmUsageRow = {
  caller: string;
  model: string;
  endpoint: "chat";
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  web_search_calls: number;
  status: "ok" | "error";
  error_code: string | null;
  user_id: string | null;
  run_ref: null;
};

function count(value: unknown): number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : 0;
}

/** Callers are "web.<name>"; the scraper side uses its own groups (scraper/llm_client.py). */
export function assertWebCaller(caller: string): void {
  if (!/^web\.[a-z0-9][a-z0-9.-]*$/.test(caller)) {
    throw new Error(`LLM caller must look like "web.<name>", got ${JSON.stringify(caller)}`);
  }
}

/** OPENAI_API_KEY_WEB when set, else OPENAI_API_KEY (#320). */
export function openaiApiKey(env: Record<string, string | undefined> = process.env): string | undefined {
  return env.OPENAI_API_KEY_WEB || env.OPENAI_API_KEY || undefined;
}

/** Pull the `error.code` (or `error.type`) out of an OpenAI error body, if any. */
export function errorCodeFrom(status: number, bodyText: string | null): string {
  if (bodyText) {
    try {
      const parsed = JSON.parse(bodyText) as { error?: { code?: unknown; type?: unknown } };
      const code = parsed.error?.code ?? parsed.error?.type;
      if (typeof code === "string" && code) return code.slice(0, 100);
    } catch {
      // not JSON
    }
  }
  return String(status);
}

export function usageRow(opts: {
  caller: string;
  model: unknown;
  userId?: string | null;
  /** Parsed chat.completions response body when the call succeeded. */
  body?: unknown;
  /** Set when the call failed: an HTTP status or "network". */
  errorCode?: string | null;
}): LlmUsageRow {
  const usage = (opts.body as { usage?: Record<string, unknown> } | undefined)?.usage;
  const details = usage?.prompt_tokens_details as Record<string, unknown> | undefined;
  return {
    caller: opts.caller,
    model: typeof opts.model === "string" && opts.model ? opts.model : "unknown",
    endpoint: "chat",
    input_tokens: count(usage?.prompt_tokens),
    cached_input_tokens: count(details?.cached_tokens),
    output_tokens: count(usage?.completion_tokens),
    web_search_calls: 0,
    status: opts.errorCode ? "error" : "ok",
    error_code: opts.errorCode ?? null,
    user_id: opts.userId ?? null,
    run_ref: null,
  };
}

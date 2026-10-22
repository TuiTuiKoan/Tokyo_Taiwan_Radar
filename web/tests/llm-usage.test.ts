import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import test from "node:test";

import { assertWebCaller, errorCodeFrom, openaiApiKey, usageRow } from "../lib/llm/usage";

test("a successful chat call records prompt, cached and completion tokens", () => {
  const row = usageRow({
    caller: "web.account.extract-from-image",
    model: "gpt-4o",
    userId: "11111111-1111-1111-1111-111111111111",
    body: { usage: { prompt_tokens: 1200, prompt_tokens_details: { cached_tokens: 1000 }, completion_tokens: 80 } },
  });
  assert.deepEqual(row, {
    caller: "web.account.extract-from-image",
    model: "gpt-4o",
    endpoint: "chat",
    input_tokens: 1200,
    cached_input_tokens: 1000,
    output_tokens: 80,
    web_search_calls: 0,
    status: "ok",
    error_code: null,
    user_id: "11111111-1111-1111-1111-111111111111",
    run_ref: null,
  });
});

test("a failed call records an error row with zero tokens", () => {
  const row = usageRow({ caller: "web.admin.annotate-event", model: "gpt-4o-mini", errorCode: "model_not_found" });
  assert.equal(row.status, "error");
  assert.equal(row.error_code, "model_not_found");
  assert.equal(row.input_tokens, 0);
  assert.equal(row.user_id, null);
});

test("missing or malformed usage counts as zero and an unknown model is labelled", () => {
  const row = usageRow({ caller: "web.line-webhook.reply-draft", model: undefined, body: { usage: { prompt_tokens: "12" } } });
  assert.equal(row.model, "unknown");
  assert.equal(row.input_tokens, 0);
});

test("error codes come from the OpenAI error body, else the HTTP status", () => {
  assert.equal(errorCodeFrom(404, JSON.stringify({ error: { code: "model_not_found" } })), "model_not_found");
  assert.equal(errorCodeFrom(429, JSON.stringify({ error: { type: "insufficient_quota", code: null } })), "insufficient_quota");
  assert.equal(errorCodeFrom(502, "<html>bad gateway</html>"), "502");
});

test("the web key wins over the shared key", () => {
  assert.equal(openaiApiKey({ OPENAI_API_KEY_WEB: "web", OPENAI_API_KEY: "shared" }), "web");
  assert.equal(openaiApiKey({ OPENAI_API_KEY: "shared" }), "shared");
  assert.equal(openaiApiKey({}), undefined);
});

test("callers must be web.<name>", () => {
  assertWebCaller("web.account.annotate-event");
  assert.throws(() => assertWebCaller("annotator.annotate"));
  assert.throws(() => assertWebCaller("web."));
});

test("only lib/llm/openai.server.ts calls the OpenAI API directly", () => {
  const root = join(__dirname, "..");
  const offenders: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      if (name === "node_modules" || name.startsWith(".")) continue;
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/\.(ts|tsx)$/.test(name) && readFileSync(path, "utf8").includes("api.openai.com")) {
        offenders.push(relative(root, path));
      }
    }
  };
  for (const dir of ["app", "lib", "components"]) walk(join(root, dir));
  assert.deepEqual(offenders, ["lib/llm/openai.server.ts"]);
});

import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(TEST_DIR, "..");

const WIZARD_PATH = path.join(WEB_ROOT, "components/EventIntakeWizard.tsx");
const NEXT_CONFIG_PATH = path.join(WEB_ROOT, "next.config.ts");

function readHandleCancelBody(): string {
  const source = fs.readFileSync(WIZARD_PATH, "utf8");
  const start = source.indexOf("async function handleCancel()");
  assert.ok(start >= 0, "handleCancel must exist in EventIntakeWizard");

  // Walk braces from the function signature so the body is captured exactly,
  // without swallowing whatever function happens to be declared next.
  const open = source.indexOf("{", start);
  let depth = 0;
  for (let i = open; i < source.length; i += 1) {
    if (source[i] === "{") depth += 1;
    else if (source[i] === "}") {
      depth -= 1;
      if (depth === 0) return source.slice(open, i + 1);
    }
  }
  throw new Error("unbalanced braces while reading handleCancel");
}

test("cancel never blocks navigation when the draft save fails", () => {
  const body = readHandleCancelBody();

  assert.doesNotMatch(
    body,
    /setActionError/,
    "cancel must not surface a blocking error — the user asked to leave",
  );
  assert.doesNotMatch(
    body,
    /return;\s*}\s*}\s*catch/,
    "cancel must not early-return on a failed save",
  );
});

test("cancel still attempts a best-effort draft save and always routes away", () => {
  const body = readHandleCancelBody();

  assert.match(body, /updateDraft|createDraft/, "cancel should still preserve work");
  assert.match(body, /catch/, "a thrown Server Action error must be caught");

  // The unconditional push must sit after the try/catch, so every path reaches it.
  const catchIdx = body.lastIndexOf("catch");
  const finallyIdx = body.lastIndexOf("finally");
  const pushIdx = body.lastIndexOf("router.push(cfg.returnPath)");
  assert.ok(pushIdx > catchIdx, "navigation must happen after the catch block");
  assert.ok(pushIdx > finallyIdx, "navigation must happen after the finally block");
});

test("step 1 and the mode chooser leave immediately without a server round-trip", () => {
  const body = readHandleCancelBody();
  const noSaveIdx = body.indexOf("noSave");
  const firstPushIdx = body.indexOf("router.push(cfg.returnPath)");

  assert.ok(noSaveIdx >= 0, "the no-save fast path must be preserved");
  assert.ok(firstPushIdx > noSaveIdx, "the fast path must route away directly");
});

test("version skew protection is configured so stale tabs reload instead of erroring", () => {
  const config = fs.readFileSync(NEXT_CONFIG_PATH, "utf8");

  assert.match(
    config,
    /deploymentId:\s*process\.env\.VERCEL_DEPLOYMENT_ID/,
    "deploymentId must be wired to the Vercel deployment ID",
  );
});

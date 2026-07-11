import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { PURE_PUBLICATION_EVENT_FORM_GUIDANCE } from "../lib/intakeGuidance";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(TEST_DIR, "..");

const ROUTE_PATHS = [
  "app/api/admin/extract-from-image/route.ts",
  "app/api/admin/annotate-event/route.ts",
  "app/api/account/extract-from-image/route.ts",
  "app/api/account/annotate-event/route.ts",
] as const;

test("shared intake publication guidance keeps required policy wording", () => {
  assert.match(PURE_PUBLICATION_EVENT_FORM_GUIDANCE, /metadata-only publication records/i);
  assert.match(PURE_PUBLICATION_EVENT_FORM_GUIDANCE, /book launch, release talk, signing, lecture, workshop/i);
  assert.match(PURE_PUBLICATION_EVENT_FORM_GUIDANCE, /must use physical event forms/i);
});

test("all intake routes reference the shared guidance constant", () => {
  for (const relativePath of ROUTE_PATHS) {
    const fullPath = path.join(WEB_ROOT, relativePath);
    const source = fs.readFileSync(fullPath, "utf8");

    assert.match(source, /from "@\/lib\/intakeGuidance"/);
    assert.match(source, /PURE_PUBLICATION_EVENT_FORM_GUIDANCE/);
  }
});

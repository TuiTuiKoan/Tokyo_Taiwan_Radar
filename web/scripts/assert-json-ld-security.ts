#!/usr/bin/env tsx

import assert from "node:assert/strict";
import { serializeJsonLd } from "../lib/security/jsonLd";

const cjk = { zh: "繁體中文", ja: "日本語", en: "English" };
assert.deepEqual(JSON.parse(serializeJsonLd(cjk)), cjk);

assert.throws(
  () => serializeJsonLd(undefined),
  /top level/,
);

const payload = '</script><script>alert("xss")</script>';
const serializedPayload = serializeJsonLd({ payload });
assert.equal(serializedPayload.includes("<"), false);
assert.equal(serializedPayload.includes("</script>"), false);
assert.equal(serializedPayload.includes("<script>"), false);
assert.deepEqual(JSON.parse(serializedPayload), { payload });

const specialCharacters = "<>&\u2028\u2029";
const serializedCharacters = serializeJsonLd(specialCharacters);
for (const escaped of ["\\u003c", "\\u003e", "\\u0026", "\\u2028", "\\u2029"]) {
  assert.equal(serializedCharacters.includes(escaped), true, `${escaped} missing`);
}
assert.equal(JSON.parse(serializedCharacters), specialCharacters);

console.log("JSON-LD security assertions passed");
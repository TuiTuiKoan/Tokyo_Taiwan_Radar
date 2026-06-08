#!/usr/bin/env tsx
/**
 * assert-i18n-parity.ts — build canary for three-locale i18n consistency.
 *
 * NOTE ON COVERAGE: This script only checks that zh/en/ja have IDENTICAL key sets.
 * It CANNOT detect the be94500-type regression where all three locales lose the
 * same keys simultaneously (equal deletion = still "parity").
 * The "no key regression" defense is in .githooks/pre-push and i18n-guard.yml.
 *
 * Run as part of prebuild: tsx scripts/assert-i18n-parity.ts
 */

import { readFileSync } from "fs";
import { join } from "path";

const MESSAGES_DIR = join(process.cwd(), "messages");
const LOCALES = ["zh", "en", "ja"] as const;

function flattenKeys(obj: Record<string, unknown>, prefix = ""): Set<string> {
  const keys = new Set<string>();
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      for (const k of flattenKeys(value as Record<string, unknown>, fullKey)) {
        keys.add(k);
      }
    } else {
      keys.add(fullKey);
    }
  }
  return keys;
}

const keysets: Record<string, Set<string>> = {};

for (const locale of LOCALES) {
  const filePath = join(MESSAGES_DIR, `${locale}.json`);
  try {
    const content = JSON.parse(readFileSync(filePath, "utf-8"));
    keysets[locale] = flattenKeys(content);
  } catch (e) {
    console.error(`Error reading ${filePath}:`, e);
    process.exit(1);
  }
}

let failed = false;
const [zh, en, ja] = [keysets["zh"], keysets["en"], keysets["ja"]];

for (const [a, b, aName, bName] of [
  [zh, en, "zh", "en"],
  [zh, ja, "zh", "ja"],
  [en, ja, "en", "ja"],
] as [Set<string>, Set<string>, string, string][]) {
  const onlyInA = [...a].filter((k) => !b.has(k));
  const onlyInB = [...b].filter((k) => !a.has(k));
  if (onlyInA.length > 0 || onlyInB.length > 0) {
    console.error(`\ni18n parity mismatch: ${aName} vs ${bName}`);
    if (onlyInA.length > 0)
      console.error(
        `  Only in ${aName} (${onlyInA.length}): ${onlyInA.slice(0, 5).join(", ")}${onlyInA.length > 5 ? "..." : ""}`
      );
    if (onlyInB.length > 0)
      console.error(
        `  Only in ${bName} (${onlyInB.length}): ${onlyInB.slice(0, 5).join(", ")}${onlyInB.length > 5 ? "..." : ""}`
      );
    failed = true;
  }
}

if (failed) {
  process.exit(1);
} else {
  const count = zh.size;
  console.log(`i18n parity OK: all three locales have ${count} keys`);
}

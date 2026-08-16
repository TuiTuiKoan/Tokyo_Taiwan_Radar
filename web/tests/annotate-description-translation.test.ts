import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  DESCRIPTION_PROMPT_MAX_CHARS,
  buildDescriptionPromptLines,
} from "../lib/eventFieldMerge";

const TEST_DIR = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(TEST_DIR, "..");

const ANNOTATE_ROUTES = [
  "app/api/admin/annotate-event/route.ts",
  "app/api/account/annotate-event/route.ts",
] as const;

test("description input keeps the whole body instead of a 400-char head", () => {
  const long = `${"あ".repeat(1200)}\n会場: 京橋 鶴園\n参加費 8,000円`;
  const [line] = buildDescriptionPromptLines({ ja: long });

  assert.ok(line.startsWith("説明（日文）: "));
  assert.ok(line.includes("会場: 京橋 鶴園"), "venue line beyond 400 chars must survive");
  assert.ok(line.includes("参加費 8,000円"), "fee line beyond 400 chars must survive");
  assert.ok(DESCRIPTION_PROMPT_MAX_CHARS >= 4000);
});

test("a locale field repeating the source text is not labelled as a translation", () => {
  const japanese = "台湾の魚料理って食べたことがありますか？";
  const lines = buildDescriptionPromptLines({
    ja: japanese,
    zh: japanese,
    en: "Have you ever tried Taiwanese fish dishes?",
  });

  assert.deepEqual(lines, [
    `説明（日文）: ${japanese}`,
    "説明（英文）: Have you ever tried Taiwanese fish dishes?",
  ]);
});

test("whitespace-only differences still count as a duplicate, blanks are dropped", () => {
  const lines = buildDescriptionPromptLines({
    ja: "台湾料理教室\n会場: 京橋",
    zh: "  台湾料理教室  会場:  京橋 ",
    en: "   ",
  });

  assert.equal(lines.length, 1);
  assert.ok(lines[0].startsWith("説明（日文）: "));
});

test("genuine translations are all forwarded in ja, zh, en order", () => {
  const lines = buildDescriptionPromptLines({
    ja: "台湾料理教室です。",
    zh: "台灣料理教室。",
    en: "A Taiwanese cooking class.",
  });

  assert.deepEqual(lines, [
    "説明（日文）: 台湾料理教室です。",
    "説明（中文）: 台灣料理教室。",
    "説明（英文）: A Taiwanese cooking class.",
  ]);
});

test("non-string and absent descriptions are ignored", () => {
  assert.deepEqual(buildDescriptionPromptLines({}), []);
  assert.deepEqual(buildDescriptionPromptLines({ ja: null, zh: 42, en: undefined }), []);
});

test("both annotate routes demand a complete translation and share the input builder", () => {
  for (const relativePath of ANNOTATE_ROUTES) {
    const source = fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8");

    assert.match(source, /buildDescriptionPromptLines/, `${relativePath} must use the shared builder`);
    assert.doesNotMatch(
      source,
      /description_(ja|zh|en)\)\.slice\(0, 400\)/,
      `${relativePath} must not truncate description input to 400 chars`,
    );
    assert.doesNotMatch(
      source,
      /description_zh: 2–4 sentence/,
      `${relativePath} must not ask for a 2–4 sentence summary`,
    );
    assert.match(source, /translate it COMPLETELY into the other two/, relativePath);
    assert.match(source, /Never summarise/, relativePath);
  }
});

test("both annotate routes keep identical translation prompt and budget settings", () => {
  const [adminSource, accountSource] = ANNOTATE_ROUTES.map((relativePath) =>
    fs.readFileSync(path.join(WEB_ROOT, relativePath), "utf8"),
  );

  const descriptionBlock = (source: string) =>
    source.match(/Description text \(always required[\s\S]*?Never leave the descriptions blank\./)?.[0];
  const maxTokens = (source: string) => source.match(/max_tokens: (\d+)/)?.[1];

  assert.ok(descriptionBlock(adminSource), "admin route must contain the description block");
  assert.equal(descriptionBlock(adminSource), descriptionBlock(accountSource));
  assert.equal(maxTokens(adminSource), maxTokens(accountSource));
  assert.ok(Number(maxTokens(adminSource)) >= 4000, "budget must fit full three-language bodies");
});

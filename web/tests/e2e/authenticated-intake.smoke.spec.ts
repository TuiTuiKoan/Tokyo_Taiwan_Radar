import { readFileSync } from "fs";
import { join } from "path";
import { expect, test, type Page } from "@playwright/test";

const LOCALES = ["ja", "zh", "en"] as const;
type Locale = (typeof LOCALES)[number];

const PLACEHOLDER_KEYS = [
  "performerPlaceholder",
  "coOrganizersPlaceholder",
  "sponsorsPlaceholder",
] as const;

const ORGANIZER_STATE = join(process.cwd(), "tests/e2e/.auth/organizer.json");
const ADMIN_STATE = join(process.cwd(), "tests/e2e/.auth/admin.json");

/** Light-theme --color-text-placeholder. Asserted as a value, because a class
 *  name proves nothing about what the browser actually painted. */
const MATCHA_PLACEHOLDER = "rgb(109, 123, 74)";

type Messages = {
  admin: Record<string, string>;
  eventIntake: Record<string, string>;
};

function messagesFor(locale: Locale): Messages {
  const file = join(process.cwd(), "messages", `${locale}.json`);
  return JSON.parse(readFileSync(file, "utf8")) as Messages;
}

async function openManualIntake(page: Page, locale: Locale, path: string): Promise<void> {
  await page.goto(`/${locale}${path}`);
  await expect(page).toHaveURL(new RegExp(`${locale}${path}`));
  await page
    .getByRole("button", { name: messagesFor(locale).eventIntake.chooseManual, exact: true })
    .click();
}

async function placeholderColor(page: Page, text: string): Promise<string> {
  return page.getByPlaceholder(text, { exact: true }).evaluate((node) =>
    getComputedStyle(node as HTMLInputElement, "::placeholder").color,
  );
}

async function expectLocalizedPlaceholders(page: Page, locale: Locale): Promise<void> {
  const messages = messagesFor(locale);
  for (const key of PLACEHOLDER_KEYS) {
    const expected = messages.admin[key];
    expect(expected, `${locale}.admin.${key} must exist`).toBeTruthy();
    expect(expected, `${locale}.admin.${key} must not be a raw key`).not.toBe(key);

    const field = page.getByPlaceholder(expected, { exact: true });
    await expect(field).toHaveCount(1);
    expect(await placeholderColor(page, expected), `${locale}.${key} tone`).toBe(
      MATCHA_PLACEHOLDER,
    );
  }
}

test.describe("authenticated organizer intake placeholders", () => {
  test.use({ storageState: ORGANIZER_STATE });

  for (const locale of LOCALES) {
    test(`${locale}: intake placeholders are localized and subtle`, async ({ page }) => {
      await openManualIntake(page, locale, "/account/events/new");
      await expectLocalizedPlaceholders(page, locale);
    });
  }

  test("organizer cannot reach the admin intake", async ({ page }) => {
    await page.goto("/ja/admin/events/new");
    await expect(page).not.toHaveURL(/\/admin\/events\/new/);
  });

  test("typed values keep the normal text colour", async ({ page }) => {
    const messages = messagesFor("ja");

    await openManualIntake(page, "ja", "/account/events/new");

    const performer = page.getByPlaceholder(messages.admin.performerPlaceholder, { exact: true });
    const hint = await placeholderColor(page, messages.admin.performerPlaceholder);
    await performer.fill("実際の出演者");

    await expect(performer).toHaveValue("実際の出演者");
    const value = await performer.evaluate((node) => getComputedStyle(node).color);
    expect(hint).toBe(MATCHA_PLACEHOLDER);
    expect(value).not.toBe(MATCHA_PLACEHOLDER);
  });

  test("locales serve distinct placeholder strings", async () => {
    for (const key of PLACEHOLDER_KEYS) {
      const values = LOCALES.map((locale) => messagesFor(locale).admin[key]);
      expect(new Set(values).size, `${key} must differ per locale`).toBe(LOCALES.length);
    }
  });
});

test.describe("authenticated admin intake placeholders", () => {
  test.use({ storageState: ADMIN_STATE });

  for (const locale of LOCALES) {
    test(`${locale}: admin intake placeholders match the organizer form`, async ({ page }) => {
      await openManualIntake(page, locale, "/admin/events/new");
      await expectLocalizedPlaceholders(page, locale);
    });
  }
});

test.describe("unauthenticated intake is denied", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("admin create redirects to login", async ({ page }) => {
    const response = await page.goto("/ja/admin/events/new");
    expect(response?.status()).toBeLessThan(400);
    await expect(page).toHaveURL(/\/ja\/auth\/login/);
  });

  test("organizer create does not expose the intake form", async ({ page }) => {
    await page.goto("/ja/account/events/new");
    const messages = messagesFor("ja");
    await expect(
      page.getByPlaceholder(messages.admin.performerPlaceholder, { exact: true }),
    ).toHaveCount(0);
  });
});

import { readFileSync } from "fs";
import { join } from "path";
import { expect, test } from "@playwright/test";

const LOCALES = ["ja", "zh", "en"] as const;
type Locale = (typeof LOCALES)[number];

const PLACEHOLDER_KEYS = [
  "performerPlaceholder",
  "coOrganizersPlaceholder",
  "sponsorsPlaceholder",
] as const;

const ORGANIZER_STATE = join(process.cwd(), "tests/e2e/.auth/organizer.json");
const SUBTLE_PLACEHOLDER_CLASS = /placeholder:text-fg-subtle/;

type Messages = {
  admin: Record<string, string>;
  eventIntake: Record<string, string>;
};

function messagesFor(locale: Locale): Messages {
  const file = join(process.cwd(), "messages", `${locale}.json`);
  return JSON.parse(readFileSync(file, "utf8")) as Messages;
}

test.describe("authenticated organizer intake placeholders", () => {
  test.use({ storageState: ORGANIZER_STATE });

  for (const locale of LOCALES) {
    test(`${locale}: intake placeholders are localized and subtle`, async ({ page }) => {
      const messages = messagesFor(locale);

      await page.goto(`/${locale}/account/events/new`);
      await expect(page).toHaveURL(new RegExp(`/${locale}/account/events/new`));

      await page
        .getByRole("button", { name: messages.eventIntake.chooseManual, exact: true })
        .click();

      for (const key of PLACEHOLDER_KEYS) {
        const expected = messages.admin[key];
        expect(expected, `${locale}.admin.${key} must exist`).toBeTruthy();
        expect(expected, `${locale}.admin.${key} must not be a raw key`).not.toBe(key);

        const field = page.getByPlaceholder(expected, { exact: true });
        await expect(field).toHaveCount(1);
        await expect(field).toHaveClass(SUBTLE_PLACEHOLDER_CLASS);
      }
    });
  }

  test("typed values are not rendered with the placeholder tone", async ({ page }) => {
    const messages = messagesFor("ja");

    await page.goto("/ja/account/events/new");
    await page
      .getByRole("button", { name: messages.eventIntake.chooseManual, exact: true })
      .click();

    const performer = page.getByPlaceholder(messages.admin.performerPlaceholder, { exact: true });
    await performer.fill("実際の出演者");

    // The subtle tone is scoped to ::placeholder, so a filled field keeps the normal colour.
    await expect(performer).toHaveValue("実際の出演者");
    const [placeholderColor, valueColor] = await performer.evaluate((node) => {
      const element = node as HTMLInputElement;
      return [
        getComputedStyle(element, "::placeholder").color,
        getComputedStyle(element).color,
      ];
    });
    expect(placeholderColor).not.toBe(valueColor);
  });

  test("locales serve distinct placeholder strings", async () => {
    for (const key of PLACEHOLDER_KEYS) {
      const values = LOCALES.map((locale) => messagesFor(locale).admin[key]);
      expect(new Set(values).size, `${key} must differ per locale`).toBe(LOCALES.length);
    }
  });
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

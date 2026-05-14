import { expect, test, type Page } from "@playwright/test";

type Snapshot = {
  darkClass: boolean;
  navbarBg: string;
  relatedBg: string;
};

function isNearWhite(rgb: string): boolean {
  const values = rgb.match(/\d+/g);
  if (!values || values.length < 3) {
    return false;
  }
  const [r, g, b] = values.slice(0, 3).map(Number);
  return r >= 245 && g >= 245 && b >= 245;
}

async function captureColors(page: Page): Promise<Snapshot> {
  return page.evaluate(() => {
    const navbar = document.querySelector("header");
    const related = document.querySelector("article a[href^='/zh/events/']");

    if (!navbar) {
      throw new Error("Navbar header not found");
    }
    if (!related) {
      throw new Error("Related event link not found");
    }

    return {
      darkClass: document.documentElement.classList.contains("dark"),
      navbarBg: getComputedStyle(navbar).backgroundColor,
      relatedBg: getComputedStyle(related).backgroundColor,
    };
  });
}

async function openAnnouncementWithRelatedSection(page: Page): Promise<void> {
  await page.goto("/zh/announcements");

  const links = page
    .locator("a[href^='/zh/announcements/']")
    .filter({ hasNotText: "admin" });
  const count = await links.count();

  if (count === 0) {
    throw new Error("No announcement detail links found on announcements page");
  }

  for (let i = 0; i < count; i += 1) {
    const href = await links.nth(i).getAttribute("href");
    if (!href) {
      continue;
    }

    await page.goto(href);
    if (await page.locator("article a[href^='/zh/events/']").first().isVisible()) {
      return;
    }
  }

  throw new Error("No announcement detail page contains related events links");
}

test("dark mode switches navbar and related-event row backgrounds", async ({ page }) => {
  await openAnnouncementWithRelatedSection(page);
  await page.evaluate(() => localStorage.setItem("ttr_theme", "light"));
  await page.reload();
  const light = await captureColors(page);

  await page.evaluate(() => localStorage.setItem("ttr_theme", "dark"));
  await page.reload();
  const dark = await captureColors(page);

  expect(dark.darkClass).toBe(true);
  expect(light.navbarBg).not.toBe(dark.navbarBg);
  expect(light.relatedBg).not.toBe(dark.relatedBg);
  expect(dark.relatedBg).not.toBe("rgb(255, 255, 255)");
  expect(isNearWhite(dark.relatedBg)).toBe(false);
});

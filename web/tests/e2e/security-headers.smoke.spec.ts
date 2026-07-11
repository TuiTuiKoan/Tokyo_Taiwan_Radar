import { expect, test, type APIResponse } from "@playwright/test";

const APP_CONTROLLED_ROUTES = [
  "/ja",
  "/ja/auth/login",
  "/ja/admin",
  "/api/me",
  "/ja/security-header-not-found-20260710",
  "/robots.txt",
  "/sitemap.xml",
  "/ja/opengraph-image",
] as const;

const PRIVATE_ROUTES = [
  "/ja/admin",
  "/ja/auth/login",
  "/en/account",
  "/ja/saved",
  "/auth/callback",
] as const;

async function expectSecurityHeaders(response: APIResponse) {
  const headers = response.headers();
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["permissions-policy"]).toBe(
    "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  );
  expect(headers["x-powered-by"]).toBeUndefined();
  expect(headers["content-security-policy"]).toBeUndefined();

  const reportOnly = headers["content-security-policy-report-only"];
  expect(reportOnly).toContain("default-src 'self'");
  expect(reportOnly).not.toContain("upgrade-insecure-requests");
  expect(reportOnly).not.toContain("report-uri");
  expect(reportOnly).not.toContain("report-to");

  const headerEntries = await response.headersArray();
  expect(
    headerEntries.filter(
      ({ name }) => name.toLowerCase() === "content-security-policy-report-only",
    ),
  ).toHaveLength(1);
}

test("security headers cover app, API, metadata, and error responses", async ({
  request,
}) => {
  const root = await request.get("/", { maxRedirects: 0 });
  expect([307, 308]).toContain(root.status());

  for (const route of APP_CONTROLLED_ROUTES) {
    const response = await request.get(route, { maxRedirects: 0 });
    await expectSecurityHeaders(response);
  }
});

test("private routes send noindex on direct and redirect responses", async ({
  request,
}) => {
  for (const route of PRIVATE_ROUTES) {
    const response = await request.get(route, { maxRedirects: 0 });
    expect(response.headers()["x-robots-tag"]).toBe("noindex, nofollow");
  }
});

test("locale preference cookie uses environment-appropriate security", async ({
  request,
}) => {
  const response = await request.get("/ja", {
    headers: { "Accept-Language": "zh-TW,zh;q=0.9" },
    maxRedirects: 0,
  });
  const cookie = response.headers()["set-cookie"] ?? "";

  expect(cookie).toContain("NEXT_LOCALE=ja");
  expect(cookie).toMatch(/Path=\//i);
  expect(cookie).toMatch(/SameSite=Lax/i);
  // This package script is a production smoke test. When testing `pnpm dev`,
  // explicitly set SECURITY_EXPECT_SECURE_COOKIE=0.
  if (process.env.SECURITY_EXPECT_SECURE_COOKIE !== "0") {
    expect(cookie).toMatch(/;\s*Secure(?:;|$)/i);
  } else {
    expect(cookie).not.toMatch(/;\s*Secure(?:;|$)/i);
  }
});
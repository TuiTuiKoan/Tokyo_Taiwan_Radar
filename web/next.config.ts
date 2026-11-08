import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";
import { withSentryConfig } from "@sentry/nextjs/config";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { LOCALES } from "./i18n/locales";
import { buildContentSecurityPolicyReportOnly } from "./lib/security/csp";

const withNextIntl = createNextIntlPlugin("./i18n.ts");

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)));

const noindexHeader = {
  key: "X-Robots-Tag",
  value: "noindex, nofollow",
};

const privateRouteSegments = ["admin", "auth", "account", "saved"] as const;

const nextConfig: NextConfig = {
  poweredByHeader: false,
  // Version skew protection. Without this, a tab loaded before a deploy keeps
  // calling Server Action IDs that no longer exist on the new deployment and
  // fails with "Failed to find Server Action" (E974). With a deployment ID,
  // Next.js detects the mismatch and performs a hard navigation instead.
  // VERCEL_DEPLOYMENT_ID is injected by Vercel; locally it is undefined, which
  // leaves the behaviour unchanged.
  deploymentId: process.env.VERCEL_DEPLOYMENT_ID,
  turbopack: {
    root: projectRoot,
  },
  // Allow LAN devices (phones, tablets) to load Next.js dev resources (HMR, RSC payloads)
  // when previewing via http://192.168.x.x:3000. No effect on production builds.
  allowedDevOrigins: ["192.168.161.110"],
  async headers() {
    const contentSecurityPolicyReportOnly =
      buildContentSecurityPolicyReportOnly({
        isDevelopment: process.env.NODE_ENV !== "production",
        supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
        sentryDsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
      });

    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "X-Content-Type-Options",
            value: "nosniff",
          },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "X-Frame-Options",
            value: "DENY",
          },
          {
            key: "Permissions-Policy",
            value:
              "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
          },
          {
            key: "Content-Security-Policy-Report-Only",
            value: contentSecurityPolicyReportOnly,
          },
        ],
      },
      ...LOCALES.flatMap((locale) =>
        privateRouteSegments.map((segment) => ({
          source: `/${locale}/${segment}/:path*`,
          headers: [noindexHeader],
        })),
      ),
      {
        source: "/auth/:path*",
        headers: [noindexHeader],
      },
    ];
  },
};

export default withSentryConfig(
  withNextIntl(nextConfig),
  {
    // Source map upload needs the org and project slugs as well as the token;
    // without them the upload was skipped and browser stack traces stayed
    // minified, so Sentry code mappings could not link to GitHub. Set
    // SENTRY_ORG (and SENTRY_PROJECT if the project is renamed) in Vercel.
    org: process.env.SENTRY_ORG,
    project: process.env.SENTRY_PROJECT ?? "javascript-nextjs-1q",
    authToken: process.env.SENTRY_AUTH_TOKEN,
    silent: !process.env.CI,
    // Also upload maps for files outside the default set (more complete traces).
    widenClientFileUpload: true,
    // Upload source maps only when SENTRY_AUTH_TOKEN is available
    sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN },
  }
);

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";
import { withSentryConfig } from "@sentry/nextjs";
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
    silent: true,
    // Upload source maps only when SENTRY_AUTH_TOKEN is available
    sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN },
  }
);

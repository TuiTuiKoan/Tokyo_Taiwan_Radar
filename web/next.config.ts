import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";
import { withSentryConfig } from "@sentry/nextjs";

const withNextIntl = createNextIntlPlugin("./i18n.ts");

const nextConfig: NextConfig = {};

export default withSentryConfig(
  withNextIntl(nextConfig),
  {
    silent: true,
    // Upload source maps only when SENTRY_AUTH_TOKEN is available
    sourcemaps: { disable: !process.env.SENTRY_AUTH_TOKEN },
  }
);

import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";
import { withSentryConfig } from "@sentry/nextjs";

const withNextIntl = createNextIntlPlugin("./i18n.ts");

const nextConfig: NextConfig = {};

export default withSentryConfig(
  withNextIntl(nextConfig),
  {
    // Silent build output
    silent: true,
    // Disable source map upload (requires SENTRY_AUTH_TOKEN env var if enabled)
    sourcemaps: { disable: true },
    // Don't create a Sentry release on every build
    autoInstrumentServerFunctions: false,
  }
);

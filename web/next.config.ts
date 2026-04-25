import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";
import { withSentryConfig } from "@sentry/nextjs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const withNextIntl = createNextIntlPlugin("./i18n.ts");

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)));

const nextConfig: NextConfig = {
  turbopack: {
    root: projectRoot,
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

/**
 * Options shared by every Sentry.init call (client, server, edge).
 * Spec: docs/specs/active/sentry-stacktrace.
 *
 * - enabled only in production builds, as before, so `next dev` stays quiet.
 * - environment comes from Vercel: "production" for the production deployment,
 *   "preview" for preview deployments (NODE_ENV is "production" on both, so it
 *   cannot tell them apart). Falls back to NODE_ENV outside Vercel.
 *   NEXT_PUBLIC_VERCEL_ENV is the browser-visible copy Vercel exposes.
 */
const isProduction = process.env.NODE_ENV === "production";

export const sentryOptions = {
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  enabled: isProduction,
  environment:
    process.env.NEXT_PUBLIC_VERCEL_ENV ?? process.env.VERCEL_ENV ?? process.env.NODE_ENV,
  // Keep quota low in production; full sampling only matters when enabled.
  tracesSampleRate: isProduction ? 0.1 : 1.0,
};

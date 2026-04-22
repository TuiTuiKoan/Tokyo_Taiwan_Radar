import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  // Captures errors in the browser. Set tracesSampleRate lower in prod to save quota.
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.1 : 1.0,
  // Only enable in production to avoid noise during dev
  enabled: process.env.NODE_ENV === "production",
});

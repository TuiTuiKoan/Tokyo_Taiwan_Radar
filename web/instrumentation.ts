// Server-side Sentry entry point. Without this file Next.js never loads
// sentry.server.config.ts / sentry.edge.config.ts, so errors in Server
// Components, route handlers and Server Actions were not reported.
import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

// Reports errors that Next.js catches while handling a request.
export const onRequestError = Sentry.captureRequestError;

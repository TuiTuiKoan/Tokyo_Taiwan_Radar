"use client";

// Root error boundary. The app has no error.tsx, so this is the only place a
// React render error is caught on the client; report it to Sentry, then show
// Next.js's built-in error page. It replaces the root layout, so it renders its
// own <html> and <body>. NextError carries no app strings, which keeps the
// i18n rule (no hardcoded UI text) without needing next-intl here.
import * as Sentry from "@sentry/nextjs";
import NextError from "next/error";
import { useEffect } from "react";

export default function GlobalError({ error }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="ja">
      <body>
        {/* statusCode 0: Next.js shows its generic error message. */}
        <NextError statusCode={0} />
      </body>
    </html>
  );
}

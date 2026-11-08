// Browser-side Sentry. Next.js 16 loads this file before the app becomes
// interactive; under Turbopack the old sentry.client.config.ts is not injected.
import * as Sentry from "@sentry/nextjs";

import { sentryOptions } from "@/lib/observability/sentry-options";

Sentry.init(sentryOptions);

// Lets Sentry trace App Router navigations.
export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;

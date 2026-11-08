// Edge runtime Sentry (the opengraph-image routes), loaded by
// instrumentation.ts register().
import * as Sentry from "@sentry/nextjs";

import { sentryOptions } from "@/lib/observability/sentry-options";

Sentry.init(sentryOptions);

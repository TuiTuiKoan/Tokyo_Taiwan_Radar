export interface ContentSecurityPolicyOptions {
  isDevelopment: boolean;
  supabaseUrl?: string;
  sentryDsn?: string;
}

const VERCEL_CONNECT_SOURCES = [
  "https://vitals.vercel-insights.com",
  "https://va.vercel-scripts.com",
] as const;

function httpOrigin(value: string | undefined): string | null {
  if (!value) return null;

  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    return url.origin;
  } catch {
    return null;
  }
}

export function buildContentSecurityPolicyReportOnly({
  isDevelopment,
  supabaseUrl,
  sentryDsn,
}: ContentSecurityPolicyOptions): string {
  const scriptSources = ["'self'", "'unsafe-inline'"];
  if (isDevelopment) scriptSources.push("'unsafe-eval'");

  const connectSources = new Set<string>([
    "'self'",
    ...VERCEL_CONNECT_SOURCES,
  ]);

  const supabaseOrigin = httpOrigin(supabaseUrl);
  if (supabaseOrigin) {
    connectSources.add(supabaseOrigin);
    const supabaseWebSocketOrigin = supabaseOrigin.replace(
      /^http(s?):/,
      (_match, secure: string) => (secure ? "wss:" : "ws:"),
    );
    connectSources.add(supabaseWebSocketOrigin);
  }

  const sentryOrigin = httpOrigin(sentryDsn);
  if (sentryOrigin) connectSources.add(sentryOrigin);

  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
    `script-src ${scriptSources.join(" ")}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    `connect-src ${Array.from(connectSources).join(" ")}`,
    "worker-src 'self' blob:",
  ];
  const policy = directives.join("; ");

  if (/[\r\n]/.test(policy)) {
    throw new Error("Content Security Policy must be a single line");
  }

  return policy;
}
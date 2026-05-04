import createMiddleware from "next-intl/middleware";
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest, type NextFetchEvent } from "next/server";
import { LOCALES } from "@/lib/types";

const intlMiddleware = createMiddleware({
  locales: LOCALES,
  defaultLocale: "zh",
  localePrefix: "always",
});

// AEO monitoring — User-Agent → bot name
// Order matters: more specific patterns first
const BOT_PATTERNS: Array<[RegExp, string]> = [
  [/GPTBot/i, "GPTBot"],
  [/OAI-SearchBot/i, "OAI-SearchBot"],
  [/ChatGPT-User/i, "ChatGPT-User"],
  [/anthropic-ai/i, "Anthropic-ai"],
  [/Claude-Web/i, "Claude-Web"],
  [/ClaudeBot/i, "ClaudeBot"],
  [/PerplexityBot/i, "PerplexityBot"],
  [/Perplexity-User/i, "Perplexity-User"],
  [/Google-Extended/i, "Google-Extended"],
  [/Googlebot/i, "Googlebot"],
  [/bingbot/i, "Bingbot"],
  [/cohere-ai/i, "cohere-ai"],
  [/Meta-ExternalAgent/i, "Meta-ExternalAgent"],
  [/FacebookBot/i, "FacebookBot"],
  [/YouBot/i, "YouBot"],
  [/DuckDuckBot/i, "DuckDuckBot"],
  [/Applebot/i, "Applebot"],
  [/Bytespider/i, "Bytespider"],
];

// AEO monitoring — referer hostname → AI source label
const AI_REFERER_HOSTS: Record<string, string> = {
  "perplexity.ai": "Perplexity",
  "www.perplexity.ai": "Perplexity",
  "chat.openai.com": "ChatGPT",
  "chatgpt.com": "ChatGPT",
  "claude.ai": "Claude",
  "gemini.google.com": "Gemini",
  "bard.google.com": "Gemini",
  "copilot.microsoft.com": "Copilot",
  "www.bing.com": "Bing-Copilot",
  "you.com": "You.com",
  "duckduckgo.com": "DuckDuckGo-AI",
};

function detectBot(ua: string | null): string | null {
  if (!ua) return null;
  for (const [pattern, name] of BOT_PATTERNS) {
    if (pattern.test(ua)) return name;
  }
  return null;
}

function detectAiReferer(referer: string | null): string | null {
  if (!referer) return null;
  try {
    const host = new URL(referer).hostname;
    return AI_REFERER_HOSTS[host] ?? null;
  } catch {
    return null;
  }
}

// Fire-and-forget log to Supabase via PostgREST. RLS allows anonymous insert.
async function logAeoVisit(payload: Record<string, unknown>): Promise<void> {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return;
  try {
    await fetch(`${url}/rest/v1/aeo_visits`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: key,
        Authorization: `Bearer ${key}`,
        Prefer: "return=minimal",
      },
      body: JSON.stringify(payload),
    });
  } catch {
    // never let logging break the request
  }
}

export async function proxy(request: NextRequest, event: NextFetchEvent) {
  // 1. Handle i18n locale routing
  const intlResponse = intlMiddleware(request);
  const response = intlResponse ?? NextResponse.next();

  // 1a. Set x-locale header so root layout can apply <html lang>
  const localeSegment = request.nextUrl.pathname.split("/")[1] ?? "";
  const detectedLocale = (LOCALES as readonly string[]).includes(localeSegment)
    ? localeSegment
    : "zh";
  response.headers.set("x-locale", detectedLocale);

  // 1b. AEO monitoring — log AI bot crawls + AI engine referrals (fire-and-forget)
  const ua = request.headers.get("user-agent");
  const referer = request.headers.get("referer");
  const country = request.headers.get("x-vercel-ip-country") ?? null;
  const botName = detectBot(ua);
  const aiSource = !botName ? detectAiReferer(referer) : null;
  if (botName || aiSource) {
    const logPromise = logAeoVisit({
      visit_type: botName ? "bot" : "ai_referral",
      bot_name: botName,
      ai_source: aiSource,
      user_agent: ua?.slice(0, 500) ?? null,
      path: request.nextUrl.pathname,
      referer: referer?.slice(0, 500) ?? null,
      country,
    });
    event.waitUntil(logPromise);
  }

  // 2. Refresh Supabase auth session
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const pathname = request.nextUrl.pathname;

  // 3. Protect /[locale]/saved — requires login
  if (pathname.match(/^\/(zh|en|ja)\/saved/) && !user) {
    const url = request.nextUrl.clone();
    const locale = pathname.split("/")[1];
    url.pathname = `/${locale}/auth/login`;
    return NextResponse.redirect(url);
  }

  // 4. Protect /[locale]/admin — check admin role server-side
  if (pathname.match(/^\/(zh|en|ja)\/admin/)) {
    if (!user) {
      const url = request.nextUrl.clone();
      const locale = pathname.split("/")[1];
      url.pathname = `/${locale}/auth/login`;
      return NextResponse.redirect(url);
    }

    // Check admin role
    const { data: role } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .single();

    if (!role || role.role !== "admin") {
      const url = request.nextUrl.clone();
      const locale = pathname.split("/")[1];
      url.pathname = `/${locale}`;
      return NextResponse.redirect(url);
    }
  }

  return response;
}

export const config = {
  matcher: [
    // Apply to all paths except /auth/*, static files, api routes, next internals,
    // and /r/* (short redirect handler — must bypass i18n locale-prefix redirect)
    "/((?!api|auth|r/|_next/static|_next/image|favicon.ico|robots\\.txt|sitemap\\.xml|llms\\.txt|.*[0-9a-f]{32,}\\.txt|google[0-9a-f]+\\.html|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};

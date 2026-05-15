import { createServerClient } from "@supabase/ssr";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Supabase Auth callback handler.
 *
 * After a user clicks the Google OAuth button or a magic-link email,
 * Supabase redirects them to:
 *   <YOUR_SITE_URL>/auth/callback?code=xxx
 *
 * This route exchanges the one-time `code` for a session cookie,
 * then redirects the user to the page they originally wanted.
 */
function normalizeNextPath(next: string | null): string {
  if (!next) return "/zh";
  return next.startsWith("/") ? next : "/zh";
}

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = normalizeNextPath(searchParams.get("next"));

  if (!code) {
    return NextResponse.redirect(`${origin}/zh/auth/login?error=auth_failed`);
  }

  const successRedirect = NextResponse.redirect(`${origin}${next}`);

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            successRedirect.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    console.error("Supabase auth callback failed", error.message);
    return NextResponse.redirect(`${origin}/zh/auth/login?error=auth_failed`);
  }

  return successRedirect;
}

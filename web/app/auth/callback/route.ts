import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

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
export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  // `next` is the page to redirect to after login (defaults to /zh)
  const next = searchParams.get("next") ?? "/zh";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // If something went wrong, redirect to login with an error flag
  return NextResponse.redirect(`${origin}/zh/auth/login?error=auth_failed`);
}

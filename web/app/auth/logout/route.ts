import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export const dynamic = "force-dynamic";

function normalizeNextPath(next: string | null): string {
  if (!next) return "/ja";
  return next.startsWith("/") ? next : "/ja";
}

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const next = normalizeNextPath(searchParams.get("next"));

  const redirectResponse = NextResponse.redirect(`${origin}${next}`);
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
            redirectResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  await supabase.auth.signOut();
  return redirectResponse;
}
import createMiddleware from "next-intl/middleware";
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { LOCALES } from "@/lib/types";

const intlMiddleware = createMiddleware({
  locales: LOCALES,
  defaultLocale: "zh",
  localePrefix: "always",
});

export async function proxy(request: NextRequest) {
  // 1. Handle i18n locale routing
  const intlResponse = intlMiddleware(request);
  const response = intlResponse ?? NextResponse.next();

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
    // Apply to all paths except static files, api routes, and next internals
    "/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};

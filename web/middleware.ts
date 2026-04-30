import { NextRequest, NextResponse } from "next/server";

const LOCALES = ["zh", "en", "ja"];

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const segment = pathname.split("/")[1] ?? "";
  const locale = LOCALES.includes(segment) ? segment : "zh";

  const response = NextResponse.next();
  response.headers.set("x-locale", locale);
  return response;
}

export const config = {
  matcher: ["/((?!_next|api|.*\\..*).*)"],
};

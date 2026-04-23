export { proxy as default } from "./proxy";

// Override the matcher to exclude /auth/* so that the OAuth/magic-link
// callback at /auth/callback is never intercepted by next-intl locale routing.
export const config = {
  matcher: [
    "/((?!api|auth|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};

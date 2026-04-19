import { redirect } from "next/navigation";

/**
 * Root page — redirects visitors to the default locale (zh).
 * e.g. visiting https://tokyo-taiwan-radar.vercel.app → /zh
 */
export default function RootPage() {
  redirect("/zh");
}

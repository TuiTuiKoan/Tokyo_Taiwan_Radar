import { redirect } from "next/navigation";

/**
 * Root page — redirects visitors to the default locale (ja).
 * e.g. visiting https://tokyotaiwanradar.com → /ja
 */
export default function RootPage() {
  redirect("/ja");
}

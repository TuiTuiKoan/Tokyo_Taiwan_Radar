import type { Locale } from "@/lib/types";
import { renderPageMotifOgImage } from "@/lib/design/pageMotifOg";

export const runtime = "edge";
export const size = { width: 1200, height: 1200 };
export const contentType = "image/png";

export default async function OGImage({
  params,
}: {
  params: Promise<{ locale: Locale }>;
}) {
  const { locale } = await params;
  return renderPageMotifOgImage(locale, "saved");
}
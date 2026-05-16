import Link from "next/link";
import { getTranslations } from "next-intl/server";
import type { Locale } from "@/lib/types";

interface Props {
  locale: Locale;
}

export default async function BackToListButton({ locale }: Props) {
  const t = await getTranslations({ locale, namespace: "event" });

  return (
    <Link
      href={`/${locale}`}
      className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-green-700 dark:hover:text-green-400 mb-4 transition"
    >
      ← {t("backToList")}
    </Link>
  );
}

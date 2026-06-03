"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { Locale } from "@/lib/types";

interface Props {
  locale: Locale;
}

export default function AccountPortalButton({ locale }: Props) {
  const t = useTranslations("home");
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  function handleClick() {
    setLoading(true);
    router.push(`/${locale}/account?tab=myEvents`);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-green-600 bg-paper text-green-700 text-xs font-semibold shadow-sm hover:bg-green-50 disabled:opacity-60 dark:bg-elevated dark:text-green-300 dark:hover:bg-green-900/30"
    >
      {loading ? t("portalLoading") : t("portalCta")}
    </button>
  );
}

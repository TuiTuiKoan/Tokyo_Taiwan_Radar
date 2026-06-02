"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import type { Locale } from "@/lib/types";

interface Props {
  locale: Locale;
}

export default function AccountPortalButton({ locale }: Props) {
  const t = useTranslations("home");
  const router = useRouter();
  const supabase = createClient();
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const {
        data: { user },
      } = await supabase.auth.getUser();

      if (!user) {
        router.push(`/${locale}/auth/login`);
        return;
      }

      const { data: profile } = await supabase
        .from("creators")
        .select("user_id")
        .eq("user_id", user.id)
        .maybeSingle();

      router.push(profile ? `/${locale}/account` : `/${locale}/account/profile`);
    } finally {
      setLoading(false);
    }
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

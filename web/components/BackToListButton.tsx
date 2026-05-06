"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { Locale } from "@/lib/types";

interface Props {
  locale: Locale;
}

export default function BackToListButton({ locale }: Props) {
  const router = useRouter();
  const t = useTranslations("event");

  function handleBack() {
    const saved = sessionStorage.getItem("ttr_list_scroll");
    if (saved) {
      router.back();
    } else {
      router.push(`/${locale}`);
    }
  }

  return (
    <button
      onClick={handleBack}
      className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-green-700 mb-4 transition"
    >
      ← {t("backToList")}
    </button>
  );
}

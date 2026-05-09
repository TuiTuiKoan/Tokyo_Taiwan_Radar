"use client";
import { useEffect } from "react";
import { useLocale } from "next-intl";

const LOCALE_MAP: Record<string, string> = {
  zh: "zh-TW",
  en: "en",
  ja: "ja",
};

export default function HtmlLangSync() {
  const locale = useLocale();
  useEffect(() => {
    const target = LOCALE_MAP[locale] ?? "zh-TW";
    if (typeof document !== "undefined" && document.documentElement.lang !== target) {
      document.documentElement.lang = target;
    }
  }, [locale]);
  return null;
}

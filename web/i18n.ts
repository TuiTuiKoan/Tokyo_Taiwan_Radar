import { getRequestConfig } from "next-intl/server";
import { LOCALES, type Locale } from "@/i18n/locales";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = (await requestLocale) as Locale;

  if (!locale || !LOCALES.includes(locale)) {
    locale = "ja";
  }

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});

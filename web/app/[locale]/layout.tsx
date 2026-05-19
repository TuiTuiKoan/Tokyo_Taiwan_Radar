import type { Metadata } from "next";
import { headers } from "next/headers";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { LOCALES, type Locale } from "@/lib/types";
import "../globals.css";
import Navbar from "@/components/Navbar";
import SiteBackground from "@/components/SiteBackground";
import { FloatingShapesAuto } from "@/lib/design/FloatingShapesAuto";
import HtmlLangSync from "@/components/HtmlLangSync";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/next";

const SITE_TITLES: Record<string, string> = {
  zh: "Tokyo Taiwan Radar 東京台灣雷達｜日本台灣活動雷達",
  en: "Tokyo Taiwan Radar — Taiwan Events in Japan",
  ja: "Tokyo Taiwan Radar 東京台湾レーダー｜日本全国の台湾関連イベント",
};

const SITE_DESCRIPTIONS: Record<string, string> = {
  zh: "彙整日本全國的台灣相關文化活動，電影、音樂、展覽、講座一站查詢。",
  en: "Aggregating Taiwan-related cultural events across Japan — films, concerts, exhibitions, and more.",
  ja: "東京・大阪・京都など日本全国の台湾関連イベントを集めたプラットフォームです。",
};

const OG_LOCALES: Record<string, string> = {
  zh: "zh_TW",
  en: "en_US",
  ja: "ja_JP",
};

async function getMetadataBaseContext() {
  const headerList = await headers();
  const requestHost =
    headerList.get("x-forwarded-host") ?? headerList.get("host");

  if (requestHost && /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(requestHost)) {
    const requestProto =
      headerList.get("x-forwarded-proto") ??
      (requestHost.startsWith("localhost") || requestHost.startsWith("127.0.0.1")
        ? "http"
        : "https");
    return {
      base: `${requestProto}://${requestHost}`,
      isLocalRequest: true,
    };
  }

  const configuredBase =
    process.env.NEXT_PUBLIC_SITE_URL ??
    process.env.VERCEL_PROJECT_PRODUCTION_URL ??
    process.env.VERCEL_URL;

  if (!configuredBase) {
    return {
      base: "http://localhost:3000",
      isLocalRequest: true,
    };
  }

  return {
    base: (configuredBase.startsWith("http")
      ? configuredBase
      : `https://${configuredBase}`
    ).replace(/\/$/, ""),
    isLocalRequest: false,
  };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const { base, isLocalRequest } = await getMetadataBaseContext();
  const title = SITE_TITLES[locale] ?? SITE_TITLES.zh;
  const description = SITE_DESCRIPTIONS[locale] ?? SITE_DESCRIPTIONS.zh;
  const image = `${base}/${locale}/opengraph-image`;

  return {
    title,
    description,
    alternates: {
      canonical: `${base}/${locale}`,
      ...(isLocalRequest
        ? {}
        : {
            languages: {
              zh: `${base}/zh`,
              en: `${base}/en`,
              ja: `${base}/ja`,
              "x-default": `${base}/zh`,
            },
          }),
    },
    openGraph: {
      title,
      description,
      url: `${base}/${locale}`,
      siteName: "Tokyo Taiwan Radar",
      locale: OG_LOCALES[locale] ?? "zh_TW",
      type: "website",
      images: [{ url: image, width: 1200, height: 1200, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [image],
    },
  };
}

export function generateStaticParams() {
  return LOCALES.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!LOCALES.includes(locale as Locale)) {
    notFound();
  }

  setRequestLocale(locale);

  const messages = await getMessages();
  const tGeneral = await getTranslations("general");

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      <SiteBackground />
      <FloatingShapesAuto />
      <HtmlLangSync />
      <Navbar locale={locale as Locale} />
      <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      <footer className="border-t border-line mt-12 py-4 text-center text-xs text-fg-muted">
        {tGeneral("footerCredit")}
      </footer>
      <Analytics />
      <SpeedInsights />
    </NextIntlClientProvider>
  );
}

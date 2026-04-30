import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { LOCALES, type Locale } from "@/lib/types";
import "../globals.css";
import Navbar from "@/components/Navbar";
import { Analytics } from "@vercel/analytics/react";
import { createClient } from "@/lib/supabase/server";

const SITE_TITLES: Record<string, string> = {
  zh: "Tokyo Taiwan Radar｜日本台灣活動雷達",
  en: "Tokyo Taiwan Radar — Taiwan Events in Japan",
  ja: "Tokyo Taiwan Radar｜日本全国の台湾関連イベント",
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

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "";
  const title = SITE_TITLES[locale] ?? SITE_TITLES.zh;
  const description = SITE_DESCRIPTIONS[locale] ?? SITE_DESCRIPTIONS.zh;

  return {
    title,
    description,
    alternates: {
      canonical: `${base}/${locale}`,
      languages: {
        zh: `${base}/zh`,
        en: `${base}/en`,
        ja: `${base}/ja`,
        "x-default": `${base}/zh`,
      },
    },
    openGraph: {
      title,
      description,
      url: `${base}/${locale}`,
      siteName: "Tokyo Taiwan Radar",
      locale: OG_LOCALES[locale] ?? "zh_TW",
      type: "website",
    },
    twitter: {
      card: "summary",
      title,
      description,
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

  const messages = await getMessages();
  const tGeneral = await getTranslations("general");

  // Check admin role server-side (for Navbar display only — access control is in middleware + page)
  let isAdmin = false;
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (user) {
    const { data: roleRow } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .single();
    isAdmin = roleRow?.role === "admin";
  }

  return (
    <NextIntlClientProvider messages={messages}>
      <Navbar locale={locale as Locale} isAdmin={isAdmin} />
      <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      <footer className="border-t border-gray-100 mt-12 py-4 text-center text-xs text-gray-400">
        {tGeneral("footerCredit")}
      </footer>
      <Analytics />
    </NextIntlClientProvider>
  );
}

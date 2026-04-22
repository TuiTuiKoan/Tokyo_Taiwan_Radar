import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { LOCALES, type Locale } from "@/lib/types";
import "../globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "Tokyo Taiwan Radar",
  description: "東京の台湾関連イベントを集めたプラットフォーム",
};

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

  return (
    <NextIntlClientProvider messages={messages}>
      <Navbar locale={locale as Locale} />
      <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      <footer className="border-t border-gray-100 mt-12 py-4 text-center text-xs text-gray-400">
        營運維護：對對觀 2026
      </footer>
    </NextIntlClientProvider>
  );
}

import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { LOCALES, type Locale } from "@/lib/types";
import "../globals.css";
import Navbar from "@/components/Navbar";
import { Analytics } from "@vercel/analytics/react";
import { createClient } from "@/lib/supabase/server";

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
        營運維護：對對觀 2026
      </footer>
      <Analytics />
    </NextIntlClientProvider>
  );
}

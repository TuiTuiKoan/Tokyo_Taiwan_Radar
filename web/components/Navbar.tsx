"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useState } from "react";
import { type Locale, LOCALES } from "@/lib/types";
import type { User } from "@supabase/supabase-js";

interface Props {
  locale: Locale;
}

const LOCALE_LABELS: Record<Locale, string> = {
  zh: "繁中",
  en: "EN",
  ja: "日本語",
};

export default function Navbar({ locale }: Props) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const supabase = createClient();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
    const { data: listener } = supabase.auth.onAuthStateChange((_, session) => {
      setUser(session?.user ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.reload();
  }

  // Build locale-switched path
  function localePath(targetLocale: Locale) {
    const segments = pathname.split("/");
    segments[1] = targetLocale;
    return segments.join("/");
  }

  return (
    <header className="border-b border-gray-200 bg-white sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link
          href={`/${locale}`}
          className="font-bold text-lg text-green-700 whitespace-nowrap"
        >
          🇹🇼 Tokyo Taiwan Radar
        </Link>

        {/* Main nav */}
        <nav className="flex items-center gap-4 text-sm">
          <Link href={`/${locale}`} className="hover:text-green-700 transition">
            {t("home")}
          </Link>
          {user && (
            <Link href={`/${locale}/saved`} className="hover:text-green-700 transition">
              {t("saved")}
            </Link>
          )}

          {/* Language switcher */}
          <div className="flex gap-1 ml-2">
            {LOCALES.map((loc) => (
              <Link
                key={loc}
                href={localePath(loc)}
                className={`px-2 py-1 rounded text-xs border transition ${
                  loc === locale
                    ? "bg-green-600 text-white border-green-600"
                    : "border-gray-300 hover:border-green-500"
                }`}
              >
                {LOCALE_LABELS[loc]}
              </Link>
            ))}
          </div>

          {/* Auth */}
          {user ? (
            <button
              onClick={handleLogout}
              className="ml-2 text-gray-500 hover:text-red-500 transition text-xs"
            >
              {t("logout")}
            </button>
          ) : (
            <Link
              href={`/${locale}/auth/login`}
              className="ml-2 bg-green-600 text-white px-3 py-1.5 rounded-md text-xs hover:bg-green-700 transition"
            >
              {t("login")}
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}

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

const LOCALE_FLAGS: Record<Locale, string> = {
  zh: "🇹🇼",
  en: "🇬🇧",
  ja: "🇯🇵",
};

export default function Navbar({ locale }: Props) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const supabase = createClient();
  const [user, setUser] = useState<User | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

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

        <div className="flex items-center gap-1">
          {/* Desktop nav links */}
          <nav className="hidden md:flex items-center gap-4 text-sm mr-2">
            <Link href={`/${locale}`} className="hover:text-green-700 transition">
              {t("home")}
            </Link>
            {user && (
              <Link href={`/${locale}/saved`} className="hover:text-green-700 transition">
                {t("saved")}
              </Link>
            )}
          </nav>

          {/* Language switcher — flags */}
          <div className="flex gap-0.5">
            {LOCALES.map((loc) => (
              <Link
                key={loc}
                href={localePath(loc)}
                title={loc.toUpperCase()}
                className={`w-8 h-8 flex items-center justify-center rounded text-lg transition ${
                  loc === locale
                    ? "bg-green-100 ring-2 ring-green-500"
                    : "opacity-50 hover:opacity-100 hover:bg-gray-100"
                }`}
              >
                {LOCALE_FLAGS[loc]}
              </Link>
            ))}
          </div>

          {/* Auth — icon only */}
          {user ? (
            <button
              onClick={handleLogout}
              title={t("logout")}
              className="w-8 h-8 flex items-center justify-center rounded hover:bg-red-50 text-gray-500 hover:text-red-500 transition"
            >
              {/* Logout icon */}
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
            </button>
          ) : (
            <Link
              href={`/${locale}/auth/login`}
              title={t("login")}
              className="w-8 h-8 flex items-center justify-center rounded bg-green-600 text-white hover:bg-green-700 transition"
            >
              {/* Person icon */}
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </Link>
          )}

          {/* Hamburger — mobile only */}
          <button
            className="md:hidden w-8 h-8 flex items-center justify-center rounded hover:bg-gray-100 transition ml-1"
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="Menu"
            aria-expanded={menuOpen}
          >
            {menuOpen ? (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile dropdown menu */}
      {menuOpen && (
        <nav className="md:hidden border-t border-gray-100 bg-white shadow-md">
          <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col gap-1 text-sm">
            <Link
              href={`/${locale}`}
              onClick={() => setMenuOpen(false)}
              className="px-3 py-2.5 rounded-md hover:bg-green-50 hover:text-green-700 transition"
            >
              {t("home")}
            </Link>
            {user && (
              <Link
                href={`/${locale}/saved`}
                onClick={() => setMenuOpen(false)}
                className="px-3 py-2.5 rounded-md hover:bg-green-50 hover:text-green-700 transition"
              >
                {t("saved")}
              </Link>
            )}
            {user && (
              <button
                onClick={() => { setMenuOpen(false); handleLogout(); }}
                className="text-left px-3 py-2.5 rounded-md text-red-500 hover:bg-red-50 transition"
              >
                {t("logout")}
              </button>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}

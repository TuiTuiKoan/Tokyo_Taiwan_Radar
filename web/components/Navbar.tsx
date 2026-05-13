"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { useEffect, useRef, useState, Suspense } from "react";
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

const LOCALE_LABELS: Record<Locale, string> = {
  zh: "繁中",
  en: "EN",
  ja: "日本語",
};

interface NavbarLangSwitcherProps {
  locale: Locale;
}

function NavbarLangSwitcher({ locale }: NavbarLangSwitcherProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [langOpen, setLangOpen] = useState(false);
  const langRef = useRef<HTMLDivElement>(null);

  // Close language dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (langRef.current && !langRef.current.contains(e.target as Node)) {
        setLangOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function localePath(targetLocale: Locale): string {
    const segments = pathname.split("/");
    segments[1] = targetLocale;
    const path = segments.join("/");
    const qs = searchParams.toString();
    return qs ? `${path}?${qs}` : path;
  }

  return (
    <div className="relative" ref={langRef}>
      <button
        onClick={() => setLangOpen((o) => !o)}
        title={locale.toUpperCase()}
        aria-expanded={langOpen}
        aria-label="Switch language"
        className="w-8 h-8 flex items-center justify-center rounded hover:bg-green-50 text-[#3A261F] hover:text-green-700 transition"
      >
        {/* Globe icon */}
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
          <circle cx="12" cy="12" r="10" />
          <line x1="2" y1="12" x2="22" y2="12" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
      </button>

      {langOpen && (
        <div className="absolute right-0 top-10 bg-surface border border-line rounded-xl shadow-lg py-1 min-w-[110px] z-50">
          {LOCALES.map((loc) => (
            <Link
              key={loc}
              href={localePath(loc)}
              scroll={false}
              onClick={() => {
                sessionStorage.setItem("ttr_locale_scroll", String(window.scrollY));
                setLangOpen(false);
              }}
              className={`flex items-center gap-2 px-3 py-2 text-sm transition hover:bg-green-50 hover:text-green-700 ${
                loc === locale ? "font-semibold text-green-700" : "text-fg"
              }`}
            >
              <span>{LOCALE_FLAGS[loc]}</span>
              <span>{LOCALE_LABELS[loc]}</span>
              {loc === locale && <span className="ml-auto text-green-500 text-xs">✓</span>}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Navbar({ locale }: Props) {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const supabase = createClient();
  const [user, setUser] = useState<User | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => setUser(data.user));
    const { data: listener } = supabase.auth.onAuthStateChange((_, session) => {
      setUser(session?.user ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    fetch("/api/me")
      .then((r) => r.json())
      .then((d) => setIsAdmin(!!d.isAdmin))
      .catch(() => {});
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.reload();
  }

  return (
    <header className="border-b border-line bg-paper/50 backdrop-blur sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo — wax-apple mascot + wordmark */}
        <Link
          href={`/${locale}`}
          className="flex items-center gap-2 sm:gap-3 text-[#3A261F] whitespace-nowrap"
        >
          <svg viewBox="0 0 200 240" className="w-8 h-8 shrink-0" aria-hidden>
            {/* inline mascot — antenna + body + cheek + eye */}
            <g transform="rotate(3 100 150)">
              <path d="M100,80 C110,30 60,0 80,20 C100,40 140,50 160,30" fill="none" stroke="#1F5E2B" strokeWidth="6" strokeLinecap="round" />
              <circle cx="164" cy="26" r="8" fill="#1F5E2B" />
              <circle cx="164" cy="26" r="3" fill="#C4E86F" />
              <path d="M100,80 C 86,80 78,88 74,98 C 72,108 66,116 60,128 C 46,146 30,166 36,190 C 44,210 72,216 102,216 C 132,216 160,210 164,190 C 170,166 154,146 140,128 C 134,116 128,108 126,98 C 122,88 114,80 100,80 Z" fill="#E84860" />
              <ellipse cx="58" cy="142" rx="13" ry="8" fill="#FF7AA0" opacity="0.7" transform="rotate(-10 58 142)" />
              <ellipse cx="80" cy="116" rx="13" ry="14" fill="white" />
              <circle cx="78" cy="118" r="7" fill="#1A1818" />
              <circle cx="75" cy="115" r="2.6" fill="white" />
              <path d="M116,128 Q124,118 132,128" fill="none" stroke="#1A1818" strokeWidth="4.5" strokeLinecap="round" />
            </g>
          </svg>
          <div className="flex flex-col sm:flex-row sm:items-center sm:gap-3">
            <span className="font-display font-black text-sm sm:text-lg shrink-0 text-[#3A261F]">Tokyo Taiwan Radar</span>
            <span className="hidden min-[380px]:block text-[7px] sm:text-[9px] font-medium text-fg-muted font-sans tracking-wide pt-[2px]">
              {locale === "en" ? "Catching all of Taiwan in Japan, daily." : locale === "zh" ? "全日本的台灣，每日捕捉。" : "日本ぜんぶの台湾を、毎日キャッチ。"}
            </span>
          </div>
        </Link>

        <div className="flex items-center gap-1">
          {/* Desktop nav links */}
          <nav className="hidden md:flex items-center gap-4 text-sm mr-2 text-[#3A261F]">
            <Link href={`/${locale}`} className="hover:text-green-700 transition">
              {t("home")}
            </Link>
            <Link href={`/${locale}/announcements`} className="hover:text-green-700 transition">
              {t("news")}
            </Link>
            <Link href={`/${locale}/about`} className="hover:text-green-700 transition">
              {t("about")}
            </Link>
            <Link href={`/${locale}/sources`} className="hover:text-green-700 transition">
              {t("sources")}
            </Link>
            {user && (
              <Link
                href={`/${locale}/saved`}
                title={t("saved")}
                className="w-8 h-8 flex items-center justify-center rounded hover:bg-green-50 text-[#3A261F] hover:text-green-700 transition"
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                </svg>
              </Link>
            )}
            {isAdmin && (
              <Link href={`/${locale}/admin`} className="hover:text-green-700 transition font-medium text-green-700">
                {t("admin")}
              </Link>
            )}
          </nav>

          {/* Language switcher — globe icon + dropdown */}
          <Suspense fallback={<div className="w-8 h-8" />}>
            <NavbarLangSwitcher locale={locale} />
          </Suspense>

          {/* Auth — icon only */}
          {user ? (
            <button
              onClick={handleLogout}
              title={t("logout")}
              className="w-8 h-8 flex items-center justify-center rounded hover:bg-green-50 text-[#3A261F] hover:text-green-700 transition"
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
              className="w-8 h-8 flex items-center justify-center rounded hover:bg-green-50 text-[#3A261F] hover:text-green-700 transition"
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
            className="md:hidden w-8 h-8 flex items-center justify-center rounded hover:bg-green-50 text-[#3A261F] hover:text-green-700 transition ml-1"
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
        <nav className="md:hidden border-t border-line bg-surface shadow-md">
          <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col gap-1 text-sm text-[#3A261F]">
            <Link
              href={`/${locale}`}
              onClick={() => setMenuOpen(false)}
              className="px-3 py-2.5 rounded-md hover:bg-green-50 hover:text-green-700 transition"
            >
              {t("home")}
            </Link>
            <Link
              href={`/${locale}/about`}
              onClick={() => setMenuOpen(false)}
              className="px-3 py-2.5 rounded-md hover:bg-green-50 hover:text-green-700 transition"
            >
              {t("about")}
            </Link>
            <Link
              href={`/${locale}/sources`}
              onClick={() => setMenuOpen(false)}
              className="px-3 py-2.5 rounded-md hover:bg-green-50 hover:text-green-700 transition"
            >
              {t("sources")}
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
            {isAdmin && (
              <Link
                href={`/${locale}/admin`}
                onClick={() => setMenuOpen(false)}
                className="px-3 py-2.5 rounded-md hover:bg-green-50 hover:text-green-700 transition font-medium"
              >
                {t("admin")}
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

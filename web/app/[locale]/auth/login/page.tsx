"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";

interface Props {
  locale: string;
}

function isInAppBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  return /Line\/|FBAN|FBAV|Instagram|MicroMessenger|Twitter|Snapchat|TikTok|Pinterest|LinkedIn/.test(
    ua
  );
}

export default function LoginPage({ params }: { params: Promise<Props> }) {
  // Note: for client components in Next.js 15 app router, we access locale from usePathname
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inAppBrowser, setInAppBrowser] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  useEffect(() => {
    setInAppBrowser(isInAppBrowser());
  }, []);

  async function handleCopyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 3000);
    } catch {
      // Fallback: prompt the user to copy manually
      window.prompt("Copy this URL and open it in Safari or Chrome:", window.location.href);
    }
  }

  const supabase = createClient();

  async function handleGoogleLogin() {
    const origin = window.location.origin;
    const locale = window.location.pathname.split("/")[1];
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        // Must match the URL added in Supabase → Authentication → URL Configuration
        redirectTo: `${origin}/auth/callback?next=/${locale}`,
      },
    });
  }

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const origin = window.location.origin;
    const locale = window.location.pathname.split("/")[1];
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        // Must match the URL added in Supabase → Authentication → URL Configuration
        emailRedirectTo: `${origin}/auth/callback?next=/${locale}`,
      },
    });
    if (error) {
      setError(error.message);
    } else {
      setSent(true);
    }
    setLoading(false);
  }

  if (sent) {
    return (
      <div className="max-w-sm mx-auto mt-24 text-center">
        <p className="text-lg text-gray-700">{t("magicLinkSent")}</p>
      </div>
    );
  }

  return (
    <div className="max-w-sm mx-auto mt-24">
      {inAppBrowser && (
        <div className="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="mb-3">{t("inAppBrowserWarning")}</p>
          <button
            onClick={handleCopyLink}
            className="w-full rounded-lg bg-amber-500 px-4 py-2 font-medium text-white hover:bg-amber-600 transition"
          >
            {linkCopied ? t("linkCopied") : t("openInBrowser")}
          </button>
        </div>
      )}

      <h1 className="text-2xl font-bold mb-2">{t("loginTitle")}</h1>
      <p className="text-gray-500 mb-8">{t("loginDesc")}</p>

      <button
        onClick={inAppBrowser ? undefined : handleGoogleLogin}
        disabled={inAppBrowser}
        className="w-full flex items-center justify-center gap-3 border border-gray-300 rounded-lg px-4 py-3 hover:bg-gray-50 transition mb-4 font-medium disabled:opacity-40 disabled:cursor-not-allowed"
      >
        <svg viewBox="0 0 24 24" className="w-5 h-5" aria-hidden="true">
          <path
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            fill="#4285F4"
          />
          <path
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            fill="#34A853"
          />
          <path
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            fill="#FBBC05"
          />
          <path
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            fill="#EA4335"
          />
        </svg>
        {t("loginGoogle")}
      </button>

      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-2 text-gray-400">or</span>
        </div>
      </div>

      <form onSubmit={handleEmailLogin} className="space-y-3">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t("email")}
          className="w-full border border-gray-300 rounded-lg px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
        />
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-green-600 text-white rounded-lg px-4 py-3 font-medium hover:bg-green-700 disabled:opacity-50 transition"
        >
          {loading ? "..." : t("loginEmail")}
        </button>
      </form>
    </div>
  );
}

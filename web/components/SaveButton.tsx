"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import type { Locale } from "@/lib/types";

interface Props {
  eventId: string;
  initialSaved: boolean;
  locale: Locale;
  /** compact: icon-only, no text label */
  compact?: boolean;
}

export default function SaveButton({ eventId, initialSaved, locale, compact = false }: Props) {
  const t = useTranslations("event");
  const [saved, setSaved] = useState(initialSaved);
  const [loading, setLoading] = useState(false);
  const supabase = createClient();

  // Self-initialize saved state on mount (page may be served from ISR cache)
  useEffect(() => {
    async function loadSaved() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from("saved_events")
        .select("id")
        .eq("user_id", user.id)
        .eq("event_id", eventId)
        .maybeSingle();
      setSaved(!!data);
    }
    loadSaved();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId]);

  async function toggle() {
    setLoading(true);
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      const next = `${window.location.pathname}${window.location.search}`;
      window.location.href = `/${locale}/auth/login?next=${encodeURIComponent(next)}`;
      return;
    }

    if (saved) {
      await supabase
        .from("saved_events")
        .delete()
        .eq("user_id", user.id)
        .eq("event_id", eventId);
    } else {
      await supabase
        .from("saved_events")
        .insert({ user_id: user.id, event_id: eventId });
    }

    setSaved(!saved);
    setLoading(false);
  }

  return (
    <button
      onClick={toggle}
      disabled={loading}
      title={saved ? t("unsave") : t("save")}
      aria-label={saved ? t("unsave") : t("save")}
      className={`inline-flex items-center gap-2 rounded-lg border text-sm font-medium transition shrink-0 ${
        compact ? "w-8 h-8 justify-center p-0" : "min-w-[108px] justify-center px-3 py-2"
      } ${
        saved
          ? "bg-green-600 text-white border-green-600 hover:bg-green-700"
          : "border-line text-[#1F5E2B] dark:text-green-400 hover:text-[#1F5E2B] dark:hover:text-green-400 hover:bg-[#F7FFE8] dark:hover:bg-[#C4E86F]/20"
      } disabled:opacity-50`}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill={saved ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="w-4 h-4 shrink-0"
        aria-hidden
      >
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
      {!compact && <span>{saved ? t("unsave") : t("save")}</span>}
    </button>
  );
}

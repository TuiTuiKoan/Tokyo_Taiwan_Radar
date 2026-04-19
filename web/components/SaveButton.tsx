"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import type { Locale } from "@/lib/types";

interface Props {
  eventId: string;
  initialSaved: boolean;
  locale: Locale;
}

export default function SaveButton({ eventId, initialSaved, locale }: Props) {
  const t = useTranslations("event");
  const [saved, setSaved] = useState(initialSaved);
  const [loading, setLoading] = useState(false);
  const supabase = createClient();

  async function toggle() {
    setLoading(true);
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      window.location.href = `/${locale}/auth/login`;
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
      className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition shrink-0 ${
        saved
          ? "bg-green-600 text-white border-green-600 hover:bg-green-700"
          : "border-gray-300 hover:border-green-500 hover:text-green-700"
      } disabled:opacity-50`}
    >
      {saved ? "♥" : "♡"} {saved ? t("unsave") : t("save")}
    </button>
  );
}

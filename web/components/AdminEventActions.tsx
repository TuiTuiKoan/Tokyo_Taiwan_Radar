"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import IsActiveToggle from "@/components/IsActiveToggle";
import Link from "next/link";
import { useTranslations } from "next-intl";

interface Props {
  eventId: string;
  locale: string;
  initialIsActive: boolean;
}

export default function AdminEventActions({ eventId, locale, initialIsActive }: Props) {
  const [isAdmin, setIsAdmin] = useState(false);
  const t = useTranslations("event");

  useEffect(() => {
    const supabase = createClient();
    async function checkAdmin() {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from("user_roles")
        .select("role")
        .eq("user_id", user.id)
        .single();
      if (data?.role === "admin") setIsAdmin(true);
    }
    checkAdmin();
  }, []);

  if (!isAdmin) return null;

  return (
    <>
      <Link
        href={`/${locale}/admin/${eventId}`}
        className="shrink-0 text-xs text-gray-400 hover:text-green-700 border border-gray-200 hover:border-green-400 rounded px-1.5 py-0.5 transition"
        title={t("editEvent")}
      >
        ✎
      </Link>
      <IsActiveToggle eventId={eventId} initialIsActive={initialIsActive} />
    </>
  );
}

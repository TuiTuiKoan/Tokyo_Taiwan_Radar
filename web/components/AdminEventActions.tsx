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
  isAdmin?: boolean;
}

export default function AdminEventActions({ eventId, locale, initialIsActive, isAdmin: isAdminProp }: Props) {
  const [isAdmin, setIsAdmin] = useState(Boolean(isAdminProp));
  const t = useTranslations("event");

  useEffect(() => {
    // Prefer server-resolved admin state when provided.
    if (typeof isAdminProp === "boolean") {
      setIsAdmin(isAdminProp);
      return;
    }

    const supabase = createClient();
    async function checkAdmin() {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) {
          setIsAdmin(false);
          return;
        }
        const { data, error } = await supabase
          .from("user_roles")
          .select("role")
          .eq("user_id", user.id)
          .single();
        if (!error && data?.role === "admin") {
          setIsAdmin(true);
        } else {
          setIsAdmin(false);
        }
      } catch {
        setIsAdmin(false);
      }
    }
    void checkAdmin();
  }, [isAdminProp]);

  if (!isAdmin) return null;

  return (
    <>
      <Link
        href={`/${locale}/admin/${eventId}`}
        className="shrink-0 text-xs text-fg-subtle hover:text-green-700 border border-line hover:border-green-400 rounded px-1.5 py-0.5 transition"
        title={t("editEvent")}
      >
        ✎
      </Link>
      <IsActiveToggle eventId={eventId} initialIsActive={initialIsActive} />
    </>
  );
}

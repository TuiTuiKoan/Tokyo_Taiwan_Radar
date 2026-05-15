"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

interface Props {
  eventId: string;
  initialIsActive: boolean;
}

export default function IsActiveToggle({ eventId, initialIsActive }: Props) {
  const [isActive, setIsActive] = useState(initialIsActive);
  const [loading, setLoading] = useState(false);

  async function handleToggle() {
    setLoading(true);
    const supabase = createClient();
    const targetActive = !isActive;
    const update: Record<string, unknown> = { is_active: targetActive };
    if (!targetActive) {
      update.deactivated_at = new Date().toISOString();
      update.deactivated_reason = "manually deactivated by admin";
      update.deactivated_by_pass = "admin_manual";
    } else {
      update.deactivated_at = null;
      update.deactivated_reason = null;
      update.deactivated_by_pass = null;
    }
    const { error } = await supabase
      .from("events")
      .update(update)
      .eq("id", eventId);
    if (!error) {
      setIsActive(targetActive);
    } else {
      alert(`切換公開狀態失敗：${error.message}`);
    }
    setLoading(false);
  }

  return (
    <button
      onClick={handleToggle}
      disabled={loading}
      title={isActive ? "停用活動（設為 inactive）" : "啟用活動（設為 active）"}
      className={`shrink-0 text-xs border rounded px-1.5 py-0.5 transition disabled:opacity-40 ${
        isActive
          ? "text-green-600 border-green-300 hover:bg-red-50 hover:text-red-600 hover:border-red-300"
          : "text-red-500 border-red-200 bg-red-50 hover:bg-green-50 hover:text-green-600 hover:border-green-300"
      }`}
    >
      {loading ? "…" : isActive ? "●" : "○"}
    </button>
  );
}

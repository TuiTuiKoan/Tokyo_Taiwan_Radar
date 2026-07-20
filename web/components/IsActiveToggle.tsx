"use client";

import { useState } from "react";
import { setAdminEventActive } from "@/app/actions/admin-events";

interface Props {
  eventId: string;
  initialIsActive: boolean;
}

export default function IsActiveToggle({ eventId, initialIsActive }: Props) {
  const [isActive, setIsActive] = useState(initialIsActive);
  const [loading, setLoading] = useState(false);

  async function handleToggle() {
    setLoading(true);
    const targetActive = !isActive;
    try {
      const result = await setAdminEventActive(eventId, targetActive);
      if (!result.ok) {
        if (result.error.includes("exact_id_mismatch")) {
          alert("切換未生效（session 可能已過期），請重新整理頁面後再試。");
        } else {
          alert(`切換公開狀態失敗：${result.error}`);
        }
      } else {
        setIsActive(targetActive);
      }
    } catch (error) {
      alert(`切換公開狀態失敗：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
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

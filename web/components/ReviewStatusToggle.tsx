"use client";

import { useState } from "react";

interface Props {
  eventId: string;
  initialAnnotationStatus: string | null;
}

/**
 * Admin-only toggle that flips an event's `annotation_status`
 * between `annotated` ↔ `reviewed`.
 *
 * `reviewed` is the "completely confirmed" state — the annotator
 * skips reviewed events on subsequent runs, protecting manually
 * verified fields from being overwritten by GPT.
 *
 * Hidden when status is `pending` or `error` (those are pipeline
 * states, not user-controllable here — use the admin edit page).
 */
export default function ReviewStatusToggle({ eventId, initialAnnotationStatus }: Props) {
  const [status, setStatus] = useState(initialAnnotationStatus ?? "");
  const [loading, setLoading] = useState(false);

  // Only show for annotated / reviewed states
  if (status !== "annotated" && status !== "reviewed") return null;

  const isReviewed = status === "reviewed";

  async function handleToggle() {
    setLoading(true);
    try {
      const target = isReviewed ? "annotated" : "reviewed";
      const res = await fetch(`/api/admin/events/${eventId}/review-status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target }),
      });
      const payload = (await res.json().catch(() => ({}))) as {
        error?: string;
        annotation_status?: string | null;
      };
      if (!res.ok) {
        alert(`切換確認狀態失敗：${payload.error ?? `HTTP ${res.status}`}`);
      } else {
        setStatus(payload.annotation_status ?? target);
      }
    } catch (err) {
      alert(`切換確認狀態失敗：${err instanceof Error ? err.message : "未知錯誤"}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={loading}
      title={
        isReviewed
          ? "已確認所有內容（取消確認 → annotated，annotator 會重新處理）"
          : "標記為已確認所有內容（reviewed → annotator 不再覆寫）"
      }
      className={`shrink-0 text-xs border rounded px-1.5 py-0.5 transition disabled:opacity-40 ${
        isReviewed
          ? "text-blue-600 border-blue-300 bg-blue-50 hover:bg-amber-50 hover:text-amber-600 hover:border-amber-300"
          : "text-fg-subtle border-line hover:text-blue-600 hover:border-blue-300"
      }`}
    >
      {loading ? "…" : isReviewed ? "✓✓" : "✓"}
    </button>
  );
}

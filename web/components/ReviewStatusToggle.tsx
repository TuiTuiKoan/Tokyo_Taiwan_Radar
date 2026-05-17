"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

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
    const supabase = createClient();
    const target = isReviewed ? "annotated" : "reviewed";
    const { error, data: updatedRows } = await supabase
      .from("events")
      .update({ annotation_status: target })
      .eq("id", eventId)
      .select("id");
    if (error) {
      alert(`切換確認狀態失敗：${error.message}`);
    } else if (!updatedRows || updatedRows.length === 0) {
      alert("切換未生效（session 可能已過期），請重新整理頁面後再試。");
    } else {
      setStatus(target);
    }
    setLoading(false);
  }

  return (
    <button
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

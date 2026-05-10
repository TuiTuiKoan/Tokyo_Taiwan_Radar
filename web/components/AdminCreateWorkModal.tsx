"use client";

import { useEffect } from "react";
import type { Locale } from "@/lib/types";
import AdminWorkForm from "@/components/AdminWorkForm";

interface Props {
  locale: Locale;
  onClose: () => void;
}

export default function AdminCreateWorkModal({ locale, onClose }: Props) {
  // Close on Escape key
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/80"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Modal card */}
      <div className="relative z-10 bg-surface rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-fg-strong">新增作品</h2>
          <button
            onClick={onClose}
            className="text-fg-subtle hover:text-fg text-xl leading-none transition"
            aria-label="關閉"
          >
            ✕
          </button>
        </div>
        <AdminWorkForm
          work={null}
          locale={locale}
          onSuccess={onClose}
        />
      </div>
    </div>
  );
}

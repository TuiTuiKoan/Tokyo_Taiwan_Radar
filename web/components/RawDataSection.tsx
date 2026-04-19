"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

interface Props {
  rawTitle: string | null;
  rawDescription: string | null;
}

export default function RawDataSection({ rawTitle, rawDescription }: Props) {
  const t = useTranslations("event");
  const [open, setOpen] = useState(false);

  if (!rawTitle && !rawDescription) return null;

  return (
    <div className="mb-8 border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-400 hover:bg-gray-50 transition"
      >
        <span className="font-medium">{t("rawData")}</span>
        <span className="text-lg leading-none">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 border-t border-gray-100">
          {rawTitle && (
            <div className="mt-3">
              <h3 className="text-xs text-gray-400 mb-1">{t("rawTitle")}</h3>
              <p className="text-sm text-gray-600">{rawTitle}</p>
            </div>
          )}
          {rawDescription && (
            <div className="mt-3">
              <h3 className="text-xs text-gray-400 mb-1">{t("rawDescription")}</h3>
              <p className="whitespace-pre-wrap text-sm text-gray-600 max-h-96 overflow-y-auto">
                {rawDescription}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

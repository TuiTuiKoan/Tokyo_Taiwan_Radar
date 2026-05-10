"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { Locale } from "@/lib/types";

export interface QualityRow {
  id: string;
  raw_title: string | null;
  source_name: string | null;
  location_name?: string | null;
  location_prefectures?: string[] | null;
}

interface Props {
  title: string;
  count: number;
  locale: Locale;
  items: QualityRow[];
  allClearLabel: string;
  previewRows?: number;
}

export default function QualitySection({
  title,
  count,
  locale,
  items,
  allClearLabel,
  previewRows = 10,
}: Props) {
  const t = useTranslations("admin");
  const [expanded, setExpanded] = useState(count > 0);
  const [showAll, setShowAll] = useState(false);

  const visible = showAll ? items : items.slice(0, previewRows);
  const hasMore = items.length > previewRows && !showAll;
  const hasVenue = items.some((i) => i.location_name !== undefined);

  return (
    <div className="rounded-xl border border-line bg-surface px-5 py-4">
      <button
        type="button"
        className="flex items-center gap-2 w-full text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="text-sm font-semibold text-fg">{title}</span>
        <span
          className={`text-sm font-medium ${count === 0 ? "text-green-600" : "text-amber-600"}`}
        >
          {count}
        </span>
        <span className="ml-auto text-fg-subtle text-xs">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="mt-3">
          {items.length === 0 ? (
            <p className="text-sm text-green-600">{allClearLabel}</p>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="text-xs text-fg-subtle border-b border-line">
                      <th className="text-left py-2 pr-4 font-medium">Title</th>
                      {hasVenue && (
                        <th className="text-left py-2 pr-4 font-medium">Venue</th>
                      )}
                      <th className="text-left py-2 pr-4 font-medium">Source</th>
                      <th className="text-left py-2 font-medium">ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((item) => (
                      <tr
                        key={item.id}
                        className="border-b border-gray-50 hover:bg-elevated"
                      >
                        <td className="py-2 pr-4 max-w-xs truncate">
                          <Link
                            href={`/${locale}/events/${item.id}`}
                            className="text-green-700 hover:underline"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {item.raw_title ?? item.id}
                          </Link>
                        </td>
                        {hasVenue && (
                          <td className="py-2 pr-4 text-xs text-fg-muted max-w-[12rem] truncate">
                            {item.location_name ?? "—"}
                          </td>
                        )}
                        <td className="py-2 pr-4">
                          <span className="px-2 py-0.5 rounded-full text-xs bg-muted text-fg-muted font-mono">
                            {item.source_name ?? "—"}
                          </span>
                        </td>
                        <td className="py-2 text-xs text-fg-subtle font-mono">
                          {item.id.slice(0, 8)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {hasMore && (
                <button
                  type="button"
                  className="mt-2 text-xs text-green-700 hover:underline"
                  onClick={() => setShowAll(true)}
                >
                  {t("qualityShowMore", { n: items.length - previewRows })}
                </button>
              )}
              {showAll && items.length > previewRows && (
                <button
                  type="button"
                  className="mt-2 text-xs text-fg-muted hover:underline"
                  onClick={() => setShowAll(false)}
                >
                  {t("qualityCollapse")}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

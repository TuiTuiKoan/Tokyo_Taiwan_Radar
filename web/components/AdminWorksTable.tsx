"use client";

import { useState, useMemo, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import type { Work, WorkType, Locale } from "@/lib/types";
import { deleteWork } from "@/app/actions/works";

interface Props {
  works: (Work & { event_count: number })[];
  locale: Locale;
}

const TYPE_KEYS: Record<WorkType, string> = {
  film: "worksTypeFilm",
  stage: "worksTypeStage",
  exhibition: "worksTypeExhibition",
  concert_tour: "worksTypeConcertTour",
  tv_drama: "worksTypeTvDrama",
  tv_variety: "worksTypeTvVariety",
  other: "worksTypeOther",
};

export default function AdminWorksTable({ works, locale }: Props) {
  const t = useTranslations("admin");
  const router = useRouter();
  const [q, setQ] = useState("");
  const [filterType, setFilterType] = useState<"" | WorkType>("");
  const [pending, startTransition] = useTransition();

  const filtered = useMemo(() => {
    const ql = q.trim().toLowerCase();
    return works.filter((w) => {
      if (filterType && w.work_type !== filterType) return false;
      if (!ql) return true;
      return (
        w.original_title.toLowerCase().includes(ql) ||
        (w.title_ja || "").toLowerCase().includes(ql) ||
        (w.title_zh || "").toLowerCase().includes(ql) ||
        (w.title_en || "").toLowerCase().includes(ql)
      );
    });
  }, [works, q, filterType]);

  function handleDelete(id: string) {
    if (!confirm(t("worksConfirmDelete"))) return;
    startTransition(async () => {
      const res = await deleteWork(id);
      if (!res.ok) {
        alert(res.error || "delete failed");
        return;
      }
      router.refresh();
    });
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <Link
          href={`/${locale}/admin/works/new`}
          className="bg-green-600 hover:bg-green-700 text-white text-sm px-4 py-2 rounded-lg transition"
        >
          + {t("worksNew")}
        </Link>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">{t("worksWorkType")}</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as "" | WorkType)}
            className="h-9 border border-gray-300 rounded-lg px-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          >
            <option value="">{t("filterAll")}</option>
            {(Object.keys(TYPE_KEYS) as WorkType[]).map((wt) => (
              <option key={wt} value={wt}>{t(TYPE_KEYS[wt] as any)}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1 flex-1 min-w-[12rem]">
          <label className="text-xs text-gray-500 font-medium">{t("worksTitle")}</label>
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("worksSearchPlaceholder")}
            className="h-9 border border-gray-300 rounded-lg px-3 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b text-left text-gray-500">
              <th className="py-2 pr-4 font-medium">{t("worksOriginalTitle")}</th>
              <th className="py-2 pr-4 font-medium">{t("worksWorkType")}</th>
              <th className="py-2 pr-4 font-medium">{t("worksTitleJa")}</th>
              <th className="py-2 pr-4 font-medium">{t("worksDirector")}</th>
              <th className="py-2 pr-4 font-medium">{t("worksReleaseYear")}</th>
              <th className="py-2 pr-4 font-medium">{t("worksLinkedEvents")}</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {filtered.map((w) => (
              <tr key={w.id} className="border-b hover:bg-gray-50 transition">
                <td className="py-2 pr-4 font-medium text-gray-800">
                  <Link
                    href={`/${locale}/admin/works/${w.id}`}
                    className="hover:underline hover:text-green-700"
                  >
                    {w.original_title}
                  </Link>
                </td>
                <td className="py-2 pr-4">
                  <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
                    {t(TYPE_KEYS[w.work_type] as any)}
                  </span>
                </td>
                <td className="py-2 pr-4 text-gray-600">{w.title_ja ?? "—"}</td>
                <td className="py-2 pr-4 text-gray-600">{w.director ?? "—"}</td>
                <td className="py-2 pr-4 text-gray-500">{w.release_year ?? "—"}</td>
                <td className="py-2 pr-4 text-gray-500">{w.event_count}</td>
                <td className="py-2 pr-4">
                  <div className="flex gap-2">
                    <Link
                      href={`/${locale}/admin/works/${w.id}`}
                      className="text-blue-600 hover:underline text-xs"
                    >
                      {t("edit")}
                    </Link>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => handleDelete(w.id)}
                      className="text-red-500 hover:text-red-700 text-xs disabled:opacity-50"
                    >
                      {t("delete") /* admin.delete */}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-gray-400 text-sm">—</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

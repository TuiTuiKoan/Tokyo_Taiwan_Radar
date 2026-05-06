"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Link from "next/link";
import type { Work, WorkType, Locale, Event } from "@/lib/types";
import { createWork, updateWork } from "@/app/actions/works";

interface Props {
  work: Work | null;       // null = new
  linkedEvents?: Event[];   // events already assigned to this work
  locale: Locale;
  onSuccess?: () => void;  // called after save instead of router.push (e.g. modal mode)
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

export default function AdminWorkForm({ work, linkedEvents = [], locale, onSuccess }: Props) {
  const t = useTranslations("admin");
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    work_type: work?.work_type ?? "film",
    original_title: work?.original_title ?? "",
    title_ja: work?.title_ja ?? "",
    title_zh: work?.title_zh ?? "",
    title_en: work?.title_en ?? "",
    director: work?.director ?? "",
    cast_summary: work?.cast_summary ?? "",
    release_year: work?.release_year ? String(work.release_year) : "",
    country: work?.country ?? "TW",
    description: work?.description ?? "",
    poster_url: work?.poster_url ?? "",
    external_links: work?.external_links ? JSON.stringify(work.external_links, null, 2) : "",
  });

  function update<K extends keyof typeof form>(key: K, value: typeof form[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit() {
    setError(null);
    let externalLinks: Record<string, string> | null = null;
    if (form.external_links.trim()) {
      try {
        externalLinks = JSON.parse(form.external_links);
      } catch {
        setError("external_links: invalid JSON");
        return;
      }
    }
    const releaseYear = form.release_year.trim() ? parseInt(form.release_year, 10) : null;
    if (releaseYear !== null && (Number.isNaN(releaseYear) || releaseYear < 1800 || releaseYear > 2100)) {
      setError("release_year out of range");
      return;
    }
    const payload = {
      work_type: form.work_type,
      original_title: form.original_title,
      title_ja: form.title_ja,
      title_zh: form.title_zh,
      title_en: form.title_en,
      director: form.director,
      cast_summary: form.cast_summary,
      release_year: releaseYear,
      country: form.country,
      description: form.description,
      poster_url: form.poster_url,
      external_links: externalLinks,
    };
    startTransition(async () => {
      const res = work
        ? await updateWork(work.id, payload)
        : await createWork(payload);
      if (!res.ok) {
        setError(res.error || "save failed");
        return;
      }
      if (onSuccess) {
        onSuccess();
      } else {
        router.push(`/${locale}/admin/works`);
        router.refresh();
      }
    });
  }

  return (
    <div className="space-y-4 max-w-3xl">
      {error && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksWorkType")} *</label>
          <select
            value={form.work_type}
            onChange={(e) => update("work_type", e.target.value as WorkType)}
            className="w-full h-9 border border-gray-300 rounded-lg px-2 text-sm"
          >
            {(Object.keys(TYPE_KEYS) as WorkType[]).map((wt) => (
              <option key={wt} value={wt}>{t(TYPE_KEYS[wt] as any)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksOriginalTitle")} *</label>
          <input
            type="text"
            value={form.original_title}
            onChange={(e) => update("original_title", e.target.value)}
            className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
            required
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksTitleJa")}</label>
          <input
            type="text"
            value={form.title_ja}
            onChange={(e) => update("title_ja", e.target.value)}
            className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksTitleZh")}</label>
          <input
            type="text"
            value={form.title_zh}
            onChange={(e) => update("title_zh", e.target.value)}
            className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksTitleEn")}</label>
          <input
            type="text"
            value={form.title_en}
            onChange={(e) => update("title_en", e.target.value)}
            className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksDirector")}</label>
          <input
            type="text"
            value={form.director}
            onChange={(e) => update("director", e.target.value)}
            className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksReleaseYear")}</label>
          <input
            type="number"
            value={form.release_year}
            onChange={(e) => update("release_year", e.target.value)}
            className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksCountry")}</label>
          <input
            type="text"
            value={form.country}
            onChange={(e) => update("country", e.target.value)}
            className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksCastSummary")}</label>
        <textarea
          value={form.cast_summary}
          onChange={(e) => update("cast_summary", e.target.value)}
          rows={2}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksDescription")}</label>
        <textarea
          value={form.description}
          onChange={(e) => update("description", e.target.value)}
          rows={4}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksPosterUrl")}</label>
        <input
          type="url"
          value={form.poster_url}
          onChange={(e) => update("poster_url", e.target.value)}
          className="w-full h-9 border border-gray-300 rounded-lg px-3 text-sm"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-500 mb-1">{t("worksExternalLinks")}</label>
        <textarea
          value={form.external_links}
          onChange={(e) => update("external_links", e.target.value)}
          rows={3}
          placeholder='{"imdb":"https://...","official_site":"https://..."}'
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
        />
      </div>

      {linkedEvents.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-gray-500 mb-2">{t("worksLinkedEvents")} ({linkedEvents.length})</h3>
          <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 text-sm">
            {linkedEvents.map((ev) => (
              <Link
                key={ev.id}
                href={`/${locale}/admin/${ev.id}`}
                className="block px-3 py-2 hover:bg-gray-50"
              >
                <span className="text-gray-800">{ev.name_ja || ev.name_zh || ev.name_en}</span>
                <span className="text-xs text-gray-500 ml-2">
                  {ev.source_name} · {ev.start_date ?? "—"} · {ev.location_name ?? "—"}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={pending}
          className="bg-green-600 hover:bg-green-700 text-white text-sm px-4 py-2 rounded-lg transition disabled:opacity-50"
        >
          {pending ? "..." : t("save")}
        </button>
        <Link
          href={`/${locale}/admin/works`}
          className="border border-gray-300 hover:bg-gray-50 text-sm px-4 py-2 rounded-lg transition"
        >
          {t("cancel")}
        </Link>
      </div>
    </div>
  );
}

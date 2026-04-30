"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import type { Announcement, SocialPlatform, Locale } from "@/lib/types";
import type { Event } from "@/lib/types";

const PLATFORMS: { key: SocialPlatform; label: string; color: string }[] = [
  { key: "instagram", label: "Instagram", color: "bg-pink-500" },
  { key: "threads", label: "Threads", color: "bg-gray-800" },
  { key: "facebook", label: "Facebook", color: "bg-blue-600" },
  { key: "linkedin", label: "LinkedIn", color: "bg-blue-700" },
  { key: "line", label: "LINE", color: "bg-green-500" },
];

const LOCALES: { key: Locale; label: string }[] = [
  { key: "zh", label: "中文" },
  { key: "en", label: "English" },
  { key: "ja", label: "日本語" },
];

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[\s_]+/g, "-")
    .replace(/[^\w-]/g, "")
    .replace(/--+/g, "-")
    .slice(0, 80);
}

interface Props {
  announcement?: Announcement;
  recentEvents: Pick<Event, "id" | "name_ja" | "name_zh" | "name_en">[];
  locale: Locale;
  tAdmin: (key: string) => string;
  tAnn: (key: string) => string;
}

export default function AnnouncementForm({ announcement, recentEvents, locale, tAdmin, tAnn }: Props) {
  const router = useRouter();
  const isEdit = Boolean(announcement?.id);

  const [slug, setSlug] = useState(announcement?.slug ?? "");
  const [titleJa, setTitleJa] = useState(announcement?.title_ja ?? "");
  const [titleZh, setTitleZh] = useState(announcement?.title_zh ?? "");
  const [titleEn, setTitleEn] = useState(announcement?.title_en ?? "");
  const [bodyJa, setBodyJa] = useState(announcement?.body_ja ?? "");
  const [bodyZh, setBodyZh] = useState(announcement?.body_zh ?? "");
  const [bodyEn, setBodyEn] = useState(announcement?.body_en ?? "");
  const [coverImageUrl, setCoverImageUrl] = useState(announcement?.cover_image_url ?? "");
  const [imageJa, setImageJa] = useState(announcement?.image_ja ?? "");
  const [imageZh, setImageZh] = useState(announcement?.image_zh ?? "");
  const [imageEn, setImageEn] = useState(announcement?.image_en ?? "");
  const [isFeatured, setIsFeatured] = useState(announcement?.is_featured ?? false);
  const [publishedAt, setPublishedAt] = useState(
    announcement?.published_at ? announcement.published_at.slice(0, 16) : ""
  );
  const [linkedEvents, setLinkedEvents] = useState<string[]>(announcement?.linked_events ?? []);
  const [socialStatus, setSocialStatus] = useState(announcement?.social_status ?? {});
  const [publishLocales, setPublishLocales] = useState<Record<SocialPlatform, Locale>>({
    instagram: "ja",
    threads: "zh",
    facebook: "zh",
    linkedin: "en",
    line: "zh",
  });

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [publishingPlatform, setPublishingPlatform] = useState<SocialPlatform | null>(null);

  const handleSlugFromTitle = useCallback(() => {
    if (!slug && titleZh) setSlug(slugify(titleZh));
    else if (!slug && titleEn) setSlug(slugify(titleEn));
    else if (!slug && titleJa) setSlug(slugify(titleJa));
  }, [slug, titleZh, titleEn, titleJa]);

  const toggleLinkedEvent = (eventId: string) => {
    setLinkedEvents((prev) =>
      prev.includes(eventId) ? prev.filter((id) => id !== eventId) : [...prev, eventId]
    );
  };

  const buildPayload = () => ({
    slug,
    title_ja: titleJa || null,
    title_zh: titleZh || null,
    title_en: titleEn || null,
    body_ja: bodyJa || null,
    body_zh: bodyZh || null,
    body_en: bodyEn || null,
    cover_image_url: coverImageUrl || null,
    image_ja: imageJa || null,
    image_zh: imageZh || null,
    image_en: imageEn || null,
    is_featured: isFeatured,
    published_at: publishedAt ? new Date(publishedAt).toISOString() : null,
    linked_events: linkedEvents,
  });

  const handleSave = async () => {
    if (!slug) { setSaveError(tAnn("slugRequired")); return; }
    setSaving(true);
    setSaveError(null);
    try {
      const method = isEdit ? "PUT" : "POST";
      const url = isEdit ? `/api/announcements/${announcement!.id}` : "/api/announcements";
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error ?? "Save failed");
      }
      const saved = await res.json();
      router.push(`/${locale}/admin/announcements/${saved.id}`);
      router.refresh();
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async (platform: SocialPlatform) => {
    if (!announcement?.id) return;
    setPublishingPlatform(platform);
    try {
      const res = await fetch(`/api/announcements/${announcement.id}/publish/${platform}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ locale: publishLocales[platform] }),
      });
      const data = await res.json();
      setSocialStatus((prev) => ({
        ...prev,
        [platform]: res.ok
          ? { status: "published", published_at: new Date().toISOString(), post_id: data.post_id, locale: publishLocales[platform] }
          : { status: "error", error: data.error, locale: publishLocales[platform] },
      }));
    } finally {
      setPublishingPlatform(null);
    }
  };

  const statusBadge = (platform: SocialPlatform) => {
    const s = socialStatus[platform];
    if (!s || s.status === "idle") return null;
    if (s.status === "publishing") return <span className="text-xs text-amber-600">{tAnn("publishing")}</span>;
    if (s.status === "published") return <span className="text-xs text-green-600">{tAnn("published")} {s.published_at ? new Date(s.published_at).toLocaleString(locale) : ""}</span>;
    if (s.status === "error") return <span className="text-xs text-red-600" title={s.error ?? ""}>{tAnn("publishError")}</span>;
    return null;
  };

  return (
    <div className="space-y-8">
      {/* Slug */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">{tAnn("slug")}</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
            onBlur={handleSlugFromTitle}
            placeholder="my-announcement-slug"
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono"
          />
        </div>
        <p className="text-xs text-gray-400 mt-1">{tAnn("slugHint")}</p>
      </div>

      {/* Titles */}
      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">{tAnn("titles")}</p>
        <div className="grid gap-2">
          {[
            { label: "中文", value: titleZh, set: setTitleZh },
            { label: "English", value: titleEn, set: setTitleEn },
            { label: "日本語", value: titleJa, set: setTitleJa },
          ].map(({ label, value, set }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="w-16 text-xs text-gray-500 shrink-0">{label}</span>
              <input
                type="text"
                value={value}
                onChange={(e) => set(e.target.value)}
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Body */}
      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">{tAnn("bodies")}</p>
        <div className="space-y-3">
          {[
            { label: "中文", value: bodyZh, set: setBodyZh },
            { label: "English", value: bodyEn, set: setBodyEn },
            { label: "日本語", value: bodyJa, set: setBodyJa },
          ].map(({ label, value, set }) => (
            <div key={label}>
              <p className="text-xs text-gray-500 mb-1">{label}</p>
              <textarea
                rows={4}
                value={value}
                onChange={(e) => set(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm resize-y"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Images */}
      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">{tAnn("images")}</p>
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="w-24 text-xs text-gray-500 shrink-0">{tAnn("coverImage")}</span>
            <input
              type="url"
              value={coverImageUrl}
              onChange={(e) => setCoverImageUrl(e.target.value)}
              placeholder="https://..."
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          {[
            { label: "中文 override", value: imageZh, set: setImageZh },
            { label: "English override", value: imageEn, set: setImageEn },
            { label: "日本語 override", value: imageJa, set: setImageJa },
          ].map(({ label, value, set }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="w-24 text-xs text-gray-400 shrink-0">{label}</span>
              <input
                type="url"
                value={value}
                onChange={(e) => set(e.target.value)}
                placeholder="https://..."
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Featured + Publish date */}
      <div className="flex flex-wrap gap-6 items-start">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={isFeatured}
            onChange={(e) => setIsFeatured(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          <span className="text-sm">{tAnn("isFeatured")}</span>
        </label>
        <div>
          <label className="block text-xs text-gray-500 mb-1">{tAnn("publishedAt")} ({tAnn("publishedAtHint")})</label>
          <input
            type="datetime-local"
            value={publishedAt}
            onChange={(e) => setPublishedAt(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </div>

      {/* Linked Events */}
      {recentEvents.length > 0 && (
        <div>
          <p className="text-sm font-medium text-gray-700 mb-2">{tAnn("linkedEvents")}</p>
          <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-2 space-y-1">
            {recentEvents.map((ev) => {
              const name = ev[`name_${locale}`] ?? ev.name_ja ?? ev.name_zh ?? ev.name_en ?? ev.id;
              return (
                <label key={ev.id} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 px-2 py-1 rounded">
                  <input
                    type="checkbox"
                    checked={linkedEvents.includes(ev.id)}
                    onChange={() => toggleLinkedEvent(ev.id)}
                    className="w-4 h-4 rounded"
                  />
                  <span className="text-sm truncate">{name}</span>
                </label>
              );
            })}
          </div>
          {linkedEvents.length > 0 && (
            <p className="text-xs text-green-600 mt-1">{tAnn("linkedEventsCount").replace("{n}", String(linkedEvents.length))}</p>
          )}
        </div>
      )}

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50"
        >
          {saving ? tAdmin("save") + "…" : tAdmin("save")}
        </button>
        {saveError && <p className="text-sm text-red-600">{saveError}</p>}
      </div>

      {/* Social Media Publish Panel — only shown for saved announcements */}
      {isEdit && (
        <div className="border-t border-gray-200 pt-6">
          <p className="text-sm font-semibold text-gray-800 mb-4">{tAnn("socialPublish")}</p>
          <div className="space-y-3">
            {PLATFORMS.map(({ key, label, color }) => {
              const isPublishing = publishingPlatform === key;
              const status = socialStatus[key];
              return (
                <div key={key} className="flex items-center gap-3 flex-wrap">
                  <span className={`w-24 text-xs text-white font-medium px-2 py-1 rounded ${color} text-center`}>
                    {label}
                  </span>
                  {/* Locale selector */}
                  <select
                    value={publishLocales[key]}
                    onChange={(e) => setPublishLocales((prev) => ({ ...prev, [key]: e.target.value as Locale }))}
                    className="text-xs border border-gray-200 rounded px-2 py-1"
                  >
                    {LOCALES.map((l) => (
                      <option key={l.key} value={l.key}>{l.label}</option>
                    ))}
                  </select>
                  <button
                    onClick={() => handlePublish(key)}
                    disabled={isPublishing}
                    className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded-lg disabled:opacity-50"
                  >
                    {isPublishing ? tAnn("publishing") : tAnn("publishNow")}
                  </button>
                  {statusBadge(key)}
                  {status?.status === "published" && status.post_id && (
                    <span className="text-xs text-gray-400 font-mono">{status.post_id.slice(0, 20)}</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

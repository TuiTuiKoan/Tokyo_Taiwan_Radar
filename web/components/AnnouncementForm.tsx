"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { Announcement, SocialPlatform, Locale } from "@/lib/types";
import type { Event } from "@/lib/types";
import DesignSelect from "@/components/DesignSelect";

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
  recentEvents: Pick<Event, "id" | "name_ja" | "name_zh" | "name_en" | "location_name" | "start_date">[];
  locale: Locale;
}

export default function AnnouncementForm({ announcement, recentEvents, locale }: Props) {
  const router = useRouter();
  const tAnn = useTranslations("announcements");
  const tAdmin = useTranslations("admin");
  const isEdit = Boolean(announcement?.id);

  const [slug, setSlug] = useState(announcement?.slug ?? "");
  const [titleJa, setTitleJa] = useState(announcement?.title_ja ?? "");
  const [titleZh, setTitleZh] = useState(announcement?.title_zh ?? "");
  const [titleEn, setTitleEn] = useState(announcement?.title_en ?? "");
  const [bodyJa, setBodyJa] = useState(announcement?.body_ja ?? "");
  const [bodyZh, setBodyZh] = useState(announcement?.body_zh ?? "");
  const [bodyEn, setBodyEn] = useState(announcement?.body_en ?? "");
  const [coverImageUrl, setCoverImageUrl] = useState(announcement?.cover_image_url ?? "");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  const [deleting, setDeleting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [publishingPlatform, setPublishingPlatform] = useState<SocialPlatform | null>(null);
  const [eventSearch, setEventSearch] = useState("");

  const handleDeleteImage = async () => {
    if (!coverImageUrl) return;
    if (!window.confirm("確定要刪除此圖片？此操作無法復原。")) return;
    // If it's our Supabase Storage URL, delete the file too
    const storagePrefix = `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/announcements/`;
    if (coverImageUrl.startsWith(storagePrefix)) {
      const filePath = coverImageUrl.replace(storagePrefix, "");
      setDeleting(true);
      try {
        const res = await fetch(`/api/upload?path=${encodeURIComponent(filePath)}`, { method: "DELETE" });
        if (!res.ok) {
          const data = await res.json();
          setUploadError(data.error ?? "Delete failed");
          return;
        }
      } catch (e: unknown) {
        setUploadError(e instanceof Error ? e.message : "Delete failed");
        return;
      } finally {
        setDeleting(false);
      }
    }
    setCoverImageUrl("");
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({ error: "Upload failed (server error)" }));
      if (!res.ok) throw new Error(data.error ?? "Upload failed");
      setCoverImageUrl(data.url);
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

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
        <label className="block text-sm font-medium text-fg mb-1">{tAnn("slug")}</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={slug}
            onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
            onBlur={handleSlugFromTitle}
            placeholder="my-announcement-slug"
            className="flex-1 border border-line-strong rounded-lg px-3 py-2 text-sm font-mono"
          />
        </div>
        <p className="text-xs text-fg-subtle mt-1">{tAnn("slugHint")}</p>
      </div>

      {/* Titles */}
      <div>
        <p className="text-sm font-medium text-fg mb-2">{tAnn("titles")}</p>
        <div className="grid gap-2">
          {[
            { label: "中文", value: titleZh, set: setTitleZh },
            { label: "English", value: titleEn, set: setTitleEn },
            { label: "日本語", value: titleJa, set: setTitleJa },
          ].map(({ label, value, set }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="w-16 text-xs text-fg-muted shrink-0">{label}</span>
              <input
                type="text"
                value={value}
                onChange={(e) => set(e.target.value)}
                className="flex-1 border border-line rounded-lg px-3 py-2 text-sm"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Body */}
      <div>
        <p className="text-sm font-medium text-fg mb-2">{tAnn("bodies")}</p>
        <div className="space-y-3">
          {[
            { label: "中文", value: bodyZh, set: setBodyZh },
            { label: "English", value: bodyEn, set: setBodyEn },
            { label: "日本語", value: bodyJa, set: setBodyJa },
          ].map(({ label, value, set }) => (
            <div key={label}>
              <p className="text-xs text-fg-muted mb-1">{label}</p>
              <textarea
                rows={4}
                value={value}
                onChange={(e) => set(e.target.value)}
                className="w-full border border-line rounded-lg px-3 py-2 text-sm resize-y"
              />
            </div>
          ))}
        </div>
      </div>

      {/* Images */}
      <div>
        <p className="text-sm font-medium text-fg mb-2">{tAnn("images")}</p>
        <div className="space-y-3">
          {/* Current image preview with hover-delete */}
          {coverImageUrl && (
            <div className="relative group rounded-lg overflow-hidden border border-line bg-elevated">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={coverImageUrl} alt="cover preview" className="w-full h-auto max-h-72 object-contain" />
              <button
                type="button"
                onClick={handleDeleteImage}
                disabled={deleting}
                title="刪除圖片"
                className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity
                           text-red-500 hover:text-red-700 disabled:text-red-300
                           w-8 h-8 flex items-center justify-center drop-shadow"
              >
                {deleting ? (
                  <span className="text-xs font-bold">…</span>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
                    <path fillRule="evenodd" d="M16.5 4.478v.227a48.816 48.816 0 0 1 3.878.512.75.75 0 1 1-.256 1.478l-.209-.035-1.005 13.07a3 3 0 0 1-2.991 2.77H8.084a3 3 0 0 1-2.991-2.77L4.087 6.66l-.209.035a.75.75 0 0 1-.256-1.478A48.567 48.567 0 0 1 7.5 4.705v-.227c0-1.564 1.213-2.9 2.816-2.951a52.662 52.662 0 0 1 3.369 0c1.603.051 2.815 1.387 2.815 2.951Zm-6.136-1.452a51.196 51.196 0 0 1 3.273 0C14.39 3.05 15 3.684 15 4.478v.113a49.488 49.488 0 0 0-6 0v-.113c0-.794.609-1.428 1.364-1.452Zm-.355 5.945a.75.75 0 1 0-1.5.058l.347 9a.75.75 0 1 0 1.499-.058l-.346-9Zm5.48.058a.75.75 0 1 0-1.498-.058l-.347 9a.75.75 0 0 0 1.5.058l.345-9Z" clipRule="evenodd" />
                  </svg>
                )}
              </button>
            </div>
          )}
          {/* Cover image URL + upload */}
          <div className="flex items-center gap-2">
            <span className="w-24 text-xs text-fg-muted shrink-0">{tAnn("coverImage")}</span>
            <input
              type="url"
              value={coverImageUrl}
              onChange={(e) => setCoverImageUrl(e.target.value)}
              placeholder="https://..."
              className="flex-1 border border-line rounded-lg px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="shrink-0 text-xs px-3 py-2 border border-line-strong rounded-lg hover:bg-elevated disabled:opacity-50"
            >
              {uploading ? "上傳中…" : "📁 上傳"}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
              e.target.value = "";
            }}
          />
          {uploadError && <p className="text-xs text-red-600">{uploadError}</p>}
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
          <label className="block text-xs text-fg-muted mb-1">{tAnn("publishedAt")} ({tAnn("publishedAtHint")})</label>
          <input
            type="datetime-local"
            value={publishedAt}
            onChange={(e) => setPublishedAt(e.target.value)}
            className="border border-line rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </div>

      {/* Linked Events */}
      {recentEvents.length > 0 && (
        <div>
          <p className="text-sm font-medium text-fg mb-2">{tAnn("linkedEvents")}</p>
          {/* Search box */}
          <input
            type="search"
            placeholder="搜尋活動…"
            value={eventSearch}
            onChange={(e) => setEventSearch(e.target.value)}
            className="w-full border border-line rounded-lg px-3 py-2 text-sm mb-2"
          />
          <div className="max-h-48 overflow-y-auto border border-line rounded-lg p-2 space-y-1">
            {(() => {
              const q = eventSearch.trim().toLowerCase();
              const filtered = recentEvents.filter((ev) => {
                if (!q) return true;
                const name = (ev.name_ja ?? "") + (ev.name_zh ?? "") + (ev.name_en ?? "");
                return name.toLowerCase().includes(q);
              });
              // Checked items first, then unchecked
              const sorted = [
                ...filtered.filter((ev) => linkedEvents.includes(ev.id)),
                ...filtered.filter((ev) => !linkedEvents.includes(ev.id)),
              ];
              return sorted.map((ev) => {
                const name = ev[`name_${locale}`] ?? ev.name_ja ?? ev.name_zh ?? ev.name_en ?? ev.id;
                const dateStr = ev.start_date ? new Date(ev.start_date).toLocaleDateString("ja-JP", { month: "2-digit", day: "2-digit" }) : null;
                const meta = [dateStr, ev.location_name].filter(Boolean).join(" · ");
                return (
                  <label key={ev.id} className="flex items-center gap-2 cursor-pointer hover:bg-elevated px-2 py-1 rounded">
                    <input
                      type="checkbox"
                      checked={linkedEvents.includes(ev.id)}
                      onChange={() => toggleLinkedEvent(ev.id)}
                      className="w-4 h-4 rounded"
                    />
                    <span className="text-sm truncate">
                      {name}
                      {meta && <span className="text-fg-subtle ml-1">{meta}</span>}
                    </span>
                  </label>
                );
              });
            })()}
          </div>
          {linkedEvents.length > 0 && (
            <p className="text-xs text-green-600 mt-1">{tAnn("linkedEventsCount", { n: linkedEvents.length })}</p>
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
        <div className="border-t border-line pt-6">
          <p className="text-sm font-semibold text-fg-strong mb-4">{tAnn("socialPublish")}</p>
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
                  <DesignSelect
                    value={publishLocales[key]}
                    onChange={(v) => setPublishLocales((prev) => ({ ...prev, [key]: v as Locale }))}
                    options={LOCALES.map((l) => ({ value: l.key, label: l.label }))}
                    className="min-w-[8rem]"
                  />
                  <button
                    onClick={() => handlePublish(key)}
                    disabled={isPublishing}
                    className="px-3 py-1 text-xs bg-muted hover:bg-gray-200 rounded-lg disabled:opacity-50"
                  >
                    {isPublishing ? tAnn("publishing") : tAnn("publishNow")}
                  </button>
                  {statusBadge(key)}
                  {status?.status === "published" && status.post_id && (
                    <span className="text-xs text-fg-subtle font-mono">{status.post_id.slice(0, 20)}</span>
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

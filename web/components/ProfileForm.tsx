"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import { saveProfile, type ProfileInput, type ProfileErrorCode } from "@/app/actions/profile";
import DesignSelect from "@/components/DesignSelect";
import { ACTOR_CATEGORIES, type ActorCategory } from "@/lib/actorTypes";
import type { Locale } from "@/lib/types";

const MAX_AVATAR_BYTES = 2 * 1024 * 1024;
const ALLOWED_AVATAR_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;

export type CreatorProfile = ProfileInput & {
  category: ActorCategory | null;
};

interface Props {
  locale: Locale;
  initialProfile: CreatorProfile | null;
}

function extensionForMime(type: string): string {
  if (type === "image/png") return "png";
  if (type === "image/webp") return "webp";
  return "jpg";
}

function emptyProfile(): ProfileInput {
  return {
    user_handle: "",
    organizer_name_zh: "",
    organizer_name_ja: "",
    organizer_name_en: "",
    website_url: "",
    social_x: "",
    social_instagram: "",
    social_note: "",
    social_facebook: "",
    social_threads: "",
    social_youtube: "",
    avatar_url: "",
    category: "",
    region: "",
  };
}

export default function ProfileForm({ locale, initialProfile }: Props) {
  const t = useTranslations("profile");
  const tActor = useTranslations("actorCategory");
  const router = useRouter();
  const supabase = createClient();
  const [form, setForm] = useState<ProfileInput>(() => ({
    ...emptyProfile(),
    ...initialProfile,
  }));
  const [error, setError] = useState<ProfileErrorCode | "avatarTooLarge" | "avatarInvalidType" | "avatarUploadFailed" | null>(null);
  const [saving, setSaving] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);

  function setField<K extends keyof ProfileInput>(key: K, value: ProfileInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleAvatarUpload(file: File | null) {
    if (!file) return;
    setError(null);
    if (!ALLOWED_AVATAR_TYPES.includes(file.type as (typeof ALLOWED_AVATAR_TYPES)[number])) {
      setError("avatarInvalidType");
      return;
    }
    if (file.size > MAX_AVATAR_BYTES) {
      setError("avatarTooLarge");
      return;
    }

    setAvatarUploading(true);
    try {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) {
        setError("authRequired");
        return;
      }

      const path = `${user.id}/${Date.now()}.${extensionForMime(file.type)}`;
      const { error: uploadError } = await supabase.storage
        .from("avatars")
        .upload(path, file, {
          contentType: file.type,
          upsert: true,
        });

      if (uploadError) {
        setError("avatarUploadFailed");
        return;
      }

      const { data } = supabase.storage.from("avatars").getPublicUrl(path);
      setField("avatar_url", data.publicUrl);
    } finally {
      setAvatarUploading(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const result = await saveProfile(form);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      router.push(`/${locale}/account`);
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  const errorMessage = error ? t(`errors.${error}`) : null;
  const categoryOptions = [
    { value: "", label: t("categoryPlaceholder") },
    ...ACTOR_CATEGORIES.map((category) => ({
      value: category,
      label: tActor(category),
    })),
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-6" aria-busy={saving || avatarUploading}>
      {errorMessage && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </div>
      )}

      <section className="space-y-4">
        <div>
          <label htmlFor="user_handle" className="block text-sm font-medium text-fg mb-1">
            {t("userHandle")}
          </label>
          <input
            id="user_handle"
            name="user_handle"
            value={form.user_handle}
            required
            pattern="[a-z0-9]+"
            onChange={(event) => setField("user_handle", event.target.value.toLowerCase().replace(/[^a-z0-9]/g, ""))}
            className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder={t("userHandlePlaceholder")}
          />
          <p className="mt-1 text-xs text-fg-subtle">{t("userHandleHint")}</p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <label htmlFor="organizer_name_zh" className="block text-sm font-medium text-fg mb-1">
              {t("organizerNameZh")}
            </label>
            <input
              id="organizer_name_zh"
              name="organizer_name_zh"
              value={form.organizer_name_zh}
              required
              onChange={(event) => setField("organizer_name_zh", event.target.value)}
              className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label htmlFor="organizer_name_ja" className="block text-sm font-medium text-fg mb-1">
              {t("organizerNameJa")}
            </label>
            <input
              id="organizer_name_ja"
              name="organizer_name_ja"
              value={form.organizer_name_ja}
              required
              onChange={(event) => setField("organizer_name_ja", event.target.value)}
              className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
          <div>
            <label htmlFor="organizer_name_en" className="block text-sm font-medium text-fg mb-1">
              {t("organizerNameEn")}
            </label>
            <input
              id="organizer_name_en"
              name="organizer_name_en"
              value={form.organizer_name_en}
              required
              onChange={(event) => setField("organizer_name_en", event.target.value)}
              className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            />
          </div>
        </div>

        <div>
          <label htmlFor="website_url" className="block text-sm font-medium text-fg mb-1">
            {t("websiteUrl")}
          </label>
          <input
            id="website_url"
            name="website_url"
            type="url"
            value={form.website_url}
            required
            onChange={(event) => setField("website_url", event.target.value)}
            className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder={t("urlPlaceholder")}
          />
        </div>
      </section>

      <section className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-fg mb-1">
              {t("category")}
            </label>
            <DesignSelect
              id="category"
              value={form.category ?? ""}
              onChange={(value) => setField("category", value)}
              options={categoryOptions}
              placeholder={t("categoryPlaceholder")}
            />
          </div>
          <div>
            <label htmlFor="region" className="block text-sm font-medium text-fg mb-1">
              {t("region")}
            </label>
            <input
              id="region"
              name="region"
              value={form.region ?? ""}
              onChange={(event) => setField("region", event.target.value)}
              className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
              placeholder={t("regionPlaceholder")}
            />
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          {(["social_x", "social_instagram", "social_note", "social_facebook", "social_threads", "social_youtube"] as const).map((field) => (
            <div key={field}>
              <label htmlFor={field} className="block text-sm font-medium text-fg mb-1">
                {t(field)}
              </label>
              <input
                id={field}
                name={field}
                type="url"
                value={form[field] ?? ""}
                onChange={(event) => setField(field, event.target.value)}
                className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder={t("urlPlaceholder")}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        {form.avatar_url && (
          <img
            src={form.avatar_url}
            alt={t("avatarPreviewAlt")}
            className="h-20 w-20 rounded-full border border-line object-cover"
          />
        )}
        <div>
          <label htmlFor="avatar_upload" className="block text-sm font-medium text-fg mb-1">
            {t("avatarUpload")}
          </label>
          <input
            id="avatar_upload"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            disabled={avatarUploading}
            onChange={(event) => handleAvatarUpload(event.target.files?.[0] ?? null)}
            className="block w-full text-sm text-fg-muted file:mr-4 file:rounded-lg file:border-0 file:bg-green-600 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-green-700 disabled:opacity-60"
          />
          <p className="mt-1 text-xs text-fg-subtle">{t("avatarUploadHint")}</p>
        </div>
        <div>
          <label htmlFor="avatar_url" className="block text-sm font-medium text-fg mb-1">
            {t("avatarUrl")}
          </label>
          <input
            id="avatar_url"
            name="avatar_url"
            type="url"
            value={form.avatar_url ?? ""}
            onChange={(event) => setField("avatar_url", event.target.value)}
            className="w-full rounded-lg border border-line-strong bg-paper px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder={t("urlPlaceholder")}
          />
        </div>
      </section>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => router.push(`/${locale}/account`)}
          className="rounded-lg border border-line-strong px-4 py-2 text-sm text-fg-muted hover:bg-elevated transition"
        >
          {t("cancel")}
        </button>
        <button
          type="submit"
          disabled={saving || avatarUploading}
          className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition disabled:opacity-60"
        >
          {saving ? t("saving") : t("save")}
        </button>
      </div>
    </form>
  );
}

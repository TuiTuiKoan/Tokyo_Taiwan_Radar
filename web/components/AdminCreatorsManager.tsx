"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import type { Locale } from "@/lib/types";
import type { Creator } from "@/app/[locale]/admin/creators/page";
import { ACTOR_CATEGORIES } from "@/lib/actorTypes";
import DesignSelect from "@/components/DesignSelect";

const PLATFORMS = [
  "note",
  "youtube",
  "twitter",
  "x",
  "instagram",
  "facebook",
  "threads",
  "blog",
  "substack",
  "other",
] as const;

const LOCATIONS = ["tokyo", "osaka", "fukuoka", "kyoto", "sapporo", "nationwide", "other"] as const;

const NATIONALITIES = ["taiwanese_in_japan", "japanese", "other"] as const;

type CreatorForm = Omit<Creator, "id" | "created_at" | "updated_at">;

const EMPTY_FORM: CreatorForm = {
  name: "",
  name_zh: null,
  platform: "note",
  handle: null,
  profile_url: "",
  category: null,
  base_location: null,
  nationality: null,
  is_active: true,
  approx_followers: null,
  last_post_at: null,
  notes: null,
};

interface Props {
  initialCreators: Creator[];
  locale: Locale;
}

function toNullableString(value: string): string | null {
  return value.trim() ? value.trim() : null;
}

function CreatorFieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="mb-1 block text-xs font-medium text-fg-muted">{children}</label>;
}

export default function AdminCreatorsManager({ initialCreators, locale }: Props) {
  const t = useTranslations("admin");
  const tActor = useTranslations("actorCategory");
  const [creators, setCreators] = useState<Creator[]>(initialCreators);
  const [form, setForm] = useState<CreatorForm>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, startSaving] = useTransition();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function resetForm() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setError(null);
  }

  function openCreate() {
    resetForm();
  }

  function openEdit(creator: Creator) {
    setEditingId(creator.id);
    setError(null);
    setForm({
      name: creator.name,
      name_zh: creator.name_zh,
      platform: creator.platform,
      handle: creator.handle,
      profile_url: creator.profile_url,
      category: creator.category,
      base_location: creator.base_location,
      nationality: creator.nationality,
      is_active: creator.is_active,
      approx_followers: creator.approx_followers,
      last_post_at: creator.last_post_at,
      notes: creator.notes,
    });
  }

  function handleChange(
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value, type } = event.target;
    const nextValue = type === "checkbox" ? (event.target as HTMLInputElement).checked : value;
    setForm((prev) => ({
      ...prev,
      [name]:
        type === "checkbox"
          ? nextValue
          : value === ""
            ? null
            : name === "approx_followers"
              ? Number.parseInt(value, 10)
              : value,
    }));
  }

  async function saveCreator() {
    if (!form.name.trim()) {
      setError("Name is required");
      return;
    }
    if (!form.profile_url.trim()) {
      setError("Profile URL is required");
      return;
    }

    startSaving(async () => {
      setError(null);
      const supabase = createClient();
      const payload = {
        ...form,
        name_zh: toNullableString(form.name_zh ?? ""),
        handle: toNullableString(form.handle ?? ""),
        profile_url: form.profile_url.trim(),
        category: form.category,
        base_location: form.base_location,
        nationality: form.nationality,
        approx_followers:
          typeof form.approx_followers === "number" && Number.isFinite(form.approx_followers)
            ? form.approx_followers
            : null,
        last_post_at: form.last_post_at,
        notes: toNullableString(form.notes ?? ""),
        updated_at: new Date().toISOString(),
      };

      const result = editingId
        ? await supabase.from("creators").update(payload).eq("id", editingId).select().single()
        : await supabase.from("creators").insert({ ...payload, created_at: new Date().toISOString() }).select().single();

      if (result.error) {
        setError(result.error.message);
        return;
      }

      const saved = result.data as Creator;
      setCreators((prev) =>
        editingId ? prev.map((creator) => (creator.id === editingId ? saved : creator)) : [saved, ...prev],
      );
      resetForm();
    });
  }

  async function toggleActive(creator: Creator) {
    const supabase = createClient();
    const { data, error: updateError } = await supabase
      .from("creators")
      .update({ is_active: !creator.is_active, updated_at: new Date().toISOString() })
      .eq("id", creator.id)
      .select()
      .single();

    if (updateError) {
      setError(updateError.message);
      return;
    }

    if (data) {
      setCreators((prev) => prev.map((item) => (item.id === creator.id ? (data as Creator) : item)));
    }
  }

  async function deleteCreator(creator: Creator) {
    if (!confirm(`Delete creator ${creator.name}?`)) return;

    setDeletingId(creator.id);
    try {
      const supabase = createClient();
      const { error: deleteError } = await supabase.from("creators").delete().eq("id", creator.id);
      if (deleteError) {
        setError(deleteError.message);
        return;
      }

      setCreators((prev) => prev.filter((item) => item.id !== creator.id));
      if (editingId === creator.id) {
        resetForm();
      }
    } finally {
      setDeletingId(null);
    }
  }

  const activeCount = creators.filter((creator) => creator.is_active).length;

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-line bg-surface p-4 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-fg-strong">
              {t("creatorsPageTitle")} — {activeCount} active / {creators.length} total
            </p>
            <p className="mt-1 text-xs text-fg-muted">Inline editing only. No modal workflow.</p>
          </div>
          <button
            type="button"
            onClick={openCreate}
            className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-700"
          >
            + {t("creatorsAdd")}
          </button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <CreatorFieldLabel>{t("creatorsName")} *</CreatorFieldLabel>
            <input
              name="name"
              value={form.name}
              onChange={handleChange}
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              placeholder="Display name"
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsName")} (ZH)</CreatorFieldLabel>
            <input
              name="name_zh"
              value={form.name_zh ?? ""}
              onChange={handleChange}
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              placeholder="中文名稱（選填）"
            />
          </div>
          <div className="md:col-span-2">
            <CreatorFieldLabel>{t("creatorsProfileUrl")} *</CreatorFieldLabel>
            <input
              name="profile_url"
              value={form.profile_url}
              onChange={handleChange}
              type="url"
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              placeholder="https://..."
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsPlatform")}</CreatorFieldLabel>
            <DesignSelect
              value={form.platform}
              onChange={(value) => setForm((prev) => ({ ...prev, platform: value as CreatorForm["platform"] }))}
              options={PLATFORMS.map((platform) => ({ value: platform, label: platform }))}
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsHandle")}</CreatorFieldLabel>
            <input
              name="handle"
              value={form.handle ?? ""}
              onChange={handleChange}
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              placeholder="@handle"
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsCategory")}</CreatorFieldLabel>
            <DesignSelect
              value={form.category ?? ""}
              onChange={(value) => setForm((prev) => ({ ...prev, category: value || null }))}
              options={[{ value: "", label: "—" }, ...ACTOR_CATEGORIES.map((category) => ({ value: category, label: tActor(category) }))]}
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsLocation")}</CreatorFieldLabel>
            <DesignSelect
              value={form.base_location ?? ""}
              onChange={(value) => setForm((prev) => ({ ...prev, base_location: value || null }))}
              options={[{ value: "", label: "—" }, ...LOCATIONS.map((location) => ({ value: location, label: location }))]}
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsNationality")}</CreatorFieldLabel>
            <DesignSelect
              value={form.nationality ?? ""}
              onChange={(value) => setForm((prev) => ({ ...prev, nationality: value || null }))}
              options={[{ value: "", label: "—" }, ...NATIONALITIES.map((nationality) => ({ value: nationality, label: nationality }))]}
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsFollowers")}</CreatorFieldLabel>
            <input
              name="approx_followers"
              value={form.approx_followers ?? ""}
              onChange={handleChange}
              type="number"
              min={0}
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              placeholder="0"
            />
          </div>
          <div>
            <CreatorFieldLabel>{t("creatorsLastPost")}</CreatorFieldLabel>
            <input
              name="last_post_at"
              value={form.last_post_at ?? ""}
              onChange={handleChange}
              type="date"
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            />
          </div>
          <div className="md:col-span-2">
            <CreatorFieldLabel>{t("creatorsNotes")}</CreatorFieldLabel>
            <textarea
              name="notes"
              value={form.notes ?? ""}
              onChange={handleChange}
              rows={3}
              className="w-full rounded-lg border border-line px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
            />
          </div>
          <div className="flex items-center gap-2 md:col-span-2">
            <input
              id="creator-is-active"
              name="is_active"
              type="checkbox"
              checked={form.is_active}
              onChange={handleChange}
              className="h-4 w-4 rounded border-line text-green-600 focus:ring-green-400"
            />
            <label htmlFor="creator-is-active" className="text-sm text-fg">
              {t("creatorsIsActive")}
            </label>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="mt-4 flex items-center gap-2">
          <button
            type="button"
            onClick={saveCreator}
            disabled={saving}
            aria-busy={saving}
            className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-green-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? "Saving..." : editingId ? t("creatorsEdit") : t("creatorsAdd")}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={resetForm}
              className="rounded-lg border border-line px-4 py-2 text-sm text-fg-muted transition hover:bg-muted"
            >
              Cancel edit
            </button>
          )}
        </div>
      </section>

      <section className="space-y-3">
        {creators.length === 0 ? (
          <p className="py-8 text-center text-sm text-fg-subtle">{t("creatorsNone")}</p>
        ) : (
          creators.map((creator) => (
            <div
              key={creator.id}
              className={`rounded-xl border border-line bg-surface p-4 shadow-sm ${creator.is_active ? "" : "opacity-60"}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <a
                    href={creator.profile_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-fg-strong hover:text-green-700 hover:underline"
                  >
                    {creator.name}
                  </a>
                  {creator.name_zh && <p className="text-xs text-fg-subtle">{creator.name_zh}</p>}
                  {creator.handle && <p className="text-xs text-fg-subtle">@{creator.handle}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={() => openEdit(creator)} className="text-xs text-blue-600 hover:underline">
                    {t("creatorsEdit")}
                  </button>
                  <button type="button" onClick={() => toggleActive(creator)} className="text-xs text-fg-subtle hover:underline">
                    {creator.is_active ? t("creatorsDeactivate") : t("creatorsActivate")}
                  </button>
                  <button
                    type="button"
                    onClick={() => deleteCreator(creator)}
                    disabled={deletingId === creator.id}
                    className="text-xs text-red-700 hover:underline disabled:opacity-50"
                  >
                    {deletingId === creator.id ? "..." : "Delete"}
                  </button>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-fg-muted">
                <span>{creator.platform}</span>
                {creator.category && <span>· {creator.category}</span>}
                {creator.base_location && <span>· {creator.base_location}</span>}
                {creator.nationality && <span>· {creator.nationality}</span>}
                {creator.approx_followers != null && <span>· {creator.approx_followers.toLocaleString()} followers</span>}
                <span>· {creator.last_post_at ? new Date(creator.last_post_at).toLocaleDateString(locale) : "—"}</span>
              </div>
              {creator.notes && <p className="mt-2 text-xs text-fg-subtle line-clamp-2">{creator.notes}</p>}
            </div>
          ))
        )}
      </section>
    </div>
  );
}
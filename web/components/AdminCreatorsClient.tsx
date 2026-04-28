"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { createClient } from "@/lib/supabase/client";
import type { Creator } from "@/app/[locale]/admin/creators/page";
import type { Locale } from "@/lib/types";

const PLATFORMS = [
  "note",
  "youtube",
  "twitter",
  "instagram",
  "blog",
  "substack",
  "other",
] as const;

const CATEGORIES = [
  "researcher",
  "traveler",
  "writer",
  "activist",
  "food",
  "art",
  "business",
  "media",
] as const;

const LOCATIONS = [
  "tokyo",
  "osaka",
  "fukuoka",
  "kyoto",
  "sapporo",
  "nationwide",
  "other",
] as const;

const NATIONALITIES = [
  "taiwanese_in_japan",
  "japanese",
  "other",
] as const;

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

export default function AdminCreatorsClient({ initialCreators, locale }: Props) {
  const t = useTranslations("admin");
  const [creators, setCreators] = useState<Creator[]>(initialCreators);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<CreatorForm>(EMPTY_FORM);
  const [saving, startSaving] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function openAdd() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowForm(true);
  }

  function openEdit(c: Creator) {
    setEditId(c.id);
    setForm({
      name: c.name,
      name_zh: c.name_zh,
      platform: c.platform,
      handle: c.handle,
      profile_url: c.profile_url,
      category: c.category,
      base_location: c.base_location,
      nationality: c.nationality,
      is_active: c.is_active,
      approx_followers: c.approx_followers,
      last_post_at: c.last_post_at,
      notes: c.notes,
    });
    setError(null);
    setShowForm(true);
  }

  function handleChange(
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) {
    const { name, value, type } = e.target;
    const checked =
      type === "checkbox" ? (e.target as HTMLInputElement).checked : undefined;
    setForm((prev) => ({
      ...prev,
      [name]:
        type === "checkbox"
          ? checked
          : value === ""
            ? null
            : name === "approx_followers"
              ? parseInt(value, 10)
              : value,
    }));
  }

  function handleSave() {
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
      let result;

      if (editId) {
        result = await supabase
          .from("creators")
          .update({ ...form, updated_at: new Date().toISOString() })
          .eq("id", editId)
          .select()
          .single();
      } else {
        result = await supabase.from("creators").insert(form).select().single();
      }

      if (result.error) {
        setError(result.error.message);
        return;
      }

      const saved = result.data as Creator;
      if (editId) {
        setCreators((prev) =>
          prev.map((c) => (c.id === editId ? saved : c))
        );
      } else {
        setCreators((prev) => [saved, ...prev]);
      }
      setShowForm(false);
    });
  }

  async function toggleActive(c: Creator) {
    const supabase = createClient();
    const { data, error: err } = await supabase
      .from("creators")
      .update({ is_active: !c.is_active })
      .eq("id", c.id)
      .select()
      .single();
    if (!err && data) {
      setCreators((prev) =>
        prev.map((x) => (x.id === c.id ? (data as Creator) : x))
      );
    }
  }

  const active = creators.filter((c) => c.is_active);
  const inactive = creators.filter((c) => !c.is_active);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-500">
          {t("creatorsPageTitle")} — {active.length} active / {creators.length} total
        </p>
        <button
          onClick={openAdd}
          className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition"
        >
          + {t("creatorsAdd")}
        </button>
      </div>

      {creators.length === 0 ? (
        <p className="text-gray-400 text-sm py-8 text-center">
          {t("creatorsNone")}
        </p>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">{t("creatorsName")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("creatorsPlatform")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("creatorsCategory")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("creatorsLocation")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("creatorsFollowers")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("creatorsLastPost")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("creatorsIsActive")}</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {creators.map((c) => (
                  <tr key={c.id} className={c.is_active ? "hover:bg-gray-50" : "opacity-50 hover:bg-gray-50"}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">
                        <a
                          href={c.profile_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:text-green-700 hover:underline"
                        >
                          {c.name}
                        </a>
                      </div>
                      {c.name_zh && (
                        <div className="text-xs text-gray-400">{c.name_zh}</div>
                      )}
                      {c.handle && (
                        <div className="text-xs text-gray-400">@{c.handle}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{c.platform}</td>
                    <td className="px-4 py-3 text-gray-600">{c.category ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-600">{c.base_location ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-600">
                      {c.approx_followers != null
                        ? c.approx_followers.toLocaleString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {c.last_post_at
                        ? new Date(c.last_post_at).toLocaleDateString(locale)
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                          c.is_active
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {c.is_active ? "✓" : "—"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                      <button
                        onClick={() => openEdit(c)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        {t("creatorsEdit")}
                      </button>
                      <button
                        onClick={() => toggleActive(c)}
                        className="text-xs text-gray-400 hover:text-gray-700 hover:underline"
                      >
                        {c.is_active ? t("creatorsDeactivate") : t("creatorsActivate")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {creators.map((c) => (
              <div
                key={c.id}
                className={`rounded-xl border border-gray-200 bg-white px-4 py-3 ${
                  c.is_active ? "" : "opacity-50"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <a
                      href={c.profile_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-gray-900 hover:text-green-700 hover:underline text-sm"
                    >
                      {c.name}
                    </a>
                    {c.name_zh && (
                      <p className="text-xs text-gray-400">{c.name_zh}</p>
                    )}
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => openEdit(c)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      {t("creatorsEdit")}
                    </button>
                    <button
                      onClick={() => toggleActive(c)}
                      className="text-xs text-gray-400 hover:underline"
                    >
                      {c.is_active ? t("creatorsDeactivate") : t("creatorsActivate")}
                    </button>
                  </div>
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
                  <span>{c.platform}</span>
                  {c.category && <span>· {c.category}</span>}
                  {c.base_location && <span>· {c.base_location}</span>}
                  {c.approx_followers != null && (
                    <span>· {c.approx_followers.toLocaleString()} followers</span>
                  )}
                </div>
                {c.notes && (
                  <p className="mt-1 text-xs text-gray-400 line-clamp-2">{c.notes}</p>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Add / Edit form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-lg max-h-screen overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold mb-4">
              {editId ? t("creatorsEdit") : t("creatorsAdd")}
            </h2>

            {error && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsName")} *
                  </label>
                  <input
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="Display name"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsName")} (ZH)
                  </label>
                  <input
                    name="name_zh"
                    value={form.name_zh ?? ""}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="中文名稱（選填）"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t("creatorsProfileUrl")} *
                </label>
                <input
                  name="profile_url"
                  value={form.profile_url}
                  onChange={handleChange}
                  type="url"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  placeholder="https://..."
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsPlatform")}
                  </label>
                  <select
                    name="platform"
                    value={form.platform}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    {PLATFORMS.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsHandle")}
                  </label>
                  <input
                    name="handle"
                    value={form.handle ?? ""}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="@handle"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsCategory")}
                  </label>
                  <select
                    name="category"
                    value={form.category ?? ""}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    <option value="">—</option>
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsLocation")}
                  </label>
                  <select
                    name="base_location"
                    value={form.base_location ?? ""}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    <option value="">—</option>
                    {LOCATIONS.map((l) => (
                      <option key={l} value={l}>{l}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsNationality")}
                  </label>
                  <select
                    name="nationality"
                    value={form.nationality ?? ""}
                    onChange={handleChange}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                  >
                    <option value="">—</option>
                    {NATIONALITIES.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    {t("creatorsFollowers")}
                  </label>
                  <input
                    name="approx_followers"
                    value={form.approx_followers ?? ""}
                    onChange={handleChange}
                    type="number"
                    min={0}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                    placeholder="0"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t("creatorsLastPost")}
                </label>
                <input
                  name="last_post_at"
                  value={form.last_post_at ?? ""}
                  onChange={handleChange}
                  type="date"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  {t("creatorsNotes")}
                </label>
                <textarea
                  name="notes"
                  value={form.notes ?? ""}
                  onChange={handleChange}
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  id="is_active"
                  name="is_active"
                  type="checkbox"
                  checked={form.is_active}
                  onChange={handleChange}
                  className="h-4 w-4 rounded border-gray-300 text-green-600 focus:ring-green-500"
                />
                <label
                  htmlFor="is_active"
                  className="text-sm text-gray-700"
                >
                  {t("creatorsIsActive")}
                </label>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setShowForm(false)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition disabled:opacity-60"
              >
                {saving ? "..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

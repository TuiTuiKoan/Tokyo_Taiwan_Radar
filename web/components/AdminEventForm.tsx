"use client";

import { type Event, type Locale, CATEGORY_GROUPS, getEventName } from "@/lib/types";

export const EMPTY_FORM = {
  name_ja: "",
  name_zh: "",
  name_en: "",
  description_ja: "",
  description_zh: "",
  description_en: "",
  category: [] as string[],
  start_date: "",
  end_date: "",
  location_name: "",
  location_address: "",
  business_hours: "",
  is_paid: false,
  price_info: "",
  source_url: "",
  source_name: "manual",
  original_language: "zh",
  is_active: true,
  parent_event_id: "" as string,
  record_links: [] as { title: string; url: string }[],
};

export type FormState = typeof EMPTY_FORM;

interface Props {
  form: FormState;
  t: any;
  tCat: any;
  updateField: (k: string, v: any) => void;
  toggleCategory: (cat: string) => void;
  events: Event[];
  editingId: string | null;
  locale: Locale;
}

export default function AdminEventForm({
  form,
  t,
  tCat,
  updateField,
  toggleCategory,
  events,
  editingId,
  locale,
}: Props) {
  const parentCandidates = events.filter((e) => e.id !== editingId);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Multilingual names */}
      {(["ja", "zh", "en"] as const).map((lang) => (
        <div key={lang}>
          <label className="block text-xs text-gray-500 mb-1">
            {t(`name${lang.charAt(0).toUpperCase() + lang.slice(1)}` as any)}
          </label>
          <input
            type="text"
            value={(form as any)[`name_${lang}`]}
            onChange={(e) => updateField(`name_${lang}`, e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
      ))}

      {/* Dates */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("startDate")}</label>
        <input
          type="date"
          value={form.start_date}
          onChange={(e) => updateField("start_date", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("endDate")}</label>
        <input
          type="date"
          value={form.end_date}
          onChange={(e) => updateField("end_date", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Location */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("location")}</label>
        <input
          type="text"
          value={form.location_name}
          onChange={(e) => updateField("location_name", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("address")}</label>
        <input
          type="text"
          value={form.location_address}
          onChange={(e) => updateField("location_address", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Hours */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("hours")}</label>
        <input
          type="text"
          value={form.business_hours}
          onChange={(e) => updateField("business_hours", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Source URL */}
      <div>
        <label className="block text-xs text-gray-500 mb-1">{t("sourceUrl")}</label>
        <input
          type="url"
          value={form.source_url}
          onChange={(e) => updateField("source_url", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Paid */}
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="is_paid"
          checked={form.is_paid}
          onChange={(e) => updateField("is_paid", e.target.checked)}
          className="w-4 h-4"
        />
        <label htmlFor="is_paid" className="text-sm">{t("isPaid")}</label>
      </div>

      {/* Active */}
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          id="is_active"
          checked={form.is_active}
          onChange={(e) => updateField("is_active", e.target.checked)}
          className="w-4 h-4"
        />
        <label htmlFor="is_active" className="text-sm">{t("isActive")}</label>
      </div>

      {/* Price info */}
      <div className="md:col-span-2">
        <label className="block text-xs text-gray-500 mb-1">{t("priceInfo")}</label>
        <input
          type="text"
          value={form.price_info}
          onChange={(e) => updateField("price_info", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Categories */}
      <div className="md:col-span-2">
        <label className="block text-xs text-gray-500 mb-2">{t("category")}</label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
          {CATEGORY_GROUPS.map((group) => (
            <div key={group.labelKey} className="flex flex-wrap gap-2 items-start">
              <span className="text-xs text-gray-400 w-16 shrink-0">{tCat(group.labelKey as any)}</span>
              {group.categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  className={`px-3 py-1 rounded-full text-xs border transition ${
                    form.category.includes(cat)
                      ? "bg-green-600 text-white border-green-600"
                      : "border-gray-300 hover:border-green-400"
                  }`}
                >
                  {tCat(cat as any)}
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>

      {/* Parent event */}
      <div className="md:col-span-2">
        <label className="block text-xs text-gray-500 mb-1">{t("parentEvent")}</label>
        <select
          value={form.parent_event_id}
          onChange={(e) => updateField("parent_event_id", e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
        >
          <option value="">{t("noParent")}</option>
          {parentCandidates.map((e) => (
            <option key={e.id} value={e.id}>
              {getEventName(e, locale)} ({e.start_date?.slice(0, 10) ?? "—"})
            </option>
          ))}
        </select>
      </div>

      {/* Multilingual descriptions */}
      {(["ja", "zh", "en"] as const).map((lang) => (
        <div key={lang} className="md:col-span-2">
          <label className="block text-xs text-gray-500 mb-1">
            {t(`desc${lang.charAt(0).toUpperCase() + lang.slice(1)}` as any)}
          </label>
          <textarea
            rows={3}
            value={(form as any)[`description_${lang}`]}
            onChange={(e) => updateField(`description_${lang}`, e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
      ))}

      {/* Record links */}
      <div className="md:col-span-2">
        <label className="block text-xs text-gray-500 mb-2">{t("recordLinksSection" as any)}</label>
        <div className="space-y-2">
          {form.record_links.map((link, i) => (
            <div key={i} className="flex gap-2 items-center">
              <input
                type="text"
                placeholder={t("recordLinksLinkTitle" as any)}
                value={link.title}
                onChange={(e) => {
                  const updated = [...form.record_links];
                  updated[i] = { ...updated[i], title: e.target.value };
                  updateField("record_links", updated);
                }}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              />
              <input
                type="url"
                placeholder={t("recordLinksUrl" as any)}
                value={link.url}
                onChange={(e) => {
                  const updated = [...form.record_links];
                  updated[i] = { ...updated[i], url: e.target.value };
                  updateField("record_links", updated);
                }}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              />
              <button
                type="button"
                onClick={() => updateField("record_links", form.record_links.filter((_, j) => j !== i))}
                className="text-xs text-red-500 hover:text-red-700 border border-red-200 rounded px-2 py-1 shrink-0"
              >
                {t("recordLinksRemove" as any)}
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => updateField("record_links", [...form.record_links, { title: "", url: "" }])}
            className="text-xs text-green-600 hover:text-green-700 border border-green-300 rounded px-3 py-1"
          >
            + {t("recordLinksAdd" as any)}
          </button>
        </div>
      </div>
    </div>
  );
}

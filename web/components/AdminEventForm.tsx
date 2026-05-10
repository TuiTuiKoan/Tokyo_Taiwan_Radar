"use client";

import { type Event, type Locale, CATEGORY_GROUPS, getEventName } from "@/lib/types";

const VALID_EVENT_FORMS = [
  "exhibition", "screening", "lecture", "performance", "market",
  "workshop", "conference", "networking", "screening_with_talk",
  "tour", "competition", "tasting", "other",
] as const;

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
  location_url: "",
  business_hours: "",
  performer: "",
  organizer: "",
  organizer_url: "",
  event_form: [] as string[],
  co_organizers: "",
  sponsors: "",
  primary_language: "",
  has_japanese_support: false,
  has_english_support: false,
  has_chinese_support: false,
  is_paid: false,
  price_info: "",
  source_url: "",
  source_name: "manual",
  original_language: "zh",
  is_active: true,
  parent_event_id: "" as string,
  record_links: [] as { title: string; url: string; recommended?: boolean }[],
};

export type FormState = typeof EMPTY_FORM;

interface Props {
  form: FormState;
  t: any;
  tCat: any;
  tEventForm: any;
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
  tEventForm,
  updateField,
  toggleCategory,
  events,
  editingId,
  locale,
}: Props) {
  const parentCandidates = events.filter((e) => e.id !== editingId);
  return (
    <div className="grid grid-cols-1 gap-4">
      {/* Multilingual names */}
      {(["ja", "zh", "en"] as const).map((lang) => (
        <div key={lang}>
          <label className="block text-xs text-fg-muted mb-1">
            {t(`name${lang.charAt(0).toUpperCase() + lang.slice(1)}` as any)}
          </label>
          <input
            type="text"
            value={(form as any)[`name_${lang}`]}
            onChange={(e) => updateField(`name_${lang}`, e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
      ))}

      {/* Dates */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("startDate")}</label>
        <input
          type="date"
          value={form.start_date}
          onChange={(e) => updateField("start_date", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("endDate")}</label>
        <input
          type="date"
          value={form.end_date}
          onChange={(e) => updateField("end_date", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Location */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("location")}</label>
        <input
          type="text"
          value={form.location_name}
          onChange={(e) => updateField("location_name", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("address")}</label>
        <input
          type="text"
          value={form.location_address}
          onChange={(e) => updateField("location_address", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Venue website URL */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("locationUrl")}</label>
        <input
          type="url"
          value={(form as any).location_url ?? ""}
          onChange={(e) => updateField("location_url", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Hours */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("hours")}</label>
        <input
          type="text"
          value={form.business_hours}
          onChange={(e) => updateField("business_hours", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Performer */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("performer")}</label>
        <input
          type="text"
          value={(form as any).performer ?? ""}
          onChange={(e) => updateField("performer", e.target.value)}
          placeholder="例: 李映萱、唐 顥芸"
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Organizer + Organizer URL */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("organizer")}</label>
        <input
          type="text"
          value={(form as any).organizer ?? ""}
          onChange={(e) => updateField("organizer", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("organizerUrl")}</label>
        <input
          type="url"
          value={(form as any).organizer_url ?? ""}
          onChange={(e) => updateField("organizer_url", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Event Form (multi-checkbox) */}
      <div className="">
        <label className="block text-xs text-fg-muted mb-2">{t("eventForm")}</label>
        <div className="flex flex-wrap gap-2">
          {VALID_EVENT_FORMS.map((ef) => (
            <button
              key={ef}
              type="button"
              onClick={() => {
                const cur: string[] = (form as any).event_form ?? [];
                updateField(
                  "event_form",
                  cur.includes(ef) ? cur.filter((x) => x !== ef) : [...cur, ef]
                );
              }}
              className={`px-3 py-1 rounded-full text-xs border transition ${
                ((form as any).event_form ?? []).includes(ef)
                  ? "bg-blue-600 text-white border-blue-600"
                  : "border-line-strong hover:border-blue-400"
              }`}
            >
              {tEventForm(ef as any)}
            </button>
          ))}
        </div>
      </div>

      {/* Co-organizers + Sponsors */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("coOrganizers")}</label>
        <input
          type="text"
          value={(form as any).co_organizers ?? ""}
          onChange={(e) => updateField("co_organizers", e.target.value)}
          placeholder="例: A機構, B機構"
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("sponsors")}</label>
        <input
          type="text"
          value={(form as any).sponsors ?? ""}
          onChange={(e) => updateField("sponsors", e.target.value)}
          placeholder="例: C企業, D企業"
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Primary language */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("primaryLanguage")}</label>
        <select
          value={(form as any).primary_language ?? ""}
          onChange={(e) => updateField("primary_language", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        >
          <option value="">—</option>
          <option value="ja">日本語</option>
          <option value="zh">中文</option>
          <option value="en">English</option>
          <option value="mixed">Mixed</option>
        </select>
      </div>

      {/* Language support checkboxes */}
      <div className="flex items-center gap-4">
        {([
          ["has_japanese_support", t("hasJapaneseSupport")],
          ["has_english_support", t("hasEnglishSupport")],
          ["has_chinese_support", t("hasChineseSupport")],
        ] as [string, string][]).map(([key, label]) => (
          <label key={key} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
            <input
              type="checkbox"
              checked={!!(form as any)[key]}
              onChange={(e) => updateField(key, e.target.checked)}
              className="w-3.5 h-3.5"
            />
            {label}
          </label>
        ))}
      </div>

      {/* Source URL */}
      <div>
        <label className="block text-xs text-fg-muted mb-1">{t("sourceUrl")}</label>
        <input
          type="url"
          value={form.source_url}
          onChange={(e) => updateField("source_url", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
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
      <div className="">
        <label className="block text-xs text-fg-muted mb-1">{t("priceInfo")}</label>
        <input
          type="text"
          value={form.price_info}
          onChange={(e) => updateField("price_info", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm"
        />
      </div>

      {/* Categories */}
      <div className="">
        <label className="block text-xs text-fg-muted mb-2">{t("category")}</label>
        <div className="space-y-2">
          {CATEGORY_GROUPS.map((group) => (
            <div key={group.labelKey} className="grid grid-cols-[4.5rem_1fr] gap-x-3 items-start">
              <span className="text-xs text-fg-subtle font-medium pt-1 text-right leading-tight shrink-0">{tCat(group.labelKey as any)}</span>
              <div className="flex flex-wrap gap-2">
              {group.categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  className={`px-3 py-1 rounded-full text-xs border transition ${
                    form.category.includes(cat)
                      ? "bg-green-600 text-white border-green-600"
                      : "border-line-strong hover:border-green-400"
                  }`}
                >
                  {tCat(cat as any)}
                </button>
              ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Parent event */}
      <div className="">
        <label className="block text-xs text-fg-muted mb-1">{t("parentEvent")}</label>
        <select
          value={form.parent_event_id}
          onChange={(e) => updateField("parent_event_id", e.target.value)}
          className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
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
        <div key={lang} className="">
          <label className="block text-xs text-fg-muted mb-1">
            {t(`desc${lang.charAt(0).toUpperCase() + lang.slice(1)}` as any)}
          </label>
          <textarea
            rows={3}
            value={(form as any)[`description_${lang}`]}
            onChange={(e) => updateField(`description_${lang}`, e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm resize-y focus:outline-none focus:ring-2 focus:ring-green-400"
          />
        </div>
      ))}

      {/* Record links */}
      <div className="">
        <label className="block text-xs text-fg-muted mb-2">{t("recordLinksSection" as any)}</label>
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
                className="flex-1 border border-line-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
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
                className="flex-1 border border-line-strong rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
              />
              <label className="flex items-center gap-1 text-xs text-fg-muted shrink-0 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={!!link.recommended}
                  onChange={(e) => {
                    const updated = [...form.record_links];
                    updated[i] = { ...updated[i], recommended: e.target.checked };
                    updateField("record_links", updated);
                  }}
                  className="w-3.5 h-3.5"
                />
                {t("recordLinksRecommended" as any)}
              </label>
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
            onClick={() => updateField("record_links", [...form.record_links, { title: "", url: "", recommended: false }])}
            className="text-xs text-green-600 hover:text-green-700 border border-green-300 rounded px-3 py-1"
          >
            + {t("recordLinksAdd" as any)}
          </button>
        </div>
      </div>
    </div>
  );
}

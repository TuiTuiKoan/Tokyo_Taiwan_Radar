"use client";

import { type Event, type Locale, CATEGORY_GROUPS, EVENT_FORMS, getEventName } from "@/lib/types";
import DesignSelect from "@/components/DesignSelect";
import { PillButton, RadioGroup } from "@/components/UiControls";

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
  co_organizers: null as string[] | null,
  sponsors: null as string[] | null,
  primary_language: "",
  has_japanese_support: false,
  has_english_support: false,
  has_chinese_support: false,
  is_paid: false,
  price_info: "",
  official_url: "",
  submission_url: "",
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
  tEventForm?: any;
  updateField: (k: string, v: any) => void;
  toggleCategory: (cat: string) => void;
  events: Event[];
  editingId: string | null;
  locale: Locale;
  /** Intake-wizard label overrides keyed by eventIntake namespace keys. */
  fieldLabels?: Partial<Record<string, string>>;
  /** Languages to render for name/description blocks. Defaults to all three. */
  nameDescriptionLangs?: Locale[];
  showParentEvent?: boolean;
  showIsActive?: boolean;
  /** Show the source/provenance URL input (edit pages only; hidden on create). */
  showSourceUrl?: boolean;
  /** Lock the public/private radio: owner cannot re-publish a deactivated event. */
  isActiveLocked?: boolean;
  requiredMarkers?: boolean;
  paidMode?: "checkbox" | "choice";
  paidChoice?: "" | "free" | "paid";
  onPaidChoiceChange?: (choice: "free" | "paid") => void;
  hideMixedLanguage?: boolean;
  venuePlaceholder?: string;
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
  fieldLabels,
  nameDescriptionLangs = ["ja", "zh", "en"],
  showParentEvent = true,
  showIsActive = true,
  showSourceUrl = false,
  isActiveLocked = false,
  requiredMarkers = false,
  paidChoice = "",
  onPaidChoiceChange,
  hideMixedLanguage = false,
  venuePlaceholder,
}: Props) {
  const parentCandidates = events.filter((e) => e.id !== editingId);
  const labels = fieldLabels;
  const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
  const langName = (lang: Locale): string =>
    labels?.[`lang${cap(lang)}`] ?? (lang === "ja" ? "日本語" : lang === "zh" ? "中文" : "English");
  const label = (intakeKey: string, adminKey: string): string => labels?.[intakeKey] ?? t(adminKey);
  const sectionLabel = (intakeKey: string, fallback: string): string => labels?.[intakeKey] ?? fallback;
  const mark = (required: boolean) =>
    requiredMarkers && required ? <span className="text-green-600">{" *"}</span> : null;
  const nameLabel = (lang: Locale): string => {
    const tpl = labels?.fieldEventNameLang;
    return tpl ? tpl.replace("{lang}", langName(lang)) : t(`name${cap(lang)}`);
  };
  const descLabel = (lang: Locale): string => {
    const tpl = labels?.fieldEventDescLang;
    return tpl ? tpl.replace("{lang}", langName(lang)) : t(`desc${cap(lang)}`);
  };
  const primaryLang = form.primary_language;
  const singleLang = nameDescriptionLangs.length === 1;
  return (
    <div className="space-y-8">
      {/* ===== Section 1: Basic info ===== */}
      <section className="grid grid-cols-1 gap-4 rounded-2xl bg-paper/60 p-5">
        <div className="text-sm font-semibold text-fg-strong">{sectionLabel("sectionBasicInfo", "基本情報")}</div>

        {/* Primary language */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("primaryLanguageLabel", "primaryLanguage")}{mark(true)}</label>
          <DesignSelect
            value={(form as any).primary_language ?? ""}
            onChange={(v) => updateField("primary_language", v)}
            options={[
              { value: "", label: "—" },
              { value: "ja", label: "日本語" },
              { value: "zh", label: "中文" },
              { value: "en", label: "English" },
              ...(hideMixedLanguage ? [] : [{ value: "mixed", label: "Mixed" }]),
            ]}
          />
        </div>

        {/* Language support */}
        <div className="flex items-center gap-4">
          {([
            ["has_japanese_support", labels?.fieldJaSupport ?? t("hasJapaneseSupport")],
            ["has_english_support", labels?.fieldEnSupport ?? t("hasEnglishSupport")],
            ["has_chinese_support", labels?.fieldZhSupport ?? t("hasChineseSupport")],
          ] as [string, string][]).map(([key, lbl]) => (
            <label key={key} className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
              <input
                type="checkbox"
                checked={!!(form as any)[key]}
                onChange={(e) => updateField(key, e.target.checked)}
                className="w-3.5 h-3.5"
              />
              {lbl}
            </label>
          ))}
        </div>

        {/* Multilingual names */}
        {nameDescriptionLangs.map((lang) => (
          <div key={lang}>
            <label className="block text-xs text-fg-muted mb-1">
              {singleLang ? label("fieldEventName", `name${cap(lang)}`) : nameLabel(lang)}
              {mark(singleLang || lang === primaryLang)}
            </label>
            <input
              type="text"
              value={(form as any)[`name_${lang}`] ?? ""}
              onChange={(e) => updateField(`name_${lang}`, e.target.value)}
              className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper focus:outline-none focus:ring-2 focus:ring-green-400"
            />
          </div>
        ))}

        {/* Multilingual descriptions */}
        {nameDescriptionLangs.map((lang) => (
          <div key={lang} className="">
            <label className="block text-xs text-fg-muted mb-1">
              {singleLang ? label("fieldEventDesc", `desc${cap(lang)}`) : descLabel(lang)}
              {mark(singleLang || lang === primaryLang)}
            </label>
            <textarea
              rows={3}
              value={(form as any)[`description_${lang}`] ?? ""}
              onChange={(e) => updateField(`description_${lang}`, e.target.value)}
              className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper resize-y focus:outline-none focus:ring-2 focus:ring-green-400"
            />
          </div>
        ))}

        {/* Announcement URL (official_url) */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldPromoUrl", "sourceUrl")}</label>
          <input
            type="url"
            value={(form as any).official_url ?? ""}
            onChange={(e) => updateField("official_url", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Registration URL (submission_url) */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldSubmissionUrl", "sourceUrl")}</label>
          <input
            type="url"
            value={(form as any).submission_url ?? ""}
            onChange={(e) => updateField("submission_url", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Source / provenance URL (edit pages only) */}
        {showSourceUrl && (
          <div>
            <label className="block text-xs text-fg-muted mb-1">{label("fieldSourceUrl", "sourceUrl")}</label>
            <input
              type="url"
              value={form.source_url}
              onChange={(e) => updateField("source_url", e.target.value)}
              className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
            />
          </div>
        )}

        {/* Paid */}
        <div>
          <label className="block text-xs text-fg-muted mb-2">{label("fieldPaidLabel", "isPaid")}{mark(true)}</label>
          <RadioGroup
            value={paidChoice}
            onChange={(v) => onPaidChoiceChange?.(v as "free" | "paid")}
            options={[
              { value: "free", label: labels?.paidFree ?? "免費" },
              { value: "paid", label: labels?.paidPaid ?? "收費" },
            ]}
          />
        </div>

        {/* Price info (paid only) */}
        {paidChoice === "paid" && (
          <div>
            <label className="block text-xs text-fg-muted mb-1">{label("fieldPriceInfo", "priceInfo")}{mark(true)}</label>
            <input
              type="text"
              value={form.price_info}
              onChange={(e) => updateField("price_info", e.target.value)}
              className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
            />
          </div>
        )}

        {/* Categories */}
        <div className="">
          <label className="block text-xs text-fg-muted mb-2">{label("fieldCategory", "category")}{mark(true)}</label>
          <div className="space-y-2">
            {CATEGORY_GROUPS.map((group) => (
              <div key={group.labelKey} className="grid grid-cols-[4.5rem_1fr] gap-x-3 items-start">
                <span className="text-xs text-fg-subtle font-medium pt-1 text-right leading-tight shrink-0">{tCat(group.labelKey as any)}</span>
                <div className="flex flex-wrap gap-2">
                {group.categories.map((cat) => (
                  <PillButton
                    key={cat}
                    onClick={() => toggleCategory(cat)}
                    active={form.category.includes(cat)}
                  >
                    {tCat(cat as any)}
                  </PillButton>
                ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Record links */}
        <div className="">
          <label className="block text-xs text-fg-muted mb-2">{label("fieldRecordLinks", "recordLinksSection")}</label>
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
                  className="flex-1 border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper focus:outline-none focus:ring-2 focus:ring-green-400"
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
                  className="flex-1 border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper focus:outline-none focus:ring-2 focus:ring-green-400"
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

        {/* Visibility (public / private) */}
        {showIsActive && (
          <div>
            <label className="block text-xs text-fg-muted mb-2">{label("fieldPublicDisplay", "isActive")}</label>
            <RadioGroup
              value={form.is_active ? "public" : "private"}
              onChange={(v) => updateField("is_active", v === "public")}
              disabled={isActiveLocked}
              options={[
                { value: "public", label: labels?.fieldVisibilityPublic ?? "公開" },
                { value: "private", label: labels?.fieldVisibilityPrivate ?? "非公開" },
              ]}
            />
            {isActiveLocked && labels?.fieldVisibilityLockedNote ? (
              <p className="mt-1.5 text-xs text-fg-subtle">{labels.fieldVisibilityLockedNote}</p>
            ) : null}
          </div>
        )}
      </section>

      {/* ===== Section 2: Date & venue ===== */}
      <section className="grid grid-cols-1 gap-4 rounded-2xl bg-paper/60 p-5">
        <div className="text-sm font-semibold text-fg-strong">{sectionLabel("sectionDateLocation", "日時・会場")}</div>

        {/* Start date */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldStartDate", "startDate")}{mark(true)}</label>
          <input
            type="date"
            value={form.start_date}
            onChange={(e) => updateField("start_date", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* End date */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldEndDate", "endDate")}{mark(true)}</label>
          <input
            type="date"
            value={form.end_date}
            onChange={(e) => updateField("end_date", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Venue name */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldVenue", "location")}{mark(true)}</label>
          <input
            type="text"
            value={form.location_name}
            onChange={(e) => updateField("location_name", e.target.value)}
            placeholder={venuePlaceholder || undefined}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Address */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldAddress", "address")}{mark(true)}</label>
          <input
            type="text"
            value={form.location_address}
            onChange={(e) => updateField("location_address", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Venue website URL */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldVenueUrl", "locationUrl")}</label>
          <input
            type="url"
            value={(form as any).location_url ?? ""}
            onChange={(e) => updateField("location_url", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Business hours */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldBusinessHours", "hours")}</label>
          <input
            type="text"
            value={form.business_hours}
            onChange={(e) => updateField("business_hours", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>
      </section>

      {/* ===== Section 3: Organizer & format ===== */}
      <section className="grid grid-cols-1 gap-4 rounded-2xl bg-paper/60 p-5">
        <div className="text-sm font-semibold text-fg-strong">{sectionLabel("sectionOrganizer", "主催・開催形式")}</div>

        {/* Performer */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldPerformer", "performer")}</label>
          <input
            type="text"
            value={(form as any).performer ?? ""}
            onChange={(e) => updateField("performer", e.target.value)}
            placeholder="例: 李映萱、唐 顥芸"
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Organizer */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldOrganizer", "organizer")}{mark(true)}</label>
          <input
            type="text"
            value={(form as any).organizer ?? ""}
            onChange={(e) => updateField("organizer", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Organizer URL */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldOrganizerUrl", "organizerUrl")}</label>
          <input
            type="url"
            value={(form as any).organizer_url ?? ""}
            onChange={(e) => updateField("organizer_url", e.target.value)}
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Event Form (multi-checkbox) */}
        <div className="">
          <label className="block text-xs text-fg-muted mb-2">{label("fieldEventForm", "eventForm")}{mark(true)}</label>
          <div className="flex flex-wrap gap-2">
            {EVENT_FORMS.map((ef) => (
              <PillButton
                key={ef}
                onClick={() => {
                  const cur: string[] = (form as any).event_form ?? [];
                  updateField(
                    "event_form",
                    cur.includes(ef) ? cur.filter((x) => x !== ef) : [...cur, ef]
                  );
                }}
                active={((form as any).event_form ?? []).includes(ef)}
                tone="blue"
              >
                {tEventForm ? tEventForm(ef as any) : ef}
              </PillButton>
            ))}
          </div>
        </div>

        {/* Co-organizers */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldCoOrganizers", "coOrganizers")}</label>
          <input
            type="text"
            value={(form as any).co_organizers ?? ""}
            onChange={(e) => updateField("co_organizers", e.target.value)}
            placeholder="例: A機構, B機構"
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>

        {/* Sponsors */}
        <div>
          <label className="block text-xs text-fg-muted mb-1">{label("fieldSponsors", "sponsors")}</label>
          <input
            type="text"
            value={(form as any).sponsors ?? ""}
            onChange={(e) => updateField("sponsors", e.target.value)}
            placeholder="例: C企業, D企業"
            className="w-full border border-line-strong rounded-lg px-3 py-2 text-sm bg-paper"
          />
        </div>
      </section>

      {/* Parent event (admin only) */}
      {showParentEvent && (
        <section className="grid grid-cols-1 gap-4 border-t border-line pt-6">
          <div className="">
            <label className="block text-xs text-fg-muted mb-1">{t("parentEvent")}</label>
            <DesignSelect
              value={form.parent_event_id}
              onChange={(v) => updateField("parent_event_id", v)}
              options={[
                { value: "", label: t("noParent") },
                ...parentCandidates.map((e) => ({
                  value: e.id,
                  label: `${getEventName(e, locale)} (${e.start_date?.slice(0, 10) ?? "—"})`,
                })),
              ]}
            />
          </div>
        </section>
      )}
    </div>
  );
}

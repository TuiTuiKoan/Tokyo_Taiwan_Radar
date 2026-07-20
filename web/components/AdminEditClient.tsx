"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { type Event, type Locale } from "@/lib/types";
import Button from "@/components/Button";
import AdminEventForm, { type FormState } from "@/components/AdminEventForm";
import { saveAdminEditedEvent } from "@/app/actions/admin-events";

interface Props {
  event: Event;
  allEvents: Event[];
  locale: Locale;
}

export default function AdminEditClient({ event, allEvents, locale }: Props) {
  const t = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tEventForm = useTranslations("eventForm");
  const tIntake = useTranslations("eventIntake");
  const router = useRouter();

  const [form, setForm] = useState<FormState>({
    name_ja: event.name_ja ?? "",
    name_zh: event.name_zh ?? "",
    name_en: event.name_en ?? "",
    description_ja: event.description_ja ?? "",
    description_zh: event.description_zh ?? "",
    description_en: event.description_en ?? "",
    category: event.category ?? [],
    start_date: event.start_date?.slice(0, 10) ?? "",
    end_date: event.end_date?.slice(0, 10) ?? "",
    location_name: event.location_name ?? "",
    location_address: event.location_address ?? "",
    location_url: event.location_url ?? "",
    business_hours: event.business_hours ?? "",
    performer: (event as any).performer ?? "",
    organizer: (event as any).organizer ?? "",
    organizer_url: (event as any).organizer_url ?? "",
    event_form: (event as any).event_form ?? [],
    co_organizers: ((event as any).co_organizers ?? []).join(", "),
    sponsors: ((event as any).sponsors ?? []).join(", "),
    primary_language: (event as any).primary_language ?? "",
    has_japanese_support: (event as any).has_japanese_support ?? false,
    has_english_support: (event as any).has_english_support ?? false,
    has_chinese_support: (event as any).has_chinese_support ?? false,
    is_paid: event.is_paid ?? false,
    price_info: event.price_info ?? "",
    official_url: event.official_url ?? "",
    submission_url: event.submission_url ?? "",
    source_url: event.source_url,
    source_name: event.source_name,
    original_language: event.original_language,
    is_active: event.is_active,
    parent_event_id: event.parent_event_id ?? "",
    record_links: (event.record_links as { title: string; url: string }[]) ?? [],
  });
  const [paidChoice, setPaidChoice] = useState<"" | "free" | "paid">(
    event.is_paid === true ? "paid" : event.is_paid === false ? "free" : ""
  );
  const [saving, setSaving] = useState(false);
  const busyStartedAtRef = useRef<number | null>(null);
  const [busyElapsedMs, setBusyElapsedMs] = useState(0);
  const [, startTransition] = useTransition();

  useEffect(() => {
    if (!saving) {
      busyStartedAtRef.current = null;
      setBusyElapsedMs(0);
      return;
    }

    if (!busyStartedAtRef.current) {
      busyStartedAtRef.current = Date.now();
    }

    const timer = window.setInterval(() => {
      const startedAt = busyStartedAtRef.current ?? Date.now();
      setBusyElapsedMs(Date.now() - startedAt);
    }, 1000);

    return () => window.clearInterval(timer);
  }, [saving]);

  function updateField(key: string, value: any) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handlePaidChoiceChange(choice: "free" | "paid") {
    setPaidChoice(choice);
    updateField("is_paid", choice === "paid");
  }

  function toggleCategory(cat: string) {
    setForm((prev) => ({
      ...prev,
      category: prev.category.includes(cat)
        ? prev.category.filter((c) => c !== cat)
        : [...prev.category, cat],
    }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      const result = await saveAdminEditedEvent(event.id, form);
      if (!result.ok) {
        if (result.error === "unauthenticated") {
          alert("Session 已過期，請重新登入後再試。");
        } else if (result.error === "eventNotFound" || result.error.includes("exact_id_mismatch")) {
          alert("儲存未生效（session 可能已過期），請重新整理頁面後再試。");
        } else {
          alert(`Save failed: ${result.error}`);
        }
        return;
      }
      router.push(`/${locale}/admin`);
    } catch (err) {
      console.error("Unexpected save error:", err);
      alert(`儲存失敗：${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    router.push(`/${locale}/admin`);
  }

  // Plain string labels only — never pass a translation function across the
  // server/client boundary (RSC guard).
  const fieldLabels: Record<string, string> = {
    langJa: tIntake("langJa"),
    langZh: tIntake("langZh"),
    langEn: tIntake("langEn"),
    fieldEventNameLang: tIntake("fieldEventNameLang"),
    fieldEventDescLang: tIntake("fieldEventDescLang"),
    fieldEventName: tIntake("fieldEventName"),
    fieldEventDesc: tIntake("fieldEventDesc"),
    fieldStartDate: tIntake("fieldStartDate"),
    fieldEndDate: tIntake("fieldEndDate"),
    fieldVenue: tIntake("fieldVenue"),
    fieldAddress: tIntake("fieldAddress"),
    fieldVenueUrl: tIntake("fieldVenueUrl"),
    fieldBusinessHours: tIntake("fieldBusinessHours"),
    fieldPerformer: tIntake("fieldPerformer"),
    fieldOrganizer: tIntake("fieldOrganizer"),
    fieldOrganizerUrl: tIntake("fieldOrganizerUrl"),
    fieldEventForm: tIntake("fieldEventForm"),
    fieldCoOrganizers: tIntake("fieldCoOrganizers"),
    fieldSponsors: tIntake("fieldSponsors"),
    primaryLanguageLabel: tIntake("primaryLanguageLabel"),
    fieldJaSupport: tIntake("fieldJaSupport"),
    fieldEnSupport: tIntake("fieldEnSupport"),
    fieldZhSupport: tIntake("fieldZhSupport"),
    fieldPromoUrl: tIntake("fieldPromoUrl"),
    fieldSubmissionUrl: tIntake("fieldSubmissionUrl"),
    fieldSourceUrl: tIntake("fieldSourceUrl"),
    fieldPaidLabel: tIntake("fieldPaidLabel"),
    paidFree: tIntake("paidFree"),
    paidPaid: tIntake("paidPaid"),
    fieldPriceInfo: tIntake("fieldPriceInfo"),
    fieldCategory: tIntake("fieldCategory"),
    fieldRecordLinks: tIntake("fieldRecordLinks"),
    sectionBasicInfo: tIntake("sectionBasicInfo"),
    sectionDateLocation: tIntake("sectionDateLocation"),
    sectionOrganizer: tIntake("sectionOrganizer"),
    fieldPublicDisplay: tIntake("fieldPublicDisplay"),
    fieldVisibilityPublic: tIntake("fieldVisibilityPublic"),
    fieldVisibilityPrivate: tIntake("fieldVisibilityPrivate"),
    fieldVisibilityLockedNote: tIntake("fieldVisibilityLockedNote"),
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <Button type="button" variant="ghost" onClick={handleCancel} className="-ml-4 shrink-0 text-sm font-medium relative z-10">
          ← {t("back")}
        </Button>
        <h1 className="text-2xl font-bold text-fg-strong truncate">{t("edit")}</h1>
      </div>
      <div className="space-y-6">
        <AdminEventForm
          form={form}
          t={t}
          tCat={tCat}
          tEventForm={tEventForm}
          updateField={updateField}
          toggleCategory={toggleCategory}
          events={allEvents}
          editingId={event.id}
          locale={locale}
          fieldLabels={fieldLabels}
          nameDescriptionLangs={["ja", "zh", "en"]}
          showSourceUrl={true}
          showIsActive={true}
          isActiveLocked={false}
          showParentEvent={true}
          parentEventsStatus="loaded"
          requiredMarkers
          paidMode="choice"
          paidChoice={paidChoice}
          onPaidChoiceChange={handlePaidChoiceChange}
          hideMixedLanguage
        />
        <div className="flex gap-3 pt-4 border-t border-line">
          <Button type="button" loading={saving} onClick={handleSave} className="shadow-sm">
            {t("save")}
          </Button>
          <Button type="button" variant="secondary" onClick={handleCancel} className="shadow-sm">
            {t("cancel")}
          </Button>
        </div>
      </div>
    </div>
  );
}

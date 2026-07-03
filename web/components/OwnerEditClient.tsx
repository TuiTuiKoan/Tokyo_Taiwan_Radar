"use client";

import { useState, useRef, useTransition } from "react";
import { useTranslations } from "next-intl";
import { type Event, type Locale } from "@/lib/types";
import { useRouter } from "next/navigation";
import AdminEventForm, { type FormState } from "@/components/AdminEventForm";
import Button from "@/components/Button";
import { updateOwnerEvent, updateOwnerDraft } from "@/app/actions/owner-events";
import {
  TRANSLATION_LOCK_FIELDS,
  getActionErrorMessage,
} from "@/lib/eventIntakeClient";
import {
  collectMissingRequiredFields,
  buildMissingFieldsMessage,
} from "@/lib/eventIntakeValidation";

interface Props {
  event: Event;
  locale: Locale;
}

export default function OwnerEditClient({ event, locale }: Props) {
  const t = useTranslations("account");
  const tAdmin = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tEventForm = useTranslations("eventForm");
  const tIntake = useTranslations("eventIntake");
  const router = useRouter();

  const isPublished = event.is_active === true;

  const [form, setForm] = useState<FormState>({
    name_ja: event.name_ja || "",
    name_zh: event.name_zh || "",
    name_en: event.name_en || "",
    description_ja: event.description_ja || "",
    description_zh: event.description_zh || "",
    description_en: event.description_en || "",
    category: event.category || [],
    start_date: event.start_date ? event.start_date.substring(0, 10) : "",
    end_date: event.end_date ? event.end_date.substring(0, 10) : "",
    location_name: event.location_name || "",
    location_address: event.location_address || "",
    location_url: event.location_url || "",
    business_hours: event.business_hours || "",
    performer: event.performer || "",
    organizer: event.organizer || "",
    organizer_url: event.organizer_url || "",
    event_form: event.event_form || [],
    co_organizers: event.co_organizers || null,
    sponsors: event.sponsors || null,
    primary_language: event.primary_language || "",
    has_japanese_support: event.has_japanese_support || false,
    has_english_support: event.has_english_support || false,
    has_chinese_support: event.has_chinese_support || false,
    is_paid: event.is_paid || false,
    price_info: event.price_info || "",
    official_url: event.official_url || "",
    submission_url: event.submission_url || "",
    source_url: event.source_url || "",
    source_name: event.source_name || "user_submission",
    original_language: event.original_language || "zh",
    is_active: event.is_active || false,
    parent_event_id: event.parent_event_id || "",
    record_links: event.record_links as any || [],
  });

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [paidChoice, setPaidChoice] = useState<"" | "free" | "paid">(
    event.is_paid === true ? "paid" : event.is_paid === false ? "free" : ""
  );

  const actionLockRef = useRef(false);
  const translationEditedFieldsRef = useRef<Set<string>>(new Set());
  const [, startTransition] = useTransition();

  function updateField(k: string, v: unknown) {
    if ((TRANSLATION_LOCK_FIELDS as readonly string[]).includes(k)) {
      translationEditedFieldsRef.current.add(k);
    }
    setForm((prev) => ({ ...prev, [k]: v }) as FormState);
  }

  function handlePaidChoiceChange(choice: "free" | "paid") {
    setPaidChoice(choice);
    setForm((prev) => ({ ...prev, is_paid: choice === "paid" }));
  }

  function toggleCategory(cat: string) {
    setForm((prev) => {
      const arr = prev.category ? [...prev.category] : [];
      const idx = arr.indexOf(cat);
      if (idx >= 0) arr.splice(idx, 1);
      else arr.push(cat);
      return { ...prev, category: arr };
    });
  }

  async function handleSaveChanges() {
    // Publish-state-preserving save:
    //   draft     -> updateOwnerDraft  (stays is_active=false / pending)
    //   published -> updateOwnerEvent  (stays is_active=true; never deactivate)
    if (actionLockRef.current) return;
    setSaveError(null);
    if (isPublished) {
      const missing = collectMissingRequiredFields(form, {
        requirePrimaryContent: true,
        primaryLang: form.primary_language,
        paidChoiceMade: paidChoice !== "",
      });
      if (missing.length > 0) {
        setSaveError(buildMissingFieldsMessage(missing, tIntake));
        return;
      }
    }
    actionLockRef.current = true;
    setSaving(true);
    try {
      const res = isPublished
        ? await updateOwnerEvent(event.id, form, {
            lockedTranslationFields: Array.from(translationEditedFieldsRef.current),
            paidChoiceMade: paidChoice !== "",
          })
        : await updateOwnerDraft(event.id, form);

      if (!res.ok) {
        if (res.error === "requiredFieldsMissing") {
          setSaveError(tIntake("requiredFieldsMissing"));
        } else {
          setSaveError(t(res.error) || t("saveFailed"));
        }
        return;
      }

      alert(t("saveSuccess"));
      startTransition(() => {
        router.push(`/${locale}/account?tab=myEvents`);
      });
    } catch (e: unknown) {
      alert(getActionErrorMessage(e, t("saveFailed")));
    } finally {
      setSaving(false);
      actionLockRef.current = false;
    }
  }

  async function handlePublishDraft() {
    // Draft-only "公開發佈": flip to active via the owner publish gate.
    if (actionLockRef.current) return;
    setSaveError(null);
    const missing = collectMissingRequiredFields(form, {
      requirePrimaryContent: true,
      primaryLang: form.primary_language,
      paidChoiceMade: paidChoice !== "",
    });
    if (missing.length > 0) {
      setSaveError(buildMissingFieldsMessage(missing, tIntake));
      return;
    }
    actionLockRef.current = true;
    setSaving(true);
    try {
      const res = await updateOwnerEvent(event.id, form, {
        lockedTranslationFields: Array.from(translationEditedFieldsRef.current),
        paidChoiceMade: paidChoice !== "",
      });

      if (!res.ok) {
        if (res.error === "requiredFieldsMissing") {
          setSaveError(tIntake("requiredFieldsMissing"));
        } else {
          setSaveError(t(res.error) || t("saveFailed"));
        }
        return;
      }

      alert(t("saveSuccess"));
      startTransition(() => {
        router.push(`/${locale}/account?tab=myEvents`);
      });
    } catch (e: unknown) {
      alert(getActionErrorMessage(e, t("saveFailed")));
    } finally {
      setSaving(false);
      actionLockRef.current = false;
    }
  }

  function handleCancel() {
    router.push(`/${locale}/account?tab=myEvents`);
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
      {/* Navigation and Header */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={handleCancel}
          className="text-sm font-medium text-fg-muted hover:text-fg-strong transition"
        >
          ← {t("back") || "返回"}
        </button>
        <h1 className="text-2xl font-bold text-fg-strong">
          {t("editingEvent") || t("editEvent") || "編輯活動"}
        </h1>
        <div className="w-10" />
      </div>

      {/* Floating Event Form Fields */}
      <div className="space-y-6">
        <AdminEventForm
          form={form}
          t={tAdmin}
          tCat={tCat}
          tEventForm={tEventForm}
          updateField={updateField}
          toggleCategory={toggleCategory}
          events={[]}
          editingId={event.id}
          locale={locale}
          fieldLabels={fieldLabels}
          nameDescriptionLangs={["ja", "zh", "en"]}
          showParentEvent={false}
          showIsActive={false}
          requiredMarkers
          paidMode="choice"
          paidChoice={paidChoice}
          onPaidChoiceChange={handlePaidChoiceChange}
          hideMixedLanguage
          venuePlaceholder={tIntake("fieldVenuePlaceholder")}
        />
      </div>

      {saveError && (
        <p
          className="text-sm font-semibold text-red-500 whitespace-pre-line"
          aria-live="assertive"
        >
          {saveError}
        </p>
      )}

      {/* Floating Save Actions Section */}
      <div className="flex items-center gap-3 pt-4 border-t border-line">
        <Button type="button" variant="secondary" onClick={handleCancel} className="shadow-sm">
          {tIntake("cancel")}
        </Button>
        {isPublished ? (
          <Button
            type="button"
            onClick={handleSaveChanges}
            disabled={saving}
            loading={saving}
            className="min-w-[11rem] shadow-sm"
          >
            {tIntake("saveChanges")}
          </Button>
        ) : (
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={handleSaveChanges}
              disabled={saving}
              loading={saving}
              className="min-w-[9rem] shadow-sm"
            >
              {tIntake("saveDraft")}
            </Button>
            <Button
              type="button"
              onClick={handlePublishDraft}
              disabled={saving}
              loading={saving}
              className="min-w-[9rem] shadow-sm"
            >
              {tIntake("publish")}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

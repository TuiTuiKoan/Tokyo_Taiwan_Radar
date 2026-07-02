"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import { flushSync } from "react-dom";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { type Event, type Locale } from "@/lib/types";
import Button from "@/components/Button";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";
import EventIntakeStepper from "@/components/EventIntakeStepper";
import { createOwnerDraft, updateOwnerDraft, updateOwnerEvent } from "@/app/actions/owner-events";
import {
  createDraftEvent,
  updateAdminEvent,
  publishAdminWizardEvent,
} from "@/app/actions/admin-events";
import { collectMissingRequiredFields, buildMissingFieldsMessage } from "@/lib/eventIntakeValidation";
import {
  ANNOTATE_LOCATION_FIELDS,
  TRANSLATION_LOCK_FIELDS,
  getActionErrorMessage,
  pickReturnedFormFields,
  readJsonResponse,
} from "@/lib/eventIntakeClient";

type ActionResult<T> = { ok: true; data: T } | { ok: false; error: string };
type WizardMode = "choice" | "manual" | "image";
type PaidChoice = "" | "free" | "paid";

interface Props {
  context: "owner" | "admin";
  locale: Locale;
  allEvents?: Event[];
}

const CONTENT_LANGS: Locale[] = ["ja", "zh", "en"];

export default function EventIntakeWizard({ context, locale, allEvents }: Props) {
  const tIntake = useTranslations("eventIntake");
  const tAdmin = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tEventForm = useTranslations("eventForm");
  const router = useRouter();

  const isAdmin = context === "admin";

  const [mode, setMode] = useState<WizardMode>("choice");
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<FormState>(() => ({ ...EMPTY_FORM, primary_language: "ja" }));
  const [paidChoice, setPaidChoice] = useState<PaidChoice>("");
  const [savedEventId, setSavedEventId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [annotating, setAnnotating] = useState(false);
  const [busyElapsedMs, setBusyElapsedMs] = useState(0);
  const [actionError, setActionError] = useState<string | null>(null);
  const [posterPreview, setPosterPreview] = useState<string | null>(null);
  const [posterDataUrl, setPosterDataUrl] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  const posterFileRef = useRef<HTMLInputElement>(null);
  const busyStartedAtRef = useRef<number | null>(null);
  const actionLockRef = useRef(false);
  const autoFilledFieldsRef = useRef<Set<string>>(new Set());
  const manualEditedFieldsRef = useRef<Set<string>>(new Set());
  const translationEditedFieldsRef = useRef<Set<string>>(new Set());

  const cfg: {
    createDraft: (form: FormState) => Promise<ActionResult<Event>>;
    updateDraft: (id: string, form: FormState) => Promise<ActionResult<Event>>;
    publish: (
      id: string,
      form: FormState,
      opt: { lockedTranslationFields?: string[]; paidChoiceMade?: boolean },
    ) => Promise<ActionResult<Event>>;
    extractEndpoint: string;
    annotateEndpoint: string;
    returnPath: string;
    showParentEvent: boolean;
  } = isAdmin
    ? {
        createDraft: (f) => createDraftEvent(f),
        updateDraft: (id, f) => updateAdminEvent(id, f, { isActive: false }),
        publish: (id, f, opt) => publishAdminWizardEvent(id, f, opt),
        extractEndpoint: "/api/admin/extract-from-image",
        annotateEndpoint: "/api/admin/annotate-event",
        returnPath: `/${locale}/admin`,
        showParentEvent: true,
      }
    : {
        createDraft: (f) => createOwnerDraft(f),
        updateDraft: (id, f) => updateOwnerDraft(id, f),
        publish: (id, f, opt) => updateOwnerEvent(id, f, opt),
        extractEndpoint: "/api/account/extract-from-image",
        annotateEndpoint: "/api/account/annotate-event",
        returnPath: `/${locale}/account?tab=myEvents`,
        showParentEvent: false,
      };

  useEffect(() => {
    if (!saving && !extracting && !annotating) {
      busyStartedAtRef.current = null;
      return;
    }
    busyStartedAtRef.current = Date.now();
    const timer = window.setInterval(() => {
      const startedAt = busyStartedAtRef.current ?? Date.now();
      setBusyElapsedMs(Date.now() - startedAt);
    }, 1000);
    return () => {
      window.clearInterval(timer);
      setBusyElapsedMs(0);
    };
  }, [saving, extracting, annotating]);

  function isFormFieldKey(key: string): key is keyof FormState {
    return key in EMPTY_FORM;
  }
  function isAnnotateLocationField(
    key: string,
  ): key is (typeof ANNOTATE_LOCATION_FIELDS)[number] {
    return ANNOTATE_LOCATION_FIELDS.includes(key as (typeof ANNOTATE_LOCATION_FIELDS)[number]);
  }
  function isTranslationField(key: string): boolean {
    return (TRANSLATION_LOCK_FIELDS as readonly string[]).includes(key);
  }

  function updateField(k: string, v: unknown) {
    if (!isFormFieldKey(k)) return;
    if (isAnnotateLocationField(k)) manualEditedFieldsRef.current.add(k);
    if (isTranslationField(k)) translationEditedFieldsRef.current.add(k);
    setForm((prev) => ({ ...prev, [k]: v as FormState[typeof k] }));
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

  function handlePaidChoiceChange(choice: "free" | "paid") {
    setPaidChoice(choice);
    setForm((prev) => ({ ...prev, is_paid: choice === "paid" }));
  }

  // OCR / annotate may report is_paid. true -> "paid"; false stays unstated ("")
  // so the publish gate keeps requiring an explicit choice.
  function syncPaidChoiceFromFields(fields: Record<string, unknown>) {
    if (fields.is_paid === true) {
      setPaidChoice("paid");
      setForm((prev) => ({ ...prev, is_paid: true }));
    }
  }

  function applyReturnedFields(fields: Record<string, unknown>) {
    // Phase H client-side merge guard: never re-apply a locked translation field.
    const ignore = Array.from(translationEditedFieldsRef.current);
    const next = pickReturnedFormFields(EMPTY_FORM, fields, ignore);
    if (Object.keys(next).length > 0) setForm((prev) => ({ ...prev, ...next }));
    syncPaidChoiceFromFields(fields);
  }

  function applyOcrFields(fields: Record<string, unknown>) {
    const next = pickReturnedFormFields(EMPTY_FORM, fields);
    for (const key of Object.keys(next)) {
      if (!isAnnotateLocationField(key)) continue;
      autoFilledFieldsRef.current.add(key);
      manualEditedFieldsRef.current.delete(key);
    }
    if (Object.keys(next).length > 0) setForm((prev) => ({ ...prev, ...next }));
    syncPaidChoiceFromFields(fields);
  }

  function getLockedLocationFields() {
    return ANNOTATE_LOCATION_FIELDS.filter((f) => manualEditedFieldsRef.current.has(f));
  }
  function getOverwriteableLocationFields() {
    return ANNOTATE_LOCATION_FIELDS.filter(
      (f) => autoFilledFieldsRef.current.has(f) && !manualEditedFieldsRef.current.has(f),
    );
  }

  // Manual step1 primary-language name/description are native human input. Lock
  // them as provenance so the first annotate run cannot clobber them. Empty or
  // mixed primary language contributes nothing (avoids locking blanks).
  function collectPrimaryProvenanceFields(): string[] {
    const lang = form.primary_language;
    if (!CONTENT_LANGS.includes(lang as Locale)) return [];
    const out: string[] = [];
    const f = form as unknown as Record<string, unknown>;
    for (const base of ["name", "description"]) {
      const key = `${base}_${lang}`;
      const val = f[key];
      if (
        typeof val === "string" &&
        val.trim() !== "" &&
        (TRANSLATION_LOCK_FIELDS as readonly string[]).includes(key)
      ) {
        out.push(key);
      }
    }
    return out;
  }

  function mergeLockedTranslations(opts: { includePrimaryProvenance: boolean }): string[] {
    const edited = Array.from(translationEditedFieldsRef.current);
    if (!opts.includePrimaryProvenance) return edited;
    return Array.from(new Set([...edited, ...collectPrimaryProvenanceFields()]));
  }

  const primaryLang: Locale = CONTENT_LANGS.includes(form.primary_language as Locale)
    ? (form.primary_language as Locale)
    : "ja";

  function beginBusy(kind: "saving" | "extracting" | "annotating") {
    actionLockRef.current = true;
    busyStartedAtRef.current = Date.now();
    flushSync(() => {
      setBusyElapsedMs(0);
      setActionError(null);
      if (kind === "saving") setSaving(true);
      else if (kind === "extracting") setExtracting(true);
      else setAnnotating(true);
    });
  }
  function finishBusy(kind: "saving" | "extracting" | "annotating") {
    actionLockRef.current = false;
    if (kind === "saving") setSaving(false);
    else if (kind === "extracting") setExtracting(false);
    else setAnnotating(false);
  }

  function describePreflight(missing: string[]): string {
    return buildMissingFieldsMessage(missing, tIntake);
  }
  function describeServerError(error: string): string {
    if (error === "translationLockFailed") return tIntake("translationLockFailed");
    if (error === "requiredFieldsMissing") return tIntake("requiredFieldsMissing");
    return error;
  }

  function handleChooseManual() {
    setActionError(null);
    setMode("manual");
    setStep(1);
  }
  function handleChooseImage() {
    setActionError(null);
    setMode("image");
    setStep(1);
  }

  function handleSelectImage() {
    posterFileRef.current?.click();
  }
  function handlePosterChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setPosterPreview(dataUrl);
      setPosterDataUrl(dataUrl);
    };
    reader.onerror = () => setActionError(tIntake("requiredFieldsMissing"));
    reader.readAsDataURL(file);
  }

  async function handleExtractImage() {
    if (actionLockRef.current || !posterDataUrl) return;
    beginBusy("extracting");
    try {
      const res = await fetch(cfg.extractEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: posterDataUrl }),
      });
      const data = await readJsonResponse(res);
      if (!res.ok) {
        const errKey = typeof data.error === "string" ? data.error : null;
        throw new Error(errKey ? describeServerError(errKey) : tIntake("busyExtracting"));
      }
      applyOcrFields((data.fields ?? {}) as Record<string, unknown>);
      setStep(2);
    } catch (error: unknown) {
      setActionError(getActionErrorMessage(error, tIntake("requiredFieldsMissing")));
    } finally {
      finishBusy("extracting");
    }
  }

  // Shared by manual step1 and image step2.
  async function handleSaveAndTranslate() {
    if (actionLockRef.current) return;
    const missing = collectMissingRequiredFields(form, {
      requirePrimaryContent: true,
      primaryLang: form.primary_language,
      paidChoiceMade: paidChoice !== "",
    });
    if (missing.length > 0) {
      setActionError(describePreflight(missing));
      return;
    }
    beginBusy("annotating");
    let eventId = savedEventId;
    try {
      const saveRes = eventId ? await cfg.updateDraft(eventId, form) : await cfg.createDraft(form);
      if (!saveRes.ok) throw new Error(describeServerError(saveRes.error));
      if (!eventId) {
        eventId = saveRes.data.id;
        setSavedEventId(eventId);
      }
      const res = await fetch(cfg.annotateEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          eventId,
          lockedFields: getLockedLocationFields(),
          overwriteableFields: getOverwriteableLocationFields(),
          lockedTranslationFields: mergeLockedTranslations({
            includePrimaryProvenance: mode === "manual",
          }),
        }),
        signal: AbortSignal.timeout(58000),
      });
      const data = await readJsonResponse(res);
      if (!res.ok) {
        const errKey = typeof data.error === "string" ? data.error : null;
        const detail = typeof data.detail === "string" ? data.detail : null;
        const base = errKey ? describeServerError(errKey) : tIntake("requiredFieldsMissing");
        throw new Error(detail ? `${base}（${detail}）` : base);
      }
      applyReturnedFields((data.fields ?? {}) as Record<string, unknown>);
      setStep(mode === "manual" ? 2 : 3);
    } catch (error: unknown) {
      setActionError(getActionErrorMessage(error, tIntake("requiredFieldsMissing")));
    } finally {
      finishBusy("annotating");
    }
  }

  // Shared by manual step2 and image step3.
  async function handlePublish() {
    if (actionLockRef.current) return;
    const missing = collectMissingRequiredFields(form, { paidChoiceMade: paidChoice !== "" });
    if (missing.length > 0) {
      setActionError(describePreflight(missing));
      return;
    }
    const eventId = savedEventId;
    if (!eventId) {
      setActionError(tIntake("requiredFieldsMissing"));
      return;
    }
    beginBusy("saving");
    try {
      const res = await cfg.publish(eventId, form, {
        lockedTranslationFields: mergeLockedTranslations({
          includePrimaryProvenance: mode === "manual",
        }),
        paidChoiceMade: paidChoice !== "",
      });
      if (!res.ok) {
        setActionError(describeServerError(res.error));
        return;
      }
      startTransition(() => router.push(cfg.returnPath));
    } catch (error: unknown) {
      setActionError(getActionErrorMessage(error, tIntake("requiredFieldsMissing")));
    } finally {
      finishBusy("saving");
    }
  }

  async function handleCancel() {
    const noSave =
      mode === "choice" ||
      (mode === "manual" && step === 1) ||
      (mode === "image" && step === 1);
    if (noSave) {
      router.push(cfg.returnPath);
      return;
    }
    if (actionLockRef.current) return;
    beginBusy("saving");
    try {
      const res = savedEventId
        ? await cfg.updateDraft(savedEventId, form)
        : await cfg.createDraft(form);
      if (!res.ok) {
        setActionError(describeServerError(res.error));
        return;
      }
      startTransition(() => router.push(cfg.returnPath));
    } catch (error: unknown) {
      setActionError(getActionErrorMessage(error, tIntake("requiredFieldsMissing")));
    } finally {
      finishBusy("saving");
    }
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

  const stepDesc =
    mode === "manual"
      ? step === 1
        ? tIntake("manualStep1Desc")
        : tIntake("manualStep2Desc")
      : step === 1
        ? tIntake("imageStep1Desc")
        : step === 2
          ? tIntake("imageStep2Desc")
          : tIntake("imageStep3Desc");

  const totalSteps = mode === "manual" ? 2 : 3;
  const nameDescriptionLangs: Locale[] =
    mode === "manual" && step === 1 ? [primaryLang] : CONTENT_LANGS;
  const showForm = !(mode === "image" && step === 1);
  const busy = saving || extracting || annotating;
  const elapsedSec = Math.floor(busyElapsedMs / 1000);

  const renderPrimaryButton = () => {
    if (mode === "image" && step === 1) {
      return (
        <Button
          type="button"
          onClick={handleExtractImage}
          disabled={busy || !posterDataUrl}
          loading={extracting}
          className="min-w-[11rem] shadow-sm"
        >
          {tIntake("extractImage")}
        </Button>
      );
    }
    const isPublishStep = (mode === "manual" && step === 2) || (mode === "image" && step === 3);
    if (isPublishStep) {
      return (
        <Button
          type="button"
          onClick={handlePublish}
          disabled={busy}
          loading={saving}
          className="min-w-[11rem] shadow-sm"
        >
          {tIntake("publish")}
        </Button>
      );
    }
    return (
      <Button
        type="button"
        onClick={handleSaveAndTranslate}
        disabled={busy}
        loading={annotating}
        className="min-w-[11rem] shadow-sm"
      >
        {tIntake("saveAndTranslate")}
      </Button>
    );
  };

  if (mode === "choice") {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-fg-strong">{tIntake("chooseTitle")}</h1>
        <div className="grid gap-4 sm:grid-cols-2">
          <Button
            type="button"
            onClick={handleChooseManual}
            className="h-24 text-base shadow-sm"
          >
            {tIntake("chooseManual")}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={handleChooseImage}
            className="h-24 text-base shadow-sm"
          >
            {tIntake("chooseImage")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold text-fg-strong">{tIntake("chooseTitle")}</h1>
      <EventIntakeStepper
        steps={totalSteps}
        current={step}
        labels={
          mode === "manual"
            ? [tIntake("stepBasicInfo"), tIntake("stepReview")]
            : [tIntake("stepImageUpload"), tIntake("stepImageReview"), tIntake("stepReview")]
        }
      />
      <p className="text-sm text-fg-muted">{stepDesc}</p>

      {mode === "image" && step === 1 && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={handleSelectImage}
              disabled={extracting}
              className="min-w-[10rem] shadow-sm"
            >
              {tIntake("selectImage")}
            </Button>
            <input
              type="file"
              ref={posterFileRef}
              className="hidden"
              accept="image/*"
              onChange={handlePosterChange}
            />
          </div>
        </div>
      )}

      {posterPreview && (
        <div className="-mx-6 sm:mx-0 overflow-hidden sm:rounded-xl border border-line bg-surface">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={posterPreview} alt="Poster preview" className="w-full max-h-96 object-contain" />
        </div>
      )}

      {busy && (
        <div
          aria-live="polite"
          className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm font-semibold text-amber-700 dark:text-amber-300"
        >
          {extracting
            ? `${tIntake("busyExtracting")} ${elapsedSec}s`
            : `${tIntake("busyTranslating")} ${elapsedSec}s`}
        </div>
      )}

      {showForm && (
        <div className="space-y-6">
          <AdminEventForm
            form={form}
            t={tAdmin}
            tCat={tCat}
            tEventForm={tEventForm}
            updateField={updateField}
            toggleCategory={toggleCategory}
            events={isAdmin ? allEvents ?? [] : []}
            editingId={null}
            locale={locale}
            fieldLabels={fieldLabels}
            nameDescriptionLangs={nameDescriptionLangs}
            showParentEvent={cfg.showParentEvent}
            showIsActive={false}
            showSourceUrl={false}
            requiredMarkers
            paidMode="choice"
            paidChoice={paidChoice}
            onPaidChoiceChange={handlePaidChoiceChange}
            hideMixedLanguage
            venuePlaceholder={tIntake("fieldVenuePlaceholder")}
          />
        </div>
      )}

      {actionError && (
        <p
          className="text-sm font-semibold text-red-500 whitespace-pre-line"
          aria-live="assertive"
        >
          {actionError}
        </p>
      )}

      <div className="flex items-center gap-3 pt-4 border-t border-line">
        <Button
          type="button"
          variant="secondary"
          onClick={handleCancel}
          disabled={busy}
          className="shadow-sm"
        >
          {tIntake("cancel")}
        </Button>
        {renderPrimaryButton()}
      </div>
    </div>
  );
}

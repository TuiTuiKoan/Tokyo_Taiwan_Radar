"use client";

import { useEffect, useState, useRef, useTransition } from "react";
import { flushSync } from "react-dom";
import { useTranslations } from "next-intl";
import { type Event, type Locale } from "@/lib/types";
import { useRouter } from "next/navigation";
import Button from "@/components/Button";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";
import {
  createDraftEvent,
  createEventNoAnnotate,
  updateAdminEvent,
} from "@/app/actions/admin-events";
import {
  ANNOTATE_LOCATION_FIELDS,
  getActionErrorMessage,
  pickReturnedFormFields,
  readJsonResponse,
} from "@/lib/eventIntakeClient";

interface Props {
  locale: Locale;
  allEvents: Event[];
}

export default function AdminCreateClient({ locale, allEvents }: Props) {
  const t = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tEventForm = useTranslations("eventForm");
  const router = useRouter();

  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [posterPreview, setPosterPreview] = useState<string | null>(null);
  const [annotating, setAnnotating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [savedEventId, setSavedEventId] = useState<string | null>(null);
  const [ocrFilled, setOcrFilled] = useState(false);
  const [annotationDone, setAnnotationDone] = useState(false);

  const posterFileRef = useRef<HTMLInputElement>(null);
  const busyStartedAtRef = useRef<number | null>(null);
  const actionLockRef = useRef(false);
  const autoFilledFieldsRef = useRef<Set<string>>(new Set());
  const manualEditedFieldsRef = useRef<Set<string>>(new Set());
  const [busyElapsedMs, setBusyElapsedMs] = useState(0);
  const [, startTransition] = useTransition();

  function isFormFieldKey(key: string): key is keyof FormState {
    return key in EMPTY_FORM;
  }

  function isAnnotateLocationField(
    key: string,
  ): key is (typeof ANNOTATE_LOCATION_FIELDS)[number] {
    return ANNOTATE_LOCATION_FIELDS.includes(key as (typeof ANNOTATE_LOCATION_FIELDS)[number]);
  }

  useEffect(() => {
    if (!saving && !extracting && !annotating) {
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
  }, [saving, extracting, annotating]);

  function updateField(k: string, v: unknown) {
    if (!isFormFieldKey(k)) return;

    if (isAnnotateLocationField(k)) {
      manualEditedFieldsRef.current.add(k);
    }

    setForm((prev) => ({ ...prev, [k]: v as FormState[typeof k] }));
  }

  function applyReturnedFields(fields: Record<string, unknown>) {
    const nextFields = pickReturnedFormFields(EMPTY_FORM, fields);

    if (Object.keys(nextFields).length === 0) return;
    setForm((prev) => ({ ...prev, ...nextFields }));
  }

  function applyOcrFields(fields: Record<string, unknown>) {
    const nextFields = pickReturnedFormFields(EMPTY_FORM, fields);

    if (Object.keys(nextFields).length === 0) return;

    for (const key of Object.keys(nextFields)) {
      if (!isAnnotateLocationField(key)) continue;
      autoFilledFieldsRef.current.add(key);
      manualEditedFieldsRef.current.delete(key);
    }

    setForm((prev) => ({ ...prev, ...nextFields }));
  }

  function getLockedLocationFields() {
    return ANNOTATE_LOCATION_FIELDS.filter((field) => manualEditedFieldsRef.current.has(field));
  }

  function getOverwriteableLocationFields() {
    return ANNOTATE_LOCATION_FIELDS.filter(
      (field) =>
        autoFilledFieldsRef.current.has(field) &&
        !manualEditedFieldsRef.current.has(field),
    );
  }

  function beginPrimaryAction(mode: "save" | "annotate") {
    actionLockRef.current = true;
    busyStartedAtRef.current = Date.now();

    flushSync(() => {
      setBusyElapsedMs(0);
      setActionError(null);
      setAnnotationDone(false);
      if (mode === "annotate") {
        setAnnotating(true);
      } else {
        setSaving(true);
      }
    });
  }

  function finishPrimaryAction(mode: "save" | "annotate") {
    actionLockRef.current = false;
    if (mode === "annotate") {
      setAnnotating(false);
      return;
    }
    setSaving(false);
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

  async function handleImageExtract(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    busyStartedAtRef.current = Date.now();
    setBusyElapsedMs(0);
    setExtracting(true);
    setExtractError(null);

    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = reader.result as string;
      setPosterPreview(dataUrl);

      try {
        const res = await fetch("/api/admin/extract-from-image", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: dataUrl }),
        });
        const data = await readJsonResponse(res);
        if (!res.ok) {
          const errorKey = typeof data.error === "string" ? data.error : null;
          throw new Error(errorKey ? t(errorKey) : "Extraction failed");
        }

        applyOcrFields((data.fields ?? {}) as Record<string, unknown>);

        setOcrFilled(true);
        setAnnotationDone(false);
      } catch (error: unknown) {
        setExtractError(getActionErrorMessage(error, "Failed to extract"));
      } finally {
        setExtracting(false);
      }
    };
    reader.onerror = () => {
      setExtractError("Failed to read file");
      setExtracting(false);
    };
    reader.readAsDataURL(file);
  }

  async function handleAIAnnotate() {
    if (actionLockRef.current) return;
    beginPrimaryAction("annotate");
    let eventId = savedEventId;

    try {
      if (!eventId) {
        const res = await createDraftEvent(form);
        if (!res.ok) {
          throw new Error(res.error ? t(res.error) : "Draft save failed");
        }
        eventId = res.data.id;
        setSavedEventId(eventId);
      } else {
        const res = await updateAdminEvent(eventId, form, { isActive: false });
        if (!res.ok) {
          throw new Error(res.error ? t(res.error) : "Draft save failed");
        }
      }

      const annotateRes = await fetch("/api/admin/annotate-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          eventId,
          lockedFields: getLockedLocationFields(),
          overwriteableFields: getOverwriteableLocationFields(),
        }),
        signal: AbortSignal.timeout(58000),
      });

      const data = await readJsonResponse(annotateRes);
      if (!annotateRes.ok) {
        const errorKey = typeof data.error === "string" ? data.error : null;
        const detail = typeof data.detail === "string" ? data.detail : null;
        const baseMsg = errorKey ? t(errorKey) : t("saveFailed");
        throw new Error(detail ? `${baseMsg}（${detail}）` : baseMsg);
      }

      applyReturnedFields((data.fields ?? {}) as Record<string, unknown>);
      setOcrFilled(false);
      setAnnotationDone(true);
    } catch (error: unknown) {
      setActionError(getActionErrorMessage(error, t("saveFailed")));
    } finally {
      finishPrimaryAction("annotate");
    }
  }

  async function handleSaveEvent() {
    if (actionLockRef.current) return;
    beginPrimaryAction("save");
    try {
      const res = savedEventId
        ? await updateAdminEvent(savedEventId, form, { isActive: true })
        : await createEventNoAnnotate(form);

      if (!res.ok) {
        setActionError(t(res.error) || res.error || t("saveFailed"));
        return;
      }

      startTransition(() => {
        router.push(`/${locale}/admin`);
      });
    } catch (error: unknown) {
      setActionError(getActionErrorMessage(error, t("saveFailed")));
    } finally {
      finishPrimaryAction("save");
    }
  }

  function handleCancel() {
    const isEdited = JSON.stringify(form) !== JSON.stringify(EMPTY_FORM);
    if (isEdited) {
      if (!window.confirm(t("unsaved_confirm"))) {
        return;
      }
    }
    router.push(`/${locale}/admin`);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Navigation and Header */}
      <div className="flex items-center justify-between gap-3">
        <Button type="button" variant="ghost" onClick={handleCancel} className="-ml-4 shrink-0 text-sm font-medium relative z-10">
          ← {t("back") || "返回"}
        </Button>
        <h1 className="text-2xl font-bold text-fg-strong text-center truncate">
          {t("newEvent") || "新增活動"}
        </h1>
        <div className="w-10 shrink-0" />
      </div>

      {/* Floating Poster Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => posterFileRef.current?.click()}
            disabled={extracting}
            loading={extracting}
            className="min-w-[10rem] shadow-sm"
          >
            {t("extractFromImage") || "由海報提取資訊"}
          </Button>
          <input
            type="file"
            ref={posterFileRef}
            className="hidden"
            accept="image/*"
            onChange={handleImageExtract}
          />
          {extracting && (
            <span className="text-sm text-fg-muted font-medium animate-pulse">
              {t("extracting") || "解析中..."}
            </span>
          )}
        </div>

        {posterPreview && (
          <div className="-mx-6 sm:mx-0 overflow-hidden sm:rounded-xl border border-line bg-surface">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={posterPreview}
              alt="Poster preview"
              className="w-full max-h-96 object-contain"
            />
          </div>
        )}

        {extractError && (
          <p className="text-sm text-red-500 font-semibold" aria-live="polite">{extractError}</p>
        )}
      </div>

      {annotationDone && (
        <div className="rounded-xl bg-green-500/10 border border-green-500/20 p-4 text-green-700 dark:text-green-300 text-sm font-semibold flex items-center justify-between">
          <span>{t("annotationDone") || "標注完成，請確認資料後發布"}</span>
          <Button type="button" variant="ghost" onClick={() => setAnnotationDone(false)} className="px-1 py-0 text-green-500 hover:text-green-700 dark:hover:text-green-100 font-bold">
            ✕
          </Button>
        </div>
      )}

      {(saving || annotating) && (
        <div
          aria-live="polite"
          className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-4 text-sm font-semibold text-amber-700 dark:text-amber-300"
        >
          {annotating
            ? `${t("extracting")} ${Math.floor(busyElapsedMs / 1000)}s`
            : `${t("saving")} ${Math.floor(busyElapsedMs / 1000)}s`}
        </div>
      )}

      {actionError && (
        <p className="text-sm text-red-500 font-semibold" aria-live="polite">{actionError}</p>
      )}

      {/* Floating Event Form Fields */}
      <div className="space-y-6">
        <AdminEventForm
          form={form}
          t={t}
          tCat={tCat}
          tEventForm={tEventForm}
          updateField={updateField}
          toggleCategory={toggleCategory}
          events={allEvents}
          editingId={null}
          locale={locale}
        />
      </div>

      {/* Floating Save Actions Section */}
      <div className="flex items-center gap-3 pt-4 border-t border-line">
        <Button type="button" variant="secondary" onClick={handleCancel} className="shadow-sm">
          {t("cancel")}
        </Button>
        <Button
          type="button"
          onClick={ocrFilled ? handleAIAnnotate : handleSaveEvent}
          disabled={saving || extracting || annotating}
          loading={saving || annotating}
          className={`min-w-[11rem] shadow-sm ${ocrFilled ? "bg-blue-600 hover:bg-blue-700" : ""}`}
        >
          {ocrFilled ? t("saveAndAnnotate") || "儲存並標注" : t("save")}
        </Button>
      </div>

      {extractError && (
        <p className="text-sm font-semibold text-red-500" aria-live="assertive">
          {extractError}
        </p>
      )}

      {actionError && (
        <p className="text-sm font-semibold text-red-500" aria-live="assertive">
          {actionError}
        </p>
      )}
      {annotationDone && !actionError && (
        <p className="text-sm font-semibold text-green-600">
          {t("annotationDone") || "標注完成，請確認資料後發布"}
        </p>
      )}
    </div>
  );
}

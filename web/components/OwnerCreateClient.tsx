"use client";

import { useEffect, useState, useRef, useTransition } from "react";
import { useTranslations } from "next-intl";
import { type Locale } from "@/lib/types";
import { useRouter } from "next/navigation";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";
import { createOwnerEvent, createOwnerDraft, updateOwnerEvent } from "@/app/actions/owner-events";

interface Props {
  locale: Locale;
}

export default function OwnerCreateClient({ locale }: Props) {
  const t = useTranslations("account");
  const tAdmin = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tEventForm = useTranslations("eventForm");
  const router = useRouter();

  const [form, setForm] = useState<FormState>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [posterPreview, setPosterPreview] = useState<string | null>(null);
  const [annotating, setAnnotating] = useState(false);
  const [annotationError, setAnnotationError] = useState<string | null>(null);
  const [savedEventId, setSavedEventId] = useState<string | null>(null);
  const [ocrFilled, setOcrFilled] = useState(false);
  const [annotationDone, setAnnotationDone] = useState(false);

  const posterFileRef = useRef<HTMLInputElement>(null);
  const busyStartedAtRef = useRef<number | null>(null);
  const actionLockRef = useRef(false);
  const [busyElapsedMs, setBusyElapsedMs] = useState(0);
  const [, startTransition] = useTransition();

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

  function updateField(k: string, v: any) {
    setForm((prev) => ({ ...prev, [k]: v }));
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
    setExtracting(true);
    setExtractError(null);

    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = reader.result as string;
      setPosterPreview(dataUrl);

      try {
        const res = await fetch("/api/account/extract-from-image", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image: dataUrl }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ? t(data.error) : "Extraction failed");
        
        const fields = data.fields as Record<string, any>;
        const ARRAY_FIELDS = new Set(["event_form", "category", "co_organizers", "sponsors"]);
        for (const [key, val] of Object.entries(fields)) {
          if (val === null || val === undefined) continue;
          if (ARRAY_FIELDS.has(key) && Array.isArray(val)) {
            updateField(key, val);
          } else if (!ARRAY_FIELDS.has(key)) {
            updateField(key, val === true ? true : val === false ? false : String(val));
          }
        }
        if (typeof fields.is_paid === "boolean") updateField("is_paid", fields.is_paid);
        if (typeof fields.has_japanese_support === "boolean") updateField("has_japanese_support", fields.has_japanese_support);
        if (typeof fields.has_english_support === "boolean") updateField("has_english_support", fields.has_english_support);
        if (typeof fields.has_chinese_support === "boolean") updateField("has_chinese_support", fields.has_chinese_support);

        setOcrFilled(true);
        setAnnotationDone(false);
      } catch (err: any) {
        setExtractError(err.message || "Failed to extract");
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
    actionLockRef.current = true;
    setAnnotationError(null);
    let eventId = savedEventId;

    setAnnotating(true);
    try {
      if (!eventId) {
        const res = await createOwnerDraft(form);
        if (!res.ok) {
          throw new Error(res.error ? t(res.error) : "Draft save failed");
        }
        eventId = res.data.id;
        setSavedEventId(eventId);
      } else {
        const res = await updateOwnerEvent(eventId, form);
        if (!res.ok) {
          throw new Error(res.error ? t(res.error) : "Draft save failed");
        }
      }

      const res = await fetch("/api/account/annotate-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventId }),
        signal: AbortSignal.timeout(58000),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error ? t(data.error) : "Annotation failed");

      const fields = data.fields as Record<string, any>;
      for (const [key, val] of Object.entries(fields)) {
        if (val === null || val === undefined || val === "") continue;
        updateField(key, val);
      }
      
      setOcrFilled(false);
      setAnnotationDone(true);
    } catch (err: any) {
      setAnnotationError(err.message || "Annotation failed");
    } finally {
      setAnnotating(false);
      actionLockRef.current = false;
    }
  }

  async function handleSaveEvent() {
    if (actionLockRef.current) return;
    actionLockRef.current = true;
    setSaving(true);
    try {
      let res;
      if (savedEventId) {
        res = await updateOwnerEvent(savedEventId, form);
      } else {
        res = await createOwnerEvent(form);
      }

      if (!res.ok) {
        alert(t(res.error) || t("saveFailed"));
        return;
      }

      alert(t("saveSuccess"));
      startTransition(() => {
        router.push(`/${locale}/account`);
      });
    } catch (e: any) {
      alert(e.message || t("saveFailed"));
    } finally {
      setSaving(false);
      actionLockRef.current = false;
    }
  }

  function handleCancel() {
    const isEdited = JSON.stringify(form) !== JSON.stringify(EMPTY_FORM);
    if (isEdited) {
      if (!window.confirm(tAdmin("unsaved_confirm"))) {
        return;
      }
    }
    router.push(`/${locale}/account`);
  }

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
          {t("createEvent") || t("newEvent") || "建立新活動"}
        </h1>
        <div className="w-10" /> {/* Spacer to center the title slightly or balance */}
      </div>

      {/* Floating Poster Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => posterFileRef.current?.click()}
            disabled={extracting}
            className="inline-flex min-w-[10rem] items-center justify-center whitespace-nowrap rounded-lg border border-line-strong px-4 py-2 text-sm font-medium bg-paper hover:bg-elevated transition disabled:opacity-50 shadow-sm"
          >
            {extracting ? t("saving") : t("extract") || "由海報提取資訊"}
          </button>
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
          <p className="text-sm text-red-500 font-semibold">{extractError}</p>
        )}
      </div>

      {annotationDone && (
        <div className="rounded-xl bg-green-500/10 border border-green-500/20 p-4 text-green-700 dark:text-green-300 text-sm font-semibold flex items-center justify-between">
          <span>{tAdmin("annotationDone") || "標注完成，請確認資料後發布"}</span>
          <button
            type="button"
            onClick={() => setAnnotationDone(false)}
            className="text-green-500 hover:text-green-700 dark:hover:text-green-100 font-bold px-1"
          >
            ✕
          </button>
        </div>
      )}

      {annotationError && (
        <p className="text-sm text-red-500 font-semibold">{annotationError}</p>
      )}

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
          editingId={null}
          locale={locale}
        />
      </div>

      {/* Floating Save Actions Section */}
      <div className="flex items-center gap-3 pt-4 border-t border-line">
        <button
          type="button"
          onClick={handleCancel}
          className="rounded-lg border border-line-strong bg-paper px-4 py-2 text-sm font-semibold text-fg-muted hover:bg-elevated transition shadow-sm"
        >
          {tAdmin("cancel")}
        </button>
        <button
          type="button"
          onClick={ocrFilled ? handleAIAnnotate : handleSaveEvent}
          disabled={saving || extracting || annotating}
          className={`inline-flex min-w-[11rem] items-center justify-center whitespace-nowrap rounded-lg px-4 py-2 text-sm font-semibold text-white transition disabled:opacity-50 shadow-sm ${
            ocrFilled
              ? "bg-blue-600 hover:bg-blue-700"
              : "bg-green-600 hover:bg-green-700"
          }`}
        >
          {ocrFilled ? (
            annotating
              ? `解析中... ${Math.floor(busyElapsedMs / 1000)} 秒`
              : tAdmin("saveAndAnnotate") || "儲存並標注"
          ) : (
            saving
              ? `儲存中... ${Math.floor(busyElapsedMs / 1000)} 秒`
              : tAdmin("save")
          )}
        </button>
      </div>
    </div>
  );
}

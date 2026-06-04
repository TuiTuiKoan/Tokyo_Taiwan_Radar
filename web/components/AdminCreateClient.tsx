"use client";

import { useEffect, useState, useRef, useTransition } from "react";
import { useTranslations } from "next-intl";
import { type Event, type Locale } from "@/lib/types";
import { useRouter } from "next/navigation";
import Button from "@/components/Button";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";
import { createDraftEvent, createEventNoAnnotate } from "@/app/actions/admin-events";

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
        const res = await fetch("/api/admin/extract-from-image", {
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
    setAnnotating(true);
    let eventId = savedEventId;

    try {
      if (!eventId) {
        const res = await createDraftEvent(form);
        if (!res.ok) {
          throw new Error(res.error ? String(res.error) : "Draft save failed");
        }
        eventId = res.data.id;
        setSavedEventId(eventId);
      }

      const annotateRes = await fetch("/api/admin/annotate-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventId }),
        signal: AbortSignal.timeout(58000),
      });

      const data = await annotateRes.json();
      if (!annotateRes.ok) throw new Error(data.error ? String(data.error) : "Annotation failed");

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
      const res = await createEventNoAnnotate(form);

      if (!res.ok) {
        alert(t(res.error) || t("saveFailed") || "儲存失敗");
        return;
      }

      alert("儲存成功");
      startTransition(() => {
        router.push(`/${locale}/admin`);
      });
    } catch (e: any) {
      alert(e.message || "儲存失敗");
    } finally {
      setSaving(false);
      actionLockRef.current = false;
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
          <p className="text-sm text-red-500 font-semibold">{extractError}</p>
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

      {annotationError && (
        <p className="text-sm text-red-500 font-semibold">{annotationError}</p>
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
    </div>
  );
}

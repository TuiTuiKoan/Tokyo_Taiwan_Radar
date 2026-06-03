"use client";

import { useState, useRef, useTransition, useEffect } from "react";
import { useTranslations } from "next-intl";
import { type Event, type Locale, getEventName } from "@/lib/types";
import { useRouter } from "next/navigation";
import AdminEventForm, { EMPTY_FORM, type FormState } from "@/components/AdminEventForm";
import { createOwnerEvent, updateOwnerEvent, deactivateOwnEvent, createOwnerDraft } from "@/app/actions/owner-events";

interface Props {
  events: Event[];
  locale: Locale;
}

export default function OwnerEventTable({ events: initialEvents, locale }: Props) {
  const t = useTranslations("account");
  const tAdmin = useTranslations("admin");
  const tCat = useTranslations("categories");
  const tEvent = useTranslations("event");
  const tEventForm = useTranslations("eventForm");
  const router = useRouter();

  const [events, setEvents] = useState<Event[]>(initialEvents);
  const [showModal, setShowNew] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

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

  useEffect(() => {
    if (showModal) {
      const oldOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = oldOverflow;
      };
    }
  }, [showModal]);

  const posterFileRef = useRef<HTMLInputElement>(null);
  const [, startTransition] = useTransition();

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

  // Opens modal for creating a new UGC event
  function openNewModal() {
    setForm({ ...EMPTY_FORM });
    setEditingId(null);
    setSavedEventId(null);
    setPosterPreview(null);
    setExtractError(null);
    setAnnotationError(null);
    setOcrFilled(false);
    setAnnotationDone(false);
    setShowNew(true);
  }

  // Opens modal for editing an existing event
  function openEditModal(event: Event) {
    const f: FormState = {
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
      source_url: event.source_url || "",
      source_name: "user_submission",
      original_language: event.original_language || "zh",
      is_active: event.is_active || false,
      parent_event_id: event.parent_event_id || "",
      record_links: event.record_links as any || [],
    };
    setForm(f);
    setEditingId(event.id);
    setSavedEventId(event.id);
    setPosterPreview(null);
    setExtractError(null);
    setAnnotationError(null);
    setOcrFilled(false);
    setAnnotationDone(false);
    setShowNew(true);
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
    setAnnotationError(null);
    let eventId = editingId || savedEventId;

    setAnnotating(true);
    try {
      if (!eventId) {
        const res = await createOwnerDraft(form);
        if (!res.ok) {
          throw new Error(res.error ? t(res.error) : "Draft save failed");
        }
        eventId = res.data.id;
        setSavedEventId(eventId);
        setEvents((prev) => [res.data, ...prev]);
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
      router.refresh();
    } catch (err: any) {
      setAnnotationError(err.message || "Annotation failed");
    } finally {
      setAnnotating(false);
    }
  }

  async function handleSaveEvent() {
    setSaving(true);
    try {
      let res;
      if (editingId) {
        res = await updateOwnerEvent(editingId, form);
      } else {
        res = await createOwnerEvent(form);
      }

      if (!res.ok) {
        alert(t(res.error) || t("saveFailed"));
        return;
      }

      // Success
      alert(t("saveSuccess"));
      setShowNew(false);
      startTransition(() => {
        router.refresh();
      });
    } catch (e: any) {
      alert(e.message || t("saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDeactivate(id: string) {
    if (!confirm(t("deactivateConfirm") + "\n\n" + t("deactivateConfirmDesc"))) return;
    const res = await deactivateOwnEvent(id);
    if (!res.ok) {
      alert(t(res.error) || "Deactivation failed");
      return;
    }
    startTransition(() => {
      router.refresh();
    });
  }

  function handleDismiss() {
    if (JSON.stringify(form) !== JSON.stringify(EMPTY_FORM)) {
      if (!window.confirm(tAdmin("unsaved_confirm"))) {
        return;
      }
    }
    setShowNew(false);
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <button
          type="button"
          onClick={openNewModal}
          className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 transition"
        >
          {t("createEvent")}
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-paper">
        <table className="min-w-full divide-y divide-line text-left text-sm">
          <thead>
            <tr className="bg-surface text-fg-muted font-bold">
              <th className="px-4 py-3">{t("tableHeaderName")}</th>
              <th className="px-4 py-3">{t("tableHeaderDate")}</th>
              <th className="px-4 py-3">{t("tableHeaderStatus")}</th>
              <th className="px-4 py-3 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {events.map((event) => {
              const name = getEventName(event, locale);
              const isClosed = event.closed_by_owner;
              const isMerged = !!event.merged_into_event_id;

              let statusNode = (
                <span className="inline-flex rounded-full bg-green-50 px-2 py-0.5 text-xs font-semibold text-green-700 dark:bg-green-900/30 dark:text-green-200">
                  {t("statusActive")}
                </span>
              );

              if (isClosed) {
                statusNode = (
                  <span className="inline-flex rounded-full bg-stone-100 px-2 py-0.5 text-xs font-semibold text-stone-500 dark:bg-stone-800 dark:text-stone-400">
                    {t("statusClosed")}
                  </span>
                );
              } else if (isMerged) {
                statusNode = (
                  <span className="inline-flex rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
                    {t("statusMerged")}
                  </span>
                );
              } else if (!event.is_active) {
                statusNode = (
                  <span className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:bg-amber-900/30 dark:text-amber-200">
                    Draft
                  </span>
                );
              }

              return (
                <tr key={event.id} className="hover:bg-elevated transition">
                  <td className="px-4 py-3 font-semibold text-fg-strong max-w-sm truncate">
                    {name}
                  </td>
                  <td className="px-4 py-3 text-fg-muted">
                    {event.start_date ? event.start_date.substring(0, 10) : "-"}
                  </td>
                  <td className="px-4 py-3">
                    {statusNode}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                    {!isClosed && !isMerged && (
                      <>
                        <button
                          type="button"
                          onClick={() => openEditModal(event)}
                          className="text-green-600 hover:text-green-700 font-medium text-xs py-1 px-2.5 rounded border border-green-200 hover:border-green-300 transition"
                        >
                          {t("tableActionEdit")}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeactivate(event.id)}
                          className="text-stone-500 hover:text-red-600 font-medium text-xs py-1 px-2.5 rounded border border-line hover:border-red-200 transition"
                        >
                          {t("tableActionDeactivate")}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-0 sm:p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
          <div className="bg-paper w-full h-full sm:h-auto sm:max-h-[95vh] sm:max-w-4xl lg:max-w-5xl sm:rounded-2xl border-0 sm:border border-line shadow-2xl flex flex-col overflow-hidden relative z-50">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface">
              <h2 className="text-lg font-bold text-fg-strong">
                {editingId ? t("editingEvent") : t("createEvent")}
              </h2>
              <button
                type="button"
                onClick={handleDismiss}
                className="text-fg-muted hover:text-fg-strong font-semibold p-1"
              >
                ✕
              </button>
            </div>

            {/* Scrollable Container */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {/* Image poster extraction */}
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => posterFileRef.current?.click()}
                    disabled={extracting}
                    className="rounded-lg border border-line-strong px-4 py-2 text-sm font-medium hover:bg-elevated transition disabled:opacity-50"
                  >
                    {extracting ? t("saving") : t("extract")}
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
                  <p className="mt-1 text-sm text-red-500 font-semibold">{extractError}</p>
                )}
              </div>

              {annotationDone && (
                <div className="rounded-xl bg-green-500/10 border border-green-500/20 p-4 text-green-700 dark:text-green-300 text-sm font-semibold flex items-center justify-between">
                  <span>{tAdmin("annotationDone") || "✅ 標注完成，請確認資料後發布"}</span>
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

              {/* Core Event Form */}
              <AdminEventForm
                form={form}
                t={tAdmin}
                tCat={tCat}
                tEventForm={tEventForm}
                updateField={updateField}
                toggleCategory={toggleCategory}
                events={[]}
                editingId={editingId}
                locale={locale}
              />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-line bg-surface">
              <button
                type="button"
                onClick={handleDismiss}
                className="rounded-lg border border-line-strong px-4 py-2 text-sm font-semibold text-fg-muted hover:bg-elevated transition"
              >
                {tAdmin("cancel")}
              </button>
              <button
                type="button"
                onClick={ocrFilled ? handleAIAnnotate : handleSaveEvent}
                disabled={saving || extracting || annotating}
                className={`rounded-lg px-4 py-2 text-sm font-semibold text-white transition disabled:opacity-50 ${
                  ocrFilled
                    ? "bg-blue-600 hover:bg-blue-700"
                    : "bg-green-600 hover:bg-green-700"
                }`}
              >
                {ocrFilled ? (
                  annotating ? t("saving") || "解析中..." : tAdmin("saveAndAnnotate") || "儲存並標注"
                ) : (
                  saving ? t("saving") : tAdmin("save")
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

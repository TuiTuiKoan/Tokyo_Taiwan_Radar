"use client";

import { useState, useRef, useTransition } from "react";
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
    let eventId = savedEventId;

    if (!eventId) {
      setSaving(true);
      const res = await createOwnerDraft(form);
      setSaving(false);
      if (!res.ok) {
        setAnnotationError(res.error ? t(res.error) : "Draft save failed");
        return;
      }
      eventId = res.data.id;
      setSavedEventId(eventId);
      setEvents((prev) => [res.data, ...prev]);
    }

    setAnnotating(true);
    try {
      const res = await fetch("/api/account/annotate-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ? t(data.error) : "Annotation failed");

      const fields = data.fields as Record<string, any>;
      for (const [key, val] of Object.entries(fields)) {
        if (val === null || val === undefined || val === "") continue;
        updateField(key, val);
      }
      
      // Fetch latest row to refresh UI
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm overflow-y-auto">
          <div className="bg-paper border border-line rounded-2xl shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-line bg-surface">
              <h2 className="text-lg font-bold text-fg-strong">
                {editingId ? t("editingEvent") : t("createEvent")}
              </h2>
              <button
                type="button"
                onClick={() => setShowNew(false)}
                className="text-fg-muted hover:text-fg-strong font-semibold p-1"
              >
                ✕
              </button>
            </div>

            {/* Scrollable Container */}
            <div className="p-6 overflow-y-auto flex-1 space-y-6">
              {/* Image poster extraction */}
              <div>
                <label className="block text-sm font-semibold text-fg-strong mb-2">
                  {tAdmin("labelPosterImage") || "宣傳海報圖片 (Poster)"}
                </label>
                <div className="flex flex-wrap items-center gap-4">
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
                  {posterPreview && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={posterPreview}
                      alt="Poster preview"
                      className="h-16 w-16 object-cover rounded-lg border border-line"
                    />
                  )}
                </div>
                {extractError && (
                  <p className="mt-1 text-sm text-red-500 font-semibold">{extractError}</p>
                )}
              </div>

              {/* AI Auto-annotate */}
              <div className="bg-surface rounded-xl p-4 border border-line flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-bold text-fg-strong">
                    {t("annotate") || "AI 標註與翻譯"}
                  </h3>
                  <p className="text-xs text-fg-muted mt-0.5">
                    基於名稱和參考網頁，自動翻譯三語、生成摘要、預分類。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAIAnnotate}
                  disabled={annotating || saving}
                  className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 transition disabled:opacity-50"
                >
                  {annotating ? t("saving") : t("annotate")}
                </button>
              </div>
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
                onClick={() => setShowNew(false)}
                className="rounded-lg border border-line-strong px-4 py-2 text-sm font-semibold text-fg-muted hover:bg-elevated transition"
              >
                {tAdmin("cancel")}
              </button>
              <button
                type="button"
                onClick={handleSaveEvent}
                disabled={saving || extracting || annotating}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 transition disabled:opacity-50"
              >
                {saving ? t("saving") : tAdmin("save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

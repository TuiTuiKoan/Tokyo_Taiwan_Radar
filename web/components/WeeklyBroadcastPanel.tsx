"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import type { Locale } from "@/lib/types";

interface DraftInfo {
  id: string;
  slug: string;
  title_zh: string | null;
  title_ja: string | null;
  created_at: string;
}

interface BroadcastSettings {
  auto_publish: boolean;
  draft: DraftInfo | null;
}

interface Props {
  locale: Locale;
}

export default function WeeklyBroadcastPanel({ locale }: Props) {
  const t = useTranslations("announcements");
  const [settings, setSettings] = useState<BroadcastSettings | null>(null);
  const [toggling, setToggling] = useState(false);
  const [sending, setSending] = useState(false);
  const [sentMsg, setSentMsg] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/admin/weekly-broadcast")
      .then((r) => r.json())
      .then((d) => setSettings(d))
      .catch(console.error);
  }, []);

  async function handleToggle(value: boolean) {
    if (!settings) return;
    setToggling(true);
    try {
      const res = await fetch("/api/admin/weekly-broadcast", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_publish: value }),
      });
      if (res.ok) {
        setSettings((s) => s ? { ...s, auto_publish: value } : s);
      }
    } finally {
      setToggling(false);
    }
  }

  async function handleSendNow() {
    if (!settings?.draft) return;
    setSending(true);
    setSentMsg(null);
    setSendError(null);
    try {
      const res = await fetch("/api/admin/weekly-broadcast/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: settings.draft.id }),
      });
      const data = await res.json();
      if (res.ok) {
        setSentMsg(t("weeklyBroadcastSent", { n: data.sent_to ?? 0 }));
        // Clear draft from UI (it's now published)
        setSettings((s) => s ? { ...s, draft: null } : s);
      } else {
        setSendError(data.error ?? "Send failed");
      }
    } catch (e) {
      setSendError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  if (!settings) return null;

  const draftTitle = settings.draft
    ? (locale === "ja" ? settings.draft.title_ja : settings.draft.title_zh) ?? settings.draft.title_zh ?? settings.draft.slug
    : null;
  const draftDate = settings.draft
    ? new Date(settings.draft.created_at).toLocaleDateString(locale)
    : null;

  return (
    <div className="mb-6 border border-blue-100 bg-blue-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-blue-800">{t("weeklyBroadcast")}</h2>
        {/* Auto-publish toggle */}
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <span className="text-xs text-gray-600">{t("weeklyBroadcastAutoPublish")}</span>
          <button
            type="button"
            role="switch"
            aria-checked={settings.auto_publish}
            disabled={toggling}
            onClick={() => handleToggle(!settings.auto_publish)}
            className={[
              "relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500",
              settings.auto_publish ? "bg-blue-600" : "bg-gray-300",
              toggling ? "opacity-50 cursor-not-allowed" : "",
            ].join(" ")}
          >
            <span
              className={[
                "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                settings.auto_publish ? "translate-x-6" : "translate-x-1",
              ].join(" ")}
            />
          </button>
        </label>
      </div>

      {sentMsg && (
        <p className="text-xs text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2 mb-3">
          ✓ {sentMsg}
        </p>
      )}
      {sendError && (
        <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3">
          ✗ {sendError}
        </p>
      )}

      {settings.draft ? (
        <div className="flex items-start justify-between gap-3 bg-white border border-blue-200 rounded-lg px-3 py-2">
          <div className="min-w-0">
            <p className="text-xs font-medium text-gray-700 truncate">{draftTitle}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              {t("weeklyBroadcastCreatedAt")}: {draftDate} · /{settings.draft.slug}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Link
              href={`/${locale}/admin/announcements/${settings.draft.id}`}
              className="text-xs px-2.5 py-1 rounded-lg border border-blue-300 text-blue-700 hover:bg-blue-100 transition"
            >
              {t("weeklyBroadcastEdit")}
            </Link>
            <button
              type="button"
              disabled={sending}
              onClick={handleSendNow}
              className="text-xs px-2.5 py-1 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition"
            >
              {sending ? t("weeklyBroadcastSending") : t("weeklyBroadcastSendNow")}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-400 italic">{t("weeklyBroadcastNoDraft")}</p>
      )}
    </div>
  );
}

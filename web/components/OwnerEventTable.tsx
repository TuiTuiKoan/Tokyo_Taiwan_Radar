"use client";

import { useTransition } from "react";
import { useTranslations } from "next-intl";
import { type Event, type Locale, getEventName } from "@/lib/types";
import { useRouter } from "next/navigation";
import { deactivateOwnEvent } from "@/app/actions/owner-events";

interface Props {
  events: Event[];
  locale: Locale;
}

export default function OwnerEventTable({ events, locale }: Props) {
  const t = useTranslations("account");
  const router = useRouter();
  const [, startTransition] = useTransition();

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
          onClick={() => router.push(`/${locale}/account/events/new`)}
          className="rounded-lg bg-green-600 px-4 py-2 text-sm font-semibold text-white hover:bg-green-700 transition"
        >
          {t("createEvent")}
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-line bg-paper">
        <table className="min-w-full divide-y divide-line text-left text-sm">
          <thead>
            <tr className="bg-surface text-fg-muted font-bold font-display">
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
                          onClick={() => router.push(`/${locale}/account/events/${event.id}/edit`)}
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
    </div>
  );
}

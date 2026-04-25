import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale, type Event } from "@/lib/types";
import AdminEventTable from "@/components/AdminEventTable";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

type PendingIssueKey =
  | "pendingReasonLocalizedLocationAddress"
  | "pendingReasonLocalizedLocationName"
  | "pendingReasonLocalizedBusinessHours";

export default async function AdminPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");
  const hasText = (value: string | null | undefined) => Boolean(value && value.trim());

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    redirect(`/${locale}/auth/login`);
  }

  // Check admin role
  const { data: roleRow } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", user.id)
    .single();

  if (!roleRow || roleRow.role !== "admin") {
    redirect(`/${locale}`);
  }

  // Fetch all events (including inactive) for admin view
  const { data: events } = await supabase
    .from("events")
    .select("*")
    .order("created_at", { ascending: false });

  // Stats
  const totalEvents = events?.length ?? 0;
  const activeEvents = events?.filter((e) => e.is_active).length ?? 0;
  const activePendingEvents = events?.filter((e) => e.is_active && e.annotation_status === "pending") ?? [];
  const pendingEvents = activePendingEvents.length;
  const totalPendingEvents = events?.filter((e) => e.annotation_status === "pending").length ?? 0;
  const inactivePendingEvents = totalPendingEvents - pendingEvents;
  const pendingIssuesRaw: Array<{ key: PendingIssueKey; count: number }> = [
    {
      key: "pendingReasonLocalizedLocationAddress",
      count: activePendingEvents.filter(
        (e) => hasText(e.location_address) && (!hasText(e.location_address_zh) || !hasText(e.location_address_en))
      ).length,
    },
    {
      key: "pendingReasonLocalizedLocationName",
      count: activePendingEvents.filter(
        (e) => hasText(e.location_name) && (!hasText(e.location_name_zh) || !hasText(e.location_name_en))
      ).length,
    },
    {
      key: "pendingReasonLocalizedBusinessHours",
      count: activePendingEvents.filter(
        (e) => hasText(e.business_hours) && (!hasText(e.business_hours_zh) || !hasText(e.business_hours_en))
      ).length,
    },
  ];
  const pendingIssues = pendingIssuesRaw.filter((issue) => issue.count > 0);

  const { count: userCount } = await supabase
    .from("user_roles")
    .select("*", { count: "exact", head: true });

  const { count: reportCount } = await supabase
    .from("event_reports")
    .select("*", { count: "exact", head: true })
    .eq("status", "pending");

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
          <p className="text-xs text-gray-400 mb-1">活動總數</p>
          <p className="text-2xl font-bold text-gray-800">{totalEvents}</p>
          <p className="text-xs text-gray-400 mt-0.5">開放中 {activeEvents}</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
          <p className="text-xs text-gray-400 mb-1">待標注</p>
          <p className={`text-2xl font-bold ${pendingEvents > 0 ? "text-amber-500" : "text-gray-800"}`}>{pendingEvents}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {inactivePendingEvents > 0
              ? t("pendingCountDetail", { active: pendingEvents, total: totalPendingEvents })
              : t("pendingCountActiveOnly", { count: pendingEvents })}
          </p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
          <p className="text-xs text-gray-400 mb-1">註冊用戶</p>
          <p className="text-2xl font-bold text-gray-800">{userCount ?? 0}</p>
          <p className="text-xs text-gray-400 mt-0.5">擁有角色的用戶</p>
        </div>
        <div className="bg-white border border-gray-200 rounded-xl px-4 py-3">
          <p className="text-xs text-gray-400 mb-1">待審問題回報</p>
          <p className={`text-2xl font-bold ${(reportCount ?? 0) > 0 ? "text-red-500" : "text-gray-800"}`}>{reportCount ?? 0}</p>
          <p className="text-xs text-gray-400 mt-0.5">status = pending</p>
        </div>
      </div>

      <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-4">
        <p className="text-sm font-semibold text-amber-900">{t("pendingSummaryTitle")}</p>
        {pendingEvents > 0 ? (
          <>
            <p className="mt-1 text-sm text-amber-800">
              {t("pendingSummaryLead", { count: pendingEvents })}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {pendingIssues.map((issue) => (
                <span
                  key={issue.key}
                  className="rounded-full border border-amber-300 bg-white px-2.5 py-1 text-xs text-amber-900"
                >
                  {issue.key === "pendingReasonLocalizedLocationAddress"
                    ? t("pendingReasonLocalizedLocationAddress", { count: issue.count })
                    : issue.key === "pendingReasonLocalizedLocationName"
                      ? t("pendingReasonLocalizedLocationName", { count: issue.count })
                      : t("pendingReasonLocalizedBusinessHours", { count: issue.count })}
                </span>
              ))}
              {inactivePendingEvents > 0 && (
                <span className="rounded-full border border-gray-200 bg-white px-2.5 py-1 text-xs text-gray-600">
                  {t("pendingSummaryInactive", { count: inactivePendingEvents })}
                </span>
              )}
            </div>
          </>
        ) : inactivePendingEvents > 0 ? (
          <p className="mt-1 text-sm text-gray-700">{t("pendingSummaryInactiveOnly", { count: inactivePendingEvents })}</p>
        ) : (
          <p className="mt-1 text-sm text-green-700">{t("pendingSummaryHealthy")}</p>
        )}
      </div>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {t("eventsTab")}
        </span>
        <Link
          href={`/${locale}/admin/reports`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("reports")}
        </Link>
        <Link
          href={`/${locale}/admin/stats`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("statsTab")}
        </Link>
        <Link
          href={`/${locale}/admin/research`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("researchTab")}
        </Link>
        <Link
          href={`/${locale}/admin/sources`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("sourcesTab")}
        </Link>
      </div>

      <AdminEventTable
        events={(events ?? []) as Event[]}
        locale={locale}
      />
    </div>
  );
}

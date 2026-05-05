import { createClient } from "@/lib/supabase/server";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import Link from "next/link";
import AdminReportsBadge from "@/components/AdminReportsBadge";

type AdminTab =
  | "events"
  | "announcements"
  | "reports"
  | "exclusions"
  | "quality"
  | "research"
  | "sources"
  | "creators"
  | "works"
  | "users"
  | "stats"
  | "aeo"
  | "specs"
  | "roadmap";

interface Props {
  locale: Locale;
  activeTab: AdminTab;
}

export default async function AdminTabNav({ locale, activeTab }: Props) {
  const t = await getTranslations("admin");

  const supabase = await createClient();
  const { count: pendingCount } = await supabase
    .from("event_reports")
    .select("*", { count: "exact", head: true })
    .eq("status", "pending");
  const pending = pendingCount ?? 0;

  function tab(key: AdminTab, label: string, href: string) {
    const isActive = activeTab === key;
    const isReports = key === "reports";
    const className = isActive
      ? "px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600 flex items-center gap-1"
      : "px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition flex items-center gap-1";
    // For the reports tab: use client component so the count stays live
    // via Supabase Realtime without a page refresh.
    const badge = isReports ? <AdminReportsBadge initialCount={pending} /> : null;
    if (isActive) {
      return (
        <span key={key} className={className}>
          {label}
          {badge}
        </span>
      );
    }
    return (
      <Link key={key} href={href} className={className}>
        {label}
        {badge}
      </Link>
    );
  }

  return (
    <div className="flex gap-1 border-b border-gray-200 mb-6 flex-wrap">
      {tab("events",        t("eventsTab"),        `/${locale}/admin`)}
      {tab("reports",       t("reports"),           `/${locale}/admin/reports`)}
      {tab("exclusions",    t("exclusionsTab"),     `/${locale}/admin/exclusions`)}
      {tab("quality",       t("qualityTab"),        `/${locale}/admin/quality`)}
      <span className="mx-1 border-l border-green-600 h-6 self-center" />
      {tab("announcements", t("announcementsTab"),  `/${locale}/admin/announcements`)}
      <span className="mx-1 border-l border-green-600 h-6 self-center" />
      {tab("research",      t("researchTab"),       `/${locale}/admin/research`)}
      {tab("sources",       t("sourcesTab"),        `/${locale}/admin/sources`)}
      {tab("creators",       t("creatorsTab"),        `/${locale}/admin/creators`)}
      {tab("works",         t("worksTab"),          `/${locale}/admin/works`)}
      <span className="mx-1 border-l border-green-600 h-6 self-center" />
      {tab("users",         t("usersTab"),          `/${locale}/admin/users`)}
      {tab("stats",         t("statsTab"),          `/${locale}/admin/stats`)}
      {tab("aeo",           t("aeoTab"),            `/${locale}/admin/aeo`)}
      <span className="mx-1 border-l border-green-600 h-6 self-center" />
      {tab("specs",         t("tabs.specs"),        `/${locale}/admin/specs`)}
      {tab("roadmap",       t("tabs.roadmap"),      `/${locale}/admin/roadmap`)}
    </div>
  );
}

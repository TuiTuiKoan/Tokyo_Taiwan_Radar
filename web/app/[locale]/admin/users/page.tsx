import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { type Locale } from "@/lib/types";
import Link from "next/link";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

export const dynamic = "force-dynamic";

export default async function AdminUsersPage({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations("admin");

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

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

  // Fetch all users via secure admin view (returns 0 rows for non-admins)
  const { data: users, error } = await supabase
    .from("admin_users_view")
    .select("id, email, created_at, last_sign_in_at, role");

  const formatDate = (iso: string | null) => {
    if (!iso) return null;
    return new Date(iso).toLocaleString(locale === "en" ? "en-US" : locale === "ja" ? "ja-JP" : "zh-TW", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{t("title")}</h1>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-gray-200 mb-6 flex-wrap">
        <Link
          href={`/${locale}/admin`}
          className="px-4 py-2 text-sm text-gray-500 hover:text-green-700 transition"
        >
          {t("eventsTab")}
        </Link>
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
        <span className="px-4 py-2 text-sm font-medium text-green-700 border-b-2 border-green-600">
          {t("usersTab")}
        </span>
      </div>

      <h2 className="text-lg font-semibold mb-3">
        {t("usersPageTitle")}
        <span className="ml-2 text-sm font-normal text-gray-400">
          ({users?.length ?? 0})
        </span>
      </h2>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 mb-4">
          {error.message}
        </div>
      )}

      {/* Desktop table */}
      <div className="hidden md:block overflow-x-auto rounded-xl border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
            <tr>
              <th className="px-4 py-3 text-left">{t("usersEmail")}</th>
              <th className="px-4 py-3 text-left">{t("usersRole")}</th>
              <th className="px-4 py-3 text-left">{t("usersCreatedAt")}</th>
              <th className="px-4 py-3 text-left">{t("usersLastSignIn")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {(users ?? []).map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-gray-700">
                  {u.email ?? "—"}
                </td>
                <td className="px-4 py-3">
                  {u.role === "admin" ? (
                    <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800">
                      {t("usersRoleAdmin")}
                    </span>
                  ) : u.role === "user" ? (
                    <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                      {t("usersRoleUser")}
                    </span>
                  ) : (
                    <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                      {t("usersRoleNone")}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {formatDate(u.created_at) ?? "—"}
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {u.last_sign_in_at
                    ? formatDate(u.last_sign_in_at)
                    : <span className="text-gray-300">{t("usersNeverSignedIn")}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile card list */}
      <div className="md:hidden space-y-2">
        {(users ?? []).map((u) => (
          <div key={u.id} className="rounded-xl border border-gray-200 bg-white px-4 py-3">
            <p className="font-mono text-xs text-gray-700 truncate">{u.email ?? "—"}</p>
            <div className="mt-1 flex items-center gap-2">
              {u.role === "admin" ? (
                <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800">
                  {t("usersRoleAdmin")}
                </span>
              ) : u.role === "user" ? (
                <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700">
                  {t("usersRoleUser")}
                </span>
              ) : (
                <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                  {t("usersRoleNone")}
                </span>
              )}
              <span className="text-xs text-gray-400">{formatDate(u.created_at)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

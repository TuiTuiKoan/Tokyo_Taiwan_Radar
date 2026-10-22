import { redirect } from "next/navigation";
import type { Locale } from "@/lib/types";

interface PageProps {
  params: Promise<{ locale: Locale }>;
}

// The spec kanban was removed on 2026-10-22 (#329). Progress lives on the
// TTR Roadmap GitHub Project; this route keeps old links and bookmarks working.
export default async function AdminSpecsPage({ params }: PageProps) {
  const { locale } = await params;
  redirect(`/${locale}/admin/specs/architecture`);
}

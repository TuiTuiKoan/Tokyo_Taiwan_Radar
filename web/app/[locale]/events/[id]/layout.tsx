import { createClient as createSupabaseClient } from "@supabase/supabase-js";
import { notFound, permanentRedirect } from "next/navigation";

interface LayoutProps {
  children: React.ReactNode;
  params: Promise<{ locale: string; id: string }>;
}

/**
 * Settles redirect / 404 before `loading.tsx` starts streaming.
 *
 * Once the loading skeleton is flushed the response status is already 200, so a
 * `notFound()` thrown from page.tsx renders the not-found UI with a 200 and only
 * a noindex meta. Resolving the stub here, above the Suspense boundary, lets
 * Next.js answer with a real 404 / 308. page.tsx keeps its own checks.
 */
export default async function EventDetailLayout({ children, params }: LayoutProps) {
  const { locale, id } = await params;
  const admin = createSupabaseClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
  const { data: stub } = await admin
    .from("events")
    .select("id, merged_into_event_id, is_active, annotation_status")
    .eq("id", id)
    .maybeSingle();

  if (stub?.merged_into_event_id) {
    permanentRedirect(`/${locale}/events/${stub.merged_into_event_id}`);
  }
  if (!stub || !stub.is_active) {
    notFound();
  }
  if (stub.annotation_status !== "annotated" && stub.annotation_status !== "reviewed") {
    notFound();
  }

  return children;
}

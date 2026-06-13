/**
 * Loading boundary for /design — overrides the homepage-shaped skeleton
 * from [locale]/loading.tsx so users don't see fake event-card placeholders
 * while the design preview page fetches its real Supabase data.
 */
export default function DesignLoading() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-10">
      <div className="flex items-center gap-4 mb-8">
        <div className="h-22 w-22 rounded-full bg-muted animate-pulse" style={{ width: 88, height: 88 }} />
        <div className="space-y-2">
          <div className="h-8 w-64 bg-muted rounded animate-pulse" />
          <div className="h-4 w-48 bg-muted rounded animate-pulse" />
        </div>
      </div>
      <div className="h-12 w-72 bg-muted rounded animate-pulse mb-3" />
      <div className="h-12 w-56 bg-muted rounded animate-pulse mb-3" />
      <div className="h-12 w-60 bg-muted rounded animate-pulse mb-8" />
      <p className="text-sm text-fg-muted">Loading design preview…</p>
    </div>
  );
}

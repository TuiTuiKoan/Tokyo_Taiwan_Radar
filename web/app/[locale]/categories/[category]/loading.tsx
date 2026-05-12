export default function Loading() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      {/* Back link skeleton */}
      <div className="h-4 w-20 bg-muted rounded animate-pulse mb-4" />

      {/* Category title */}
      <div className="h-8 w-36 bg-muted rounded animate-pulse mb-2" />
      <div className="h-5 w-56 bg-muted rounded animate-pulse mb-6" />

      {/* Event card skeletons */}
      <div className="space-y-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="border border-line rounded-xl p-4 bg-surface">
            <div className="flex gap-2 mb-2">
              <div className="h-5 w-14 bg-muted rounded-full animate-pulse" />
            </div>
            <div className="h-5 w-3/4 bg-muted rounded animate-pulse mb-2" />
            <div className="flex gap-1 mb-3">
              <div className="h-5 w-14 bg-muted rounded-full animate-pulse" />
            </div>
            <div className="space-y-1">
              <div className="h-4 w-40 bg-muted rounded animate-pulse" />
              <div className="h-4 w-52 bg-muted rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}

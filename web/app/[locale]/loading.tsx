export default function Loading() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      {/* Title skeleton */}
      <div className="h-8 w-48 bg-muted rounded animate-pulse mb-2" />
      <div className="h-5 w-64 bg-muted rounded animate-pulse mb-6" />

      {/* Filter bar skeleton */}
      <div className="flex gap-2 mb-6 overflow-hidden">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-8 w-20 bg-muted rounded-full animate-pulse flex-shrink-0" />
        ))}
      </div>

      {/* Event card skeletons */}
      <div className="space-y-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="border border-line rounded-xl p-4 bg-surface">
            {/* Status badge */}
            <div className="flex gap-2 mb-2">
              <div className="h-5 w-14 bg-muted rounded-full animate-pulse" />
              <div className="h-5 w-10 bg-muted rounded-full animate-pulse" />
            </div>
            {/* Title */}
            <div className="h-5 w-3/4 bg-muted rounded animate-pulse mb-2" />
            {/* Categories */}
            <div className="flex gap-1 mb-3">
              <div className="h-5 w-14 bg-muted rounded-full animate-pulse" />
              <div className="h-5 w-16 bg-muted rounded-full animate-pulse" />
            </div>
            {/* Date + location */}
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

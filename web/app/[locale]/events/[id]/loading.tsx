export default function Loading() {
  return (
    <main className="max-w-3xl mx-auto px-4 py-8">
      {/* Back link skeleton */}
      <div className="h-4 w-24 bg-muted rounded animate-pulse mb-4" />

      {/* Title */}
      <div className="h-8 w-2/3 bg-muted rounded animate-pulse mb-2" />

      {/* Category badges */}
      <div className="flex gap-1 mb-4">
        <div className="h-5 w-14 bg-muted rounded-full animate-pulse" />
        <div className="h-5 w-16 bg-muted rounded-full animate-pulse" />
      </div>

      {/* Date + location info */}
      <div className="space-y-2 mb-6">
        <div className="h-4 w-48 bg-muted rounded animate-pulse" />
        <div className="h-4 w-56 bg-muted rounded animate-pulse" />
        <div className="h-4 w-36 bg-muted rounded animate-pulse" />
      </div>

      {/* Description skeleton */}
      <div className="space-y-2 mb-6">
        <div className="h-4 w-full bg-muted rounded animate-pulse" />
        <div className="h-4 w-full bg-muted rounded animate-pulse" />
        <div className="h-4 w-5/6 bg-muted rounded animate-pulse" />
        <div className="h-4 w-full bg-muted rounded animate-pulse" />
        <div className="h-4 w-3/4 bg-muted rounded animate-pulse" />
      </div>

      {/* CTA button skeleton */}
      <div className="h-10 w-40 bg-muted rounded-lg animate-pulse" />
    </main>
  );
}
